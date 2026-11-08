import { useLocalSearchParams, useRouter } from 'expo-router';
import { useEffect, useState } from 'react';
import { Pressable, StyleSheet, Text, View } from 'react-native';

import { deleteRoutine, Exercise, getExercises, getRoutine, updateRoutine } from '@/api/client';
import { ExerciseSelector } from '@/components/ExerciseSelector';
import { Field } from '@/components/Field';
import { PrimaryButton } from '@/components/PrimaryButton';
import { RoutineExerciseFields } from '@/components/RoutineExerciseFields';
import { ZenithCard, ZenithHeader, ZenithNotice } from '@/components/ZenithUI';
import { ZenithScreen } from '@/components/ZenithScreen';
import { zenith } from '@/constants/zenithTheme';
import {
  buildRoutineExercises,
  newRoutineExerciseRow,
  routineExerciseToRow,
  RoutineExerciseRow,
} from '@/utils/routineForm';
import { plannedRoutineExercises } from '@/utils/workoutDisplay';

function paramValue(value: string | string[] | undefined) {
  return Array.isArray(value) ? value[0] : value;
}

export default function EditRoutineScreen() {
  const router = useRouter();
  const { routineId } = useLocalSearchParams();
  const id = paramValue(routineId);
  const [name, setName] = useState('');
  const [goal, setGoal] = useState('');
  const [description, setDescription] = useState('');
  const [exercises, setExercises] = useState<Exercise[]>([]);
  const [rows, setRows] = useState<RoutineExerciseRow[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(Boolean(id));
  const [saving, setSaving] = useState(false);
  const [deleteConfirm, setDeleteConfirm] = useState(false);
  const [deleting, setDeleting] = useState(false);

  useEffect(() => {
    if (!id) {
      return;
    }
    Promise.all([getExercises(), getRoutine(id)])
      .then(([exerciseItems, routine]) => {
        setExercises(exerciseItems);
        setName(routine.name);
        setGoal(routine.goal ?? '');
        setDescription(routine.description ?? '');
        setRows(plannedRoutineExercises(routine).map(routineExerciseToRow));
      })
      .catch((caught) => setError(caught instanceof Error ? caught.message : 'Error'))
      .finally(() => setLoading(false));
  }, [id]);

  function updateRow(key: string, patch: Partial<RoutineExerciseRow>) {
    setRows((current) => current.map((row) => (row.key === key ? { ...row, ...patch } : row)));
  }

  function addRow() {
    const exerciseId = exercises[0]?.id;
    if (exerciseId) {
      setRows((current) => [...current, newRoutineExerciseRow(exerciseId)]);
    }
  }

  function removeRow(key: string) {
    setRows((current) => current.filter((row) => row.key !== key));
  }

  async function submit() {
    if (!id) {
      setError('Rutina no encontrada.');
      return;
    }
    if (!name.trim()) {
      setError('El nombre de la rutina es obligatorio.');
      return;
    }
    const result = buildRoutineExercises(rows);
    if (result.exercises === null) {
      setError(result.error);
      return;
    }
    setSaving(true);
    setError(null);
    try {
      await updateRoutine(id, {
        name: name.trim(),
        goal: goal.trim() || null,
        description: description.trim() || null,
        exercises: result.exercises,
      });
      router.replace('/routines?notice=updated');
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : 'No se pudo guardar la rutina.');
    } finally {
      setSaving(false);
    }
  }

  async function submitDelete() {
    if (!id) {
      setError('Rutina no encontrada.');
      return;
    }
    if (!deleteConfirm) {
      setDeleteConfirm(true);
      return;
    }
    setDeleting(true);
    setError(null);
    try {
      await deleteRoutine(id);
      router.replace('/routines?notice=deleted');
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : 'No se pudo eliminar la rutina.');
    } finally {
      setDeleting(false);
    }
  }

  return (
    <ZenithScreen>
      <ZenithHeader title="Editar rutina" subtitle="Plan activo" />
      {loading && <ZenithNotice>Cargando rutina...</ZenithNotice>}
      <Field label="Nombre" onChangeText={setName} placeholder="Ej: Torso fuerza, Pierna A..." value={name} />
      <Field label="Objetivo opcional" onChangeText={setGoal} value={goal} />
      <Field label="Descripción opcional" multiline onChangeText={setDescription} value={description} />
      <Text style={styles.section}>Ejercicios planificados</Text>
      {rows.map((row, index) => (
        <ZenithCard key={row.key} style={styles.card}>
          <Text style={styles.cardTitle}>Ejercicio {index + 1}</Text>
          <ExerciseSelector
            exercises={exercises}
            label="Ejercicio"
            onSelect={(exercise_id) => updateRow(row.key, { exercise_id })}
            selectedExerciseId={row.exercise_id}
          />
          <RoutineExerciseFields onChange={(patch) => updateRow(row.key, patch)} row={row} />
          {rows.length > 1 && (
            <Pressable accessibilityRole="button" onPress={() => removeRow(row.key)} style={styles.removeButton}>
              <Text style={styles.removeText}>Quitar ejercicio</Text>
            </Pressable>
          )}
        </ZenithCard>
      ))}
      <Pressable accessibilityRole="button" onPress={addRow} style={styles.secondaryButton}>
        <Text style={styles.secondaryText}>Añadir ejercicio</Text>
      </Pressable>
      {!id && <ZenithNotice tone="danger">Rutina no encontrada.</ZenithNotice>}
      {error && <ZenithNotice tone="danger">{error}</ZenithNotice>}
      <PrimaryButton disabled={saving || deleting || loading || exercises.length === 0} onPress={submit} title={saving ? 'Guardando...' : 'Guardar rutina'} />
      <View style={styles.dangerZone}>
        <Text style={styles.dangerTitle}>Eliminar rutina</Text>
        <Text style={styles.dangerText}>La rutina se ocultara, pero las sesiones historicas asociadas se conservaran.</Text>
        {deleteConfirm && <Text style={styles.dangerText}>Pulsa otra vez para confirmar.</Text>}
        <Pressable accessibilityRole="button" disabled={deleting} onPress={submitDelete} style={[styles.deleteButton, deleting && styles.disabled]}>
          <Text style={styles.deleteText}>{deleting ? 'Eliminando...' : 'Eliminar rutina'}</Text>
        </Pressable>
      </View>
    </ZenithScreen>
  );
}

const styles = StyleSheet.create({
  section: { color: zenith.colors.foreground, fontFamily: zenith.font.display, fontSize: 24, textTransform: 'uppercase' },
  card: { gap: 12 },
  cardTitle: { color: zenith.colors.foreground, fontFamily: zenith.font.display, fontSize: 23, textTransform: 'uppercase' },
  secondaryButton: { alignItems: 'center', borderColor: zenith.colors.primaryBorder, borderRadius: 16, borderWidth: 1, padding: 14 },
  secondaryText: { color: zenith.colors.primary, fontFamily: zenith.font.bodyBold },
  removeButton: { alignItems: 'center', borderColor: 'rgba(232,64,64,0.35)', borderRadius: 12, borderWidth: 1, padding: 10 },
  removeText: { color: '#fca5a5', fontFamily: zenith.font.bodyBold },
  dangerZone: { backgroundColor: zenith.colors.dangerSoft, borderColor: 'rgba(232,64,64,0.35)', borderRadius: 16, borderWidth: 1, gap: 10, padding: 14 },
  dangerTitle: { color: '#fecaca', fontFamily: zenith.font.bodyBold, fontSize: 16 },
  dangerText: { color: '#fca5a5', fontFamily: zenith.font.body },
  deleteButton: { alignItems: 'center', backgroundColor: zenith.colors.danger, borderRadius: 12, padding: 12 },
  deleteText: { color: '#fff', fontFamily: zenith.font.bodyBold },
  disabled: { opacity: 0.55 },
});
