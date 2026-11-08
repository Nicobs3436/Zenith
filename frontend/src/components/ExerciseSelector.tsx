import { useState } from 'react';
import { Pressable, StyleSheet, Text, View } from 'react-native';

import { Exercise } from '@/api/client';
import { Field } from '@/components/Field';
import { zenith } from '@/constants/zenithTheme';

type ExerciseSelectorProps = {
  label: string;
  exercises: Exercise[];
  selectedExerciseId: string;
  onSelect: (exerciseId: string) => void;
};

const ALL = '__all__';

export function ExerciseSelector({ label, exercises, selectedExerciseId, onSelect }: ExerciseSelectorProps) {
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState('');
  const [muscle, setMuscle] = useState(ALL);
  const [equipment, setEquipment] = useState(ALL);
  const [difficulty, setDifficulty] = useState(ALL);

  const selected = exercises.find((exercise) => exercise.id === selectedExerciseId);
  const muscleOptions = uniqueReferenceNames(exercises.flatMap((exercise) => exercise.muscle_groups));
  const equipmentOptions = uniqueReferenceNames(exercises.flatMap((exercise) => exercise.equipment));
  const difficultyOptions = uniqueStrings(exercises.map((exercise) => exercise.difficulty).filter(isString));
  const filteredExercises = filterExercises(exercises, { query, muscle, equipment, difficulty });
  const hasFilters = query.trim() || muscle !== ALL || equipment !== ALL || difficulty !== ALL;

  function selectExercise(exerciseId: string) {
    onSelect(exerciseId);
    setOpen(false);
  }

  function clearFilters() {
    setQuery('');
    setMuscle(ALL);
    setEquipment(ALL);
    setDifficulty(ALL);
  }

  return (
    <View style={styles.container}>
      <Text style={styles.label}>{label}</Text>
      <Pressable accessibilityRole="button" onPress={() => setOpen((current) => !current)} style={styles.selectedButton}>
        <View style={styles.selectedTextBlock}>
          <Text style={styles.selectedName}>{selected?.name ?? 'Selecciona ejercicio'}</Text>
          <Text style={styles.selectedMeta}>{selected ? exerciseMeta(selected) : 'Buscar por nombre, músculo o equipo'}</Text>
        </View>
        <Text style={styles.toggleText}>{open ? 'Cerrar' : 'Cambiar'}</Text>
      </Pressable>

      {open && (
        <View style={styles.panel}>
          <Field
            autoCapitalize="none"
            autoCorrect={false}
            label="Buscar"
            onChangeText={setQuery}
            placeholder="Press, sentadilla, espalda..."
            returnKeyType="search"
            value={query}
          />

          <FilterChips label="Músculo" options={muscleOptions} selectedValue={muscle} onChange={setMuscle} />
          <FilterChips label="Equipo" options={equipmentOptions} selectedValue={equipment} onChange={setEquipment} />
          <FilterChips
            label="Dificultad"
            options={difficultyOptions.map((value) => ({ label: difficultyLabel(value), value }))}
            selectedValue={difficulty}
            onChange={setDifficulty}
          />

          {hasFilters && (
            <Pressable accessibilityRole="button" onPress={clearFilters} style={styles.clearButton}>
              <Text style={styles.clearText}>Limpiar filtros</Text>
            </Pressable>
          )}

          <Text style={styles.resultCount}>{filteredExercises.length} resultado(s)</Text>
          <View style={styles.results}>
            {filteredExercises.map((exercise) => {
              const selectedExercise = exercise.id === selectedExerciseId;
              return (
                <Pressable accessibilityRole="button"
                  key={exercise.id}
                  onPress={() => selectExercise(exercise.id)}
                  style={[styles.resultCard, selectedExercise && styles.resultCardSelected]}
                >
                  <View style={styles.resultHeader}>
                    <Text style={styles.resultName}>{exercise.name}</Text>
                    <Text style={[styles.badge, selectedExercise && styles.badgeSelected]}>{selectedExercise ? 'Elegido' : exercise.is_global ? 'Global' : 'Propio'}</Text>
                  </View>
                  <Text style={styles.resultMeta}>{exerciseMeta(exercise)}</Text>
                  {exercise.description && <Text style={styles.description} numberOfLines={2}>{exercise.description}</Text>}
                </Pressable>
              );
            })}
            {filteredExercises.length === 0 && <Text style={styles.empty}>No hay ejercicios con esos filtros.</Text>}
          </View>
        </View>
      )}
    </View>
  );
}

function FilterChips({
  label,
  options,
  selectedValue,
  onChange,
}: {
  label: string;
  options: { label: string; value: string }[];
  selectedValue: string;
  onChange: (value: string) => void;
}) {
  return (
    <View style={styles.filterGroup}>
      <Text style={styles.filterLabel}>{label}</Text>
      <View style={styles.chips}>
        <Chip label="Todos" selected={selectedValue === ALL} onPress={() => onChange(ALL)} />
        {options.map((option) => (
          <Chip key={option.value} label={option.label} selected={selectedValue === option.value} onPress={() => onChange(option.value)} />
        ))}
      </View>
    </View>
  );
}

function Chip({ label, selected, onPress }: { label: string; selected: boolean; onPress: () => void }) {
  return (
    <Pressable accessibilityRole="button" onPress={onPress} style={[styles.chip, selected && styles.chipSelected]}>
      <Text style={[styles.chipText, selected && styles.chipTextSelected]}>{label}</Text>
    </Pressable>
  );
}

function filterExercises(
  exercises: Exercise[],
  filters: { query: string; muscle: string; equipment: string; difficulty: string },
) {
  const normalizedQuery = normalize(filters.query);
  return exercises.filter((exercise) => {
    const matchesQuery = !normalizedQuery || normalize([
      exercise.name,
      exercise.description,
      exercise.technique_notes,
      exercise.difficulty,
      ...exercise.muscle_groups.map((item) => item.name),
      ...exercise.equipment.map((item) => item.name),
    ].filter(Boolean).join(' ')).includes(normalizedQuery);
    const matchesMuscle = filters.muscle === ALL || exercise.muscle_groups.some((item) => item.name === filters.muscle);
    const matchesEquipment = filters.equipment === ALL || exercise.equipment.some((item) => item.name === filters.equipment);
    const matchesDifficulty = filters.difficulty === ALL || exercise.difficulty === filters.difficulty;
    return matchesQuery && matchesMuscle && matchesEquipment && matchesDifficulty;
  });
}

function uniqueReferenceNames(items: { name: string }[]) {
  return uniqueStrings(items.map((item) => item.name)).map((name) => ({ label: name, value: name }));
}

function uniqueStrings(items: string[]) {
  return [...new Set(items)].sort((left, right) => left.localeCompare(right, 'es'));
}

function isString(value: string | null): value is string {
  return typeof value === 'string';
}

function normalize(value: string) {
  return value.normalize('NFD').replace(/[\u0300-\u036f]/g, '').toLowerCase().trim();
}

function difficultyLabel(value: string | null) {
  if (value === 'beginner') {
    return 'Principiante';
  }
  if (value === 'intermediate') {
    return 'Intermedio';
  }
  if (value === 'advanced') {
    return 'Avanzado';
  }
  return 'Sin dificultad';
}

function exerciseMeta(exercise: Exercise) {
  const parts = [
    difficultyLabel(exercise.difficulty),
    exercise.muscle_groups.map((item) => item.name).join(', '),
    exercise.equipment.map((item) => item.name).join(', '),
  ].filter(Boolean);
  return parts.join(' · ');
}

const styles = StyleSheet.create({
  container: { gap: 8 },
  label: { color: zenith.colors.muted, fontFamily: zenith.font.mono, fontSize: 11, letterSpacing: 1.4, textTransform: 'uppercase' },
  selectedButton: { alignItems: 'center', backgroundColor: zenith.colors.secondary, borderColor: zenith.colors.border, borderRadius: 16, borderWidth: 1, flexDirection: 'row', gap: 12, padding: 14 },
  selectedTextBlock: { flex: 1, gap: 4 },
  selectedName: { color: zenith.colors.foreground, fontFamily: zenith.font.bodyBold, fontSize: 16 },
  selectedMeta: { color: zenith.colors.muted, fontFamily: zenith.font.body, fontSize: 12, lineHeight: 17 },
  toggleText: { color: zenith.colors.primary, fontFamily: zenith.font.bodyBold, fontSize: 13 },
  panel: { backgroundColor: zenith.colors.background, borderColor: zenith.colors.border, borderRadius: 16, borderWidth: 1, gap: 14, padding: 12 },
  filterGroup: { gap: 8 },
  filterLabel: { color: zenith.colors.muted, fontFamily: zenith.font.mono, fontSize: 11, textTransform: 'uppercase' },
  chips: { flexDirection: 'row', flexWrap: 'wrap', gap: 8 },
  chip: { borderColor: zenith.colors.border, borderRadius: 999, borderWidth: 1, paddingHorizontal: 10, paddingVertical: 7 },
  chipSelected: { backgroundColor: zenith.colors.primary, borderColor: zenith.colors.primary },
  chipText: { color: zenith.colors.muted, fontFamily: zenith.font.bodyBold, fontSize: 12 },
  chipTextSelected: { color: zenith.colors.primaryForeground },
  clearButton: { alignItems: 'center', borderColor: zenith.colors.border, borderRadius: 12, borderWidth: 1, padding: 10 },
  clearText: { color: zenith.colors.foreground, fontFamily: zenith.font.bodyBold },
  resultCount: { color: zenith.colors.muted, fontFamily: zenith.font.mono, fontSize: 11 },
  results: { gap: 10 },
  resultCard: { backgroundColor: zenith.colors.card, borderColor: zenith.colors.border, borderRadius: 14, borderWidth: 1, gap: 6, padding: 12 },
  resultCardSelected: { borderColor: zenith.colors.primary },
  resultHeader: { alignItems: 'center', flexDirection: 'row', gap: 8, justifyContent: 'space-between' },
  resultName: { color: zenith.colors.foreground, flex: 1, fontFamily: zenith.font.bodyBold, fontSize: 15 },
  badge: { backgroundColor: zenith.colors.secondary, borderRadius: 999, color: zenith.colors.muted, fontFamily: zenith.font.mono, fontSize: 11, paddingHorizontal: 8, paddingVertical: 4 },
  badgeSelected: { backgroundColor: zenith.colors.primary, color: zenith.colors.primaryForeground },
  resultMeta: { color: zenith.colors.muted, fontFamily: zenith.font.body, fontSize: 12, lineHeight: 17 },
  description: { color: zenith.colors.foreground, fontFamily: zenith.font.body, fontSize: 12, lineHeight: 17 },
  empty: { color: zenith.colors.foreground, fontFamily: zenith.font.body, padding: 10 },
});
