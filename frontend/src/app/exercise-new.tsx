import { useRouter } from 'expo-router';
import { useEffect, useState } from 'react';
import { Pressable, StyleSheet, Text, View } from 'react-native';

import { createExercise, ExercisePayload, getEquipment, getMuscleGroups, NamedReference } from '@/api/client';
import { Field } from '@/components/Field';
import { PrimaryButton } from '@/components/PrimaryButton';
import { ZenithCard, ZenithHeader, ZenithNotice } from '@/components/ZenithUI';
import { ZenithScreen } from '@/components/ZenithScreen';
import { zenith } from '@/constants/zenithTheme';

const DIFFICULTIES: { label: string; value: ExercisePayload['difficulty'] }[] = [
  { label: 'Principiante', value: 'beginner' },
  { label: 'Intermedio', value: 'intermediate' },
  { label: 'Avanzado', value: 'advanced' },
];

export default function ExerciseNewScreen() {
  const router = useRouter();
  const [name, setName] = useState('');
  const [description, setDescription] = useState('');
  const [difficulty, setDifficulty] = useState<ExercisePayload['difficulty']>('beginner');
  const [techniqueNotes, setTechniqueNotes] = useState('');
  const [muscleGroups, setMuscleGroups] = useState<NamedReference[]>([]);
  const [equipment, setEquipment] = useState<NamedReference[]>([]);
  const [selectedMuscles, setSelectedMuscles] = useState<string[]>([]);
  const [selectedEquipment, setSelectedEquipment] = useState<string[]>([]);
  const [loadingRefs, setLoadingRefs] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    Promise.all([getMuscleGroups(), getEquipment()])
      .then(([nextMuscles, nextEquipment]) => {
        if (!cancelled) {
          setMuscleGroups(nextMuscles);
          setEquipment(nextEquipment);
        }
      })
      .catch((caught) => {
        if (!cancelled) {
          setError(caught instanceof Error ? caught.message : 'No se pudieron cargar las referencias.');
        }
      })
      .finally(() => {
        if (!cancelled) {
          setLoadingRefs(false);
        }
      });
    return () => {
      cancelled = true;
    };
  }, []);

  async function submit() {
    if (name.trim().length < 2) {
      setError('El nombre debe tener al menos 2 caracteres.');
      return;
    }

    setSaving(true);
    setError(null);
    try {
      await createExercise({
        name: name.trim(),
        description: description.trim() || null,
        difficulty,
        technique_notes: techniqueNotes.trim() || null,
        muscle_group_ids: selectedMuscles,
        equipment_ids: selectedEquipment,
      });
      router.replace({ pathname: '/exercises', params: { notice: 'created' } });
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : 'No se pudo crear el ejercicio.');
    } finally {
      setSaving(false);
    }
  }

  return (
    <ZenithScreen>
      <ZenithHeader title="Nuevo ejercicio" subtitle="Catalogo propio" />
      <Text style={styles.subtitle}>Crea ejercicios privados para usarlos en tus rutinas y sesiones.</Text>
      {loadingRefs && <ZenithNotice>Cargando músculos y equipamiento...</ZenithNotice>}
      {error && <ZenithNotice tone="danger">{error}</ZenithNotice>}

      <ZenithCard style={styles.formCard}>
        <Field label="Nombre" onChangeText={setName} placeholder="Ej: Press banca con pausa" value={name} />
        <Field label="Descripción" multiline onChangeText={setDescription} placeholder="Que trabaja y cuando usarlo" value={description} />
        <Text style={styles.label}>Dificultad</Text>
        <View style={styles.chips}>
          {DIFFICULTIES.map((item) => (
            <Chip key={item.value} label={item.label} selected={difficulty === item.value} onPress={() => setDifficulty(item.value)} />
          ))}
        </View>
        <ReferencePicker label="Músculos" items={muscleGroups} selectedIds={selectedMuscles} onChange={setSelectedMuscles} />
        <ReferencePicker label="Equipamiento" items={equipment} selectedIds={selectedEquipment} onChange={setSelectedEquipment} />
        <Field label="Notas técnicas" multiline onChangeText={setTechniqueNotes} placeholder="Claves de ejecución, rango, seguridad" value={techniqueNotes} />
      </ZenithCard>

      <PrimaryButton disabled={saving || loadingRefs} onPress={submit} title={saving ? 'Guardando...' : 'Crear ejercicio'} />
    </ZenithScreen>
  );
}

function ReferencePicker({ label, items, onChange, selectedIds }: { label: string; items: NamedReference[]; selectedIds: string[]; onChange: (ids: string[]) => void }) {
  function toggle(id: string) {
    onChange(selectedIds.includes(id) ? selectedIds.filter((item) => item !== id) : [...selectedIds, id]);
  }

  return (
    <View style={styles.referenceGroup}>
      <Text style={styles.label}>{label}</Text>
      <View style={styles.chips}>
        {items.map((item) => <Chip key={item.id} label={item.name} selected={selectedIds.includes(item.id)} onPress={() => toggle(item.id)} />)}
      </View>
    </View>
  );
}

function Chip({ label, onPress, selected }: { label: string; selected: boolean; onPress: () => void }) {
  return (
    <Pressable accessibilityRole="button" onPress={onPress} style={[styles.chip, selected && styles.chipSelected]}>
      <Text style={[styles.chipText, selected && styles.chipTextSelected]}>{label}</Text>
    </Pressable>
  );
}

const styles = StyleSheet.create({
  subtitle: { color: zenith.colors.muted, fontFamily: zenith.font.body, lineHeight: 21 },
  formCard: { gap: 14 },
  label: { color: zenith.colors.muted, fontFamily: zenith.font.mono, fontSize: 11, letterSpacing: 1.4, textTransform: 'uppercase' },
  referenceGroup: { gap: 8 },
  chips: { flexDirection: 'row', flexWrap: 'wrap', gap: 8 },
  chip: { backgroundColor: zenith.colors.secondary, borderColor: zenith.colors.border, borderRadius: 999, borderWidth: 1, paddingHorizontal: 11, paddingVertical: 8 },
  chipSelected: { backgroundColor: zenith.colors.primary, borderColor: zenith.colors.primary },
  chipText: { color: zenith.colors.muted, fontFamily: zenith.font.bodyBold, fontSize: 12 },
  chipTextSelected: { color: zenith.colors.primaryForeground },
});
