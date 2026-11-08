import { Link, useLocalSearchParams, useRouter } from 'expo-router';
import { Bot, Star } from 'lucide-react-native';
import { useEffect, useState } from 'react';
import { Pressable, StyleSheet, Text, View } from 'react-native';

import {
  AiSessionSummary,
  deleteWorkoutSession,
  Exercise,
  generateSessionSummary,
  getExercises,
  getRoutines,
  getSessionSummary,
  getWorkoutSession,
  Routine,
  WorkoutSession,
} from '@/api/client';
import { ZenithButton, ZenithCard, ZenithHeader, ZenithNotice } from '@/components/ZenithUI';
import { ZenithScreen } from '@/components/ZenithScreen';
import { zenith } from '@/constants/zenithTheme';
import { exerciseName, formatVolumeByUnit, routineName } from '@/utils/workoutDisplay';

function paramValue(value: string | string[] | undefined) {
  return Array.isArray(value) ? value[0] : value;
}

function formatWeight(weightValue: string | null | undefined, weightUnit: string | null | undefined) {
  if (!weightValue || !weightUnit) {
    return 'sin peso';
  }
  return `${weightValue} ${weightUnit}`;
}

function providerSummary(summary: AiSessionSummary) {
  const model = summary.model ? ` · ${summary.model}` : '';
  const fallback = summary.fallback_used ? ' · fallback interno' : '';
  return `${summary.provider}${model}${fallback}`;
}

function SummaryList({ items, title, variant }: { items: string[]; title: string; variant?: 'warning' }) {
  if (items.length === 0) {
    return null;
  }
  return (
    <View style={styles.summaryGroup}>
      <Text style={styles.summaryGroupTitle}>{title}</Text>
      {items.map((item) => (
        <Text key={item} style={variant === 'warning' ? styles.warningItem : styles.summaryItem}>- {item}</Text>
      ))}
    </View>
  );
}

export default function SessionDetailScreen() {
  const router = useRouter();
  const { sessionId } = useLocalSearchParams();
  const id = paramValue(sessionId);
  const [session, setSession] = useState<WorkoutSession | null>(null);
  const [routines, setRoutines] = useState<Routine[]>([]);
  const [exercises, setExercises] = useState<Exercise[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(Boolean(id));
  const [deleteConfirm, setDeleteConfirm] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const [summary, setSummary] = useState<AiSessionSummary | null>(null);
  const [summaryLoading, setSummaryLoading] = useState(Boolean(id));
  const [summarySaving, setSummarySaving] = useState(false);

  useEffect(() => {
    if (!id) {
      return;
    }
    Promise.all([getWorkoutSession(id), getRoutines(), getExercises()])
      .then(([sessionItem, routineItems, exerciseItems]) => {
        setSession(sessionItem);
        setRoutines(routineItems);
        setExercises(exerciseItems);
      })
      .catch((caught) => setError(caught instanceof Error ? caught.message : 'Error'))
      .finally(() => setLoading(false));
    getSessionSummary(id)
      .then(setSummary)
      .catch((caught) => {
        if (!(caught instanceof Error) || !caught.message.includes('Session summary not found')) {
          setError(caught instanceof Error ? caught.message : 'No se pudo cargar el resumen IA.');
        }
      })
      .finally(() => setSummaryLoading(false));
  }, [id]);

  async function submitGenerateSummary() {
    if (!id) {
      setError('Sesión no encontrada.');
      return;
    }
    setSummarySaving(true);
    setError(null);
    try {
      setSummary(await generateSessionSummary(id));
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : 'No se pudo generar el resumen IA.');
    } finally {
      setSummarySaving(false);
    }
  }

  async function submitDelete() {
    if (!id) {
      setError('Sesión no encontrada.');
      return;
    }
    if (!deleteConfirm) {
      setDeleteConfirm(true);
      return;
    }
    setDeleting(true);
    setError(null);
    try {
      await deleteWorkoutSession(id);
      router.replace('/sessions?notice=deleted');
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : 'No se pudo eliminar la sesión.');
    } finally {
      setDeleting(false);
    }
  }

  return (
    <ZenithScreen>
      <ZenithHeader title="Detalle sesión" subtitle="Historial" />
      {loading && <ZenithNotice>Cargando sesión...</ZenithNotice>}
      {!id && <ZenithNotice tone="danger">Sesión no encontrada.</ZenithNotice>}
      {error && <ZenithNotice tone="danger">{error}</ZenithNotice>}
      {session && (
        <>
          <ZenithCard style={styles.card}>
            <Text style={styles.name}>{new Date(session.started_at).toLocaleString()}</Text>
            <Text style={styles.meta}>Rutina: {routineName(session.routine_id, routines)}</Text>
            <Text style={styles.meta}>Inicio: {session.started_at}</Text>
            <Text style={styles.meta}>Fin: {session.finished_at ?? 'No informado'}</Text>
            <Text style={styles.meta}>Zona horaria: {session.timezone}</Text>
            <Text style={styles.meta}>Volumen: {formatVolumeByUnit(session.sets)}</Text>
            {session.notes && <Text style={styles.notes}>{session.notes}</Text>}
            <Link href={{ pathname: '/session-edit', params: { sessionId: session.id } }} style={styles.link}>Editar sesión</Link>
            <View style={styles.summaryBox}>
              <Text style={styles.summaryTitle}>Resumen IA post-sesion</Text>
              <Text style={styles.summaryHelp}>Genera un análisis revisable. No modifica rutinas ni sesiones.</Text>
              {summaryLoading && <Text style={styles.meta}>Buscando resumen existente...</Text>}
              <ZenithButton disabled={summarySaving} icon={<Bot color={zenith.colors.primaryForeground} size={14} />} onPress={submitGenerateSummary} title={summarySaving ? 'Generando...' : summary ? 'Regenerar resumen IA' : 'Generar resumen IA'} />
              {summary && (
                <View style={styles.summaryResult}>
                  <Text style={styles.summaryText}>{summary.summary}</Text>
                  <SummaryList items={summary.improvements} title="Mejoras" />
                  <SummaryList items={summary.drops} title="Caidas" />
                  <SummaryList items={summary.warnings} title="Warnings" variant="warning" />
                  <View style={styles.summaryGroup}>
                    <Text style={styles.summaryGroupTitle}>Próxima recomendación</Text>
                    <Text style={styles.summaryItem}>{summary.next_recommendation}</Text>
                  </View>
                  <Text style={styles.providerText}>Proveedor IA: {providerSummary(summary)}</Text>
                </View>
              )}
            </View>
            <View style={styles.dangerZone}>
              <Text style={styles.dangerTitle}>Eliminar sesión</Text>
              <Text style={styles.dangerText}>La sesión se ocultara y dejara de contar para estadísticas y rango.</Text>
              {deleteConfirm && <Text style={styles.dangerText}>Pulsa otra vez para confirmar.</Text>}
              <Pressable accessibilityRole="button" disabled={deleting} onPress={submitDelete} style={[styles.deleteButton, deleting && styles.disabled]}>
                <Text style={styles.deleteText}>{deleting ? 'Eliminando...' : 'Eliminar sesión'}</Text>
              </Pressable>
            </View>
          </ZenithCard>
          <Text style={styles.section}>Series</Text>
          {session.sets.map((set) => (
            <ZenithCard key={set.id ?? `${set.exercise_id}-${set.set_number}`} style={styles.setCard}>
              <Star color={zenith.colors.primary} size={14} />
              <Text style={styles.setTitle}>Serie {set.set_number}: {exerciseName(set.exercise_id, exercises)}</Text>
              <Text style={styles.meta}>{set.reps} reps · {formatWeight(set.weight_value, set.weight_unit)}</Text>
              <Text style={styles.meta}>RPE {set.rpe ?? '-'} · RIR {set.rir ?? '-'} · Descanso {set.rest_seconds ?? '-'}s</Text>
              {set.notes && <Text style={styles.notes}>{set.notes}</Text>}
            </ZenithCard>
          ))}
        </>
      )}
    </ZenithScreen>
  );
}

const styles = StyleSheet.create({
  section: { color: zenith.colors.foreground, fontFamily: zenith.font.display, fontSize: 24, textTransform: 'uppercase' },
  card: { gap: 10 },
  setCard: { flexDirection: 'column', gap: 6 },
  name: { color: zenith.colors.foreground, fontFamily: zenith.font.display, fontSize: 26, lineHeight: 28, textTransform: 'uppercase' },
  setTitle: { color: zenith.colors.foreground, fontFamily: zenith.font.bodyBold },
  meta: { color: zenith.colors.muted, fontFamily: zenith.font.body },
  notes: { color: zenith.colors.foreground, fontFamily: zenith.font.body, fontStyle: 'italic' },
  link: { color: zenith.colors.primary, fontFamily: zenith.font.bodyBold, marginTop: 4 },
  summaryBox: { backgroundColor: zenith.colors.primarySoft, borderColor: zenith.colors.primaryBorder, borderRadius: 16, borderWidth: 1, gap: 8, marginTop: 8, padding: 12 },
  summaryTitle: { color: zenith.colors.primary, fontFamily: zenith.font.bodyBold },
  summaryHelp: { color: zenith.colors.foreground, fontFamily: zenith.font.body, lineHeight: 20 },
  summaryResult: { backgroundColor: zenith.colors.background, borderRadius: 12, gap: 8, padding: 10 },
  summaryText: { color: zenith.colors.foreground, fontFamily: zenith.font.bodyBold, lineHeight: 20 },
  summaryGroup: { gap: 4 },
  summaryGroupTitle: { color: zenith.colors.primary, fontFamily: zenith.font.mono, fontSize: 11, textTransform: 'uppercase' },
  summaryItem: { color: zenith.colors.foreground, fontFamily: zenith.font.body, lineHeight: 20 },
  warningItem: { color: '#fca5a5', lineHeight: 20 },
  providerText: { color: zenith.colors.cyan, fontFamily: zenith.font.mono, fontSize: 11 },
  dangerZone: { backgroundColor: zenith.colors.dangerSoft, borderColor: 'rgba(232,64,64,0.35)', borderRadius: 14, borderWidth: 1, gap: 8, marginTop: 8, padding: 12 },
  dangerTitle: { color: '#fecaca', fontFamily: zenith.font.bodyBold },
  dangerText: { color: '#fca5a5' },
  deleteButton: { alignItems: 'center', backgroundColor: zenith.colors.danger, borderRadius: 12, padding: 12 },
  deleteText: { color: '#fff', fontFamily: zenith.font.bodyBold },
  disabled: { opacity: 0.55 },
});
