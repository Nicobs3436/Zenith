import { Link, useRouter } from 'expo-router';
import { Activity, ChevronRight, Flame, Play, Sparkles, TrendingUp, Trophy, Zap } from 'lucide-react-native';
import { useEffect, useState } from 'react';
import { Pressable, StyleSheet, Text, View } from 'react-native';

import { AuthExpiredError, Exercise, ExerciseStats, getExercises, getExerciseStats, getMe, getRank, getRoutines, getWorkoutSessions, logout, RankProgress, Routine, User, WorkoutSession } from '@/api/client';
import { ZenithBottomNav, ZenithButton, ZenithCard, ZenithNotice, ZenithPill, ZenithStatCard, zenithText } from '@/components/ZenithUI';
import { ZenithScreen } from '@/components/ZenithScreen';
import { routineAccents, zenith } from '@/constants/zenithTheme';
import { formatRankScore } from '@/utils/rankDisplay';
import { formatStatsValue } from '@/utils/statsDisplay';
import { exerciseName, plannedRoutineExercises } from '@/utils/workoutDisplay';

export default function DashboardScreen() {
  const router = useRouter();
  const [user, setUser] = useState<User | null>(null);
  const [rank, setRank] = useState<RankProgress | null>(null);
  const [routines, setRoutines] = useState<Routine[]>([]);
  const [sessions, setSessions] = useState<WorkoutSession[]>([]);
  const [stats, setStats] = useState<ExerciseStats[]>([]);
  const [exercises, setExercises] = useState<Exercise[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let active = true;
    Promise.all([getMe(), getRank(), getRoutines(), getWorkoutSessions(), getExerciseStats('30d'), getExercises()])
      .then(([nextUser, nextRank, nextRoutines, nextSessions, nextStats, nextExercises]) => {
        if (!active) {
          return;
        }
        setUser(nextUser);
        setRank(nextRank);
        setRoutines(nextRoutines);
        setSessions(nextSessions);
        setStats(nextStats);
        setExercises(nextExercises);
      })
      .catch((caught) => {
        if (!active) {
          return;
        }
        if (caught instanceof AuthExpiredError) {
          return;
        }
        setError(caught instanceof Error ? caught.message : 'Error');
        router.replace('/login');
      })
      .finally(() => {
        if (active) {
          setLoading(false);
        }
      });
    return () => {
      active = false;
    };
  }, [router]);

  async function submitLogout() {
    await logout();
    router.replace('/login');
  }

  const totalVolume = stats.reduce((total, item) => total + Number(item.total_volume ?? 0), 0);
  const totalSets = stats.reduce((total, item) => total + item.total_sets, 0);
  const finishedSessions = sessions.filter((session) => session.finished_at).length;
  const nextRoutine = routines[0];
  const nextRoutineExercises = plannedRoutineExercises(nextRoutine);
  const username = user?.username ?? 'atleta';
  const initials = username.slice(0, 2).toUpperCase();
  const today = new Intl.DateTimeFormat('es', { day: '2-digit', month: 'short', weekday: 'short' }).format(new Date());

  return (
    <ZenithScreen bottomNav={<ZenithBottomNav />}>
      <View style={styles.heroHeader}>
        <View style={styles.heroTitleBlock}>
          <Text style={styles.date}>{today}</Text>
          <Text style={styles.title}>Hola, <Text style={styles.titleAccent}>{username}</Text></Text>
        </View>
        <View style={styles.headerActions}>
          <View style={styles.avatar}><Text style={styles.avatarText}>{initials}</Text></View>
        </View>
      </View>

      {loading && <ZenithNotice>Cargando tu base de entrenamiento...</ZenithNotice>}
      {error && <ZenithNotice tone="danger">{error}</ZenithNotice>}

      <View style={styles.topCards}>
        <ZenithCard style={styles.compactCard}>
          <View style={styles.inlineCardContent}>
            <Flame color="#fb923c" size={18} />
            <View>
              <Text style={styles.bigNumber}>{finishedSessions}</Text>
              <Text style={styles.smallLabel}>Sesiones</Text>
            </View>
          </View>
        </ZenithCard>
        <Link href="/rank" asChild>
          <Pressable accessibilityRole="button" style={styles.rankCard}>
            <Trophy color={zenith.colors.primary} size={20} />
            <View style={styles.rankTextBlock}>
              <Text style={styles.rankName}>{rank?.rank.name ?? 'Sin rango'}</Text>
              <Text style={styles.rankScore}>{rank ? formatRankScore(rank.score) : '0 pts'}</Text>
            </View>
            <ChevronRight color={zenith.colors.muted} size={15} />
          </Pressable>
        </Link>
      </View>

      <View style={styles.statGrid}>
        <ZenithStatCard icon={<Activity color={zenith.colors.muted} size={13} />} label="Rutinas" value={String(routines.length)} unit="activas" />
        <ZenithStatCard icon={<TrendingUp color={zenith.colors.muted} size={13} />} label="Volumen" value={formatCompactVolume(totalVolume)} unit="30 días" />
        <ZenithStatCard icon={<Zap color={zenith.colors.muted} size={13} />} label="Series" value={String(totalSets)} unit="30 días" />
      </View>

      <ZenithCard style={styles.sessionCard}>
        <View style={styles.sessionHeader}>
          <View>
            <Text style={styles.sessionKicker}>Próxima rutina</Text>
            <Text style={styles.sessionTitle}>{nextRoutine?.name ?? 'Crea tu primer plan'}</Text>
          </View>
          <ZenithPill active>{nextRoutine ? `${nextRoutineExercises.length} ${nextRoutineExercises.length === 1 ? 'ejercicio' : 'ejercicios'}` : 'Nuevo'}</ZenithPill>
        </View>
        {nextRoutine ? (
          <View style={styles.exerciseList}>
            {nextRoutineExercises.slice(0, 4).map((exercise, index) => (
              <View key={exercise.id ?? `${exercise.exercise_id}-${exercise.position}`} style={styles.exerciseLine}>
                <View style={[styles.exerciseDot, { backgroundColor: routineAccents[index % routineAccents.length] }]} />
                <Text style={styles.exerciseName}>{exerciseName(exercise.exercise_id, exercises)}</Text>
                <Text style={styles.exerciseSpec}>{exercise.target_sets ?? '-'}x{exercise.target_reps_min ?? '-'}</Text>
              </View>
            ))}
          </View>
        ) : (
          <Text style={styles.mutedText}>Todavía no tienes rutinas. Crea una para empezar a registrar entrenamientos.</Text>
        )}
        <View style={styles.sessionActions}>
          <Link href={nextRoutine ? { pathname: '/session-active', params: { routineId: nextRoutine.id } } : '/routine-new'} asChild>
            <Pressable accessibilityRole="button" style={styles.primaryAction}>
              <Play color={zenith.colors.primaryForeground} fill={zenith.colors.primaryForeground} size={15} />
              <Text style={styles.primaryActionText}>{nextRoutine ? 'Iniciar sesión' : 'Crear rutina'}</Text>
            </Pressable>
          </Link>
        </View>
      </ZenithCard>

      <ZenithCard style={styles.aiCard}>
        <View style={styles.aiIcon}><Sparkles color={zenith.colors.primary} size={15} /></View>
        <View style={styles.aiTextBlock}>
          <Text style={styles.aiTitle}>Coach IA preparado</Text>
          <Text style={styles.aiText}>Genera sugerencias cuando tengas varias sesiones registradas. Solo se aplican si las aceptas.</Text>
        </View>
      </ZenithCard>

      <View style={styles.quickGrid}>
        <Link accessibilityRole="link" href="/sessions" style={styles.quickLink}>Historial de sesiones</Link>
        <Link accessibilityRole="link" href={'/account' as never} style={styles.quickLink}>Cuenta y datos</Link>
      </View>

      <ZenithButton onPress={submitLogout} title="Cerrar sesión" variant="danger" />
    </ZenithScreen>
  );
}

function formatCompactVolume(value: number) {
  if (value >= 1000) {
    return `${Math.round(value / 1000)}K`;
  }
  return formatStatsValue(String(value));
}

const styles = StyleSheet.create({
  heroHeader: { alignItems: 'center', flexDirection: 'row', gap: 12, justifyContent: 'space-between' },
  heroTitleBlock: { flex: 1, gap: 2 },
  date: { color: zenith.colors.muted, fontFamily: zenith.font.mono, fontSize: 11, letterSpacing: 2, textTransform: 'uppercase' },
  title: { color: zenith.colors.foreground, fontFamily: zenith.font.display, fontSize: 34, lineHeight: 38, textTransform: 'uppercase' },
  titleAccent: { color: zenith.colors.primary },
  headerActions: { alignItems: 'center', flexDirection: 'row', gap: 8 },
  avatar: { alignItems: 'center', backgroundColor: zenith.colors.primarySoft, borderRadius: 999, height: 38, justifyContent: 'center', width: 38 },
  avatarText: { color: zenith.colors.primary, fontFamily: zenith.font.display, fontSize: 16, fontWeight: '900' },
  topCards: { flexDirection: 'row', gap: 10 },
  compactCard: { flex: 1, padding: 14 },
  inlineCardContent: { alignItems: 'center', flexDirection: 'row', gap: 10 },
  bigNumber: { color: zenith.colors.primary, fontFamily: zenith.font.display, fontSize: 24, lineHeight: 25 },
  smallLabel: { color: zenith.colors.muted, fontFamily: zenith.font.mono, fontSize: 11, textTransform: 'uppercase' },
  rankCard: { alignItems: 'center', backgroundColor: zenith.colors.card, borderColor: zenith.colors.border, borderRadius: zenith.radius.xl, borderWidth: 1, flex: 1, flexDirection: 'row', gap: 10, padding: 14 },
  rankTextBlock: { flex: 1 },
  rankName: { color: zenith.colors.foreground, fontFamily: zenith.font.bodyBold, fontSize: 14 },
  rankScore: { color: zenith.colors.muted, fontFamily: zenith.font.mono, fontSize: 11 },
  statGrid: { flexDirection: 'row', gap: 8 },
  sessionCard: { gap: 14, padding: 0, overflow: 'hidden' },
  sessionHeader: { alignItems: 'center', backgroundColor: 'rgba(200,241,53,0.04)', borderBottomColor: zenith.colors.primaryBorder, borderBottomWidth: 1, flexDirection: 'row', justifyContent: 'space-between', padding: 16 },
  sessionKicker: { color: zenith.colors.muted, fontFamily: zenith.font.mono, fontSize: 11, letterSpacing: 1.2, textTransform: 'uppercase' },
  sessionTitle: { color: zenith.colors.foreground, fontFamily: zenith.font.display, fontSize: 24, textTransform: 'uppercase' },
  exerciseList: { gap: 10, paddingHorizontal: 16 },
  exerciseLine: { alignItems: 'center', flexDirection: 'row', gap: 10 },
  exerciseDot: { borderRadius: 999, height: 5, width: 5 },
  exerciseName: { color: zenith.colors.foreground, flex: 1, fontFamily: zenith.font.bodyMedium, fontSize: 13 },
  exerciseSpec: { color: zenith.colors.muted, fontFamily: zenith.font.mono, fontSize: 11 },
  mutedText: { ...zenithText.muted, lineHeight: 20, paddingHorizontal: 16 },
  sessionActions: { padding: 16, paddingTop: 0 },
  primaryAction: { alignItems: 'center', backgroundColor: zenith.colors.primary, borderRadius: 14, flexDirection: 'row', gap: 8, justifyContent: 'center', padding: 14 },
  primaryActionText: { color: zenith.colors.primaryForeground, fontFamily: zenith.font.bodyBold, fontWeight: '900' },
  aiCard: { alignItems: 'flex-start', backgroundColor: 'rgba(200,241,53,0.06)', borderColor: zenith.colors.primaryBorder, flexDirection: 'row', gap: 12 },
  aiIcon: { alignItems: 'center', backgroundColor: zenith.colors.primarySoft, borderRadius: 999, height: 36, justifyContent: 'center', width: 36 },
  aiTextBlock: { flex: 1, gap: 4 },
  aiTitle: { color: zenith.colors.foreground, fontFamily: zenith.font.bodyBold },
  aiText: { color: zenith.colors.muted, fontFamily: zenith.font.body, fontSize: 12, lineHeight: 18 },
  quickGrid: { flexDirection: 'row', flexWrap: 'wrap', gap: 10 },
  quickLink: { backgroundColor: zenith.colors.card, borderColor: zenith.colors.border, borderRadius: 16, borderWidth: 1, color: zenith.colors.foreground, fontFamily: zenith.font.bodyBold, minWidth: '47%', padding: 15, textAlign: 'center' },
});
