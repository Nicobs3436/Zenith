import { ExerciseStats, ExerciseStatsPoint, StatsWeightUnit } from '@/api/client';

export type StatsChartMetric = 'estimated_1rm' | 'max_weight' | 'volume';

export function statsKey(item: ExerciseStats) {
  return `${item.exercise_id}-${item.weight_unit ?? 'bodyweight'}`;
}

export function isStatsWeightUnit(value: string | null): value is StatsWeightUnit {
  return value === 'kg' || value === 'lb';
}

export function numeric(value: string | null) {
  if (!value) {
    return 0;
  }
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : 0;
}

export function formatStatsValue(value: string | null, unit?: string | null) {
  if (!value) {
    return '-';
  }
  return unit ? `${value} ${unit}` : value;
}

export function formatStatsPoint(point: ExerciseStatsPoint, unit: string | null) {
  if (point.total_volume) {
    return `Vol ${formatStatsValue(point.total_volume)} · 1RM ${formatStatsValue(point.best_estimated_1rm, unit)}`;
  }
  return `${point.total_reps} reps · ${point.total_sets} series`;
}

export function formatStatsUnit(unit: string | null) {
  return unit ?? 'sin peso';
}

export function formatStatsDateRange(item: ExerciseStats) {
  if (!item.first_session_at || !item.last_session_at) {
    return 'sin fechas';
  }
  if (item.first_session_at === item.last_session_at) {
    return formatStatsDate(item.first_session_at);
  }
  return `${formatStatsDate(item.first_session_at)} - ${formatStatsDate(item.last_session_at)}`;
}

export function formatStatsDate(value: string) {
  return new Date(value).toLocaleDateString('es-ES', { day: '2-digit', month: 'short' });
}

// period_start es una etiqueta de calendario (fecha local de la sesion a medianoche UTC):
// se formatea en UTC para que no cambie de dia segun la zona del dispositivo.
export function formatPeriodDate(value: string) {
  return new Date(value).toLocaleDateString('es-ES', { day: '2-digit', month: 'short', timeZone: 'UTC' });
}

export function shortStatsDate(value: string) {
  return new Date(value).toLocaleDateString('es-ES', { day: '2-digit', month: '2-digit', timeZone: 'UTC' });
}

export function buildStatsChart(points: ExerciseStatsPoint[]) {
  const hasVolume = points.some((point) => numeric(point.total_volume) > 0);
  return {
    label: hasVolume ? 'Volumen por periodo' : 'Reps por periodo',
    bars: points.map((point) => ({
      label: shortStatsDate(point.period_start),
      value: hasVolume ? numeric(point.total_volume) : point.total_reps,
    })),
  };
}

export function buildMetricStatsChart(points: ExerciseStatsPoint[], metric: StatsChartMetric) {
  const labels: Record<StatsChartMetric, string> = {
    estimated_1rm: '1RM estimado',
    max_weight: 'Peso maximo',
    volume: 'Volumen total',
  };
  const valueForPoint = (point: ExerciseStatsPoint) => {
    if (metric === 'estimated_1rm') {
      return numeric(point.best_estimated_1rm);
    }
    if (metric === 'max_weight') {
      return numeric(point.max_weight);
    }
    return numeric(point.total_volume);
  };
  return {
    label: labels[metric],
    bars: points.map((point) => ({
      label: shortStatsDate(point.period_start),
      value: valueForPoint(point),
    })),
  };
}

export function formatMetricStatsPoint(point: ExerciseStatsPoint, metric: StatsChartMetric, unit: string | null) {
  if (metric === 'estimated_1rm') {
    return `1RM ${formatStatsValue(point.best_estimated_1rm, unit)}`;
  }
  if (metric === 'max_weight') {
    return `Peso ${formatStatsValue(point.max_weight, unit)}`;
  }
  return `Vol ${formatStatsValue(point.total_volume, unit)}`;
}
