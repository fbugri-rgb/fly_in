"""Custom exceptions for the fly_in package."""

from __future__ import annotations


class FlyInError(Exception):
    """Base class for all fly_in exceptions."""


class ParseError(FlyInError):
    """Raised when a map file is malformed.

    Always carries the source line number and a human-readable cause so
    the top-level CLI can report ``line <N>: <cause>`` and exit cleanly.
    """

    def __init__(self, line_no: int, cause: str) -> None:
        super().__init__(f"line {line_no}: {cause}")
        self.line_no: int = line_no
        self.cause: str = cause


class SimulationError(FlyInError):
    """Raised when a rule of the simulation is violated at runtime."""


class NoSolutionError(FlyInError):
    """Raised when the scheduler cannot deliver all drones."""
