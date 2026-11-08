import { useLocalSearchParams, useRouter } from 'expo-router';
import { useEffect, useState } from 'react';
import { Pressable, StyleSheet, Text, View } from 'react-native';

import { Exercise, getExercises, getRoutines, getWorkoutSession, Routine, updateWorkoutSession } from '@/api/client';
import { Field } from '@/components/Field';
import { PickerField } from '@/components/PickerField';
import { PrimaryButton } from '@/components/PrimaryButton';
import { SegmentedField } from '@/components/SegmentedField';
import { ZenithCard, ZenithHeader, ZenithNotice } from '@/components/ZenithUI';
import { ZenithScreen } from '@/components/ZenithScreen';
import { zenith } from '@/constants/zenithTheme';
import { buildWorkoutSets, duplicateSetRow, newSetRow, SetRow, toIsoDateTime, WeightUnit } from '@/utils/sessionForm';

const UNIT_OPTIONS = [
  { label: 'kg', value: 'kg' },
  { label: 'lb', value: 'lb' },
];

function paramValue(value: string | string[] | undefined) {
  return Array.isArray(value) ? value[0] : value;
}

export default function EditSessionScreen() {
  const router = useRouter();
  const { sessionId } = useLocalSearchParams();
  const id = paramValue(sessionId);
  const [exercises, setExercises] = useState<Exercise[]>([]);
  const [routines, setRoutines] = useState<Routine[]>([]);
  const [routineId, setRoutineId] = useState('');
  const [startedAt, setStartedAt] = useState('');
  const [finishedAt, setFinishedAt] = useState('');
  const [timezone, setTimezone] = useState('UTC');
  const [notes, setNotes] = useState('');
  const [rows, setRows] = useState<SetRow[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(Boolean(id));
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    if (!id) {
      return;
    }
    Promise.all([getExercises(), getRoutines(), getWorkoutSession(id)])
      .then(([exerciseItems, routineItems, session]) => {
        setExercises(exerciseItems);
        setRoutines(routineItems);
        setRoutineId(session.routine_id ?? '');
        setStartedAt(session.started_at);
        setFinishedAt(session.finished_at ?? '');
        setTimezone(session.timezone);
        setNotes(session.notes ?? '');
        setRows(
          session.sets.map((set) => ({
            key: set.id ?? `${set.exercise_id}-${set.set_number}`,
            exercise_id: set.exercise_id,
            reps: set.reps.toString(),
            weight_value: set.weight_value ?? '',
            weight_unit: set.weight_unit ?? 'kg',
            rpe: set.rpe ?? '',
            rir: set.rir?.toString() ?? '',
            rest_seconds: set.rest_seconds?.toString() ?? '',
            notes: set.notes ?? '',
          }))
        );
      })
      .catch((caught) => setError(caught instanceof Error ? caught.message : 'Error'))
      .finally(() => setLoading(false));
  }, [id]);

  function updateRow(key: string, patch: Partial<SetRow>) {
    setRows((current) => current.map((row) => (row.key === key ? { ...row, ...patch } : row)));
  }

  function addRow() {
    const exerciseId = exercises[0]?.id;
    if (exerciseId) {
      setRows((current) => [...current, newSetRow(exerciseId)]);
    }
  }

  function duplicateRow(row: SetRow) {
    setRows((current) => {
      const index = current.findIndex((item) => item.key === row.key);
      if (index === -1) {
        return current;
      }
      return [...current.slice(0, index + 1), duplicateSetRow(row), ...current.slice(index + 1)];
    });
  }

  function removeRow(key: string) {
    setRows((current) => current.filter((row) => row.key !== key));
  }

  async function submit() {
    if (!id) {
      setError('Sesion no encontrada.');
      return;
    }
    const startedAtIso = toIsoDateTime(startedAt);
    if (!startedAtIso) {
      setError('La fecha de inicio no es valida. Usa el formato AAAA-MM-DD HH:MM.');
      return;
    }
    const finishedAtIso = finishedAt.trim() ? toIsoDateTime(finishedAt) : null;
    if (finishedAt.trim() && !finishedAtIso) {
      setError('La fecha de fin no es valida. Usa el formato AAAA-MM-DD HH:MM.');
      return;
    }
    if (!timezone.trim()) {
      setError('La zona horaria es obligatoria.');
      return;
    }

    const result = buildWorkoutSets(rows);
    if (result.sets === null) {
      setError(result.error);
      return;
    }
    if (result.sets.length === 0) {
      setError('Necesitas series validas para guardar la sesion.');
      return;
    }

    setSaving(true);
    setError(null);
    try {
      await updateWorkoutSession(id, {
        routine_id: routineId || null,
        started_at: startedAtIso,
        finished_at: finishedAtIso,
        timezone,
        notes: notes.trim() || null,
        sets: result.sets,
      });
      router.replace('/sessions?notice=updated');
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : 'No se pudo guardar la sesion.');
    } finally {
      setSaving(false);
    }
  }

  const exerciseOptions = exercises.map((exercise) => ({ label: exercise.name, value: exercise.id }));
  const routineOptions = [{ label: 'Sin rutina', value: '' }, ...routines.map((routine) => ({ label: routine.name, value: routine.id }))];

  return (
    <ZenithScreen>
      <ZenithHeader title="Editar sesion" subtitle="Historial" />
      {loading && <ZenithNotice>Cargando sesion...</ZenithNotice>}
      <PickerField label="Rutina opcional" onValueChange={setRoutineId} options={routineOptions} selectedValue={routineId} />
      <Field label="Inicio ISO" onChangeText={setStartedAt} value={startedAt} />
      <Field label="Fin ISO opcional" onChangeText={setFinishedAt} value={finishedAt} />
      <Field label="Zona horaria" onChangeText={setTimezone} value={timezone} />
      <Field label="Notas opcionales" multiline onChangeText={setNotes} value={notes} />
      <Text style={styles.section}>Series</Text>
      {rows.map((row, index) => (
        <ZenithCard key={row.key} style={styles.card}>
          <Text style={styles.cardTitle}>Serie {index + 1}</Text>
          <PickerField
            label="Ejercicio"
            onValueChange={(exercise_id) => updateRow(row.key, { exercise_id })}
            options={exerciseOptions}
            selectedValue={row.exercise_id}
          />
          <View style={styles.grid}>
            <Field keyboardType="numeric" label="Reps" onChangeText={(reps) => updateRow(row.key, { reps })} value={row.reps} />
            <Field keyboardType="decimal-pad" label="Peso opcional" onChangeText={(weight_value) => updateRow(row.key, { weight_value })} value={row.weight_value} />
            <SegmentedField
              label="Unidad"
              onValueChange={(weight_unit) => updateRow(row.key, { weight_unit: weight_unit as WeightUnit })}
              options={UNIT_OPTIONS}
              selectedValue={row.weight_unit}
            />
            <Field keyboardType="decimal-pad" label="RPE opcional" onChangeText={(rpe) => updateRow(row.key, { rpe })} value={row.rpe} />
            <Field keyboardType="numeric" label="RIR opcional" onChangeText={(rir) => updateRow(row.key, { rir })} value={row.rir} />
            <Field keyboardType="numeric" label="Descanso seg opcional" onChangeText={(rest_seconds) => updateRow(row.key, { rest_seconds })} value={row.rest_seconds} />
          </View>
          <Field label="Notas serie opcionales" multiline onChangeText={(setNotesValue) => updateRow(row.key, { notes: setNotesValue })} value={row.notes} />
          <View style={styles.actionsRow}>
            <Pressable onPress={() => duplicateRow(row)} style={styles.secondarySmallButton}>
              <Text style={styles.secondaryText}>Duplicar</Text>
            </Pressable>
            {rows.length > 1 && (
              <Pressable onPress={() => removeRow(row.key)} style={styles.removeSmallButton}>
                <Text style={styles.removeText}>Quitar</Text>
              </Pressable>
            )}
          </View>
        </ZenithCard>
      ))}
      <Pressable onPress={addRow} style={styles.secondaryButton}>
        <Text style={styles.secondaryText}>Anadir serie</Text>
      </Pressable>
      {!id && <ZenithNotice tone="danger">Sesion no encontrada.</ZenithNotice>}
      {error && <ZenithNotice tone="danger">{error}</ZenithNotice>}
      <PrimaryButton disabled={saving || loading || exercises.length === 0} onPress={submit} title={saving ? 'Guardando...' : 'Guardar sesion'} />
    </ZenithScreen>
  );
}

const styles = StyleSheet.create({
  section: { color: zenith.colors.foreground, fontFamily: zenith.font.display, fontSize: 24, textTransform: 'uppercase' },
  card: { gap: 12 },
  cardTitle: { color: zenith.colors.foreground, fontFamily: zenith.font.display, fontSize: 23, textTransform: 'uppercase' },
  grid: { gap: 12 },
  actionsRow: { flexDirection: 'row', gap: 10 },
  secondaryButton: { alignItems: 'center', borderColor: zenith.colors.primaryBorder, borderRadius: 16, borderWidth: 1, padding: 14 },
  secondarySmallButton: { alignItems: 'center', borderColor: zenith.colors.primaryBorder, borderRadius: 12, borderWidth: 1, flex: 1, padding: 10 },
  secondaryText: { color: zenith.colors.primary, fontFamily: zenith.font.bodyBold },
  removeSmallButton: { alignItems: 'center', borderColor: 'rgba(232,64,64,0.35)', borderRadius: 12, borderWidth: 1, flex: 1, padding: 10 },
  removeText: { color: '#fca5a5', fontFamily: zenith.font.bodyBold },
});
