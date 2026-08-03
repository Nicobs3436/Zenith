import { Check, Sparkles, X } from 'lucide-react-native';
import { useEffect, useState } from 'react';
import { Pressable, StyleSheet, Text, View } from 'react-native';

import {
  acceptCoachV2Proposal,
  acceptTrainingPlan,
  AiTrainingPlan,
  CoachV2State,
  generateCoachV2Plan,
  generateCoachV2PlannedSession,
  getCoachV2State,
  getTrainingPlans,
  rejectCoachV2Proposal,
  rejectTrainingPlan,
  resetCoachV2,
  sendCoachV2Message,
} from '@/api/client';
import { Field } from '@/components/Field';
import { ZenithBottomNav, ZenithButton, ZenithCard, ZenithHeader, ZenithNotice, ZenithPill } from '@/components/ZenithUI';
import { ZenithScreen } from '@/components/ZenithScreen';
import { zenith } from '@/constants/zenithTheme';

function fieldLabel(field: string) {
  const labels: Record<string, string> = {
    personal_data_acknowledged: 'aviso de datos personales',
    goal: 'objetivo',
    biological_sex: 'sexo biologico',
    age: 'edad',
    height_cm: 'altura',
    weight_kg: 'peso',
    experience_level: 'nivel',
    days_per_week: 'dias por semana',
    session_duration_minutes: 'minutos por sesion',
    equipment: 'equipamiento',
  };
  return labels[field] ?? field;
}

function goalLabel(value: string | null) {
  const labels: Record<string, string> = {
    strength: 'Fuerza',
    hypertrophy: 'Hipertrofia',
    fat_loss: 'Perdida de grasa',
    general_health: 'Salud general',
    endurance: 'Resistencia',
  };
  return value ? labels[value] ?? value : 'pendiente';
}

function sexLabel(value: string | null) {
  if (value === 'male') return 'Masculino';
  if (value === 'female') return 'Femenino';
  return 'pendiente';
}

function planRoutines(plan: AiTrainingPlan) {
  const routines = plan.plan_payload.routines;
  return Array.isArray(routines) ? routines.filter((item): item is Record<string, unknown> => typeof item === 'object' && item !== null) : [];
}

function asRecord(value: unknown): Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value) ? value as Record<string, unknown> : {};
}

function asRecords(value: unknown): Record<string, unknown>[] {
  return Array.isArray(value) ? value.filter((item): item is Record<string, unknown> => typeof item === 'object' && item !== null) : [];
}

function asStrings(value: unknown): string[] {
  return Array.isArray(value) ? value.filter((item): item is string => typeof item === 'string' && item.trim().length > 0) : [];
}

function textValue(value: unknown, fallback = '-') {
  if (typeof value === 'string' && value.trim()) return value;
  if (typeof value === 'number') return String(value);
  return fallback;
}

function volumeEntries(plan: AiTrainingPlan) {
  const volume = asRecord(plan.plan_payload.volume_by_muscle);
  return Object.entries(volume).map(([muscle, raw]) => ({ muscle, data: asRecord(raw) }));
}

function resolutionSummary(plan: AiTrainingPlan) {
  return asRecord(asRecord(plan.plan_payload.exercise_resolution).summary);
}

function progressionSummary(plan: AiTrainingPlan) {
  const progression = asRecord(plan.plan_payload.progression_model);
  return [textValue(progression.type, ''), textValue(progression.load_rule, ''), textValue(progression.rep_rule, '')].filter(Boolean).join(' · ');
}

function isV3Plan(plan: AiTrainingPlan) {
  return plan.plan_payload.version === 3;
}

export default function CoachScreen() {
  const [state, setState] = useState<CoachV2State | null>(null);
  const [plans, setPlans] = useState<AiTrainingPlan[]>([]);
  const [message, setMessage] = useState('');
  const [personalAck, setPersonalAck] = useState(false);
  const [sensitiveAck, setSensitiveAck] = useState(false);
  const [loading, setLoading] = useState(true);
  const [sending, setSending] = useState(false);
  const [generatingPlan, setGeneratingPlan] = useState(false);
  const [generatingSession, setGeneratingSession] = useState(false);
  const [working, setWorking] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function loadAll() {
    const [loadedState, loadedPlans] = await Promise.all([getCoachV2State(), getTrainingPlans()]);
    setState(loadedState);
    setPlans(loadedPlans);
    setPersonalAck(loadedState.profile.personal_data_acknowledged);
    setSensitiveAck(loadedState.profile.sensitive_data_acknowledged);
  }

  useEffect(() => {
    let cancelled = false;
    Promise.all([getCoachV2State(), getTrainingPlans()])
      .then(([loadedState, loadedPlans]) => {
        if (!cancelled) {
          setState(loadedState);
          setPlans(loadedPlans);
          setPersonalAck(loadedState.profile.personal_data_acknowledged);
          setSensitiveAck(loadedState.profile.sensitive_data_acknowledged);
        }
      })
      .catch((caught) => {
        if (!cancelled) setError(caught instanceof Error ? caught.message : 'No se pudo cargar el Coach.');
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  async function submitMessage() {
    const text = message.trim();
    if (!text) return;
    setSending(true);
    setError(null);
    setNotice(null);
    try {
      const response = await sendCoachV2Message({ message: text, personal_data_acknowledged: personalAck, sensitive_data_acknowledged: sensitiveAck });
      setState(response);
      setPersonalAck(response.profile.personal_data_acknowledged);
      setSensitiveAck(response.profile.sensitive_data_acknowledged);
      setMessage('');
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : 'No se pudo enviar el mensaje.');
    } finally {
      setSending(false);
    }
  }

  async function submitGeneratePlan() {
    setGeneratingPlan(true);
    setError(null);
    setNotice(null);
    try {
      await generateCoachV2Plan();
      await loadAll();
      setNotice('Plan borrador generado. Revisalo y aceptalo para crear rutinas reales.');
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : 'No se pudo generar el plan.');
    } finally {
      setGeneratingPlan(false);
    }
  }

  async function submitGenerateSession() {
    setGeneratingSession(true);
    setError(null);
    setNotice(null);
    try {
      await generateCoachV2PlannedSession();
      await loadAll();
      setNotice('Proxima sesion recomendada creada.');
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : 'No se pudo crear la sesion recomendada.');
    } finally {
      setGeneratingSession(false);
    }
  }

  async function submitAcceptPlan(planId: string) {
    setWorking(planId);
    setError(null);
    setNotice(null);
    try {
      await acceptTrainingPlan(planId);
      await loadAll();
      setNotice('Plan aceptado. Se crearon rutinas reales.');
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : 'No se pudo aceptar el plan.');
    } finally {
      setWorking(null);
    }
  }

  async function submitRejectPlan(planId: string) {
    setWorking(planId);
    setError(null);
    setNotice(null);
    try {
      await rejectTrainingPlan(planId);
      await loadAll();
      setNotice('Plan rechazado. No se crearon rutinas.');
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : 'No se pudo rechazar el plan.');
    } finally {
      setWorking(null);
    }
  }

  async function reviewProposal(proposalId: string, accept: boolean) {
    setWorking(proposalId);
    setError(null);
    setNotice(null);
    try {
      if (accept) await acceptCoachV2Proposal(proposalId);
      else await rejectCoachV2Proposal(proposalId);
      await loadAll();
      setNotice(accept ? 'Propuesta aceptada.' : 'Propuesta rechazada.');
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : 'No se pudo revisar la propuesta.');
    } finally {
      setWorking(null);
    }
  }

  async function submitReset() {
    setSending(true);
    setError(null);
    setNotice(null);
    try {
      const response = await resetCoachV2();
      setState(response);
      setPersonalAck(false);
      setSensitiveAck(false);
      setMessage('');
      setNotice('Coach reiniciado.');
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : 'No se pudo reiniciar el Coach.');
    } finally {
      setSending(false);
    }
  }

  const readyForPlan = state?.ready_for_plan ?? false;
  const draftPlans = plans.filter((plan) => plan.status === 'draft');

  return (
    <ZenithScreen bottomNav={<ZenithBottomNav />}>
      <ZenithHeader title="Coach" subtitle="Entrenador personal" right={<View style={styles.headerIcon}><Sparkles color={zenith.colors.primary} size={15} /></View>} />
      <Text style={styles.subtitle}>Coach V2 crea planes cientificos revisables, analiza progreso y propone ajustes. Nada se aplica sin tu aceptacion.</Text>
      {notice && <ZenithNotice tone="success">{notice}</ZenithNotice>}
      {error && <ZenithNotice tone="danger">{error}</ZenithNotice>}
      {loading && <ZenithNotice>Cargando Coach...</ZenithNotice>}

      {state && (
        <ZenithCard style={styles.chatCard}>
          <Text style={styles.sectionTitle}>Entrevista profesional</Text>
          <Text style={styles.privacy}>{state.privacy_notice}</Text>
          {state.conversation.recent_messages.length === 0 && <View style={styles.assistantBubble}><Text style={styles.chatText}>{state.assistant_message}</Text></View>}
          {state.conversation.recent_messages.map((item, index) => (
            <View key={`${item.role}-${index}`} style={item.role === 'user' ? styles.userBubble : styles.assistantBubble}>
              <Text style={styles.chatText}>{item.content}</Text>
            </View>
          ))}
          {state.missing_required_fields.length > 0 && <Text style={styles.missing}>Falta: {state.missing_required_fields.map(fieldLabel).join(', ')}</Text>}
          <View style={styles.ackBox}>
            <Text style={styles.ackTitle}>Datos personales obligatorios</Text>
            <Text style={styles.ackText}>Para un plan serio, Coach necesita sexo biologico, edad, altura y peso. Se usan solo para ajustar entrenamiento.</Text>
            <Pressable onPress={() => setPersonalAck((current) => !current)} style={[styles.checkbox, personalAck && styles.checkboxChecked]}>
              <Text style={styles.checkboxText}>{personalAck ? 'Aviso de datos personales confirmado' : 'Confirmo el aviso de datos personales'}</Text>
            </Pressable>
            <Pressable onPress={() => setSensitiveAck((current) => !current)} style={[styles.checkbox, sensitiveAck && styles.checkboxChecked]}>
              <Text style={styles.checkboxText}>{sensitiveAck ? 'Aviso medico confirmado' : 'Confirmo el aviso si menciono dolor o limitaciones'}</Text>
            </Pressable>
          </View>
          <Field label="Habla con tu Coach" multiline maxLength={1200} onChangeText={setMessage} placeholder="Ej: acepto. Mi objetivo es hipertrofia..." value={message} />
          <View style={styles.actions}>
            <ZenithButton disabled={sending || !message.trim()} onPress={submitMessage} title={sending ? 'Enviando...' : 'Enviar'} />
            <Pressable disabled={!readyForPlan || generatingPlan} onPress={submitGeneratePlan} style={[styles.primaryAction, (!readyForPlan || generatingPlan) && styles.disabled]}>
              <Text style={styles.primaryActionText}>{generatingPlan ? 'Generando...' : 'Generar plan cientifico'}</Text>
            </Pressable>
            <Pressable disabled={sending} onPress={submitReset} style={[styles.secondaryAction, sending && styles.disabled]}>
              <Text style={styles.secondaryActionText}>Reiniciar Coach</Text>
            </Pressable>
          </View>
        </ZenithCard>
      )}

      {state && (
        <ZenithCard style={styles.profileCard}>
          <Text style={styles.sectionTitle}>Perfil resumido</Text>
          <Text style={styles.profileLine}>Objetivo: {goalLabel(state.profile.goal)}</Text>
          <Text style={styles.profileLine}>Sexo biologico: {sexLabel(state.profile.biological_sex)} · Edad: {state.profile.age ?? 'pendiente'} · Altura: {state.profile.height_cm ?? 'pendiente'} cm · Peso: {state.profile.weight_kg ?? 'pendiente'} kg</Text>
          <Text style={styles.profileLine}>Nivel: {state.profile.experience_level ?? 'pendiente'} · {state.profile.days_per_week ?? '-'} dias · {state.profile.session_duration_minutes ?? '-'} min</Text>
          <Text style={styles.profileLine}>Equipo: {state.profile.equipment.length > 0 ? state.profile.equipment.join(', ') : 'pendiente'}</Text>
          <Text style={styles.profileLine}>Prioridades: {state.profile.priorities.length > 0 ? state.profile.priorities.join(', ') : 'sin prioridad concreta'}</Text>
          <Text style={styles.profileLine}>Evitar: {state.profile.avoided_exercises.length > 0 ? state.profile.avoided_exercises.join(', ') : 'sin restricciones de ejercicios'}</Text>
        </ZenithCard>
      )}

      {state && state.proposals.length > 0 && (
        <View style={styles.block}>
          <Text style={styles.sectionTitle}>Propuestas automaticas</Text>
          {state.proposals.map((proposal) => (
            <ZenithCard key={proposal.id} style={styles.itemCard}>
              <View style={styles.cardHeader}><Text style={styles.itemTitle}>{proposal.recommendation}</Text><ZenithPill active={proposal.status === 'pending'}>{proposal.status}</ZenithPill></View>
              <Text style={styles.cardText}>{proposal.explanation}</Text>
              {proposal.status === 'pending' && (
                <View style={styles.inlineActions}>
                  <Pressable disabled={working === proposal.id} onPress={() => reviewProposal(proposal.id, true)} style={[styles.primaryAction, working === proposal.id && styles.disabled]}><Check color={zenith.colors.primaryForeground} size={13} /><Text style={styles.primaryActionText}>Aceptar</Text></Pressable>
                  <Pressable disabled={working === proposal.id} onPress={() => reviewProposal(proposal.id, false)} style={[styles.secondaryAction, working === proposal.id && styles.disabled]}><X color={zenith.colors.muted} size={13} /><Text style={styles.secondaryActionText}>Rechazar</Text></Pressable>
                </View>
              )}
            </ZenithCard>
          ))}
        </View>
      )}

      <View style={styles.block}>
        <View style={styles.cardHeader}>
          <Text style={styles.sectionTitle}>Proxima sesion</Text>
          <Pressable disabled={generatingSession} onPress={submitGenerateSession} style={[styles.secondaryAction, generatingSession && styles.disabled]}><Text style={styles.secondaryActionText}>{generatingSession ? 'Creando...' : 'Crear recomendacion'}</Text></Pressable>
        </View>
        {state?.planned_sessions.length === 0 && <Text style={styles.empty}>Aun no hay sesiones recomendadas.</Text>}
        {state?.planned_sessions.map((session) => <ZenithCard key={session.id} style={styles.itemCard}><Text style={styles.itemTitle}>{session.title}</Text><Text style={styles.cardText}>{session.rationale}</Text></ZenithCard>)}
      </View>

      <View style={styles.block}>
        <Text style={styles.sectionTitle}>Planes revisables</Text>
        {draftPlans.length === 0 && <Text style={styles.empty}>Aun no hay planes en borrador.</Text>}
        {draftPlans.map((plan) => (
          <ZenithCard key={plan.id} style={styles.itemCard}>
            <View style={styles.cardHeader}><Text style={styles.itemTitle}>{plan.days_per_week} dias · {goalLabel(plan.goal)}</Text><ZenithPill active>{plan.status}</ZenithPill></View>
            <Text style={styles.cardText}>{plan.explanation}</Text>
            {plan.risk_notes && <Text style={styles.risk}>{plan.risk_notes}</Text>}
            {isV3Plan(plan) ? (
              <View style={styles.previewBlock}>
                <View style={styles.previewBox}>
                  <Text style={styles.previewTitle}>Resumen IA</Text>
                  <Text style={styles.cardText}>Split: {textValue(asRecord(plan.plan_payload.program_blueprint).split_name)}</Text>
                  <Text style={styles.cardText}>Estrategia: {textValue(asRecord(plan.plan_payload.program_blueprint).strategy)}</Text>
                  <Text style={styles.cardText}>Por que: {textValue(asRecord(plan.plan_payload.coach_rationale).summary)}</Text>
                </View>
                <View style={styles.previewBox}>
                  <Text style={styles.previewTitle}>Ejercicios</Text>
                  <Text style={styles.cardText}>Existentes: {textValue(resolutionSummary(plan).catalog_matched_count, '0')} · Nuevos IA: {textValue(resolutionSummary(plan).ai_generated_pending_count, '0')}</Text>
                  <Text style={styles.cardText}>Los nuevos se crean en tu catalogo privado solo si aceptas el plan.</Text>
                </View>
                <View style={styles.previewBox}>
                  <Text style={styles.previewTitle}>Volumen semanal</Text>
                  {volumeEntries(plan).slice(0, 8).map(({ muscle, data }) => (
                    <Text key={`${plan.id}-volume-${muscle}`} style={styles.cardText}>{muscle}: {textValue(data.direct_sets, '0')} series directas · rango {asStrings(data.target_range).join('-') || (Array.isArray(data.target_range) ? data.target_range.join('-') : '-')}</Text>
                  ))}
                </View>
                <View style={styles.previewBox}>
                  <Text style={styles.previewTitle}>Progresion</Text>
                  <Text style={styles.cardText}>{progressionSummary(plan) || textValue(plan.plan_payload.progression)}</Text>
                </View>
                {planRoutines(plan).map((routine, index) => (
                  <View key={`${plan.id}-routine-${index}`} style={styles.routinePreview}>
                    <Text style={styles.previewTitle}>Dia {textValue(routine.day, String(index + 1))}: {textValue(routine.name, 'Sesion')}</Text>
                    <Text style={styles.cardText}>{textValue(routine.description)}</Text>
                    {asRecords(routine.exercises).map((exercise, exerciseIndex) => (
                      <View key={`${plan.id}-routine-${index}-exercise-${exerciseIndex}`} style={styles.exercisePreview}>
                        <Text style={styles.exerciseName}>{exerciseIndex + 1}. {textValue(exercise.exercise_name, 'Ejercicio')}</Text>
                        <Text style={styles.cardText}>{textValue(exercise.exercise_source, 'ai_generated_pending')} · {textValue(exercise.primary_muscle)} · {textValue(exercise.target_sets, '0')}x{textValue(exercise.target_reps_min, '?')}-{textValue(exercise.target_reps_max, '?')} · RIR {textValue(exercise.target_rir)} · descanso {textValue(exercise.rest_seconds)}s</Text>
                        <Text style={styles.cardText}>Motivo: {textValue(exercise.reason)}</Text>
                      </View>
                    ))}
                  </View>
                ))}
              </View>
            ) : (
              planRoutines(plan).slice(0, 3).map((routine, index) => <Text key={`${plan.id}-${index}`} style={styles.cardText}>Dia {index + 1}: {typeof routine.name === 'string' ? routine.name : 'Sesion'} · {Array.isArray(routine.exercises) ? routine.exercises.length : 0} ejercicios</Text>)
            )}
            <View style={styles.inlineActions}>
              <Pressable disabled={working === plan.id} onPress={() => submitAcceptPlan(plan.id)} style={[styles.primaryAction, working === plan.id && styles.disabled]}><Text style={styles.primaryActionText}>Aceptar y crear rutinas</Text></Pressable>
              <Pressable disabled={working === plan.id} onPress={() => submitRejectPlan(plan.id)} style={[styles.secondaryAction, working === plan.id && styles.disabled]}><Text style={styles.secondaryActionText}>Rechazar</Text></Pressable>
            </View>
          </ZenithCard>
        ))}
      </View>
    </ZenithScreen>
  );
}

const styles = StyleSheet.create({
  headerIcon: { alignItems: 'center', backgroundColor: zenith.colors.primarySoft, borderRadius: 999, height: 38, justifyContent: 'center', width: 38 },
  subtitle: { color: zenith.colors.muted, fontFamily: zenith.font.body, fontSize: 14, lineHeight: 22 },
  chatCard: { borderColor: zenith.colors.primaryBorder, gap: 12 },
  profileCard: { gap: 8 },
  block: { gap: 12 },
  sectionTitle: { color: zenith.colors.foreground, fontFamily: zenith.font.display, fontSize: 24, lineHeight: 27, textTransform: 'uppercase' },
  privacy: { color: zenith.colors.cyan, fontFamily: zenith.font.bodyMedium, lineHeight: 20 },
  assistantBubble: { alignSelf: 'flex-start', backgroundColor: zenith.colors.secondary, borderColor: zenith.colors.border, borderRadius: 16, borderWidth: 1, maxWidth: '92%', padding: 12 },
  userBubble: { alignSelf: 'flex-end', backgroundColor: zenith.colors.primarySoft, borderColor: zenith.colors.primaryBorder, borderRadius: 16, borderWidth: 1, maxWidth: '92%', padding: 12 },
  chatText: { color: zenith.colors.foreground, fontFamily: zenith.font.body, lineHeight: 20 },
  missing: { color: zenith.colors.amber, fontFamily: zenith.font.bodyBold, lineHeight: 20 },
  ackBox: { backgroundColor: zenith.colors.dangerSoft, borderColor: 'rgba(232,64,64,0.28)', borderRadius: 16, borderWidth: 1, gap: 10, padding: 14 },
  ackTitle: { color: '#fecaca', fontFamily: zenith.font.bodyBold, fontSize: 16 },
  ackText: { color: '#fca5a5', fontFamily: zenith.font.body, lineHeight: 20 },
  checkbox: { alignItems: 'center', borderColor: zenith.colors.border, borderRadius: 12, borderWidth: 1, padding: 12 },
  checkboxChecked: { backgroundColor: zenith.colors.primarySoft, borderColor: zenith.colors.primary },
  checkboxText: { color: zenith.colors.foreground, fontFamily: zenith.font.bodyBold, textAlign: 'center' },
  actions: { gap: 10 },
  inlineActions: { gap: 10, marginTop: 6 },
  primaryAction: { alignItems: 'center', backgroundColor: zenith.colors.primary, borderRadius: 12, flexDirection: 'row', gap: 7, justifyContent: 'center', padding: 12 },
  primaryActionText: { color: zenith.colors.primaryForeground, fontFamily: zenith.font.bodyBold },
  secondaryAction: { alignItems: 'center', borderColor: zenith.colors.border, borderRadius: 12, borderWidth: 1, flexDirection: 'row', gap: 7, justifyContent: 'center', padding: 12 },
  secondaryActionText: { color: zenith.colors.muted, fontFamily: zenith.font.bodyBold },
  disabled: { opacity: 0.55 },
  profileLine: { color: zenith.colors.foreground, fontFamily: zenith.font.body, lineHeight: 20 },
  itemCard: { gap: 9 },
  cardHeader: { alignItems: 'center', flexDirection: 'row', gap: 10, justifyContent: 'space-between' },
  itemTitle: { color: zenith.colors.foreground, flex: 1, fontFamily: zenith.font.bodyBold, fontSize: 16, lineHeight: 21 },
  cardText: { color: zenith.colors.muted, fontFamily: zenith.font.body, lineHeight: 20 },
  previewBlock: { gap: 10 },
  previewBox: { backgroundColor: zenith.colors.secondary, borderColor: zenith.colors.border, borderRadius: 14, borderWidth: 1, gap: 5, padding: 12 },
  previewTitle: { color: zenith.colors.foreground, fontFamily: zenith.font.bodyBold, lineHeight: 20 },
  routinePreview: { backgroundColor: zenith.colors.card, borderColor: zenith.colors.primaryBorder, borderRadius: 14, borderWidth: 1, gap: 8, padding: 12 },
  exercisePreview: { borderColor: zenith.colors.border, borderRadius: 12, borderWidth: 1, gap: 4, padding: 10 },
  exerciseName: { color: zenith.colors.foreground, fontFamily: zenith.font.bodyBold, lineHeight: 20 },
  risk: { color: '#fca5a5', fontFamily: zenith.font.bodyBold, lineHeight: 20 },
  empty: { backgroundColor: zenith.colors.card, borderColor: zenith.colors.border, borderRadius: 16, borderWidth: 1, color: zenith.colors.muted, fontFamily: zenith.font.body, padding: 16 },
});
