from __future__ import annotations


def exception_detail(error: BaseException) -> str:
    """Return a useful persisted message, including for exceptions with empty str()."""
    name = type(error).__name__
    message = str(error).strip()
    return f"{name}: {message}" if message else name
