import { Link, useLocalSearchParams } from 'expo-router';
import { Dumbbell } from 'lucide-react-native';
import { useEffect, useState } from 'react';
import { StyleSheet, Text, View } from 'react-native';

import { Exercise, ExerciseStatsDetail, getExercise, getExerciseStatsDetail } from '@/api/client';
import { ZenithCard, ZenithHeader, ZenithNotice, ZenithPill } from '@/components/ZenithUI';
import { ZenithScreen } from '@/components/ZenithScreen';
import { zenith } from '@/constants/zenithTheme';
import { buildStatsChart, formatPeriodDate, formatStatsPoint } from '@/utils/statsDisplay';

function paramValue(value: string | string[] | undefined) {
  return Array.isArray(value) ? value[0] : value;
}

export default function ExerciseDetailScreen() {
  const { exerciseId } = useLocalSearchParams();
  const id = paramValue(exerciseId);
  const [exercise, setExercise] = useState<Exercise | null>(null);
  const [stats, setStats] = useState<ExerciseStatsDetail | null>(null);
  const [loading, setLoading] = useState(Boolean(id));
  const [error, setError] = useState<string | null>(null);
  const [statsError, setStatsError] = useState<string | null>(null);

  useEffect(() => {
    if (!id) {
      return;
    }
    let cancelled = false;
    getExercise(id)
      .then((nextExercise) => {
        if (!cancelled) {
          setExercise(nextExercise);
        }
      })
      .catch((caught) => {
        if (!cancelled) {
          setError(caught instanceof Error ? caught.message : 'No se pudo cargar el ejercicio.');
        }
      })
      .finally(() => {
        if (!cancelled) {
          setLoading(false);
        }
      });

    getExerciseStatsDetail(id, { periodFilter: '90d', period: 'week' })
      .then((nextStats) => {
        if (!cancelled) {
          setStats(nextStats);
        }
      })
      .catch((caught) => {
        if (!cancelled) {
          setStatsError(caught instanceof Error ? caught.message : 'No se pudo cargar el progreso.');
        }
      });
    return () => {
      cancelled = true;
    };
  }, [id]);

  return (
    <ZenithScreen>
      <ZenithHeader title="Detalle ejercicio" subtitle="Catalogo" />
      {loading && <ZenithNotice>Cargando ejercicio...</ZenithNotice>}
      {!id && <ZenithNotice tone="danger">Ejercicio no encontrado.</ZenithNotice>}
      {error && <ZenithNotice tone="danger">{error}</ZenithNotice>}

      {exercise && (
        <>
          <ZenithCard style={styles.heroCard}>
            <View style={styles.iconBox}><Dumbbell color={zenith.colors.primary} size={22} /></View>
            <View style={styles.heroText}>
              <Text style={styles.name}>{exercise.name}</Text>
              <Text style={styles.meta}>{exercise.is_global ? 'Ejercicio global' : 'Ejercicio propio'}</Text>
            </View>
            <ZenithPill active>{difficultyLabel(exercise.difficulty)}</ZenithPill>
          </ZenithCard>

          <View style={styles.metaGrid}>
            <InfoCard label="Músculos" value={referenceNames(exercise.muscle_groups)} />
            <InfoCard label="Equipo" value={referenceNames(exercise.equipment)} />
          </View>

          {exercise.description && (
            <ZenithCard style={styles.sectionCard}>
              <Text style={styles.sectionTitle}>Descripción</Text>
              <Text style={styles.body}>{exercise.description}</Text>
            </ZenithCard>
          )}

          {exercise.technique_notes && (
            <ZenithCard style={styles.sectionCard}>
              <Text style={styles.sectionTitle}>Técnica</Text>
              <Text style={styles.body}>{exercise.technique_notes}</Text>
            </ZenithCard>
          )}

          <ZenithCard style={styles.sectionCard}>
            <Text style={styles.sectionTitle}>Progreso reciente</Text>
            {statsError && <Text style={styles.muted}>{statsError}</Text>}
            {!statsError && stats && stats.points.length > 0 && <StatsPreview stats={stats} />}
            {!statsError && (!stats || stats.points.length === 0) && <Text style={styles.muted}>Aun no hay sesiones registradas para este ejercicio.</Text>}
          </ZenithCard>

          <Link href="/routine-new" style={styles.primaryLink}>Crear rutina con este ejercicio</Link>
        </>
      )}
    </ZenithScreen>
  );
}

function InfoCard({ label, value }: { label: string; value: string }) {
  return (
    <ZenithCard style={styles.infoCard}>
      <Text style={styles.infoLabel}>{label}</Text>
      <Text style={styles.infoValue}>{value || 'Sin datos'}</Text>
    </ZenithCard>
  );
}

function StatsPreview({ stats }: { stats: ExerciseStatsDetail }) {
  const chart = buildStatsChart(stats.points);
  const visibleBars = chart.bars.slice(-8);
  const max = Math.max(...visibleBars.map((bar) => bar.value), 0);
  const latestPoint = stats.points[stats.points.length - 1];
  return (
    <View style={styles.statsPreview}>
      <Text style={styles.body}>{formatPeriodDate(latestPoint.period_start)} · {formatStatsPoint(latestPoint, latestPoint.weight_unit)}</Text>
      <View style={styles.chart}>
        {visibleBars.map((bar, index) => {
          const height = max > 0 ? Math.max(8, Math.round((bar.value / max) * 72)) : 8;
          return <View key={`${bar.label}-${index}`} style={[styles.bar, { height }]} />;
        })}
      </View>
    </View>
  );
}

function referenceNames(items: { name: string }[]) {
  return items.map((item) => item.name).join(', ');
}

function difficultyLabel(value: string | null) {
  if (value === 'beginner') {
    return 'Base';
  }
  if (value === 'intermediate') {
    return 'Medio';
  }
  if (value === 'advanced') {
    return 'Avanzado';
  }
  return 'Libre';
}

const styles = StyleSheet.create({
  heroCard: { alignItems: 'center', flexDirection: 'row', gap: 12 },
  iconBox: { alignItems: 'center', backgroundColor: zenith.colors.primarySoft, borderRadius: 16, height: 52, justifyContent: 'center', width: 52 },
  heroText: { flex: 1, gap: 3 },
  name: { color: zenith.colors.foreground, fontFamily: zenith.font.display, fontSize: 30, lineHeight: 32, textTransform: 'uppercase' },
  meta: { color: zenith.colors.muted, fontFamily: zenith.font.body, fontSize: 12 },
  metaGrid: { flexDirection: 'row', gap: 10 },
  infoCard: { flex: 1, gap: 6, padding: 13 },
  infoLabel: { color: zenith.colors.muted, fontFamily: zenith.font.mono, fontSize: 11, textTransform: 'uppercase' },
  infoValue: { color: zenith.colors.foreground, fontFamily: zenith.font.bodyBold, lineHeight: 20 },
  sectionCard: { gap: 8 },
  sectionTitle: { color: zenith.colors.foreground, fontFamily: zenith.font.display, fontSize: 22, lineHeight: 24, textTransform: 'uppercase' },
  body: { color: zenith.colors.foreground, fontFamily: zenith.font.body, lineHeight: 21 },
  muted: { color: zenith.colors.muted, fontFamily: zenith.font.body, lineHeight: 21 },
  statsPreview: { gap: 10 },
  chart: { alignItems: 'flex-end', backgroundColor: zenith.colors.background, borderRadius: 14, flexDirection: 'row', gap: 7, minHeight: 96, padding: 12 },
  bar: { backgroundColor: zenith.colors.primary, borderRadius: 999, flex: 1 },
  primaryLink: { backgroundColor: zenith.colors.primary, borderRadius: 18, color: zenith.colors.primaryForeground, fontFamily: zenith.font.bodyBold, overflow: 'hidden', padding: 15, textAlign: 'center' },
});
