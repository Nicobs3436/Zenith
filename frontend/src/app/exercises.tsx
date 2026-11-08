import { Link, useLocalSearchParams } from 'expo-router';
import { ChevronRight, Dumbbell, Plus, Search } from 'lucide-react-native';
import { useEffect, useState } from 'react';
import { Pressable, StyleSheet, Text, TextInput, View } from 'react-native';

import { Exercise, getExercises } from '@/api/client';
import { ZenithBottomNav, ZenithCard, ZenithHeader, ZenithIconButton, ZenithNotice, ZenithPill } from '@/components/ZenithUI';
import { ZenithScreen } from '@/components/ZenithScreen';
import { routineAccents, zenith } from '@/constants/zenithTheme';

const ALL = 'Todos';
const ORIGINS = [
  { label: 'Todos', value: 'all' },
  { label: 'Global', value: 'global' },
  { label: 'Propio', value: 'custom' },
] as const;

type OriginFilter = (typeof ORIGINS)[number]['value'];

export default function ExercisesScreen() {
  const { notice } = useLocalSearchParams();
  const [exercises, setExercises] = useState<Exercise[]>([]);
  const [query, setQuery] = useState('');
  const [muscle, setMuscle] = useState(ALL);
  const [equipment, setEquipment] = useState(ALL);
  const [difficulty, setDifficulty] = useState(ALL);
  const [origin, setOrigin] = useState<OriginFilter>('all');
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    getExercises()
      .then(setExercises)
      .catch((caught) => setError(caught instanceof Error ? caught.message : 'Error'))
      .finally(() => setLoading(false));
  }, []);

  const muscleOptions = [ALL, ...unique(exercises.flatMap((exercise) => exercise.muscle_groups.map((item) => item.name)))];
  const equipmentOptions = [ALL, ...unique(exercises.flatMap((exercise) => exercise.equipment.map((item) => item.name)))];
  const difficultyOptions = [ALL, ...unique(exercises.map((exercise) => exercise.difficulty).filter(isString))];
  const noticeText = notice === 'created' ? 'Ejercicio creado.' : null;
  const normalizedQuery = normalize(query);
  const hasFilters = query.trim() || muscle !== ALL || equipment !== ALL || difficulty !== ALL || origin !== 'all';
  const filtered = exercises.filter((exercise) => {
    const matchesMuscle = muscle === ALL || exercise.muscle_groups.some((item) => item.name === muscle);
    const matchesEquipment = equipment === ALL || exercise.equipment.some((item) => item.name === equipment);
    const matchesDifficulty = difficulty === ALL || exercise.difficulty === difficulty;
    const matchesOrigin = origin === 'all' || (origin === 'global' ? exercise.is_global : !exercise.is_global);
    const searchable = normalize([
      exercise.name,
      exercise.description,
      exercise.technique_notes,
      exercise.difficulty,
      ...exercise.muscle_groups.map((item) => item.name),
      ...exercise.equipment.map((item) => item.name),
    ].filter(Boolean).join(' '));
    return matchesMuscle && matchesEquipment && matchesDifficulty && matchesOrigin && (!normalizedQuery || searchable.includes(normalizedQuery));
  });

  function clearFilters() {
    setQuery('');
    setMuscle(ALL);
    setEquipment(ALL);
    setDifficulty(ALL);
    setOrigin('all');
  }

  return (
    <ZenithScreen bottomNav={<ZenithBottomNav />}>
      <ZenithHeader
        subtitle={`${exercises.length} en catalogo`}
        title="Ejercicios"
        right={<ZenithIconButton href={'/exercise-new' as never} label="Nuevo ejercicio"><Plus color={zenith.colors.primary} size={17} /></ZenithIconButton>}
      />
      {noticeText && <ZenithNotice tone="success">{noticeText}</ZenithNotice>}

      <View style={styles.searchBox}>
        <Search color={zenith.colors.muted} size={15} />
        <TextInput
          autoCapitalize="none"
          autoCorrect={false}
          onChangeText={setQuery}
          placeholder="Buscar ejercicio..."
          placeholderTextColor={zenith.colors.muted}
          style={styles.searchInput}
          value={query}
        />
      </View>

      <View style={styles.chips}>
        <FilterGroup label="Músculo" options={muscleOptions.map((value) => ({ label: value, value }))} selectedValue={muscle} onChange={setMuscle} />
        <FilterGroup label="Equipo" options={equipmentOptions.map((value) => ({ label: value, value }))} selectedValue={equipment} onChange={setEquipment} />
        <FilterGroup label="Dificultad" options={difficultyOptions.map((value) => ({ label: value === ALL ? value : difficultyLabel(value), value }))} selectedValue={difficulty} onChange={setDifficulty} />
        <FilterGroup label="Origen" options={ORIGINS} selectedValue={origin} onChange={(value) => setOrigin(value as OriginFilter)} />
      </View>

      <View style={styles.resultsHeader}>
        <Text style={styles.resultCount}>{filtered.length} resultado(s)</Text>
        {hasFilters && (
          <Pressable accessibilityRole="button" onPress={clearFilters} style={styles.clearButton}>
            <Text style={styles.clearText}>Limpiar filtros</Text>
          </Pressable>
        )}
      </View>

      {loading && <ZenithNotice>Cargando ejercicios...</ZenithNotice>}
      {error && <ZenithNotice tone="danger">{error}</ZenithNotice>}
      {!loading && !error && filtered.length === 0 && <ZenithNotice>No hay ejercicios con esos filtros.</ZenithNotice>}

      <View style={styles.list}>
        {filtered.map((exercise, index) => {
          const accent = routineAccents[index % routineAccents.length];
          return (
            <Link key={exercise.id} href={{ pathname: '/exercise-detail', params: { exerciseId: exercise.id } } as never} asChild>
              <Pressable>
                <ZenithCard style={styles.card}>
                  <View style={[styles.iconBox, { backgroundColor: `${accent}18` }]}>
                    <Dumbbell color={accent} size={18} />
                  </View>
                  <View style={styles.cardText}>
                    <Text style={styles.name}>{exercise.name}</Text>
                    <Text style={styles.meta} numberOfLines={1}>{primaryMuscle(exercise)} · {equipmentLabel(exercise)}</Text>
                  </View>
                  <View style={styles.badges}>
                    <ZenithPill color={accent}>{difficultyLabel(exercise.difficulty)}</ZenithPill>
                    <Text style={styles.origin}>{exercise.is_global ? 'Global' : 'Propio'}</Text>
                  </View>
                  <ChevronRight color={zenith.colors.muted} size={15} />
                </ZenithCard>
              </Pressable>
            </Link>
          );
        })}
      </View>
    </ZenithScreen>
  );
}

function unique(items: string[]) {
  return [...new Set(items)].sort((left, right) => left.localeCompare(right, 'es'));
}

function isString(value: string | null): value is string {
  return typeof value === 'string';
}

function normalize(value: string) {
  return value.normalize('NFD').replace(/[\u0300-\u036f]/g, '').toLowerCase().trim();
}

function primaryMuscle(exercise: Exercise) {
  return exercise.muscle_groups[0]?.name ?? 'Sin músculo';
}

function equipmentLabel(exercise: Exercise) {
  return exercise.equipment[0]?.name ?? 'Sin equipo';
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

function FilterGroup({ label, onChange, options, selectedValue }: { label: string; onChange: (value: string) => void; options: readonly { label: string; value: string }[]; selectedValue: string }) {
  return (
    <View style={styles.filterGroup}>
      <Text style={styles.filterLabel}>{label}</Text>
      <View style={styles.filterChips}>
        {options.map((option) => {
          const active = option.value === selectedValue;
          return (
            <Pressable accessibilityRole="button" key={option.value} onPress={() => onChange(option.value)} style={[styles.chip, active && styles.chipActive]}>
              <Text style={[styles.chipText, active && styles.chipTextActive]}>{option.label}</Text>
            </Pressable>
          );
        })}
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  searchBox: { alignItems: 'center', backgroundColor: zenith.colors.secondary, borderColor: zenith.colors.border, borderRadius: 14, borderWidth: 1, flexDirection: 'row', gap: 9, paddingHorizontal: 12 },
  searchInput: { color: zenith.colors.foreground, flex: 1, fontFamily: zenith.font.body, paddingVertical: 12 },
  chips: { gap: 12 },
  filterGroup: { gap: 7 },
  filterLabel: { color: zenith.colors.muted, fontFamily: zenith.font.mono, fontSize: 11, letterSpacing: 1.2, textTransform: 'uppercase' },
  filterChips: { flexDirection: 'row', flexWrap: 'wrap', gap: 8 },
  chip: { backgroundColor: zenith.colors.secondary, borderColor: zenith.colors.border, borderRadius: 999, borderWidth: 1, paddingHorizontal: 12, paddingVertical: 7 },
  chipActive: { backgroundColor: zenith.colors.primary, borderColor: zenith.colors.primary },
  chipText: { color: zenith.colors.muted, fontFamily: zenith.font.bodyBold, fontSize: 12 },
  chipTextActive: { color: zenith.colors.primaryForeground },
  resultsHeader: { alignItems: 'center', flexDirection: 'row', justifyContent: 'space-between', gap: 10 },
  resultCount: { color: zenith.colors.muted, fontFamily: zenith.font.mono, fontSize: 11 },
  clearButton: { borderColor: zenith.colors.border, borderRadius: 999, borderWidth: 1, paddingHorizontal: 11, paddingVertical: 7 },
  clearText: { color: zenith.colors.foreground, fontFamily: zenith.font.bodyBold, fontSize: 12 },
  list: { gap: 10 },
  card: { alignItems: 'center', flexDirection: 'row', gap: 12, padding: 14 },
  iconBox: { alignItems: 'center', borderRadius: 14, height: 44, justifyContent: 'center', width: 44 },
  cardText: { flex: 1, gap: 3 },
  name: { color: zenith.colors.foreground, fontFamily: zenith.font.bodyBold, fontSize: 14 },
  meta: { color: zenith.colors.muted, fontFamily: zenith.font.body, fontSize: 11 },
  badges: { alignItems: 'flex-end', gap: 3 },
  origin: { color: zenith.colors.primary, fontFamily: zenith.font.mono, fontSize: 11 },
});
