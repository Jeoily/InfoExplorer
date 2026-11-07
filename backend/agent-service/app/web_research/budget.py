"""Per-execution accounting; transports must enforce returned timeouts themselves."""
from dataclasses import dataclass
import math
from threading import Lock
from time import monotonic
from typing import Callable, Literal

Operation = Literal["search", "document", "model"]


class BudgetExceeded(Exception):
    """A safe code only: never include questions, URLs or credentials."""

    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


@dataclass(frozen=True)
class Limits:
    searches: int = 5
    documents: int = 8
    model_calls: int = 3
    total_seconds: float = 150.0
    request_seconds: float = 20.0
    model_request_seconds: float | None = None

    def __post_init__(self):
        for count in (self.searches, self.documents, self.model_calls):
            if type(count) is not int or count < 0:
                raise ValueError("Invalid operation limit")
        for seconds in (self.total_seconds, self.request_seconds,
                        self.request_seconds if self.model_request_seconds is None else self.model_request_seconds):
            if (type(seconds) not in (int, float) or not math.isfinite(seconds)
                    or seconds <= 0):
                raise ValueError("Invalid time limit")


@dataclass(frozen=True)
class Usage:
    searches: int
    documents: int
    model_calls: int
    remaining_seconds: float
    cancelled: bool


class ExecutionBudget:
    """One instance per run. Failed attempts remain charged; no automatic refund.

    Reservations are thread-safe, but this class does not kill an in-flight HTTP
    request. Callers must propagate cancellation/deadlines into their transports.
    """

    def __init__(self, limits: Limits = Limits(), clock: Callable[[], float] = monotonic):
        self.limits = limits
        self._clock = clock
        self._deadline = clock() + limits.total_seconds
        self._counts = {"search": 0, "document": 0, "model": 0}
        self._caps = {"search": limits.searches, "document": limits.documents,
                      "model": limits.model_calls}
        self._cancelled = False
        self._lock = Lock()

    def _remaining(self) -> float:
        from app.web_research.execution_control import current
        execution = current.get()
        if execution is not None:
            execution.check()
        if self._cancelled:
            raise BudgetExceeded("EXECUTION_CANCELLED")
        remaining = self._deadline - self._clock()
        if remaining <= 0:
            raise BudgetExceeded("EXECUTION_DEADLINE")
        return remaining

    def reserve(self, operation: Operation) -> float:
        """Charge before starting work; return its maximum remaining timeout."""
        with self._lock:
            if operation not in self._caps:
                raise ValueError("Unknown operation")
            remaining = self._remaining()
            if self._counts[operation] >= self._caps[operation]:
                raise BudgetExceeded("EXECUTION_BUDGET_EXHAUSTED")
            self._counts[operation] += 1
            cap = (self.limits.model_request_seconds if operation == 'model'
                   and self.limits.model_request_seconds is not None else self.limits.request_seconds)
            return min(remaining, cap)

    def checkpoint(self) -> float:
        """Check between stages/chunks without charging a new operation."""
        with self._lock:
            return self._remaining()

    def cancel(self) -> None:
        with self._lock:
            self._cancelled = True

    def snapshot(self) -> Usage:
        with self._lock:
            return Usage(self._counts["search"], self._counts["document"],
                         self._counts["model"], max(0.0, self._deadline - self._clock()),
                         self._cancelled)
