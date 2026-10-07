from collections.abc import Callable
from contextlib import asynccontextmanager

from fastapi import HTTPException


class JobLimiter:
    """Caps how many CPU-heavy jobs of one kind run at once; extra requests get a 503.

    Only used from the event loop, so a plain counter is enough.
    """

    def __init__(self, max_jobs: Callable[[], int]):
        # A callable so the limit is read at request time (and can be changed in tests).
        self._max_jobs = max_jobs
        self.active = 0

    def check(self, reserve: int = 0) -> None:
        """Fail fast with a 503 if no slot is free, before the caller does any upload I/O.

        `reserve` slots must stay free after this job starts, so low-priority work can't crowd out the rest.
        """
        if self.active + reserve >= self._max_jobs():
            raise HTTPException(503, "The server is busy processing other files. Please try again in a moment.")

    @asynccontextmanager
    async def slot(self, reserve: int = 0):
        # Checked again here: other jobs may have started while the upload was being saved.
        self.check(reserve)
        self.active += 1
        try:
            yield
        finally:
            self.active -= 1
