import { Link, useLocalSearchParams } from 'expo-router';
import { Bot, Play, Plus } from 'lucide-react-native';
import { useEffect, useState } from 'react';
import { Pressable, StyleSheet, Text, View } from 'react-native';

import { analyzeRoutineGoal, AuthExpiredError, deleteRoutine, Exercise, getExercises, getRoutines, Routine } from '@/api/client';
import { ZenithBottomNav, ZenithCard, ZenithHeader, ZenithIconButton, ZenithNotice, ZenithPill } from '@/components/ZenithUI';
import { ZenithScreen } from '@/components/ZenithScreen';
import { routineAccents, zenith } from '@/constants/zenithTheme';
import { exerciseName, formatPlannedExercise, plannedRoutineExercises } from '@/utils/workoutDisplay';

export function ErrorBoundary({ error, retry }: { error: Error; retry: () => void }) {
  return (
    <ZenithScreen bottomNav={<ZenithBottomNav />}>
      <ZenithHeader title="Rutinas" subtitle="Error de pantalla" />
      <ZenithNotice tone="danger">No se pudo mostrar Rutinas: {error.message}</ZenithNotice>
      <Pressable accessibilityRole="button" onPress={retry} style={styles.retryButton}>
        <Text style={styles.retryText}>Reintentar</Text>
      </Pressable>
      <Link href="/dashboard" style={styles.edit}>Volver al inicio</Link>
    </ZenithScreen>
  );
}

export default function RoutinesScreen() {
  const { notice } = useLocalSearchParams();
  const [routines, setRoutines] = useState<Routine[]>([]);
  const [exercises, setExercises] = useState<Exercise[]>([]);
  const [routinesError, setRoutinesError] = useState<string | null>(null);
  const [exercisesError, setExercisesError] = useState<string | null>(null);
  const [loadingRoutines, setLoadingRoutines] = useState(true);
  const [loadingExercises, setLoadingExercises] = useState(true);
  const [workingRoutine, setWorkingRoutine] = useState<string | null>(null);
  const [deletingRoutine, setDeletingRoutine] = useState<string | null>(null);
  const [deleteConfirm, setDeleteConfirm] = useState<string | null>(null);
  const [actionNotice, setActionNotice] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;

    getRoutines()
      .then((routineItems) => {
        if (!cancelled) {
          setRoutines(routineItems);
        }
      })
      .catch((caught) => {
        if (!cancelled && !(caught instanceof AuthExpiredError)) {
          setRoutinesError(caught instanceof Error ? caught.message : 'No se pudieron cargar las rutinas.');
        }
      })
      .finally(() => {
        if (!cancelled) {
          setLoadingRoutines(false);
        }
      });

    getExercises()
      .then((exerciseItems) => {
        if (!cancelled) {
          setExercises(exerciseItems);
        }
      })
      .catch((caught) => {
        if (!cancelled && !(caught instanceof AuthExpiredError)) {
          setExercisesError(caught instanceof Error ? caught.message : 'No se pudieron cargar los nombres de ejercicios.');
        }
      })
      .finally(() => {
        if (!cancelled) {
          setLoadingExercises(false);
        }
      });

    return () => {
      cancelled = true;
    };
  }, []);

  const noticeText = notice === 'created' ? 'Rutina creada.' : notice === 'updated' ? 'Rutina guardada.' : notice === 'deleted' ? 'Rutina eliminada.' : null;

  async function submitAnalyzeGoal(routineId: string) {
    setWorkingRoutine(routineId);
    setRoutinesError(null);
    setActionNotice(null);
    try {
      const suggestions = await analyzeRoutineGoal(routineId);
      setActionNotice(
        suggestions.length > 0
          ? `Se generaron ${suggestions.length} ajustes de objetivo. Revisalos en Entrenador IA.`
          : 'La rutina ya esta alineada con su objetivo o no tiene objetivo reconocido.',
      );
    } catch (caught) {
      if (!(caught instanceof AuthExpiredError)) {
        setRoutinesError(caught instanceof Error ? caught.message : 'No se pudo analizar el objetivo de la rutina.');
      }
    } finally {
      setWorkingRoutine(null);
    }
  }

  async function submitDeleteRoutine(routineId: string) {
    if (deleteConfirm !== routineId) {
      setDeleteConfirm(routineId);
      setActionNotice(null);
      return;
    }

    setDeletingRoutine(routineId);
    setRoutinesError(null);
    setActionNotice(null);
    try {
      await deleteRoutine(routineId);
      setRoutines((current) => current.filter((routine) => routine.id !== routineId));
      setDeleteConfirm(null);
      setActionNotice('Rutina eliminada. Las sesiones historicas se conservaron.');
    } catch (caught) {
      if (!(caught instanceof AuthExpiredError)) {
        setRoutinesError(caught instanceof Error ? caught.message : 'No se pudo eliminar la rutina.');
      }
    } finally {
      setDeletingRoutine(null);
    }
  }

  async function retryRoutines() {
    setLoadingRoutines(true);
    setRoutinesError(null);
    try {
      setRoutines(await getRoutines());
    } catch (caught) {
      if (!(caught instanceof AuthExpiredError)) {
        setRoutinesError(caught instanceof Error ? caught.message : 'No se pudieron cargar las rutinas.');
      }
    } finally {
      setLoadingRoutines(false);
    }
  }

  return (
    <ZenithScreen bottomNav={<ZenithBottomNav />}>
      <ZenithHeader
        subtitle={`${routines.length} planes activos`}
        title="Rutinas"
        right={<ZenithIconButton href="/routine-new" label="Nueva rutina"><Plus color={zenith.colors.primary} size={17} /></ZenithIconButton>}
      />
      {noticeText && <ZenithNotice tone="success">{noticeText}</ZenithNotice>}
      {actionNotice && <ZenithNotice tone="success">{actionNotice}</ZenithNotice>}
      {loadingRoutines && <ZenithNotice>Cargando rutinas...</ZenithNotice>}
      {!loadingRoutines && loadingExercises && routines.length > 0 && <ZenithNotice>Cargando nombres de ejercicios...</ZenithNotice>}
      {exercisesError && routines.length > 0 && <ZenithNotice tone="warning">{exercisesError}</ZenithNotice>}
      {routinesError && (
        <View style={styles.errorBox}>
          <Text style={styles.errorText}>{routinesError}</Text>
          <Pressable accessibilityRole="button" onPress={retryRoutines} style={styles.retryButton}>
            <Text style={styles.retryText}>Reintentar</Text>
          </Pressable>
        </View>
      )}
      {!loadingRoutines && !routinesError && routines.length === 0 && <ZenithNotice>Aun no tienes rutinas.</ZenithNotice>}

      {routines.map((routine, index) => {
        const accent = routineAccents[index % routineAccents.length];
        const plannedExercises = plannedRoutineExercises(routine);
        return (
          <ZenithCard key={routine.id} style={[styles.card, { borderLeftColor: accent }]}>
            <View style={styles.cardHeader}>
              <View style={styles.titleBlock}>
                <Text style={styles.name}>{routine.name}</Text>
                <Text style={styles.goal}>{routine.goal ?? 'Sin objetivo definido'}</Text>
              </View>
              <ZenithPill color={accent}>{plannedExercises.length} ej.</ZenithPill>
            </View>

            <View style={styles.exerciseList}>
              {plannedExercises.length === 0 && <Text style={styles.emptyRoutineText}>Sin ejercicios planificados válidos.</Text>}
              {plannedExercises.slice(0, 5).map((planned) => (
                <View key={planned.id ?? `${planned.exercise_id}-${planned.position}`} style={styles.exerciseRow}>
                  <View style={[styles.dot, { backgroundColor: accent }]} />
                  <Text style={styles.exerciseName}>{exerciseName(planned.exercise_id, exercises)}</Text>
                  <Text style={styles.exerciseMeta}>{formatPlannedExercise(planned)}</Text>
                </View>
              ))}
            </View>

            <View style={styles.actions}>
              <Link href={{ pathname: '/session-active', params: { routineId: routine.id } }} asChild>
                <Pressable accessibilityRole="button" style={StyleSheet.flatten([styles.startButton, { backgroundColor: accent }])}>
                  <Play color={zenith.colors.primaryForeground} fill={zenith.colors.primaryForeground} size={13} />
                  <Text style={styles.startText}>Iniciar</Text>
                </Pressable>
              </Link>
              <Pressable accessibilityRole="button" disabled={workingRoutine === routine.id} onPress={() => submitAnalyzeGoal(routine.id)} style={[styles.aiButton, workingRoutine === routine.id && styles.disabled]}>
                <Bot color={zenith.colors.primary} size={13} />
                <Text style={styles.aiText}>{workingRoutine === routine.id ? 'Analizando...' : 'IA'}</Text>
              </Pressable>
              <Link href={{ pathname: '/routine-edit', params: { routineId: routine.id } }} style={styles.edit}>Editar</Link>
              <Pressable accessibilityRole="button" disabled={deletingRoutine === routine.id} onPress={() => submitDeleteRoutine(routine.id)} style={[styles.deleteButton, deletingRoutine === routine.id && styles.disabled]}>
                <Text style={styles.deleteText}>{deletingRoutine === routine.id ? 'Eliminando...' : deleteConfirm === routine.id ? 'Confirmar' : 'Eliminar'}</Text>
              </Pressable>
            </View>
            {deleteConfirm === routine.id && <Text style={styles.deleteHint}>Pulsa Confirmar para ocultar esta rutina.</Text>}
          </ZenithCard>
        );
      })}
      <Link href="/routine-new" asChild>
        <Pressable accessibilityRole="button" style={styles.createButton}>
          <Plus color={zenith.colors.primaryForeground} size={16} />
          <Text style={styles.createText}>Crear rutina</Text>
        </Pressable>
      </Link>
    </ZenithScreen>
  );
}

const styles = StyleSheet.create({
  card: { borderLeftWidth: 3, gap: 14 },
  cardHeader: { alignItems: 'flex-start', flexDirection: 'row', gap: 12, justifyContent: 'space-between' },
  titleBlock: { flex: 1, gap: 2 },
  name: { color: zenith.colors.foreground, fontFamily: zenith.font.display, fontSize: 28, lineHeight: 30, textTransform: 'uppercase' },
  goal: { color: zenith.colors.muted, fontFamily: zenith.font.body, fontSize: 12 },
  exerciseList: { gap: 8 },
  exerciseRow: { alignItems: 'center', flexDirection: 'row', gap: 8 },
  emptyRoutineText: { color: zenith.colors.muted, fontFamily: zenith.font.body, lineHeight: 20 },
  dot: { borderRadius: 999, height: 5, width: 5 },
  exerciseName: { color: zenith.colors.foreground, flex: 1, fontFamily: zenith.font.bodyMedium, fontSize: 13 },
  exerciseMeta: { color: zenith.colors.muted, fontFamily: zenith.font.mono, fontSize: 11 },
  actions: { alignItems: 'center', flexDirection: 'row', gap: 8 },
  startButton: { alignItems: 'center', borderRadius: 13, flex: 1, flexDirection: 'row', gap: 6, justifyContent: 'center', padding: 11 },
  startText: { color: zenith.colors.primaryForeground, fontFamily: zenith.font.bodyBold, fontSize: 13 },
  aiButton: { alignItems: 'center', borderColor: zenith.colors.primaryBorder, borderRadius: 13, borderWidth: 1, flexDirection: 'row', gap: 6, paddingHorizontal: 13, paddingVertical: 10 },
  aiText: { color: zenith.colors.primary, fontFamily: zenith.font.bodyBold, fontSize: 12 },
  edit: { borderColor: zenith.colors.border, borderRadius: 13, borderWidth: 1, color: zenith.colors.muted, fontFamily: zenith.font.bodyBold, overflow: 'hidden', paddingHorizontal: 14, paddingVertical: 10 },
  deleteButton: { alignItems: 'center', borderColor: 'rgba(232,64,64,0.35)', borderRadius: 13, borderWidth: 1, paddingHorizontal: 13, paddingVertical: 10 },
  deleteText: { color: '#fca5a5', fontFamily: zenith.font.bodyBold, fontSize: 12 },
  deleteHint: { color: '#fca5a5', fontFamily: zenith.font.body, fontSize: 12 },
  errorBox: { backgroundColor: zenith.colors.dangerSoft, borderColor: 'rgba(232,64,64,0.28)', borderRadius: 14, borderWidth: 1, gap: 10, padding: 12 },
  errorText: { color: '#ffb4b4', fontFamily: zenith.font.bodyMedium, lineHeight: 20 },
  retryButton: { alignItems: 'center', borderColor: 'rgba(232,64,64,0.35)', borderRadius: 12, borderWidth: 1, padding: 10 },
  retryText: { color: zenith.colors.foreground, fontFamily: zenith.font.bodyBold },
  disabled: { opacity: 0.5 },
  createButton: { alignItems: 'center', backgroundColor: zenith.colors.primary, borderRadius: 18, flexDirection: 'row', gap: 8, justifyContent: 'center', padding: 15 },
  createText: { color: zenith.colors.primaryForeground, fontFamily: zenith.font.bodyBold, fontWeight: '900' },
});
