import { useRouter } from 'expo-router';
import { useEffect, useState } from 'react';
import { Pressable, StyleSheet, Text } from 'react-native';

import { createRoutine, Exercise, getExercises } from '@/api/client';
import { ExerciseSelector } from '@/components/ExerciseSelector';
import { Field } from '@/components/Field';
import { PrimaryButton } from '@/components/PrimaryButton';
import { RoutineExerciseFields } from '@/components/RoutineExerciseFields';
import { ZenithCard, ZenithHeader, ZenithNotice } from '@/components/ZenithUI';
import { ZenithScreen } from '@/components/ZenithScreen';
import { zenith } from '@/constants/zenithTheme';
import { buildRoutineExercises, newRoutineExerciseRow, RoutineExerciseRow } from '@/utils/routineForm';

export default function NewRoutineScreen() {
  const router = useRouter();
  const [name, setName] = useState('');
  const [goal, setGoal] = useState('');
  const [description, setDescription] = useState('');
  const [exercises, setExercises] = useState<Exercise[]>([]);
  const [rows, setRows] = useState<RoutineExerciseRow[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    getExercises()
      .then((items) => {
        setExercises(items);
        if (items[0]) {
          setRows([newRoutineExerciseRow(items[0].id)]);
        }
      })
      .catch((caught) => setError(caught instanceof Error ? caught.message : 'Error'))
      .finally(() => setLoading(false));
  }, []);

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
      await createRoutine({
        name: name.trim(),
        goal: goal.trim() || null,
        description: description.trim() || null,
        exercises: result.exercises,
      });
      router.replace('/routines?notice=created');
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : 'No se pudo crear la rutina.');
    } finally {
      setSaving(false);
    }
  }

  return (
    <ZenithScreen>
      <ZenithHeader title="Nueva rutina" subtitle="Plan activo" />
      <Field label="Nombre" onChangeText={setName} placeholder="Ej: Torso fuerza, Pierna A..." value={name} />
      <Field label="Objetivo opcional" onChangeText={setGoal} value={goal} />
      <Field label="Descripción opcional" multiline onChangeText={setDescription} value={description} />
      <Text style={styles.section}>Ejercicios planificados</Text>
      {loading && <ZenithNotice>Cargando ejercicios...</ZenithNotice>}
      {!loading && exercises.length === 0 && <ZenithNotice>No hay ejercicios disponibles para crear la rutina.</ZenithNotice>}
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
      {error && <ZenithNotice tone="danger">{error}</ZenithNotice>}
      <PrimaryButton disabled={saving || loading || exercises.length === 0} onPress={submit} title={saving ? 'Creando...' : 'Crear rutina'} />
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
});
