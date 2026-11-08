from dataclasses import dataclass, field
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal, ROUND_HALF_UP
from functools import lru_cache
from uuid import UUID
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from sqlalchemy.orm import Session

from app.domain.stats import (
    ExerciseStatsDetail,
    ExerciseStatsPoint,
    ExerciseStatsSummary,
    StatsMuscleGroupSummary,
    StatsOverview,
    StatsOverviewKpis,
    StatsOverviewPoint,
    StatsPeriod,
    StatsTopExerciseSummary,
    StatsVolumeByUnit,
)
from app.infrastructure.db.models.user import User
from app.infrastructure.db.repositories.exercises import ExerciseRepository
from app.infrastructure.db.repositories.stats import StatsRepository, StatsRow

TWO_PLACES = Decimal("0.01")
# Epley solo es razonablemente fiable en series cortas; fuera de 1-12 reps no se estima 1RM.
E1RM_MIN_REPS = 1
E1RM_MAX_REPS = 12


def estimate_1rm(weight: Decimal | None, reps: int) -> Decimal | None:
    """1RM estimado (Epley). None si no hay peso o las reps estan fuera del rango fiable."""
    if weight is None or reps < E1RM_MIN_REPS or reps > E1RM_MAX_REPS:
        return None
    weight = Decimal(weight)
    if reps == 1:
        return weight
    return weight * (Decimal("1") + (Decimal(reps) / Decimal("30")))


class StatsNotFoundError(Exception):
    pass


@dataclass
class StatsAccumulator:
    exercise_id: UUID
    exercise_name: str
    weight_unit: str | None
    total_sets: int = 0
    total_reps: int = 0
    weighted_sets: int = 0
    weight_sum: Decimal = Decimal("0")
    total_volume: Decimal = Decimal("0")
    max_weight: Decimal | None = None
    best_estimated_1rm: Decimal | None = None
    first_session_at: datetime | None = None
    last_session_at: datetime | None = None

    def add(self, row: StatsRow) -> None:
        workout_set, session, _exercise = row
        started_at = ensure_utc(session.started_at)
        self.total_sets += 1
        self.total_reps += workout_set.reps
        self.first_session_at = started_at if self.first_session_at is None else min(self.first_session_at, started_at)
        self.last_session_at = started_at if self.last_session_at is None else max(self.last_session_at, started_at)

        if workout_set.weight_value is None:
            return

        weight = Decimal(workout_set.weight_value)
        self.weighted_sets += 1
        self.weight_sum += weight
        self.total_volume += weight * workout_set.reps
        if workout_set.reps > 0:
            # Una serie con 0 reps es un intento fallido: no cuenta como peso maximo levantado.
            self.max_weight = weight if self.max_weight is None else max(self.max_weight, weight)
        estimated_1rm = estimate_1rm(weight, workout_set.reps)
        if estimated_1rm is not None:
            self.best_estimated_1rm = (
                estimated_1rm if self.best_estimated_1rm is None else max(self.best_estimated_1rm, estimated_1rm)
            )

    def to_summary(self) -> ExerciseStatsSummary:
        return ExerciseStatsSummary(
            exercise_id=self.exercise_id,
            exercise_name=self.exercise_name,
            weight_unit=self.weight_unit,
            total_sets=self.total_sets,
            total_reps=self.total_reps,
            total_volume=quantize_or_none(self.total_volume if self.weighted_sets else None),
            max_weight=quantize_or_none(self.max_weight),
            avg_weight=quantize_or_none(self.weight_sum / self.weighted_sets if self.weighted_sets else None),
            best_estimated_1rm=quantize_or_none(self.best_estimated_1rm),
            first_session_at=self.first_session_at,
            last_session_at=self.last_session_at,
        )

    def to_point(self, period_start: datetime) -> ExerciseStatsPoint:
        return ExerciseStatsPoint(
            period_start=period_start,
            weight_unit=self.weight_unit,
            total_sets=self.total_sets,
            total_reps=self.total_reps,
            total_volume=quantize_or_none(self.total_volume if self.weighted_sets else None),
            max_weight=quantize_or_none(self.max_weight),
            avg_weight=quantize_or_none(self.weight_sum / self.weighted_sets if self.weighted_sets else None),
            best_estimated_1rm=quantize_or_none(self.best_estimated_1rm),
        )


def ensure_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def quantize_or_none(value: Decimal | None) -> Decimal | None:
    if value is None:
        return None
    return value.quantize(TWO_PLACES, rounding=ROUND_HALF_UP)


@lru_cache(maxsize=128)
def _zone(name: str | None) -> ZoneInfo:
    try:
        return ZoneInfo(name) if name else ZoneInfo("UTC")
    except (ZoneInfoNotFoundError, ValueError):
        return ZoneInfo("UTC")


def local_date(value: datetime, timezone_name: str | None) -> date:
    return ensure_utc(value).astimezone(_zone(timezone_name)).date()


def period_start_for(value: datetime, period: StatsPeriod, timezone_name: str | None = None) -> datetime:
    """Inicio del periodo segun el calendario local de la sesion.

    Se devuelve como medianoche UTC de esa fecha local: es una etiqueta de calendario, no un instante.
    El frontend la formatea con timeZone UTC.
    """
    day = local_date(value, timezone_name)
    if period == "week":
        day = day - timedelta(days=day.weekday())
    elif period == "month":
        day = day.replace(day=1)
    return datetime(day.year, day.month, day.day, tzinfo=UTC)


def count_personal_records(
    rows: list[StatsRow], start_date: datetime | None = None, end_date: datetime | None = None
) -> int:
    """Cuenta sesiones en las que se supera el peso maximo previo de un ejercicio/unidad.

    La primera sesion de cada ejercicio/unidad es la marca de referencia, no un record.
    Solo cuentan series con peso y al menos 1 rep. kg y lb son grupos separados.
    """
    session_best: dict[tuple[UUID, str, UUID], tuple[datetime, Decimal]] = {}
    for workout_set, session, _exercise in rows:
        if workout_set.weight_value is None or workout_set.weight_unit is None or workout_set.reps < 1:
            continue
        key = (workout_set.exercise_id, workout_set.weight_unit, session.id)
        weight = Decimal(workout_set.weight_value)
        current = session_best.get(key)
        if current is None or weight > current[1]:
            session_best[key] = (ensure_utc(session.started_at), weight)

    by_group: dict[tuple[UUID, str], list[tuple[datetime, Decimal]]] = {}
    for (exercise_id, unit, _session_id), value in session_best.items():
        by_group.setdefault((exercise_id, unit), []).append(value)

    start = ensure_utc(start_date) if start_date else None
    end = ensure_utc(end_date) if end_date else None
    records = 0
    for sessions in by_group.values():
        sessions.sort(key=lambda item: item[0])
        best_so_far = sessions[0][1]
        for started_at, weight in sessions[1:]:
            if weight > best_so_far:
                best_so_far = weight
                if (start is None or started_at >= start) and (end is None or started_at <= end):
                    records += 1
    return records


def row_weight_unit(row: StatsRow) -> str | None:
    workout_set, _session, _exercise = row
    return workout_set.weight_unit if workout_set.weight_value is not None else None


class StatsService:
    def list_exercise_stats(
        self,
        db: Session,
        user: User,
        start_date: datetime | None,
        end_date: datetime | None,
        weight_unit: str | None,
    ) -> list[ExerciseStatsSummary]:
        rows = StatsRepository(db).list_workout_sets(
            user_id=user.id,
            start_date=start_date,
            end_date=end_date,
        )
        rows = filter_rows_by_weight_unit(rows, weight_unit)
        groups: dict[tuple[UUID, str | None], StatsAccumulator] = {}
        for row in rows:
            workout_set, _session, exercise = row
            unit = row_weight_unit(row)
            key = (workout_set.exercise_id, unit)
            groups.setdefault(
                key,
                StatsAccumulator(
                    exercise_id=workout_set.exercise_id,
                    exercise_name=exercise.name,
                    weight_unit=unit,
                ),
            ).add(row)

        return sorted(
            (group.to_summary() for group in groups.values()),
            key=lambda item: (item.exercise_name, item.weight_unit or ""),
        )

    def get_exercise_stats(
        self,
        db: Session,
        user: User,
        exercise_id: UUID,
        period: StatsPeriod,
        start_date: datetime | None,
        end_date: datetime | None,
        weight_unit: str | None,
    ) -> ExerciseStatsDetail:
        exercise = ExerciseRepository(db).get_accessible(exercise_id, user.id)
        if exercise is None:
            raise StatsNotFoundError

        rows = StatsRepository(db).list_workout_sets(
            user_id=user.id,
            exercise_id=exercise_id,
            start_date=start_date,
            end_date=end_date,
        )
        rows = filter_rows_by_weight_unit(rows, weight_unit)
        groups: dict[tuple[datetime, str | None], StatsAccumulator] = {}
        for row in rows:
            workout_set, session, _exercise = row
            unit = row_weight_unit(row)
            period_start = period_start_for(session.started_at, period, session.timezone)
            key = (period_start, unit)
            groups.setdefault(
                key,
                StatsAccumulator(
                    exercise_id=workout_set.exercise_id,
                    exercise_name=exercise.name,
                    weight_unit=unit,
                ),
            ).add(row)

        points = [group.to_point(period_start) for (period_start, _unit), group in groups.items()]
        points.sort(key=lambda item: (item.period_start, item.weight_unit or ""))
        return ExerciseStatsDetail(exercise_id=exercise.id, exercise_name=exercise.name, period=period, points=points)

    def get_overview(
        self,
        db: Session,
        user: User,
        period: StatsPeriod,
        start_date: datetime | None,
        end_date: datetime | None,
        weight_unit: str | None,
    ) -> StatsOverview:
        rows = StatsRepository(db).list_workout_sets(
            user_id=user.id,
            start_date=start_date,
            end_date=end_date,
        )
        rows = filter_rows_by_weight_unit(rows, weight_unit)

        sessions = {session.id: session for _set, session, _exercise in rows}
        training_seconds = sum(session_duration_seconds(session) for session in sessions.values())
        volume_by_unit: dict[str | None, Decimal] = {}
        period_groups: dict[tuple[datetime, str | None], StatsOverviewAccumulator] = {}
        muscle_groups: dict[str, int] = {}
        exercises: dict[tuple[UUID, str | None], StatsAccumulator] = {}

        for row in rows:
            workout_set, session, exercise = row
            unit = row_weight_unit(row)
            if workout_set.weight_value is not None:
                volume_by_unit[unit] = volume_by_unit.get(unit, Decimal("0")) + Decimal(workout_set.weight_value) * workout_set.reps

            period_start = period_start_for(session.started_at, period, session.timezone)
            period_key = (period_start, unit)
            period_groups.setdefault(period_key, StatsOverviewAccumulator(period_start=period_start, weight_unit=unit)).add(row)

            if exercise.muscle_groups:
                for muscle_group in exercise.muscle_groups:
                    muscle_groups[muscle_group.name] = muscle_groups.get(muscle_group.name, 0) + 1
            else:
                muscle_groups["Sin musculo"] = muscle_groups.get("Sin musculo", 0) + 1

            exercise_key = (workout_set.exercise_id, unit)
            exercises.setdefault(
                exercise_key,
                StatsAccumulator(
                    exercise_id=workout_set.exercise_id,
                    exercise_name=exercise.name,
                    weight_unit=unit,
                ),
            ).add(row)

        if start_date is None and end_date is None:
            history_rows = rows
        else:
            history_rows = filter_rows_by_weight_unit(StatsRepository(db).list_workout_sets(user_id=user.id), weight_unit)
        pr_count = count_personal_records(history_rows, start_date, end_date)

        top_exercises = [to_top_exercise(group) for group in exercises.values()]
        top_exercises.sort(key=top_exercise_sort_key)

        return StatsOverview(
            period=period,
            kpis=StatsOverviewKpis(
                total_sets=len(rows),
                session_count=len(sessions),
                training_hours=quantize_or_none(Decimal(training_seconds) / Decimal("3600")) or Decimal("0.00"),
                pr_count=pr_count,
            ),
            volume_by_unit=[
                StatsVolumeByUnit(weight_unit=unit, total_volume=quantize_or_none(total))
                for unit, total in sorted(volume_by_unit.items(), key=lambda item: item[0] or "")
            ],
            volume_points=sorted(
                (group.to_point() for group in period_groups.values()),
                key=lambda item: (item.period_start, item.weight_unit or ""),
            ),
            muscle_groups=[
                StatsMuscleGroupSummary(name=name, total_sets=total_sets)
                for name, total_sets in sorted(muscle_groups.items(), key=lambda item: item[1], reverse=True)
            ],
            top_exercises=top_exercises[:5],
        )


def filter_rows_by_weight_unit(rows: list[StatsRow], weight_unit: str | None) -> list[StatsRow]:
    if weight_unit is None:
        return rows
    return [row for row in rows if row_weight_unit(row) == weight_unit]


@dataclass
class StatsOverviewAccumulator:
    period_start: datetime
    weight_unit: str | None
    total_sets: int = 0
    total_volume: Decimal = Decimal("0")
    weighted_sets: int = 0
    session_ids: set[UUID] = field(default_factory=set)

    def add(self, row: StatsRow) -> None:
        workout_set, session, _exercise = row
        self.total_sets += 1
        self.session_ids.add(session.id)
        if workout_set.weight_value is not None:
            self.weighted_sets += 1
            self.total_volume += Decimal(workout_set.weight_value) * workout_set.reps

    def to_point(self) -> StatsOverviewPoint:
        return StatsOverviewPoint(
            period_start=self.period_start,
            weight_unit=self.weight_unit,
            total_volume=quantize_or_none(self.total_volume if self.weighted_sets else None),
            total_sets=self.total_sets,
            session_count=len(self.session_ids),
        )


def session_duration_seconds(session) -> int:
    if session.finished_at is None:
        return 0
    started_at = ensure_utc(session.started_at)
    finished_at = ensure_utc(session.finished_at)
    if finished_at <= started_at:
        return 0
    return int((finished_at - started_at).total_seconds())


def to_top_exercise(group: StatsAccumulator) -> StatsTopExerciseSummary:
    return StatsTopExerciseSummary(
        exercise_id=group.exercise_id,
        exercise_name=group.exercise_name,
        weight_unit=group.weight_unit,
        total_volume=quantize_or_none(group.total_volume if group.weighted_sets else None),
        max_weight=quantize_or_none(group.max_weight),
        best_estimated_1rm=quantize_or_none(group.best_estimated_1rm),
    )


def top_exercise_sort_key(item: StatsTopExerciseSummary) -> tuple[str, Decimal]:
    # Keep units grouped so kg and lb are not ranked against each other numerically.
    metric = item.best_estimated_1rm or item.max_weight or item.total_volume or Decimal("0")
    return (item.weight_unit or "", -metric)


stats_service = StatsService()
