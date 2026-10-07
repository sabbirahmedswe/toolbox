class ProcessingError(Exception):
    """A user-facing error raised when an uploaded file can't be processed.

    Mapped to a 400 response with the message as `detail`.
    """
