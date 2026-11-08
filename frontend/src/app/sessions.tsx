import { Link, useLocalSearchParams } from 'expo-router';
import { Plus } from 'lucide-react-native';
import { useEffect, useState } from 'react';
import { Pressable, StyleSheet, Text, View } from 'react-native';

import { deleteWorkoutSession, Exercise, getExercises, getRoutines, getWorkoutSessions, Routine, WorkoutSession } from '@/api/client';
import { ZenithCard, ZenithHeader, ZenithIconButton, ZenithNotice, ZenithPill } from '@/components/ZenithUI';
import { ZenithScreen } from '@/components/ZenithScreen';
import { routineAccents, zenith } from '@/constants/zenithTheme';
import { countLabel, formatVolumeByUnit, plannedRoutineExercises, routineName, uniqueExerciseNames } from '@/utils/workoutDisplay';

export default function SessionsScreen() {
  const { notice } = useLocalSearchParams();
  const [sessions, setSessions] = useState<WorkoutSession[]>([]);
  const [routines, setRoutines] = useState<Routine[]>([]);
  const [exercises, setExercises] = useState<Exercise[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [actionNotice, setActionNotice] = useState<string | null>(null);
  const [deleteConfirm, setDeleteConfirm] = useState<string | null>(null);
  const [deletingSession, setDeletingSession] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    Promise.all([getWorkoutSessions(), getRoutines(), getExercises()])
      .then(([sessionItems, routineItems, exerciseItems]) => {
        setSessions(sessionItems);
        setRoutines(routineItems);
        setExercises(exerciseItems);
      })
      .catch((caught) => setError(caught instanceof Error ? caught.message : 'Error'))
      .finally(() => setLoading(false));
  }, []);

  const noticeText = notice === 'created' ? 'Sesión registrada.' : notice === 'updated' ? 'Sesión guardada.' : notice === 'deleted' ? 'Sesión eliminada.' : null;

  async function submitDeleteSession(sessionId: string) {
    if (deleteConfirm !== sessionId) {
      setDeleteConfirm(sessionId);
      setActionNotice(null);
      return;
    }

    setDeletingSession(sessionId);
    setError(null);
    setActionNotice(null);
    try {
      await deleteWorkoutSession(sessionId);
      setSessions((current) => current.filter((session) => session.id !== sessionId));
      setDeleteConfirm(null);
      setActionNotice('Sesión eliminada. Ya no contara para estadísticas ni rango.');
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : 'No se pudo eliminar la sesión.');
    } finally {
      setDeletingSession(null);
    }
  }

  return (
    <ZenithScreen>
      <ZenithHeader title="Sesiones" subtitle="Entrenamiento" right={<ZenithIconButton href="/session-new" label="Registrar sesión manual"><Plus color={zenith.colors.primary} size={17} /></ZenithIconButton>} />
      {noticeText && <ZenithNotice tone="success">{noticeText}</ZenithNotice>}
      {actionNotice && <ZenithNotice tone="success">{actionNotice}</ZenithNotice>}
      {loading && <ZenithNotice>Cargando rutinas y sesiones...</ZenithNotice>}
      {error && <ZenithNotice tone="danger">{error}</ZenithNotice>}

      <Text style={styles.section}>Empezar rutina</Text>
      {!loading && !error && routines.length === 0 && <ZenithNotice>Aun no tienes rutinas. Crea una rutina para empezar entrenamientos guiados.</ZenithNotice>}
      {routines.map((routine, index) => {
        const accent = routineAccents[index % routineAccents.length];
        const plannedExercises = plannedRoutineExercises(routine);
        return (
        <ZenithCard key={routine.id} style={[styles.card, { borderLeftColor: accent }]}>
          <Text style={styles.name}>{routine.name}</Text>
          {routine.goal && <Text style={styles.meta}>{routine.goal}</Text>}
          <Text style={styles.meta}>{countLabel(plannedExercises.length, 'ejercicio planificado', 'ejercicios planificados')}</Text>
          <Link href={{ pathname: '/session-active', params: { routineId: routine.id } }} style={StyleSheet.flatten([styles.action, { backgroundColor: accent }])}>Empezar rutina</Link>
        </ZenithCard>
        );
      })}

      <Link href="/session-new" style={styles.secondaryAction}>Registrar sesión libre</Link>

      <Text style={styles.section}>Historial</Text>
      {!loading && !error && sessions.length === 0 && <ZenithNotice>Aun no registraste sesiones.</ZenithNotice>}
      {sessions.map((session) => (
        <ZenithCard key={session.id} style={styles.historyCard}>
          <Text style={styles.name}>{new Date(session.started_at).toLocaleString()}</Text>
          <ZenithPill active>{routineName(session.routine_id, routines)}</ZenithPill>
          <Text style={styles.meta}>{countLabel(session.sets.length, 'serie registrada', 'series registradas')}</Text>
          <Text style={styles.meta}>Volumen: {formatVolumeByUnit(session.sets)}</Text>
          <Text style={styles.exercises}>{uniqueExerciseNames(session.sets, exercises) || 'Sin ejercicios'}</Text>
          <View style={styles.actionsRow}>
            <Link href={{ pathname: '/session-detail', params: { sessionId: session.id } }} style={styles.link}>Ver detalle</Link>
            <Link href={{ pathname: '/session-edit', params: { sessionId: session.id } }} style={styles.link}>Editar</Link>
            <Pressable accessibilityRole="button" disabled={deletingSession === session.id} onPress={() => submitDeleteSession(session.id)} style={[styles.deleteButton, deletingSession === session.id && styles.disabled]}>
              <Text style={styles.deleteText}>{deletingSession === session.id ? 'Eliminando...' : deleteConfirm === session.id ? 'Confirmar' : 'Eliminar'}</Text>
            </Pressable>
          </View>
          {deleteConfirm === session.id && <Text style={styles.deleteHint}>Pulsa Confirmar para ocultar esta sesión.</Text>}
        </ZenithCard>
      ))}
    </ZenithScreen>
  );
}

const styles = StyleSheet.create({
  section: { color: zenith.colors.foreground, fontFamily: zenith.font.display, fontSize: 24, textTransform: 'uppercase' },
  action: { borderRadius: 14, color: zenith.colors.primaryForeground, fontFamily: zenith.font.bodyBold, marginTop: 8, overflow: 'hidden', padding: 14, textAlign: 'center' },
  secondaryAction: { borderColor: zenith.colors.primaryBorder, borderRadius: 16, borderWidth: 1, color: zenith.colors.primary, fontFamily: zenith.font.bodyBold, overflow: 'hidden', padding: 14, textAlign: 'center' },
  card: { borderLeftWidth: 3, gap: 8 },
  historyCard: { gap: 8 },
  name: { color: zenith.colors.foreground, fontFamily: zenith.font.display, fontSize: 24, lineHeight: 26, textTransform: 'uppercase' },
  meta: { color: zenith.colors.muted, fontFamily: zenith.font.body },
  exercises: { color: zenith.colors.foreground, fontFamily: zenith.font.bodyBold },
  actionsRow: { alignItems: 'center', flexDirection: 'row', flexWrap: 'wrap', gap: 16, marginTop: 4 },
  link: { color: zenith.colors.primary, fontFamily: zenith.font.bodyBold },
  deleteButton: { borderColor: 'rgba(232,64,64,0.35)', borderRadius: 12, borderWidth: 1, paddingHorizontal: 12, paddingVertical: 7 },
  deleteText: { color: '#fca5a5', fontFamily: zenith.font.bodyBold },
  deleteHint: { color: '#fca5a5', fontFamily: zenith.font.body, fontSize: 12 },
  disabled: { opacity: 0.55 },
});
