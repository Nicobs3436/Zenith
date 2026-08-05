import { Check, RotateCcw, Sparkles, X } from 'lucide-react-native';
import { useEffect, useState } from 'react';
import { Pressable, StyleSheet, Text, View } from 'react-native';

import {
  acceptCoachPlanDraft,
  AiTrainingPlan,
  CoachState,
  generateCoachPlanDraft,
  getCoachState,
  reviseCoachPlanDraft,
  rejectCoachPlanDraft,
  resetCoach,
  sendCoachMessage,
} from '@/api/client';
import { Field } from '@/components/Field';
import { ZenithBottomNav, ZenithButton, ZenithCard, ZenithHeader, ZenithNotice, ZenithPill } from '@/components/ZenithUI';
import { ZenithScreen } from '@/components/ZenithScreen';
import { zenith } from '@/constants/zenithTheme';

const REQUIRED_LABELS: Record<string, string> = {
  personal_data_acknowledged: 'Aviso datos',
  goal: 'Objetivo',
  biological_sex: 'Sexo biologico',
  age: 'Edad',
  height_cm: 'Altura',
  weight_kg: 'Peso',
  experience_level: 'Nivel',
  days_per_week: 'Dias/semana',
  session_duration_minutes: 'Min/sesion',
  equipment: 'Equipamiento',
};

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

function phaseLabel(phase: CoachState['phase']) {
  const labels: Record<CoachState['phase'], string> = {
    onboarding: 'perfil',
    ready_for_plan: 'listo',
    plan_draft: 'borrador',
    training_active: 'activo',
  };
  return labels[phase];
}

function planRoutines(plan: AiTrainingPlan) {
  return asRecords(plan.plan_payload.routines);
}

function volumeEntries(plan: AiTrainingPlan) {
  return Object.entries(asRecord(plan.plan_payload.volume_by_muscle)).map(([muscle, raw]) => ({ muscle, data: asRecord(raw) }));
}

function resolutionSummary(plan: AiTrainingPlan) {
  return asRecord(asRecord(plan.plan_payload.exercise_resolution).summary);
}

function progressionSummary(plan: AiTrainingPlan) {
  const progression = asRecord(plan.plan_payload.progression_model);
  return [textValue(progression.type, ''), textValue(progression.load_rule, ''), textValue(progression.rep_rule, '')].filter(Boolean).join(' · ');
}

function coachReport(plan: AiTrainingPlan) {
  return asRecord(plan.plan_payload.coach_report);
}

function reportText(report: Record<string, unknown>, key: string) {
  const value = report[key];
  if (typeof value === 'string') return value;
  if (Array.isArray(value)) return value.filter((item) => typeof item === 'string').join(' · ');
  return '';
}

export default function CoachScreen() {
  const [state, setState] = useState<CoachState | null>(null);
  const [message, setMessage] = useState('');
  const [personalAck, setPersonalAck] = useState(false);
  const [sensitiveAck, setSensitiveAck] = useState(false);
  const [changes, setChanges] = useState<Record<string, string>>({});
  const [loading, setLoading] = useState(true);
  const [sending, setSending] = useState(false);
  const [generating, setGenerating] = useState(false);
  const [working, setWorking] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function loadState() {
    const loaded = await getCoachState();
    setState(loaded);
    setPersonalAck(loaded.profile.personal_data_acknowledged);
    setSensitiveAck(loaded.profile.sensitive_data_acknowledged);
  }

  useEffect(() => {
    let cancelled = false;
    getCoachState()
      .then((loaded) => {
        if (!cancelled) {
          setState(loaded);
          setPersonalAck(loaded.profile.personal_data_acknowledged);
          setSensitiveAck(loaded.profile.sensitive_data_acknowledged);
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
      const response = await sendCoachMessage({ message: text, personal_data_acknowledged: personalAck, sensitive_data_acknowledged: sensitiveAck });
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
    setGenerating(true);
    setError(null);
    setNotice(null);
    try {
      await generateCoachPlanDraft();
      await loadState();
      setNotice('Plan borrador creado. Revisalo antes de aceptar.');
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : 'No se pudo crear el plan.');
    } finally {
      setGenerating(false);
    }
  }

  async function submitAcceptPlan(planId: string) {
    setWorking(planId);
    setError(null);
    setNotice(null);
    try {
      await acceptCoachPlanDraft(planId);
      await loadState();
      setNotice('Plan aceptado. Se crearon tus rutinas reales.');
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
      await rejectCoachPlanDraft(planId);
      await loadState();
      setNotice('Plan rechazado. No se creo ninguna rutina.');
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : 'No se pudo rechazar el plan.');
    } finally {
      setWorking(null);
    }
  }

  async function submitModifyPlan(planId: string) {
    const instruction = changes[planId]?.trim();
    if (!instruction) return;
    setWorking(planId);
    setError(null);
    setNotice(null);
    try {
      await reviseCoachPlanDraft(planId, { instruction, sensitive_data_acknowledged: sensitiveAck });
      setChanges((current) => ({ ...current, [planId]: '' }));
      await loadState();
      setNotice('Coach creo una nueva version del plan con tus cambios.');
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : 'No se pudo modificar el plan.');
    } finally {
      setWorking(null);
    }
  }

  async function submitReset() {
    setSending(true);
    setError(null);
    setNotice(null);
    try {
      const response = await resetCoach();
      setState(response);
      setPersonalAck(false);
      setSensitiveAck(false);
      setMessage('');
      setChanges({});
      setNotice('Coach reiniciado. Tus rutinas y sesiones existentes no se tocaron.');
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : 'No se pudo reiniciar el Coach.');
    } finally {
      setSending(false);
    }
  }

  const draftPlans = state?.draft_plans ?? [];

  return (
    <ZenithScreen bottomNav={<ZenithBottomNav />}>
      <ZenithHeader title="Coach" subtitle="Entrenador personal IA" right={<View style={styles.headerIcon}><Sparkles color={zenith.colors.primary} size={15} /></View>} />
      <Text style={styles.subtitle}>Construye un perfil, disena un plan revisable y solo aplica rutinas cuando aceptas. Nada se modifica automaticamente.</Text>
      {notice && <ZenithNotice tone="success">{notice}</ZenithNotice>}
      {error && <ZenithNotice tone="danger">{error}</ZenithNotice>}
      {loading && <ZenithNotice>Cargando Coach...</ZenithNotice>}

      {state && (
        <ZenithCard style={styles.heroCard}>
          <View style={styles.heroHeader}>
            <View>
              <Text style={styles.kicker}>Estado</Text>
              <Text style={styles.heroTitle}>{phaseLabel(state.phase)}</Text>
            </View>
            <ZenithPill active={state.ready_for_plan}>{state.ready_for_plan ? 'listo para plan' : 'faltan datos'}</ZenithPill>
          </View>
          <Text style={styles.cardText}>{state.privacy_notice}</Text>
          <Text style={styles.risk}>{state.safety_notice}</Text>
        </ZenithCard>
      )}

      {state && (
        <ZenithCard style={styles.chatCard}>
          <Text style={styles.sectionTitle}>Conversacion</Text>
          {state.recent_messages.length === 0 && <View style={styles.assistantBubble}><Text style={styles.chatText}>{state.assistant_message}</Text></View>}
          {state.recent_messages.map((item, index) => (
            <View key={`${item.role}-${index}`} style={item.role === 'user' ? styles.userBubble : styles.assistantBubble}>
              <Text style={styles.chatText}>{item.content}</Text>
            </View>
          ))}
          <View style={styles.ackBox}>
            <Pressable onPress={() => setPersonalAck((current) => !current)} style={[styles.checkbox, personalAck && styles.checkboxChecked]}>
              <Text style={styles.checkboxText}>{personalAck ? 'Datos personales confirmados' : 'Confirmo uso de datos personales de entrenamiento'}</Text>
            </Pressable>
            <Pressable onPress={() => setSensitiveAck((current) => !current)} style={[styles.checkbox, sensitiveAck && styles.checkboxChecked]}>
              <Text style={styles.checkboxText}>{sensitiveAck ? 'Aviso medico confirmado' : 'Confirmo aviso medico si menciono dolor/lesiones'}</Text>
            </Pressable>
          </View>
          <Field label="Habla con tu Coach" multiline maxLength={1500} onChangeText={setMessage} placeholder="Ej: acepto el aviso. Tengo 29 anos, 180 cm, 80 kg, quiero hipertrofia, soy intermedio, 4 dias, 60 min, gimnasio completo..." value={message} />
          <View style={styles.actions}>
            <ZenithButton disabled={sending || !message.trim()} onPress={submitMessage} title={sending ? 'Enviando...' : 'Enviar mensaje'} />
            <Pressable disabled={!state.ready_for_plan || generating} onPress={submitGeneratePlan} style={[styles.primaryAction, (!state.ready_for_plan || generating) && styles.disabled]}>
              <Sparkles color={zenith.colors.primaryForeground} size={14} />
              <Text style={styles.primaryActionText}>{generating ? 'Creando vista previa...' : 'Generar vista previa'}</Text>
            </Pressable>
            <Pressable disabled={sending} onPress={submitReset} style={[styles.secondaryAction, sending && styles.disabled]}>
              <RotateCcw color={zenith.colors.muted} size={14} />
              <Text style={styles.secondaryActionText}>Reiniciar Coach</Text>
            </Pressable>
          </View>
        </ZenithCard>
      )}

      {state && (
        <ZenithCard style={styles.profileCard}>
          <Text style={styles.sectionTitle}>Lo que Coach sabe de ti</Text>
          <Text style={styles.profileLine}>Objetivo: {goalLabel(state.profile.goal)} · Nivel: {state.profile.experience_level ?? 'pendiente'}</Text>
          <Text style={styles.profileLine}>Sexo: {sexLabel(state.profile.biological_sex)} · Edad: {state.profile.age ?? '-'} · Altura: {state.profile.height_cm ?? '-'} cm · Peso: {state.profile.weight_kg ?? '-'} kg</Text>
          <Text style={styles.profileLine}>Disponibilidad: {state.profile.days_per_week ?? '-'} dias · {state.profile.session_duration_minutes ?? '-'} min</Text>
          <Text style={styles.profileLine}>Equipo: {state.profile.equipment.length ? state.profile.equipment.join(', ') : 'pendiente'}</Text>
          <Text style={styles.profileLine}>Prioridades: {state.profile.priorities.length ? state.profile.priorities.join(', ') : 'sin prioridad concreta'}</Text>
          <Text style={styles.profileLine}>Evitar: {state.profile.avoided_exercises.length ? state.profile.avoided_exercises.join(', ') : 'sin restricciones'}</Text>
          {state.known_facts.length > 0 && <Text style={styles.profileLine}>Hechos confirmados: {state.known_facts.slice(0, 5).join(' · ')}</Text>}
          {state.misunderstanding_corrections.length > 0 && <Text style={styles.correction}>Correcciones: {state.misunderstanding_corrections.join(' · ')}</Text>}
          {state.safety_flags.length > 0 && <Text style={styles.risk}>Avisos: {state.safety_flags.join(' · ')}</Text>}
          {state.missing_critical.length > 0 && <Text style={styles.profileLine}>Imprescindible por completar: {state.missing_critical.map((field) => REQUIRED_LABELS[field] ?? field).join(', ')}</Text>}
          {state.missing_useful.length > 0 && <Text style={styles.mutedLine}>Util para afinar: {state.missing_useful.slice(0, 8).join(', ')}</Text>}
          {state.estimated_fields.length > 0 && <Text style={styles.mutedLine}>Estimado inicialmente: {state.estimated_fields.join(', ')}</Text>}
        </ZenithCard>
      )}

      <View style={styles.block}>
        <Text style={styles.sectionTitle}>Plan revisable</Text>
        {draftPlans.length === 0 && <Text style={styles.empty}>Aun no hay vista previa. Completa la entrevista y pulsa Generar vista previa.</Text>}
        {draftPlans.map((plan) => (
          <ZenithCard key={plan.id} style={styles.planCard}>
            <View style={styles.cardHeader}>
              <Text style={styles.itemTitle}>{plan.days_per_week} dias · {goalLabel(plan.goal)}</Text>
              <ZenithPill active>{plan.provider}</ZenithPill>
            </View>
            <Text style={styles.cardText}>{plan.explanation}</Text>
            {plan.risk_notes && <Text style={styles.risk}>{plan.risk_notes}</Text>}
            <View style={styles.previewBox}>
              <Text style={styles.previewTitle}>Resumen IA</Text>
              <Text style={styles.cardText}>Split: {textValue(asRecord(plan.plan_payload.program_blueprint).split_name)}</Text>
              <Text style={styles.cardText}>Estrategia: {textValue(asRecord(plan.plan_payload.program_blueprint).strategy)}</Text>
              <Text style={styles.cardText}>Razonamiento: {textValue(asRecord(plan.plan_payload.coach_rationale).summary)}</Text>
            </View>
            <View style={styles.previewBox}>
              <Text style={styles.previewTitle}>Ejercicios</Text>
              <Text style={styles.cardText}>Catalogo: {textValue(resolutionSummary(plan).catalog_matched_count, '0')} · Nuevos IA: {textValue(resolutionSummary(plan).ai_generated_pending_count, '0')}</Text>
              <Text style={styles.cardText}>Los nuevos se crean como privados solo al aceptar.</Text>
            </View>
            <View style={styles.previewBox}>
              <Text style={styles.previewTitle}>Volumen semanal</Text>
              {volumeEntries(plan).slice(0, 8).map(({ muscle, data }) => (
                <Text key={`${plan.id}-${muscle}`} style={styles.cardText}>{muscle}: {textValue(data.direct_sets, '0')} series directas</Text>
              ))}
            </View>
            <View style={styles.previewBox}>
              <Text style={styles.previewTitle}>Progresion</Text>
              <Text style={styles.cardText}>{progressionSummary(plan) || textValue(plan.plan_payload.progression)}</Text>
            </View>
            {Object.keys(coachReport(plan)).length > 0 && (
              <View style={styles.previewBox}>
                <Text style={styles.previewTitle}>Informe del Coach</Text>
                {['user_data_summary', 'assumptions', 'measurable_goals', 'split_justification', 'fatigue_and_deload', 'tracking_template', 'nutrition_and_recovery', 'mistakes_to_avoid', 'next_review_questions'].map((key) => {
                  const value = reportText(coachReport(plan), key);
                  return value ? <Text key={key} style={styles.cardText}>{key.split('_').join(' ')}: {value}</Text> : null;
                })}
                {asRecords(coachReport(plan).scientific_references).slice(0, 6).map((reference, index) => (
                  <Text key={`${plan.id}-reference-${index}`} style={styles.note}>{textValue(reference.title, 'Referencia')} · {textValue(reference.year)} · {textValue(reference.evidence_level, 'evidencia')}</Text>
                ))}
              </View>
            )}
            {planRoutines(plan).map((routine, index) => (
              <View key={`${plan.id}-routine-${index}`} style={styles.routinePreview}>
                <Text style={styles.previewTitle}>Dia {textValue(routine.day, String(index + 1))}: {textValue(routine.name, 'Sesion')}</Text>
                <Text style={styles.cardText}>{textValue(routine.description)}</Text>
                {asRecords(routine.exercises).map((exercise, exerciseIndex) => (
                  <View key={`${plan.id}-routine-${index}-exercise-${exerciseIndex}`} style={styles.exercisePreview}>
                    <Text style={styles.exerciseName}>{exerciseIndex + 1}. {textValue(exercise.exercise_name, 'Ejercicio')}</Text>
                    <Text style={styles.cardText}>{textValue(exercise.exercise_source, 'ai_generated_pending')} · {textValue(exercise.primary_muscle)} · {textValue(exercise.target_sets, '0')}x{textValue(exercise.target_reps_min, '?')}-{textValue(exercise.target_reps_max, '?')} · RIR {textValue(exercise.target_rir)} · {textValue(exercise.rest_seconds)}s</Text>
                    <Text style={styles.cardText}>Motivo: {textValue(exercise.reason)}</Text>
                    {asStrings(exercise.technique_notes).map((note) => <Text key={note} style={styles.note}>Tecnica: {note}</Text>)}
                  </View>
                ))}
              </View>
            ))}
            <Field label="Pedir cambios" multiline maxLength={1000} onChangeText={(value) => setChanges((current) => ({ ...current, [plan.id]: value }))} placeholder="Ej: baja volumen de pierna y cambia press banca por mancuernas" value={changes[plan.id] ?? ''} />
            <View style={styles.inlineActions}>
              <Pressable disabled={working === plan.id} onPress={() => submitAcceptPlan(plan.id)} style={[styles.primaryAction, working === plan.id && styles.disabled]}>
                <Check color={zenith.colors.primaryForeground} size={14} />
                <Text style={styles.primaryActionText}>Aceptar y crear rutinas</Text>
              </Pressable>
              <Pressable disabled={working === plan.id || !changes[plan.id]?.trim()} onPress={() => submitModifyPlan(plan.id)} style={[styles.secondaryAction, (working === plan.id || !changes[plan.id]?.trim()) && styles.disabled]}>
                <Sparkles color={zenith.colors.muted} size={14} />
                <Text style={styles.secondaryActionText}>Crear version ajustada</Text>
              </Pressable>
              <Pressable disabled={working === plan.id} onPress={() => submitRejectPlan(plan.id)} style={[styles.dangerAction, working === plan.id && styles.disabled]}>
                <X color="#fecaca" size={14} />
                <Text style={styles.dangerActionText}>Rechazar</Text>
              </Pressable>
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
  heroCard: { borderColor: zenith.colors.primaryBorder, gap: 12 },
  heroHeader: { alignItems: 'center', flexDirection: 'row', justifyContent: 'space-between' },
  kicker: { color: zenith.colors.cyan, fontFamily: zenith.font.bodyBold, fontSize: 12, letterSpacing: 1.5, textTransform: 'uppercase' },
  heroTitle: { color: zenith.colors.foreground, fontFamily: zenith.font.display, fontSize: 34, lineHeight: 38, textTransform: 'uppercase' },
  chatCard: { borderColor: zenith.colors.primaryBorder, gap: 12 },
  profileCard: { gap: 10 },
  block: { gap: 12 },
  sectionTitle: { color: zenith.colors.foreground, fontFamily: zenith.font.display, fontSize: 24, lineHeight: 27, textTransform: 'uppercase' },
  assistantBubble: { alignSelf: 'flex-start', backgroundColor: zenith.colors.secondary, borderColor: zenith.colors.border, borderRadius: 16, borderWidth: 1, maxWidth: '92%', padding: 12 },
  userBubble: { alignSelf: 'flex-end', backgroundColor: zenith.colors.primarySoft, borderColor: zenith.colors.primaryBorder, borderRadius: 16, borderWidth: 1, maxWidth: '92%', padding: 12 },
  chatText: { color: zenith.colors.foreground, fontFamily: zenith.font.body, lineHeight: 20 },
  ackBox: { backgroundColor: zenith.colors.card, borderColor: zenith.colors.border, borderRadius: 16, borderWidth: 1, gap: 10, padding: 12 },
  checkbox: { alignItems: 'center', borderColor: zenith.colors.border, borderRadius: 12, borderWidth: 1, padding: 12 },
  checkboxChecked: { backgroundColor: zenith.colors.primarySoft, borderColor: zenith.colors.primary },
  checkboxText: { color: zenith.colors.foreground, fontFamily: zenith.font.bodyBold, textAlign: 'center' },
  actions: { gap: 10 },
  inlineActions: { gap: 10, marginTop: 4 },
  primaryAction: { alignItems: 'center', backgroundColor: zenith.colors.primary, borderRadius: 12, flexDirection: 'row', gap: 7, justifyContent: 'center', padding: 12 },
  primaryActionText: { color: zenith.colors.primaryForeground, fontFamily: zenith.font.bodyBold },
  secondaryAction: { alignItems: 'center', borderColor: zenith.colors.border, borderRadius: 12, borderWidth: 1, flexDirection: 'row', gap: 7, justifyContent: 'center', padding: 12 },
  secondaryActionText: { color: zenith.colors.muted, fontFamily: zenith.font.bodyBold },
  dangerAction: { alignItems: 'center', backgroundColor: zenith.colors.dangerSoft, borderColor: 'rgba(232,64,64,0.35)', borderRadius: 12, borderWidth: 1, flexDirection: 'row', gap: 7, justifyContent: 'center', padding: 12 },
  dangerActionText: { color: '#fecaca', fontFamily: zenith.font.bodyBold },
  disabled: { opacity: 0.55 },
  checkGrid: { flexDirection: 'row', flexWrap: 'wrap', gap: 8 },
  checkItem: { borderColor: zenith.colors.border, borderRadius: 999, borderWidth: 1, paddingHorizontal: 10, paddingVertical: 7 },
  checkItemDone: { backgroundColor: zenith.colors.primarySoft, borderColor: zenith.colors.primaryBorder },
  checkText: { color: zenith.colors.foreground, fontFamily: zenith.font.bodyBold, fontSize: 12 },
  profileLine: { color: zenith.colors.foreground, fontFamily: zenith.font.body, lineHeight: 20 },
  mutedLine: { color: zenith.colors.muted, fontFamily: zenith.font.body, lineHeight: 20 },
  correction: { color: zenith.colors.cyan, fontFamily: zenith.font.bodyBold, lineHeight: 20 },
  cardHeader: { alignItems: 'center', flexDirection: 'row', gap: 10, justifyContent: 'space-between' },
  itemTitle: { color: zenith.colors.foreground, flex: 1, fontFamily: zenith.font.bodyBold, fontSize: 16, lineHeight: 21 },
  cardText: { color: zenith.colors.muted, fontFamily: zenith.font.body, lineHeight: 20 },
  planCard: { gap: 10 },
  previewBox: { backgroundColor: zenith.colors.secondary, borderColor: zenith.colors.border, borderRadius: 14, borderWidth: 1, gap: 5, padding: 12 },
  previewTitle: { color: zenith.colors.foreground, fontFamily: zenith.font.bodyBold, lineHeight: 20 },
  routinePreview: { backgroundColor: zenith.colors.card, borderColor: zenith.colors.primaryBorder, borderRadius: 14, borderWidth: 1, gap: 8, padding: 12 },
  exercisePreview: { borderColor: zenith.colors.border, borderRadius: 12, borderWidth: 1, gap: 4, padding: 10 },
  exerciseName: { color: zenith.colors.foreground, fontFamily: zenith.font.bodyBold, lineHeight: 20 },
  note: { color: zenith.colors.cyan, fontFamily: zenith.font.body, lineHeight: 19 },
  risk: { color: '#fca5a5', fontFamily: zenith.font.bodyBold, lineHeight: 20 },
  empty: { backgroundColor: zenith.colors.card, borderColor: zenith.colors.border, borderRadius: 16, borderWidth: 1, color: zenith.colors.muted, fontFamily: zenith.font.body, padding: 16 },
});
