import { useLocalSearchParams, useRouter } from 'expo-router';
import { Check, ChevronDown, ChevronUp, SkipForward } from 'lucide-react-native';
import { useEffect, useState } from 'react';
import { Platform, Pressable, StyleSheet, Text, View } from 'react-native';

import { createWorkoutSession, Exercise, getExercises, getRoutine, getWorkoutSessions, Routine, WorkoutSession } from '@/api/client';
import { enqueueSession, newClientRequestId } from '@/storage/sessionOutbox';
import { isRetryableError } from '@/sync/sessionSync';
import { Field } from '@/components/Field';
import { PrimaryButton } from '@/components/PrimaryButton';
import { SegmentedField } from '@/components/SegmentedField';
import { ZenithCard, ZenithNotice } from '@/components/ZenithUI';
import { ZenithScreen } from '@/components/ZenithScreen';
import { zenith } from '@/constants/zenithTheme';
import { clearWorkoutDraft, loadWorkoutDraft, saveWorkoutDraft } from '@/storage/workoutDraft';
import { restDeadline, secondsBetween, secondsUntil } from '@/utils/sessionTimers';
import { buildWorkoutSets, SetRow, WeightUnit } from '@/utils/sessionForm';
import { exerciseName, formatPlannedExercise, plannedRoutineExercises } from '@/utils/workoutDisplay';
import { progressionHintForExercise } from '@/utils/progression';

const UNIT_OPTIONS = [
  { label: 'kg', value: 'kg' },
  { label: 'lb', value: 'lb' },
];

type ActiveSetRow = SetRow & {
  plannedKey: string;
  completed: boolean;
};

function paramValue(value: string | string[] | undefined) {
  return Array.isArray(value) ? value[0] : value;
}

function newActiveSet(plannedKey: string, exerciseId: string, reps: string, index: number): ActiveSetRow {
  return {
    key: `${plannedKey}-${Date.now()}-${index}-${Math.random()}`,
    plannedKey,
    exercise_id: exerciseId,
    reps,
    weight_value: '',
    weight_unit: 'kg',
    rpe: '',
    rir: '',
    rest_seconds: '',
    notes: '',
    completed: false,
  };
}

function buildRowsFromRoutine(routine: Routine): ActiveSetRow[] {
  return plannedRoutineExercises(routine)
    .sort((left, right) => left.position - right.position)
    .flatMap((planned) => {
      const plannedKey = routineExerciseKey(planned);
      const setCount = Math.max(1, planned.target_sets ?? 1);
      return Array.from({ length: setCount }, (_, index) => ({
        ...newActiveSet(plannedKey, planned.exercise_id, planned.target_reps_min?.toString() ?? '10', index + 1),
        rpe: planned.target_rpe ?? '',
        rir: planned.target_rir?.toString() ?? '',
        rest_seconds: planned.rest_seconds?.toString() ?? '',
      }));
    });
}

function routineExerciseKey(planned: Routine['exercises'][number]) {
  return planned.id ?? `${planned.exercise_id}-${planned.position}`;
}

function numericInputValue(value: string, fallback: number) {
  const parsed = Number(value.replace(',', '.'));
  return Number.isFinite(parsed) ? parsed : fallback;
}

function formatAdjustedWeight(value: number) {
  return Number.isInteger(value) ? value.toString() : value.toFixed(1);
}

function formatDuration(totalSeconds: number) {
  const minutes = Math.floor(totalSeconds / 60).toString().padStart(2, '0');
  const seconds = (totalSeconds % 60).toString().padStart(2, '0');
  return `${minutes}:${seconds}`;
}

export default function ActiveSessionScreen() {
  const router = useRouter();
  const { routineId } = useLocalSearchParams();
  const id = paramValue(routineId);
  const [routine, setRoutine] = useState<Routine | null>(null);
  const [exercises, setExercises] = useState<Exercise[]>([]);
  const [previousSessions, setPreviousSessions] = useState<WorkoutSession[]>([]);
  const [startedAt, setStartedAt] = useState(new Date().toISOString());
  const [timezone, setTimezone] = useState(Intl.DateTimeFormat().resolvedOptions().timeZone || 'UTC');
  const [rows, setRows] = useState<ActiveSetRow[]>([]);
  const [now, setNow] = useState(() => Date.now());
  const [restEndsAt, setRestEndsAt] = useState<number | null>(null);
  const [draftReady, setDraftReady] = useState(false);
  const [restored, setRestored] = useState(false);
  const [clientRequestId, setClientRequestId] = useState(() => newClientRequestId());
  const elapsedSeconds = secondsBetween(new Date(startedAt).getTime(), now);
  const restRemaining = secondsUntil(restEndsAt, now);
  const [loading, setLoading] = useState(Boolean(id));
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [cancelConfirm, setCancelConfirm] = useState(false);

  useEffect(() => {
    const timer = setInterval(() => setNow(Date.now()), 1000);
    return () => clearInterval(timer);
  }, []);

  useEffect(() => {
    if (!draftReady || !id || rows.length === 0) {
      return;
    }
    const timer = setTimeout(() => {
      saveWorkoutDraft({ version: 1, routineId: id, startedAt, timezone, restEndsAt, rows, savedAt: Date.now(), clientRequestId }).catch(() => undefined);
    }, 400);
    return () => clearTimeout(timer);
  }, [draftReady, id, rows, startedAt, timezone, restEndsAt, clientRequestId]);

  useEffect(() => {
    const hasCompletedRows = rows.some((row) => row.completed);

    if (
      Platform.OS !== 'web' ||
      !hasCompletedRows ||
      typeof window === 'undefined' ||
      typeof window.addEventListener !== 'function' ||
      typeof window.removeEventListener !== 'function'
    ) {
      return;
    }

    const handler = (event: BeforeUnloadEvent) => {
      event.preventDefault();
      event.returnValue = '';
    };

    window.addEventListener('beforeunload', handler);
    return () => window.removeEventListener('beforeunload', handler);
  }, [rows]);

  useEffect(() => {
    if (!id) {
      return;
    }
    Promise.all([getRoutine(id), getExercises(), getWorkoutSessions(), loadWorkoutDraft<ActiveSetRow>(id)])
      .then(([routineItem, exerciseItems, sessionItems, draft]) => {
        setRoutine(routineItem);
        setExercises(exerciseItems);
        setPreviousSessions(sessionItems);
        if (draft) {
          setRows(draft.rows);
          setStartedAt(draft.startedAt);
          setTimezone(draft.timezone);
          setRestEndsAt(draft.restEndsAt);
          if (draft.clientRequestId) {
            setClientRequestId(draft.clientRequestId);
          }
          setRestored(true);
        } else {
          setRows(buildRowsFromRoutine(routineItem));
        }
        setDraftReady(true);
      })
      .catch((caught) => setError(caught instanceof Error ? caught.message : 'Error'))
      .finally(() => setLoading(false));
  }, [id]);

  function updateRow(key: string, patch: Partial<ActiveSetRow>) {
    setRows((current) => current.map((row) => (row.key === key ? { ...row, ...patch } : row)));
  }

  function addSet(plannedKey: string, exerciseId: string, reps: string) {
    setRows((current) => [...current, newActiveSet(plannedKey, exerciseId, reps || '10', current.length + 1)]);
  }

  function copyPreviousSet(row: ActiveSetRow) {
    setRows((current) => {
      const rowIndex = current.findIndex((item) => item.key === row.key);
      const previous = current
        .slice(0, rowIndex)
        .reverse()
        .find((item) => item.plannedKey === row.plannedKey);
      if (!previous) {
        return current;
      }
      return current.map((item) =>
        item.key === row.key
          ? {
              ...item,
              reps: previous.reps,
              weight_value: previous.weight_value,
              weight_unit: previous.weight_unit,
              rpe: previous.rpe,
              rir: previous.rir,
            }
          : item
      );
    });
  }

  function adjustReps(row: ActiveSetRow, delta: number) {
    const nextReps = Math.max(1, Math.round(numericInputValue(row.reps, 1) + delta));
    updateRow(row.key, { reps: nextReps.toString() });
  }

  function adjustWeight(row: ActiveSetRow, delta: number) {
    const nextWeight = Math.max(0, numericInputValue(row.weight_value, 0) + delta);
    updateRow(row.key, { weight_value: formatAdjustedWeight(nextWeight) });
  }

  function toggleCompleted(row: ActiveSetRow, plannedRestSeconds: number | null | undefined) {
    const nextCompleted = !row.completed;
    updateRow(row.key, { completed: nextCompleted });
    if (!nextCompleted) {
      return;
    }
    const rowRest = Number(row.rest_seconds || plannedRestSeconds || 0);
    if (!Number.isNaN(rowRest) && rowRest > 0) {
      setRestEndsAt(restDeadline(rowRest));
    }
  }

  function cancelSession() {
    if (completedCount > 0 && !cancelConfirm) {
      setCancelConfirm(true);
      return;
    }
    clearWorkoutDraft().finally(() => router.replace('/sessions'));
  }

  async function finishSession() {
    if (!routine || !id) {
      setError('Rutina no encontrada.');
      return;
    }
    const completedRows = rows.filter((row) => row.completed);
    if (completedRows.length === 0) {
      setError('Marca al menos una serie como completada antes de finalizar.');
      return;
    }

    const result = buildWorkoutSets(completedRows);
    if (result.sets === null) {
      setError(result.error);
      return;
    }

    setSaving(true);
    setError(null);
    const payload = {
      client_request_id: clientRequestId,
      routine_id: id,
      started_at: startedAt,
      finished_at: new Date().toISOString(),
      timezone,
      notes: `Sesión guiada desde rutina: ${routine.name}`,
      sets: result.sets,
    };
    try {
      await createWorkoutSession(payload);
      await clearWorkoutDraft();
      router.replace('/sessions?notice=created');
    } catch (caught) {
      if (isRetryableError(caught)) {
        // Sin conexion (habitual en el gimnasio): se guarda en el movil y se envia sola despues.
        await enqueueSession(payload, `${routine.name} · ${new Date(startedAt).toLocaleDateString()}`);
        await clearWorkoutDraft();
        router.replace('/sessions?notice=queued');
        return;
      }
      setError(caught instanceof Error ? caught.message : 'No se pudo finalizar la sesión.');
    } finally {
      setSaving(false);
    }
  }

  const completedCount = rows.filter((row) => row.completed).length;
  const plannedExercises = plannedRoutineExercises(routine);
  const completedExerciseCount = plannedExercises
    .filter((planned) => {
        const plannedKey = routineExerciseKey(planned);
        const exerciseRows = rows.filter((row) => row.plannedKey === plannedKey);
        return exerciseRows.length > 0 && exerciseRows.every((row) => row.completed);
      }).length;
  const activeRow = rows.find((row) => !row.completed) ?? null;
  const activePlanned = activeRow ? plannedExercises.find((planned) => routineExerciseKey(planned) === activeRow.plannedKey) ?? null : null;
  const activeExerciseRows = activeRow ? rows.filter((row) => row.plannedKey === activeRow.plannedKey) : [];
  const activeSetNumber = activeRow ? activeExerciseRows.findIndex((row) => row.key === activeRow.key) + 1 : 0;
  const weightStep = activeRow?.weight_unit === 'lb' ? 5 : 2.5;

  return (
    <ZenithScreen>
      {loading && <ZenithNotice>Cargando rutina...</ZenithNotice>}
      {!id && <ZenithNotice tone="danger">Rutina no encontrada.</ZenithNotice>}
      {routine && (
        <ZenithCard style={styles.headerCard}>
          <View style={styles.liveRow}>
            <View style={styles.liveDot} />
            <Text style={styles.liveText}>En sesión</Text>
          </View>
          <View style={styles.headerMain}>
            <View style={styles.headerTitleBlock}>
              <Text style={styles.routineName}>{routine.name}</Text>
              {routine.goal && <Text style={styles.meta}>{routine.goal}</Text>}
            </View>
            <View style={styles.timerBlock}>
              <Text style={styles.timer}>{formatDuration(elapsedSeconds)}</Text>
              <Text style={styles.timerLabel}>duración</Text>
            </View>
          </View>
          {routine.goal && <Text style={styles.meta}>{routine.goal}</Text>}
          <Text style={styles.meta}>Inicio: {new Date(startedAt).toLocaleTimeString()}</Text>
          <Text style={styles.meta}>Ejercicios: {completedExerciseCount}/{plannedExercises.length} | Series: {completedCount}/{rows.length}</Text>
          <View style={styles.progressTrack}><View style={[styles.progressFill, { width: `${rows.length > 0 ? (completedCount / rows.length) * 100 : 0}%` }]} /></View>
          {restRemaining > 0 && (
            <View style={styles.restBox}>
              <Text style={styles.restTimer}>{formatDuration(restRemaining)}</Text>
              <Text style={styles.restLabel}>Descanso activo</Text>
              <Pressable accessibilityRole="button" accessibilityLabel="Saltar descanso" onPress={() => setRestEndsAt(null)} style={styles.skipRest}><SkipForward color={zenith.colors.muted} size={12} /><Text style={styles.skipRestText}>Saltar</Text></Pressable>
            </View>
          )}
        </ZenithCard>
      )}
      {restored && <ZenithNotice>Hemos recuperado tu sesión en curso. Puedes seguir donde lo dejaste.</ZenithNotice>}
      {error && <ZenithNotice tone="danger">{error}</ZenithNotice>}

      {routine && activeRow && activePlanned && (
        <ZenithCard style={styles.activeSetCard}>
          <View style={styles.activeSetHeader}>
            <View style={styles.activeTitleBlock}>
              <Text style={styles.activeEyebrow}>Serie {activeSetNumber} de {activeExerciseRows.length}</Text>
              <Text style={styles.activeExercise}>{exerciseName(activePlanned.exercise_id, exercises)}</Text>
            </View>
            <Text style={styles.activeUnit}>{activeRow.weight_unit}</Text>
          </View>
          <View style={styles.quickControls}>
            <View style={styles.quickColumn}>
              <Text style={styles.quickLabel}>Peso</Text>
              <Pressable accessibilityLabel={`Subir peso ${weightStep} ${activeRow.weight_unit}`} accessibilityRole="button" onPress={() => adjustWeight(activeRow, weightStep)} style={styles.quickRoundButton}>
                <ChevronUp color={zenith.colors.foreground} size={22} />
              </Pressable>
              <Text accessibilityLabel={`Peso: ${activeRow.weight_value || '0'} ${activeRow.weight_unit}`} accessibilityLiveRegion="polite" style={styles.quickValue}>{activeRow.weight_value || '0'}</Text>
              <Pressable accessibilityLabel={`Bajar peso ${weightStep} ${activeRow.weight_unit}`} accessibilityRole="button" onPress={() => adjustWeight(activeRow, -weightStep)} style={styles.quickRoundButton}>
                <ChevronDown color={zenith.colors.foreground} size={22} />
              </Pressable>
              <Text style={styles.quickUnit}>{activeRow.weight_unit}</Text>
            </View>
            <View style={styles.quickDivider} />
            <View style={styles.quickColumn}>
              <Text style={styles.quickLabel}>Reps</Text>
              <Pressable accessibilityLabel="Subir una repetición" accessibilityRole="button" onPress={() => adjustReps(activeRow, 1)} style={styles.quickRoundButton}>
                <ChevronUp color={zenith.colors.foreground} size={22} />
              </Pressable>
              <Text accessibilityLabel={`Repeticiones: ${activeRow.reps || '0'}`} accessibilityLiveRegion="polite" style={styles.quickValue}>{activeRow.reps || '0'}</Text>
              <Pressable accessibilityLabel="Bajar una repetición" accessibilityRole="button" onPress={() => adjustReps(activeRow, -1)} style={styles.quickRoundButton}>
                <ChevronDown color={zenith.colors.foreground} size={22} />
              </Pressable>
              <Text style={styles.quickUnit}>reps</Text>
            </View>
          </View>
          <View style={styles.activeActions}>
            <Pressable accessibilityRole="button" onPress={() => copyPreviousSet(activeRow)} style={styles.activeSecondaryButton}>
              <Text style={styles.activeSecondaryText}>Copiar anterior</Text>
            </Pressable>
            <Pressable accessibilityRole="button" onPress={() => toggleCompleted(activeRow, activePlanned.rest_seconds)} style={styles.activePrimaryButton}>
              <Check color={zenith.colors.primaryForeground} size={16} />
              <Text style={styles.activePrimaryText}>Registrar serie</Text>
            </Pressable>
          </View>
        </ZenithCard>
      )}

      {routine && rows.length > 0 && completedCount === rows.length && (
        <ZenithNotice tone="success">Todas las series estan completadas. Finaliza la sesión para guardar el entrenamiento.</ZenithNotice>
      )}

      {routine && plannedExercises
        .sort((left, right) => left.position - right.position)
        .map((planned) => {
          const plannedKey = routineExerciseKey(planned);
          const exerciseRows = rows.filter((row) => row.plannedKey === plannedKey);
          const exerciseCompleted = exerciseRows.length > 0 && exerciseRows.every((row) => row.completed);
          const hint = progressionHintForExercise(planned, previousSessions);
          return (
            <ZenithCard key={plannedKey} style={exerciseCompleted ? [styles.exerciseCard, styles.exerciseCompletedCard] : styles.exerciseCard}>
              <Text style={styles.exerciseTitle}>{planned.position}. {exerciseName(planned.exercise_id, exercises)}</Text>
              {exerciseCompleted && <Text style={styles.completedLabel}>Ejercicio completo</Text>}
              <Text style={styles.meta}>{formatPlannedExercise(planned)}</Text>
              <View style={styles.hintCard}>
                <Text style={styles.hintTitle}>Siguiente paso</Text>
                <Text style={styles.hintText}>{hint.lastSummary}</Text>
                <Text style={styles.hintText}>{hint.recommendation}</Text>
              </View>
              {planned.notes && <Text style={styles.notes}>{planned.notes}</Text>}
              {exerciseRows.map((row, index) => (
                <View key={row.key} style={[styles.setCard, row.completed && styles.completedCard]}>
                  <Text style={styles.setTitle}>Serie {index + 1}</Text>
                  <View style={styles.grid}>
                    <Field keyboardType="numeric" label="Reps" onChangeText={(reps) => updateRow(row.key, { reps })} value={row.reps} />
                    <Field keyboardType="decimal-pad" label="Peso" onChangeText={(weight_value) => updateRow(row.key, { weight_value })} value={row.weight_value} />
                    <SegmentedField
                      label="Unidad"
                      onValueChange={(weight_unit) => updateRow(row.key, { weight_unit: weight_unit as WeightUnit })}
                      options={UNIT_OPTIONS}
                      selectedValue={row.weight_unit}
                    />
                    <Field keyboardType="decimal-pad" label="RPE" onChangeText={(rpe) => updateRow(row.key, { rpe })} value={row.rpe} />
                    <Field keyboardType="numeric" label="RIR" onChangeText={(rir) => updateRow(row.key, { rir })} value={row.rir} />
                  </View>
                  <View style={styles.setActions}>
                    <Pressable accessibilityRole="button" onPress={() => copyPreviousSet(row)} style={styles.copyButton}>
                      <Text style={styles.copyText}>Copiar anterior</Text>
                    </Pressable>
                  </View>
                  <Pressable accessibilityRole="button" onPress={() => toggleCompleted(row, planned.rest_seconds)} style={[styles.completeButton, row.completed && styles.completedButton]}>
                    {row.completed && <Check color={zenith.colors.primaryForeground} size={13} />}
                    <Text style={[styles.completeText, row.completed && styles.completedText]}>{row.completed ? 'Completada' : 'Marcar completada'}</Text>
                  </Pressable>
                </View>
              ))}
              <Pressable accessibilityRole="button" onPress={() => addSet(plannedKey, planned.exercise_id, planned.target_reps_min?.toString() ?? '10')} style={styles.addSetButton}>
                <Text style={styles.addSetText}>Añadir serie extra</Text>
              </Pressable>
            </ZenithCard>
          );
        })}

      <PrimaryButton disabled={saving || loading || completedCount === 0} onPress={finishSession} title={saving ? 'Guardando...' : 'Finalizar sesión'} />
      <Pressable accessibilityRole="button" onPress={cancelSession} style={styles.cancelButton}>
        <Text style={styles.cancelText}>{cancelConfirm ? 'Pulsar otra vez para salir sin guardar' : 'Salir sin guardar'}</Text>
      </Pressable>
    </ZenithScreen>
  );
}

const styles = StyleSheet.create({
  headerCard: { borderColor: zenith.colors.primaryBorder, gap: 10 },
  liveRow: { alignItems: 'center', flexDirection: 'row', gap: 7 },
  liveDot: { backgroundColor: zenith.colors.primary, borderRadius: 999, height: 7, width: 7 },
  liveText: { color: zenith.colors.primary, fontFamily: zenith.font.mono, fontSize: 11, textTransform: 'uppercase' },
  headerMain: { alignItems: 'flex-start', flexDirection: 'row', gap: 12, justifyContent: 'space-between' },
  headerTitleBlock: { flex: 1 },
  routineName: { color: zenith.colors.foreground, fontFamily: zenith.font.display, fontSize: 30, lineHeight: 32, textTransform: 'uppercase' },
  timerBlock: { alignItems: 'flex-end' },
  timer: { color: zenith.colors.primary, fontFamily: zenith.font.display, fontSize: 32, lineHeight: 34 },
  timerLabel: { color: zenith.colors.muted, fontFamily: zenith.font.mono, fontSize: 11 },
  progressTrack: { backgroundColor: zenith.colors.secondary, borderRadius: 999, height: 6, overflow: 'hidden' },
  progressFill: { backgroundColor: zenith.colors.primary, borderRadius: 999, height: '100%' },
  restBox: { alignItems: 'center', backgroundColor: zenith.colors.primarySoft, borderColor: zenith.colors.primaryBorder, borderRadius: 18, borderWidth: 1, gap: 4, padding: 14 },
  restTimer: { color: zenith.colors.primary, fontFamily: zenith.font.display, fontSize: 46, lineHeight: 48 },
  restLabel: { color: zenith.colors.muted, fontFamily: zenith.font.mono, fontSize: 11, textTransform: 'uppercase' },
  skipRest: { alignItems: 'center', flexDirection: 'row', gap: 5, justifyContent: 'center', marginTop: 4, minHeight: 44, paddingHorizontal: 16 },
  skipRestText: { color: zenith.colors.muted, fontFamily: zenith.font.bodyMedium, fontSize: 12 },
  activeSetCard: { alignItems: 'center', borderColor: zenith.colors.primaryBorder, gap: 18, paddingVertical: 20 },
  activeSetHeader: { alignItems: 'flex-start', flexDirection: 'row', justifyContent: 'space-between', width: '100%' },
  activeEyebrow: { color: zenith.colors.primary, fontFamily: zenith.font.mono, fontSize: 11, letterSpacing: 1.4, textTransform: 'uppercase' },
  activeExercise: { color: zenith.colors.foreground, fontFamily: zenith.font.display, fontSize: 34, lineHeight: 36, textTransform: 'uppercase' },
  activeTitleBlock: { flex: 1, paddingRight: 8 },
  activeUnit: { alignSelf: 'flex-start', flexShrink: 0, backgroundColor: zenith.colors.primarySoft, borderRadius: 999, color: zenith.colors.primary, fontFamily: zenith.font.mono, fontSize: 11, overflow: 'hidden', paddingHorizontal: 10, paddingVertical: 5 },
  quickControls: { alignItems: 'center', flexDirection: 'row', gap: 22, justifyContent: 'center', width: '100%' },
  quickColumn: { alignItems: 'center', gap: 10, minWidth: 100 },
  quickLabel: { color: zenith.colors.muted, fontFamily: zenith.font.mono, fontSize: 11, letterSpacing: 1.4, textTransform: 'uppercase' },
  quickRoundButton: { alignItems: 'center', backgroundColor: zenith.colors.secondary, borderColor: zenith.colors.border, borderRadius: 999, borderWidth: 1, height: 52, justifyContent: 'center', width: 52 },
  quickValue: { color: zenith.colors.foreground, fontFamily: zenith.font.display, fontSize: 44, lineHeight: 46, minWidth: 92, textAlign: 'center' },
  quickUnit: { color: zenith.colors.muted, fontFamily: zenith.font.mono, fontSize: 11 },
  quickDivider: { backgroundColor: zenith.colors.border, height: 140, width: 1 },
  activeActions: { gap: 10, width: '100%' },
  activeSecondaryButton: { alignItems: 'center', borderColor: zenith.colors.border, borderRadius: 14, borderWidth: 1, padding: 12 },
  activeSecondaryText: { color: zenith.colors.muted, fontFamily: zenith.font.bodyBold },
  activePrimaryButton: { alignItems: 'center', backgroundColor: zenith.colors.primary, borderRadius: 16, flexDirection: 'row', gap: 8, justifyContent: 'center', padding: 15 },
  activePrimaryText: { color: zenith.colors.primaryForeground, fontFamily: zenith.font.bodyBold, fontSize: 16 },
  exerciseCard: { gap: 12 },
  exerciseCompletedCard: { borderColor: zenith.colors.cyan },
  exerciseTitle: { color: zenith.colors.foreground, fontFamily: zenith.font.display, fontSize: 25, lineHeight: 27, textTransform: 'uppercase' },
  completedLabel: { color: zenith.colors.cyan, fontFamily: zenith.font.bodyBold },
  hintCard: { backgroundColor: zenith.colors.primarySoft, borderColor: zenith.colors.primaryBorder, borderRadius: 12, borderWidth: 1, gap: 4, padding: 10 },
  hintTitle: { color: zenith.colors.primary, fontFamily: zenith.font.mono, fontSize: 11, textTransform: 'uppercase' },
  hintText: { color: zenith.colors.foreground, fontFamily: zenith.font.body, fontSize: 12, lineHeight: 18 },
  setCard: { backgroundColor: zenith.colors.background, borderColor: zenith.colors.border, borderRadius: 14, borderWidth: 1, gap: 10, padding: 12 },
  completedCard: { borderColor: zenith.colors.cyan },
  setTitle: { color: zenith.colors.foreground, fontFamily: zenith.font.bodyBold },
  grid: { gap: 10 },
  setActions: { flexDirection: 'row', gap: 10 },
  meta: { color: zenith.colors.muted, fontFamily: zenith.font.body },
  notes: { color: zenith.colors.foreground, fontFamily: zenith.font.body, fontStyle: 'italic' },
  copyButton: { alignItems: 'center', borderColor: zenith.colors.border, borderRadius: 12, borderWidth: 1, flex: 1, padding: 10 },
  copyText: { color: zenith.colors.muted, fontFamily: zenith.font.bodyBold },
  completeButton: { alignItems: 'center', borderColor: zenith.colors.primaryBorder, borderRadius: 12, borderWidth: 1, flexDirection: 'row', gap: 7, justifyContent: 'center', padding: 12 },
  completedButton: { backgroundColor: zenith.colors.primary, borderColor: zenith.colors.primary },
  completeText: { color: zenith.colors.primary, fontFamily: zenith.font.bodyBold },
  completedText: { color: zenith.colors.primaryForeground },
  addSetButton: { alignItems: 'center', borderColor: zenith.colors.primaryBorder, borderRadius: 12, borderWidth: 1, padding: 12 },
  addSetText: { color: zenith.colors.primary, fontFamily: zenith.font.bodyBold },
  cancelButton: { alignItems: 'center', borderColor: 'rgba(232,64,64,0.35)', borderRadius: 14, borderWidth: 1, padding: 14 },
  cancelText: { color: '#fca5a5', fontFamily: zenith.font.bodyBold },
});
