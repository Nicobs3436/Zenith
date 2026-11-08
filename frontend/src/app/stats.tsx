import { Activity, Clock, Layers, Star, TrendingUp } from 'lucide-react-native';
import { useEffect, useState } from 'react';
import { Pressable, StyleSheet, Text, View } from 'react-native';
import Svg, { Circle, Line, Polyline, Text as SvgText } from 'react-native-svg';

import {
  ExerciseStats,
  ExerciseStatsDetail,
  ExerciseStatsPoint,
  getExerciseStats,
  getExerciseStatsDetail,
  getStatsOverview,
  StatsOverview,
  StatsGroupingPeriod,
  StatsPeriodFilter,
  StatsWeightUnit,
} from '@/api/client';
import { ZenithBottomNav, ZenithCard, ZenithHeader, ZenithNotice, ZenithPill } from '@/components/ZenithUI';
import { ZenithScreen } from '@/components/ZenithScreen';
import { zenith } from '@/constants/zenithTheme';
import {
  buildMetricStatsChart,
  formatPeriodDate,
  formatStatsDateRange,
  formatMetricStatsPoint,
  formatStatsUnit,
  formatStatsValue,
  isStatsWeightUnit,
  StatsChartMetric,
  statsKey,
} from '@/utils/statsDisplay';

type WeightFilter = 'all' | StatsWeightUnit;

const PERIODS: { label: string; value: StatsPeriodFilter }[] = [
  { label: '7 dias', value: '7d' },
  { label: '30 dias', value: '30d' },
  { label: '90 dias', value: '90d' },
  { label: 'Todo', value: 'all' },
];

const WEIGHT_FILTERS: { label: string; value: WeightFilter }[] = [
  { label: 'Todas', value: 'all' },
  { label: 'kg', value: 'kg' },
  { label: 'lb', value: 'lb' },
];

const GROUP_PERIODS: { label: string; value: StatsGroupingPeriod }[] = [
  { label: 'Dia', value: 'day' },
  { label: 'Semana', value: 'week' },
  { label: 'Mes', value: 'month' },
];

const CHART_METRICS: { label: string; value: StatsChartMetric }[] = [
  { label: '1RM', value: 'estimated_1rm' },
  { label: 'Peso', value: 'max_weight' },
  { label: 'Volumen', value: 'volume' },
];

export default function StatsScreen() {
  const [period, setPeriod] = useState<StatsPeriodFilter>('30d');
  const [weightFilter, setWeightFilter] = useState<WeightFilter>('all');
  const [groupPeriod, setGroupPeriod] = useState<StatsGroupingPeriod>('week');
  const [stats, setStats] = useState<ExerciseStats[]>([]);
  const [overview, setOverview] = useState<StatsOverview | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [expandedKey, setExpandedKey] = useState<string | null>(null);
  const [detail, setDetail] = useState<ExerciseStatsDetail | null>(null);
  const [detailLoading, setDetailLoading] = useState(false);
  const [detailError, setDetailError] = useState<string | null>(null);
  const [chartMetrics, setChartMetrics] = useState<Record<string, StatsChartMetric>>({});

  useEffect(() => {
    let active = true;
    const weightUnit = weightFilter === 'all' ? undefined : weightFilter;
    Promise.all([
      getExerciseStats(period, weightUnit),
      getStatsOverview(period, { period: groupPeriod, weightUnit }),
    ])
      .then(([items, nextOverview]) => {
        if (active) {
          setStats(items);
          setOverview(nextOverview);
        }
      })
      .catch((caught) => {
        if (active) {
          setError(caught instanceof Error ? caught.message : 'Error');
        }
      })
      .finally(() => {
        if (active) {
          setLoading(false);
        }
      });
    return () => {
      active = false;
    };
  }, [groupPeriod, period, weightFilter]);

  useEffect(() => {
    const item = expandedKey ? stats.find((entry) => statsKey(entry) === expandedKey) : null;
    if (!item) {
      return;
    }

    let active = true;
    getExerciseStatsDetail(item.exercise_id, {
      periodFilter: period,
      period: groupPeriod,
      weightUnit: isStatsWeightUnit(item.weight_unit) ? item.weight_unit : undefined,
    })
      .then((nextDetail) => {
        if (!active) {
          return;
        }
        const points = item.weight_unit === null
          ? nextDetail.points.filter((point) => point.weight_unit === null)
          : nextDetail.points;
        setDetail({ ...nextDetail, points });
      })
      .catch((caught) => {
        if (active) {
          setDetailError(caught instanceof Error ? caught.message : 'Error');
        }
      })
      .finally(() => {
        if (active) {
          setDetailLoading(false);
        }
      });

    return () => {
      active = false;
    };
  }, [expandedKey, groupPeriod, period, stats]);

  function selectPeriod(nextPeriod: StatsPeriodFilter) {
    if (nextPeriod === period) {
      return;
    }
    resetSummaryState();
    setPeriod(nextPeriod);
  }

  function selectWeightFilter(nextWeightFilter: WeightFilter) {
    if (nextWeightFilter === weightFilter) {
      return;
    }
    resetSummaryState();
    setWeightFilter(nextWeightFilter);
  }

  function selectGroupPeriod(nextGroupPeriod: StatsGroupingPeriod) {
    if (nextGroupPeriod === groupPeriod) {
      return;
    }
    if (expandedKey) {
      setDetail(null);
      setDetailLoading(true);
      setDetailError(null);
    }
    setGroupPeriod(nextGroupPeriod);
  }

  function resetSummaryState() {
    setLoading(true);
    setError(null);
    setExpandedKey(null);
    setDetail(null);
    setOverview(null);
    setDetailLoading(false);
    setDetailError(null);
  }

  function toggleItem(item: ExerciseStats) {
    const key = statsKey(item);
    if (expandedKey === key) {
      setExpandedKey(null);
      setDetail(null);
      setDetailLoading(false);
      setDetailError(null);
      return;
    }
    setDetail(null);
    setDetailLoading(true);
    setDetailError(null);
    setExpandedKey(key);
  }

  function selectChartMetric(key: string, metric: StatsChartMetric) {
    setChartMetrics((current) => ({ ...current, [key]: metric }));
  }

  return (
    <ZenithScreen bottomNav={<ZenithBottomNav />}>
      <ZenithHeader title="Estadisticas" subtitle="Analisis" />
      <Text style={styles.subtitle}>Volumen, carga y 1RM estimado por ejercicio, sin mezclar kg y lb.</Text>

      <FilterGroup label="Periodo" items={PERIODS} value={period} onChange={selectPeriod} />
      <FilterGroup label="Unidad" items={WEIGHT_FILTERS} value={weightFilter} onChange={selectWeightFilter} />
      <FilterGroup label="Detalle" items={GROUP_PERIODS} value={groupPeriod} onChange={selectGroupPeriod} />

      {loading && <ZenithNotice>Cargando estadisticas...</ZenithNotice>}
      {error && <ZenithNotice tone="danger">{error}</ZenithNotice>}
      {!loading && !error && overview && <OverviewSection overview={overview} />}
      {!loading && !error && stats.length === 0 && (
        <ZenithNotice>No hay datos para este periodo. Registra sesiones con ejercicios para ver estadisticas.</ZenithNotice>
      )}

      {!loading && !error && stats.map((item) => {
        const key = statsKey(item);
        const expanded = expandedKey === key;
        return (
          <View key={key} style={[styles.card, expanded && styles.cardExpanded]}>
            <View style={styles.cardHeader}>
              <View style={styles.cardTitleBlock}>
                <Text style={styles.name}>{item.exercise_name}</Text>
                <Text style={styles.meta}>{formatStatsUnit(item.weight_unit)} · {formatStatsDateRange(item)}</Text>
              </View>
              <Pressable onPress={() => toggleItem(item)} style={styles.expandButton}>
                <Text style={styles.expand}>{expanded ? 'Cerrar' : 'Detalle'}</Text>
              </Pressable>
            </View>

            <View style={styles.metricGrid}>
              <Metric label="Series" value={String(item.total_sets)} />
              <Metric label="Reps" value={String(item.total_reps)} />
              <Metric label="Volumen" value={formatStatsValue(item.total_volume)} />
              <Metric label="Peso max" value={formatStatsValue(item.max_weight, item.weight_unit)} />
              <Metric label="Promedio" value={formatStatsValue(item.avg_weight, item.weight_unit)} />
              <Metric label="1RM est." value={formatStatsValue(item.best_estimated_1rm, item.weight_unit)} />
            </View>

            {expanded && (
              <View style={styles.detail}>
                {detailLoading && <Text style={styles.detailText}>Cargando detalle...</Text>}
                {detailError && <Text style={styles.error}>{detailError}</Text>}
                {!detailLoading && !detailError && detail && detail.points.length === 0 && (
                  <Text style={styles.detailText}>No hay puntos para este filtro.</Text>
                )}
                {!detailLoading && !detailError && detail && detail.points.length > 0 && (
                  <StatsDetail
                    metric={chartMetrics[key] ?? 'estimated_1rm'}
                    onMetricChange={(metric) => selectChartMetric(key, metric)}
                    points={detail.points}
                    unit={item.weight_unit}
                  />
                )}
              </View>
            )}
          </View>
        );
      })}
    </ZenithScreen>
  );
}

function OverviewSection({ overview }: { overview: StatsOverview }) {
  return (
    <View style={styles.overviewSection}>
      <View style={styles.kpiGrid}>
        <KpiCard icon={<TrendingUp color={zenith.colors.primary} size={14} />} label="Volumen" value={formatOverviewVolume(overview)} detail="total" />
        <KpiCard icon={<Layers color={zenith.colors.cyan} size={14} />} label="Series" value={String(overview.kpis.total_sets)} detail="sets" />
        <KpiCard icon={<Clock color={zenith.colors.violet} size={14} />} label="Entreno" value={formatStatsValue(overview.kpis.training_hours)} detail="horas" />
        <KpiCard icon={<Star color={zenith.colors.amber} size={14} />} label="PRs" value={String(overview.kpis.pr_count)} detail="detectados" />
      </View>

      <ZenithCard style={styles.overviewCard}>
        <View style={styles.overviewHeader}>
          <Text style={styles.overviewTitle}>Volumen por periodo</Text>
          <ZenithPill>{overview.period}</ZenithPill>
        </View>
        {overview.volume_points.length > 0 ? <MiniBarChart bars={overview.volume_points.map((point) => ({ label: chartLabel(point.period_start, point.weight_unit), value: Number(point.total_volume ?? 0) }))} /> : <Text style={styles.detailText}>No hay volumen con peso para este filtro.</Text>}
      </ZenithCard>

      <ZenithCard style={styles.overviewCard}>
        <View style={styles.overviewHeader}>
          <Text style={styles.overviewTitle}>Series por musculo</Text>
          <Activity color={zenith.colors.primary} size={14} />
        </View>
        {overview.muscle_groups.length > 0 ? <MuscleBars items={overview.muscle_groups.slice(0, 6)} /> : <Text style={styles.detailText}>No hay grupos musculares registrados.</Text>}
      </ZenithCard>

      <ZenithCard style={styles.overviewCard}>
        <Text style={styles.overviewTitle}>Levantamientos principales</Text>
        {overview.top_exercises.length > 0 ? overview.top_exercises.map((item) => <TopExercise key={`${item.exercise_id}-${item.weight_unit ?? 'bodyweight'}`} item={item} />) : <Text style={styles.detailText}>No hay levantamientos con carga todavia.</Text>}
      </ZenithCard>
    </View>
  );
}

function KpiCard({ detail, icon, label, value }: { detail: string; icon: React.ReactNode; label: string; value: string }) {
  return (
    <ZenithCard style={styles.kpiCard}>
      <View style={styles.kpiHeader}>{icon}<Text style={styles.kpiLabel}>{label}</Text></View>
      <Text style={styles.kpiValue}>{value}</Text>
      <Text style={styles.kpiDetail}>{detail}</Text>
    </ZenithCard>
  );
}

function MuscleBars({ items }: { items: { name: string; total_sets: number }[] }) {
  const max = Math.max(...items.map((item) => item.total_sets), 1);
  return (
    <View style={styles.muscleList}>
      {items.map((item) => (
        <View key={item.name} style={styles.muscleRow}>
          <View style={styles.muscleHeader}>
            <Text style={styles.muscleName}>{item.name}</Text>
            <Text style={styles.muscleSets}>{item.total_sets} sets</Text>
          </View>
          <View style={styles.muscleTrack}><View style={[styles.muscleFill, { width: `${Math.round((item.total_sets / max) * 100)}%` }]} /></View>
        </View>
      ))}
    </View>
  );
}

function TopExercise({ item }: { item: StatsOverview['top_exercises'][number] }) {
  const metric = item.best_estimated_1rm ?? item.max_weight ?? item.total_volume;
  return (
    <View style={styles.topExerciseRow}>
      <View style={styles.topExerciseText}>
        <Text style={styles.topExerciseName}>{item.exercise_name}</Text>
        <Text style={styles.topExerciseMeta}>{item.weight_unit ? item.weight_unit : 'sin peso'} · volumen {formatStatsValue(item.total_volume, item.weight_unit)}</Text>
      </View>
      <Text style={styles.topExerciseValue}>{formatStatsValue(metric, item.weight_unit)}</Text>
    </View>
  );
}

function FilterGroup<T extends string>({
  label,
  items,
  value,
  onChange,
}: {
  label: string;
  items: { label: string; value: T }[];
  value: T;
  onChange: (value: T) => void;
}) {
  return (
    <View style={styles.filterSection}>
      <Text style={styles.filterLabel}>{label}</Text>
      <View style={styles.filters}>
        {items.map((item) => (
          <Pressable
            key={item.value}
            onPress={() => onChange(item.value)}
            style={[styles.filterButton, value === item.value && styles.filterButtonActive]}
          >
            <Text style={[styles.filterText, value === item.value && styles.filterTextActive]}>{item.label}</Text>
          </Pressable>
        ))}
      </View>
    </View>
  );
}

function Metric({ label, value }: { label: string; value: string }) {
  return (
    <View style={styles.metric}>
      <Text style={styles.metricValue}>{value}</Text>
      <Text style={styles.metricLabel}>{label}</Text>
    </View>
  );
}

function StatsDetail({ metric, onMetricChange, points, unit }: { metric: StatsChartMetric; onMetricChange: (metric: StatsChartMetric) => void; points: ExerciseStatsPoint[]; unit: string | null }) {
  const chart = buildMetricStatsChart(points, metric);
  const progressionPoints = chart.bars.filter((bar) => bar.value > 0);
  const hasMetricData = progressionPoints.length > 0;
  const visiblePoints = points.slice(-6).reverse();
  return (
    <View style={styles.detailContent}>
      <FilterGroup label="Metrica" items={CHART_METRICS} value={metric} onChange={onMetricChange} />
      <Text style={styles.chartTitle}>Progresion · {chart.label}</Text>
      {hasMetricData ? (
        <>
          <LineProgressChart points={progressionPoints} />
          <ProgressSummary points={progressionPoints} unit={unit} />
        </>
      ) : <Text style={styles.detailText}>No hay datos de esta metrica para este ejercicio.</Text>}
      <View style={styles.pointsList}>
        {visiblePoints.map((point) => (
          <View key={`${point.period_start}-${point.weight_unit ?? 'bodyweight'}`} style={styles.pointRow}>
            <Text style={styles.pointDate}>{formatPeriodDate(point.period_start)}</Text>
            <Text style={styles.pointValue}>{formatMetricStatsPoint(point, metric, unit)}</Text>
          </View>
        ))}
      </View>
    </View>
  );
}

function LineProgressChart({ points }: { points: { label: string; value: number }[] }) {
  const width = 320;
  const height = 150;
  const paddingX = 22;
  const paddingTop = 18;
  const paddingBottom = 28;
  const values = points.map((point) => point.value);
  const min = Math.min(...values);
  const max = Math.max(...values);
  const range = max - min || 1;
  const chartWidth = width - paddingX * 2;
  const chartHeight = height - paddingTop - paddingBottom;
  const coordinates = points.map((point, index) => {
    const x = paddingX + (points.length === 1 ? chartWidth / 2 : (index / (points.length - 1)) * chartWidth);
    const y = paddingTop + chartHeight - ((point.value - min) / range) * chartHeight;
    return { ...point, x, y };
  });
  const pathPoints = coordinates.map((point) => `${point.x},${point.y}`).join(' ');
  const first = coordinates[0];
  const last = coordinates[coordinates.length - 1];

  return (
    <View style={styles.lineChartBox}>
      <Svg height={height} viewBox={`0 0 ${width} ${height}`} width="100%">
        <Line stroke="rgba(255,255,255,0.08)" strokeWidth="1" x1={paddingX} x2={width - paddingX} y1={paddingTop} y2={paddingTop} />
        <Line stroke="rgba(255,255,255,0.08)" strokeWidth="1" x1={paddingX} x2={width - paddingX} y1={paddingTop + chartHeight / 2} y2={paddingTop + chartHeight / 2} />
        <Line stroke="rgba(255,255,255,0.08)" strokeWidth="1" x1={paddingX} x2={width - paddingX} y1={paddingTop + chartHeight} y2={paddingTop + chartHeight} />
        {coordinates.length > 1 && <Polyline fill="none" points={pathPoints} stroke={zenith.colors.primary} strokeLinecap="round" strokeLinejoin="round" strokeWidth="4" />}
        {coordinates.map((point, index) => (
          <Circle key={`${point.label}-${index}`} cx={point.x} cy={point.y} fill={index === coordinates.length - 1 ? zenith.colors.primary : zenith.colors.card} r="5" stroke={zenith.colors.primary} strokeWidth="3" />
        ))}
        {first && <SvgText fill={zenith.colors.muted} fontSize="10" textAnchor="start" x={paddingX} y={height - 8}>{first.label}</SvgText>}
        {last && <SvgText fill={zenith.colors.muted} fontSize="10" textAnchor="end" x={width - paddingX} y={height - 8}>{last.label}</SvgText>}
      </Svg>
      {points.length === 1 && <Text style={styles.progressHint}>Necesitas mas sesiones para ver progresion.</Text>}
    </View>
  );
}

function ProgressSummary({ points, unit }: { points: { label: string; value: number }[]; unit: string | null }) {
  const first = points[0];
  const last = points[points.length - 1];
  const change = last.value - first.value;
  const percent = first.value > 0 ? (change / first.value) * 100 : null;
  const sign = change > 0 ? '+' : '';
  return (
    <View style={styles.progressSummary}>
      <Metric label="Inicial" value={formatProgressValue(first.value, unit)} />
      <Metric label="Actual" value={formatProgressValue(last.value, unit)} />
      <Metric label="Cambio" value={`${sign}${formatProgressValue(change, unit)}`} />
      <Metric label="%" value={percent === null ? 'N/D' : `${sign}${percent.toFixed(1)}%`} />
    </View>
  );
}

function formatProgressValue(value: number, unit: string | null) {
  return formatStatsValue(String(Number(value.toFixed(2))), unit);
}

function MiniBarChart({ bars }: { bars: { label: string; value: number }[] }) {
  const max = Math.max(...bars.map((bar) => bar.value), 0);
  const visibleBars = bars.slice(-12);
  return (
    <View style={styles.chart}>
      {visibleBars.map((bar, index) => {
        const height = max > 0 ? Math.max(8, Math.round((bar.value / max) * 92)) : 8;
        return (
          <View key={`${bar.label}-${index}`} style={styles.barSlot}>
            <View style={[styles.bar, { height }]} />
            <Text style={styles.barLabel}>{bar.label}</Text>
          </View>
        );
      })}
    </View>
  );
}

function formatOverviewVolume(overview: StatsOverview) {
  if (overview.volume_by_unit.length === 0) {
    return '0';
  }
  return overview.volume_by_unit.map((item) => formatStatsValue(item.total_volume, item.weight_unit)).join(' / ');
}

function chartLabel(periodStart: string, weightUnit: string | null) {
  const unit = weightUnit ? ` ${weightUnit}` : '';
  return `${formatPeriodDate(periodStart)}${unit}`;
}

const styles = StyleSheet.create({
  subtitle: { color: zenith.colors.muted, fontFamily: zenith.font.body, fontSize: 14, lineHeight: 21 },
  overviewSection: { gap: 12 },
  kpiGrid: { flexDirection: 'row', flexWrap: 'wrap', gap: 10 },
  kpiCard: { flexGrow: 1, gap: 5, minWidth: '47%', padding: 13 },
  kpiHeader: { alignItems: 'center', flexDirection: 'row', justifyContent: 'space-between' },
  kpiLabel: { color: zenith.colors.muted, fontFamily: zenith.font.mono, fontSize: 9, textTransform: 'uppercase' },
  kpiValue: { color: zenith.colors.foreground, fontFamily: zenith.font.display, fontSize: 30, lineHeight: 32, textTransform: 'uppercase' },
  kpiDetail: { color: zenith.colors.muted, fontFamily: zenith.font.body, fontSize: 11 },
  overviewCard: { gap: 12 },
  overviewHeader: { alignItems: 'center', flexDirection: 'row', justifyContent: 'space-between' },
  overviewTitle: { color: zenith.colors.foreground, fontFamily: zenith.font.display, fontSize: 22, lineHeight: 24, textTransform: 'uppercase' },
  muscleList: { gap: 12 },
  muscleRow: { gap: 6 },
  muscleHeader: { alignItems: 'center', flexDirection: 'row', justifyContent: 'space-between' },
  muscleName: { color: zenith.colors.foreground, fontFamily: zenith.font.bodyBold },
  muscleSets: { color: zenith.colors.primary, fontFamily: zenith.font.mono, fontSize: 11 },
  muscleTrack: { backgroundColor: zenith.colors.secondary, borderRadius: 999, height: 7, overflow: 'hidden' },
  muscleFill: { backgroundColor: zenith.colors.primary, borderRadius: 999, height: '100%' },
  topExerciseRow: { alignItems: 'center', borderTopColor: zenith.colors.border, borderTopWidth: 1, flexDirection: 'row', gap: 12, paddingTop: 10 },
  topExerciseText: { flex: 1, gap: 3 },
  topExerciseName: { color: zenith.colors.foreground, fontFamily: zenith.font.bodyBold },
  topExerciseMeta: { color: zenith.colors.muted, fontFamily: zenith.font.body, fontSize: 11 },
  topExerciseValue: { color: zenith.colors.primary, fontFamily: zenith.font.display, fontSize: 20 },
  filterSection: { gap: 8 },
  filterLabel: { color: zenith.colors.foreground, fontFamily: zenith.font.mono, fontSize: 10, letterSpacing: 1.2, textTransform: 'uppercase' },
  filters: { flexDirection: 'row', flexWrap: 'wrap', gap: 8 },
  filterButton: { backgroundColor: zenith.colors.secondary, borderColor: zenith.colors.border, borderRadius: 999, borderWidth: 1, paddingHorizontal: 12, paddingVertical: 8 },
  filterButtonActive: { backgroundColor: zenith.colors.primary, borderColor: zenith.colors.primary },
  filterText: { color: zenith.colors.muted, fontFamily: zenith.font.bodyBold, fontSize: 12 },
  filterTextActive: { color: zenith.colors.primaryForeground },
  card: { backgroundColor: zenith.colors.card, borderColor: zenith.colors.border, borderRadius: 22, borderWidth: 1, gap: 14, padding: 16 },
  cardExpanded: { borderColor: zenith.colors.primaryBorder },
  cardHeader: { alignItems: 'flex-start', flexDirection: 'row', gap: 12, justifyContent: 'space-between' },
  cardTitleBlock: { flex: 1, gap: 4 },
  name: { color: zenith.colors.foreground, fontFamily: zenith.font.display, fontSize: 24, lineHeight: 26, textTransform: 'uppercase' },
  meta: { color: zenith.colors.muted, fontFamily: zenith.font.body, fontSize: 12 },
  expandButton: { borderColor: zenith.colors.primaryBorder, borderRadius: 999, borderWidth: 1, paddingHorizontal: 10, paddingVertical: 7 },
  expand: { color: zenith.colors.primary, fontFamily: zenith.font.bodyBold, fontSize: 12 },
  metricGrid: { flexDirection: 'row', flexWrap: 'wrap', gap: 10 },
  metric: { backgroundColor: zenith.colors.background, borderColor: zenith.colors.border, borderRadius: 14, borderWidth: 1, minWidth: '30%', padding: 10 },
  metricValue: { color: zenith.colors.foreground, fontFamily: zenith.font.display, fontSize: 20, lineHeight: 22 },
  metricLabel: { color: zenith.colors.muted, fontFamily: zenith.font.mono, fontSize: 10, marginTop: 4 },
  detail: { borderTopColor: zenith.colors.border, borderTopWidth: 1, paddingTop: 14 },
  detailContent: { gap: 12 },
  detailText: { color: zenith.colors.foreground, fontFamily: zenith.font.body },
  chartTitle: { color: zenith.colors.foreground, fontFamily: zenith.font.bodyBold },
  lineChartBox: { backgroundColor: zenith.colors.background, borderColor: zenith.colors.border, borderRadius: 16, borderWidth: 1, gap: 8, padding: 10 },
  progressHint: { color: zenith.colors.muted, fontFamily: zenith.font.body, fontSize: 12, textAlign: 'center' },
  progressSummary: { flexDirection: 'row', flexWrap: 'wrap', gap: 10 },
  chart: { alignItems: 'flex-end', backgroundColor: zenith.colors.background, borderRadius: 16, flexDirection: 'row', gap: 6, minHeight: 130, padding: 12 },
  barSlot: { alignItems: 'center', flex: 1, gap: 6, justifyContent: 'flex-end' },
  bar: { backgroundColor: zenith.colors.primary, borderRadius: 999, width: '100%' },
  barLabel: { color: zenith.colors.muted, fontFamily: zenith.font.mono, fontSize: 9 },
  pointsList: { gap: 8 },
  pointRow: { alignItems: 'center', flexDirection: 'row', gap: 12, justifyContent: 'space-between' },
  pointDate: { color: zenith.colors.muted, fontFamily: zenith.font.bodyBold },
  pointValue: { color: zenith.colors.foreground, flex: 1, fontFamily: zenith.font.body, textAlign: 'right' },
  error: { color: zenith.colors.danger, fontFamily: zenith.font.body },
});
