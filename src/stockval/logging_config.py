"""Lightweight, library-friendly logging.

The package never configures the root logger or emits to stdout on import
(it attaches a :class:`~logging.NullHandler`), so embedding applications keep
full control.  Call :func:`configure_logging` once from an entry point (the
Streamlit app, a CLI, a notebook) to actually see records.

A single shared logger underpins the audit trail: data fetches, validation
outcomes and every valuation run are logged with their inputs so results are
reproducible and traceable — a baseline expectation for regulated use.
"""
from __future__ import annotations

import logging

_ROOT_NAME = "stockval"

# Attach a NullHandler so "No handlers could be found" warnings never surface
# and the library stays silent until an application opts in.
logging.getLogger(_ROOT_NAME).addHandler(logging.NullHandler())


def get_logger(name: str | None = None) -> logging.Logger:
    """Return a namespaced child of the package logger."""
    if not name:
        return logging.getLogger(_ROOT_NAME)
    return logging.getLogger(f"{_ROOT_NAME}.{name}")


def configure_logging(level: int = logging.INFO, *, fmt: str | None = None) -> None:
    """Attach a stream handler to the package logger (idempotent).

    Safe to call multiple times; it will not stack duplicate handlers.
    """
    logger = logging.getLogger(_ROOT_NAME)
    logger.setLevel(level)
    for handler in logger.handlers:
        if isinstance(handler, logging.StreamHandler) and not isinstance(
            handler, logging.NullHandler
        ):
            handler.setLevel(level)
            return
    handler = logging.StreamHandler()
    handler.setLevel(level)
    handler.setFormatter(
        logging.Formatter(
            fmt or "%(asctime)s %(levelname)-7s %(name)s | %(message)s"
        )
    )
    logger.addHandler(handler)
