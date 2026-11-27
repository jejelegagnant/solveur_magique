"""Timezone- and DST-safe temporal utilities for ``Europe/Zurich`` scheduling.

All shift durations, daily spans, inter-shift rest periods, and night-window
overlaps are computed over timezone-aware UTC instants derived from
``Europe/Zurich`` wall-clock times so that spring-forward (23 h) and fall-back
(25 h) DST transitions never corrupt Swiss labor-law calculations
(``NFR-024``, ``FR-008``, ``FR-023``, ``FR-025``, ``FR-028``).
"""

from __future__ import annotations

import calendar
import re
from collections.abc import Sequence
from datetime import UTC, date, datetime, time, timedelta, timezone
from decimal import ROUND_HALF_UP, Decimal
from typing import Final, Literal
from uuid import UUID
from zoneinfo import ZoneInfo

from solver_core.schemas.legal import BreakWarning
from solver_core.schemas.shifts import ShiftSegment

ZURICH_TZ: Final[ZoneInfo] = ZoneInfo("Europe/Zurich")
UTC_TZ: Final[timezone] = UTC

_ONE_MINUTE_DELTA: Final[timedelta] = timedelta(minutes=1)
_DEFAULT_NIGHT_START: Final[time] = time(23, 0)
_DEFAULT_NIGHT_END: Final[time] = time(6, 0)
_YEAR_MONTH_RE: Final[re.Pattern[str]] = re.compile(r"[0-9]{4}-[0-9]{2}")
_MINUTES_PER_HOUR: Final[Decimal] = Decimal(60)
_ONE_UNIT: Final[Decimal] = Decimal("1")
_TWO_DECIMALS: Final[Decimal] = Decimal("0.01")

# Art. 15 al. 1 LTr mandatory minimum break thresholds (strictly greater than).
_LTR_BREAK_THRESHOLDS: Final[
    tuple[tuple[int, int, Literal["LTR_BREAK_60M", "LTR_BREAK_30M", "LTR_BREAK_15M"]], ...]
] = (
    (540, 60, "LTR_BREAK_60M"),  # > 9.0 h -> 60 min
    (420, 30, "LTR_BREAK_30M"),  # > 7.0 h -> 30 min
    (330, 15, "LTR_BREAK_15M"),  # > 5.5 h -> 15 min
)

__all__ = [
    "UTC_TZ",
    "ZURICH_TZ",
    "check_ltr_break_compliance",
    "daily_span_minutes",
    "elapsed_minutes",
    "hours_to_minutes",
    "intervals_overlap",
    "is_ambiguous_local_time",
    "is_nonexistent_local_time",
    "local_to_utc",
    "minutes_to_hours",
    "night_window_overlap_minutes",
    "paid_minutes",
    "period_date_range",
    "prior_boundary_range",
    "rest_minutes_between",
    "segment_utc_interval",
    "segments_utc_intervals",
]


def _validate_naive_time(t: time, *, name: str = "t") -> None:
    if t.tzinfo is not None:
        msg = f"{name} must be timezone-naive, got tzinfo={t.tzinfo!r}"
        raise ValueError(msg)


def _validate_fold(fold: int) -> None:
    if isinstance(fold, bool) or fold not in (0, 1):
        msg = f"fold must be 0 or 1, got {fold!r}"
        raise ValueError(msg)


def _validate_utc_interval(
    interval: tuple[datetime, datetime],
    *,
    name: str,
) -> tuple[datetime, datetime]:
    start, end = interval
    if start.tzinfo is None or start.utcoffset() is None:
        msg = f"{name} start must be timezone-aware, got {start!r}"
        raise ValueError(msg)
    if end.tzinfo is None or end.utcoffset() is None:
        msg = f"{name} end must be timezone-aware, got {end!r}"
        raise ValueError(msg)
    start_utc = start.astimezone(UTC_TZ)
    end_utc = end.astimezone(UTC_TZ)
    if start_utc > end_utc:
        msg = f"{name} start ({start_utc.isoformat()}) must be <= end ({end_utc.isoformat()})"
        raise ValueError(msg)
    return (start_utc, end_utc)


def _parse_year_month(year_month: str) -> tuple[int, int]:
    if not _YEAR_MONTH_RE.fullmatch(year_month):
        msg = f"year_month must strictly match 'YYYY-MM', got {year_month!r}"
        raise ValueError(msg)
    year = int(year_month[:4])
    month = int(year_month[5:7])
    if year < 1 or not (1 <= month <= 12):
        msg = f"Invalid year or month in year_month={year_month!r}"
        raise ValueError(msg)
    return (year, month)


def is_nonexistent_local_time(d: date, t: time) -> bool:
    """Return True if local wall time ``(d, t)`` falls in a ``Europe/Zurich`` DST gap."""
    _validate_naive_time(t)
    local_dt = datetime.combine(d, t, tzinfo=ZURICH_TZ)
    roundtrip = local_dt.astimezone(UTC_TZ).astimezone(ZURICH_TZ)
    return roundtrip.date() != d or roundtrip.time() != t


def is_ambiguous_local_time(d: date, t: time) -> bool:
    """Return True if local wall time ``(d, t)`` occurs twice in ``Europe/Zurich`` (fall-back)."""
    _validate_naive_time(t)
    if is_nonexistent_local_time(d, t):
        return False
    utc_fold0 = datetime.combine(d, t, tzinfo=ZURICH_TZ).replace(fold=0).astimezone(UTC_TZ)
    utc_fold1 = datetime.combine(d, t, tzinfo=ZURICH_TZ).replace(fold=1).astimezone(UTC_TZ)
    return utc_fold0 != utc_fold1


def local_to_utc(
    d: date,
    t: time,
    *,
    fold: int = 0,
    allow_nonexistent: bool = False,
) -> datetime:
    """Convert a naive ``Europe/Zurich`` local ``(d, t)`` pair into a UTC ``datetime``.

    Raises:
        ValueError: If ``t`` is timezone-aware, ``fold`` is not ``0`` or ``1``,
            or ``(d, t)`` is a nonexistent spring-forward DST wall time when
            ``allow_nonexistent`` is ``False``.
    """
    _validate_naive_time(t)
    _validate_fold(fold)
    if not allow_nonexistent and is_nonexistent_local_time(d, t):
        msg = (
            f"Local wall time {d.isoformat()}T{t.isoformat()} does not exist "
            "in Europe/Zurich due to spring-forward DST transition"
        )
        raise ValueError(msg)
    local_dt = datetime.combine(d, t, tzinfo=ZURICH_TZ).replace(fold=fold)
    return local_dt.astimezone(UTC_TZ)


def segment_utc_interval(work_date: date, segment: ShiftSegment) -> tuple[datetime, datetime]:
    """Convert a ``ShiftSegment`` anchored on ``work_date`` into a UTC ``(start, end)`` pair."""
    start_utc = local_to_utc(work_date, segment.start_time, fold=0)
    end_date = work_date + timedelta(days=1) if segment.crosses_midnight else work_date
    end_utc = local_to_utc(end_date, segment.end_time, fold=0)
    if end_utc <= start_utc and is_ambiguous_local_time(end_date, segment.end_time):
        end_utc = local_to_utc(end_date, segment.end_time, fold=1)
    if end_utc <= start_utc:
        msg = (
            f"Segment {segment.start_time.isoformat()}-{segment.end_time.isoformat()} "
            f"on {work_date.isoformat()} yields non-positive UTC interval "
            f"({start_utc.isoformat()} -> {end_utc.isoformat()})"
        )
        raise ValueError(msg)
    return (start_utc, end_utc)


def segments_utc_intervals(
    work_date: date,
    segments: Sequence[ShiftSegment],
) -> tuple[tuple[datetime, datetime], ...]:
    """Convert ordered, non-overlapping shift segments on ``work_date`` into UTC intervals."""
    if not segments:
        msg = "segments must be non-empty"
        raise ValueError(msg)
    intervals: list[tuple[datetime, datetime]] = []
    for segment in segments:
        interval = segment_utc_interval(work_date, segment)
        if intervals and intervals[-1][1] > interval[0]:
            msg = (
                f"Segments overlap or are out of chronological order on {work_date.isoformat()}: "
                f"previous ended at {intervals[-1][1].isoformat()}, "
                f"next starts at {interval[0].isoformat()}"
            )
            raise ValueError(msg)
        intervals.append(interval)
    return tuple(intervals)


def elapsed_minutes(work_date: date, segments: Sequence[ShiftSegment]) -> int:
    """Return exact total elapsed UTC minutes across ``segments`` on ``work_date``."""
    intervals = segments_utc_intervals(work_date, segments)
    return sum((end - start) // _ONE_MINUTE_DELTA for start, end in intervals)


def paid_minutes(
    work_date: date,
    segments: Sequence[ShiftSegment],
    unpaid_break_min: int = 0,
) -> int:
    """Return effective paid work minutes after subtracting ``unpaid_break_min``."""
    if isinstance(unpaid_break_min, bool) or unpaid_break_min < 0:
        msg = f"unpaid_break_min must be a non-negative integer, got {unpaid_break_min!r}"
        raise ValueError(msg)
    elapsed = elapsed_minutes(work_date, segments)
    if unpaid_break_min > elapsed:
        msg = (
            f"unpaid_break_min ({unpaid_break_min}) cannot exceed "
            f"elapsed shift duration ({elapsed} min)"
        )
        raise ValueError(msg)
    return elapsed - unpaid_break_min


def daily_span_minutes(work_date: date, segments: Sequence[ShiftSegment]) -> int:
    """Return total UTC minutes from first segment start to last segment end."""
    intervals = segments_utc_intervals(work_date, segments)
    return (intervals[-1][1] - intervals[0][0]) // _ONE_MINUTE_DELTA


def rest_minutes_between(
    prev_date: date,
    prev_segments: Sequence[ShiftSegment],
    next_date: date,
    next_segments: Sequence[ShiftSegment],
) -> int:
    """Return exact UTC rest minutes between ``prev_segments`` end and ``next_segments`` start.

    May be negative when the two shifts overlap in UTC.
    """
    prev_intervals = segments_utc_intervals(prev_date, prev_segments)
    next_intervals = segments_utc_intervals(next_date, next_segments)
    return (next_intervals[0][0] - prev_intervals[-1][1]) // _ONE_MINUTE_DELTA


def intervals_overlap(
    interval_a: tuple[datetime, datetime],
    interval_b: tuple[datetime, datetime],
) -> bool:
    """Return True if half-open UTC intervals ``[start, end)`` intersect."""
    a_start, a_end = _validate_utc_interval(interval_a, name="interval_a")
    b_start, b_end = _validate_utc_interval(interval_b, name="interval_b")
    return max(a_start, b_start) < min(a_end, b_end)


def night_window_overlap_minutes(
    work_date: date,
    segments: Sequence[ShiftSegment],
    night_start: time = _DEFAULT_NIGHT_START,
    night_end: time = _DEFAULT_NIGHT_END,
) -> int:
    """Return exact UTC overlap minutes between ``segments`` and local night windows.

    Night windows are anchored on ``work_date - 1``, ``work_date``, and
    ``work_date + 1`` in ``Europe/Zurich`` before conversion to UTC, handling
    early-morning shifts, overnight shifts, custom CCT windows (e.g.,
    ``20:00-06:00``), and DST transitions accurately.
    """
    _validate_naive_time(night_start, name="night_start")
    _validate_naive_time(night_end, name="night_end")
    if night_start == night_end:
        msg = f"night_start and night_end must differ, both are {night_start.isoformat()}"
        raise ValueError(msg)

    seg_intervals = segments_utc_intervals(work_date, segments)
    window_crosses_midnight = night_end < night_start

    raw_windows: list[tuple[datetime, datetime]] = []
    for day_offset in (-1, 0, 1):
        anchor = work_date + timedelta(days=day_offset)
        w_start = local_to_utc(anchor, night_start, fold=0, allow_nonexistent=True)
        w_end_date = anchor + timedelta(days=1) if window_crosses_midnight else anchor
        w_end = local_to_utc(w_end_date, night_end, fold=0, allow_nonexistent=True)
        if w_end > w_start:
            raw_windows.append((w_start, w_end))

    # Merge any overlapping windows defensively so minutes can never be double-counted.
    raw_windows.sort(key=lambda w: w[0])
    merged_windows: list[tuple[datetime, datetime]] = []
    for w_start, w_end in raw_windows:
        if merged_windows and w_start <= merged_windows[-1][1]:
            prev_start, prev_end = merged_windows[-1]
            merged_windows[-1] = (prev_start, max(prev_end, w_end))
        else:
            merged_windows.append((w_start, w_end))

    total_overlap = 0
    for seg_start, seg_end in seg_intervals:
        for w_start, w_end in merged_windows:
            overlap_start = max(seg_start, w_start)
            overlap_end = min(seg_end, w_end)
            if overlap_end > overlap_start:
                total_overlap += (overlap_end - overlap_start) // _ONE_MINUTE_DELTA
    return total_overlap


def check_ltr_break_compliance(
    work_date: date,
    segments: Sequence[ShiftSegment],
    unpaid_break_min: int,
    *,
    paid_on_post_break: bool = False,
    shift_template_id: UUID | None = None,
) -> list[BreakWarning]:
    """Check Swiss Art. 15 ``LTr`` mandatory break thresholds (``FR-008``).

    Split-shift unpaid mid-day gaps (``daily_span_minutes - elapsed_minutes``)
    count toward total available break time alongside ``unpaid_break_min``.
    """
    work_min = paid_minutes(work_date, segments, unpaid_break_min)
    if paid_on_post_break:
        return []

    elapsed = elapsed_minutes(work_date, segments)
    span = daily_span_minutes(work_date, segments)
    configured_break_min = unpaid_break_min + (span - elapsed)

    for threshold_min, required_break_min, code in _LTR_BREAK_THRESHOLDS:
        if work_min > threshold_min:
            if configured_break_min < required_break_min:
                return [
                    BreakWarning(
                        shift_template_id=shift_template_id,
                        work_duration_min=work_min,
                        required_break_min=required_break_min,
                        configured_break_min=configured_break_min,
                        code=code,
                    )
                ]
            return []
    return []


def period_date_range(year_month: str) -> tuple[date, date]:
    """Return inclusive ``(first_day, last_day)`` for a strict ``'YYYY-MM'`` string."""
    year, month = _parse_year_month(year_month)
    _, last_day = calendar.monthrange(year, month)
    return (date(year, month, 1), date(year, month, last_day))


def prior_boundary_range(year_month: str, lookback_days: int = 7) -> tuple[date, date]:
    """Return inclusive ``(start_date, end_date)`` covering the prior ``lookback_days`` days."""
    if isinstance(lookback_days, bool) or lookback_days < 1:
        msg = f"lookback_days must be an integer >= 1, got {lookback_days!r}"
        raise ValueError(msg)
    period_start, _ = period_date_range(year_month)
    return (
        period_start - timedelta(days=lookback_days),
        period_start - timedelta(days=1),
    )


def hours_to_minutes(hours: Decimal) -> int:
    """Convert a finite ``Decimal`` hour value to exact integer minutes (``ROUND_HALF_UP``)."""
    if not hours.is_finite():
        msg = f"hours must be a finite Decimal, got {hours!r}"
        raise ValueError(msg)
    return int((hours * _MINUTES_PER_HOUR).quantize(_ONE_UNIT, rounding=ROUND_HALF_UP))


def minutes_to_hours(minutes: int) -> Decimal:
    """Convert integer minutes to a 2-decimal-place ``Decimal`` hour value (``ROUND_HALF_UP``)."""
    if isinstance(minutes, bool):
        msg = f"minutes must be an int, not bool ({minutes!r})"
        raise TypeError(msg)
    return (Decimal(minutes) / _MINUTES_PER_HOUR).quantize(
        _TWO_DECIMALS,
        rounding=ROUND_HALF_UP,
    )
