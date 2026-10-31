"""Test-only SQLAlchemy statement measurement helpers."""

from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field
from time import perf_counter

from sqlalchemy import event
from sqlalchemy.engine import Engine


@dataclass
class SQLMeasurement:
    """Captured SQL statements and successful database execution durations."""

    statements: list[str] = field(default_factory=list)
    durations_ms: list[float] = field(default_factory=list)

    @property
    def statement_count(self) -> int:
        return len(self.statements)

    @property
    def database_time_ms(self) -> float:
        return sum(self.durations_ms)


@contextmanager
def measure_sql(engine: Engine) -> Iterator[SQLMeasurement]:
    """Measure statements on one engine and always detach event listeners."""

    measurement = SQLMeasurement()
    starts: list[float] = []

    def before_cursor_execute(
        _connection, _cursor, statement, _parameters, _context, _executemany
    ) -> None:
        measurement.statements.append(statement)
        starts.append(perf_counter())

    def after_cursor_execute(
        _connection, _cursor, _statement, _parameters, _context, _executemany
    ) -> None:
        measurement.durations_ms.append((perf_counter() - starts.pop()) * 1_000)

    event.listen(engine, "before_cursor_execute", before_cursor_execute)
    event.listen(engine, "after_cursor_execute", after_cursor_execute)
    try:
        yield measurement
    finally:
        event.remove(engine, "before_cursor_execute", before_cursor_execute)
        event.remove(engine, "after_cursor_execute", after_cursor_execute)
