import os
import shutil
import signal
import subprocess
import threading
from collections.abc import Iterator
from contextlib import contextmanager

from app import config

# Applies memory (KiB) and CPU-time (s) limits, then execs Ghostscript with the remaining args.
# Done in the shell rather than via preexec_fn, which isn't safe to use from a worker thread.
_LIMITED_EXEC = 'ulimit -v "$1" && ulimit -t "$2" && shift 2 && exec "$@"'

CHUNK_SIZE = 1024 * 1024


class GhostscriptMissing(Exception):
    """Raised when the Ghostscript binary can't be found."""


def ghostscript_path() -> str:
    path = shutil.which(config.GS_BINARY)
    if path is None:
        raise GhostscriptMissing(config.GS_BINARY)
    return path


def ghostscript_version() -> str | None:
    try:
        out = subprocess.run([ghostscript_path(), "--version"], capture_output=True, text=True, timeout=10)
    except (GhostscriptMissing, OSError, subprocess.SubprocessError):
        return None
    return out.stdout.strip() or None


def _limited(gs_cmd: list[str], timeout: int) -> list[str]:
    return ["sh", "-c", _LIMITED_EXEC, "sh", str(config.GS_MEMORY_LIMIT_MB * 1024), str(timeout), *gs_cmd]


def run_limited(gs_cmd: list[str], timeout: int) -> None:
    """Run a Ghostscript command under the memory limit and a `timeout` (s) on both CPU and wall-clock time.

    Raises subprocess.TimeoutExpired or CalledProcessError. The caller must pass -dSAFER.
    """
    # Output is discarded: a hostile file could otherwise make gs emit unbounded warnings.
    subprocess.run(
        _limited(gs_cmd, timeout), check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=timeout
    )


@contextmanager
def stream_limited(gs_cmd: list[str], timeout: int) -> Iterator[Iterator[bytes]]:
    """Like run_limited, but yields an iterator over the chunks Ghostscript writes to stdout (-sOutputFile=-).

    The iterator raises subprocess.TimeoutExpired or CalledProcessError once the output ends. Leaving the block
    before then (say, once the output is too big) kills Ghostscript. The caller must pass -dSAFER and
    -sstdout=%stderr, so that messages don't mix with the output.
    """
    cmd = _limited(gs_cmd, timeout)
    # Messages are discarded, as in run_limited. In its own process group, so that kill() also stops any child
    # that holds the pipe open, which would otherwise keep the read below waiting.
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, start_new_session=True)
    timed_out = threading.Event()

    def kill():
        try:
            os.killpg(proc.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass

    def on_timeout():
        timed_out.set()
        kill()

    timer = threading.Timer(timeout, on_timeout)
    timer.start()

    def chunks() -> Iterator[bytes]:
        while chunk := proc.stdout.read1(CHUNK_SIZE):
            yield chunk
        returncode = proc.wait()
        if timed_out.is_set():
            raise subprocess.TimeoutExpired(cmd, timeout)
        if returncode:
            raise subprocess.CalledProcessError(returncode, cmd)

    try:
        yield chunks()
    finally:
        timer.cancel()
        if proc.poll() is None:
            kill()
        proc.wait()
        proc.stdout.close()
