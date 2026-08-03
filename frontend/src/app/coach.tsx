import { Link, useLocalSearchParams } from 'expo-router';
import { Check, Sparkles, X, Zap } from 'lucide-react-native';
import { useEffect, useState } from 'react';
import { Pressable, StyleSheet, Text, View } from 'react-native';

import {
  acceptAiSuggestion,
  acceptTrainingPlan,
  AiCoachIntake,
  AiCoachQuestionResponse,
  AiCoachQuestionType,
  AiSuggestion,
  AiTrainingPlan,
  askCoachQuestion,
  generateAiSuggestions,
  generateTrainingPlanFromCoachIntake,
  generateTrainingPlan,
  getAiSuggestions,
  getCoachIntake,
  getRoutines,
  getTrainingPlan,
  getTrainingPlans,
  getWorkoutSessions,
  modifyTrainingPlan,
  rejectAiSuggestion,
  rejectTrainingPlan,
  resetCoachIntake,
  Routine,
  sendCoachIntakeMessage,
  TrainingPlanGoal,
  TrainingPlanLevel,
  WorkoutSession,
} from '@/api/client';
import { Field } from '@/components/Field';
import { SegmentedField } from '@/components/SegmentedField';
import { ZenithBottomNav, ZenithButton, ZenithCard, ZenithHeader, ZenithNotice, ZenithPill } from '@/components/ZenithUI';
import { ZenithScreen } from '@/components/ZenithScreen';
import { zenith } from '@/constants/zenithTheme';
import {
  AiSuggestionFilter,
  aiSuggestionChangeSummary,
  aiSuggestionConfidenceLabel,
  aiSuggestionDataSummary,
  aiSuggestionFilterLabel,
  aiSuggestionPrivacyLabel,
  aiSuggestionProviderLabel,
  aiSuggestionStatusLabel,
  aiSuggestionTypeLabel,
} from '@/utils/coachDisplay';

const FILTERS: AiSuggestionFilter[] = ['pending', 'accepted', 'rejected', 'expired', 'all'];

const GOALS: { label: string; value: TrainingPlanGoal }[] = [
  { label: 'Hipertrofia', value: 'hypertrophy' },
  { label: 'Fuerza', value: 'strength' },
  { label: 'Perdida grasa', value: 'fat_loss' },
  { label: 'Salud', value: 'general_health' },
  { label: 'Resistencia', value: 'endurance' },
];

const LEVELS: { label: string; value: TrainingPlanLevel }[] = [
  { label: 'Principiante', value: 'beginner' },
  { label: 'Intermedio', value: 'intermediate' },
  { label: 'Avanzado', value: 'advanced' },
];

const QUESTION_TYPES: { label: string; value: AiCoachQuestionType }[] = [
  { label: 'Proxima', value: 'next_workout' },
  { label: 'Progresion', value: 'progression' },
  { label: 'Fatiga', value: 'fatigue' },
  { label: 'Rutina', value: 'routine_review' },
  { label: 'Stats', value: 'stats_explanation' },
];

type CoachTab = 'chat' | 'suggestions' | 'questions' | 'plans';

function paramValue(value: string | string[] | undefined) {
  return Array.isArray(value) ? value[0] : value;
}

function tabFromParam(value: string | string[] | undefined): CoachTab {
  const current = paramValue(value);
  if (current === 'suggestions' || current === 'questions' || current === 'plans') {
    return current;
  }
  return 'chat';
}

function splitCsv(value: string) {
  return value.split(',').map((item) => item.trim()).filter(Boolean);
}

function routinesFromPlan(plan: AiTrainingPlan) {
  const routines = plan.plan_payload.routines;
  return Array.isArray(routines) ? routines.filter((item): item is Record<string, unknown> => typeof item === 'object' && item !== null) : [];
}

function exercisesFromPlanRoutine(routine: Record<string, unknown>) {
  const exercises = routine.exercises;
  return Array.isArray(exercises) ? exercises.filter((item): item is Record<string, unknown> => typeof item === 'object' && item !== null) : [];
}

function textValue(value: unknown) {
  return typeof value === 'string' || typeof value === 'number' ? String(value) : '';
}

function planExerciseSummary(exercise: Record<string, unknown>) {
  const name = textValue(exercise.exercise_name) || 'Ejercicio';
  const sets = textValue(exercise.target_sets) || '-';
  const repsMin = textValue(exercise.target_reps_min) || '-';
  const repsMax = textValue(exercise.target_reps_max) || '-';
  const rest = textValue(exercise.rest_seconds) || '-';
  const rpe = textValue(exercise.target_rpe) || '-';
  const rir = textValue(exercise.target_rir) || '-';
  return `${name}: ${sets} series · ${repsMin}-${repsMax} reps · ${rest}s · RPE ${rpe} · RIR ${rir}`;
}

function progressionFromPlan(plan: AiTrainingPlan) {
  const progression = plan.plan_payload.progression;
  return typeof progression === 'string' ? progression : null;
}

function includesSensitiveModification(value: string) {
  const normalized = value.normalize('NFD').replace(/[\u0300-\u036f]/g, '').toLowerCase();
  return ['dolor', 'lesion', 'molestia', 'rodilla', 'limitacion'].some((marker) => normalized.includes(marker));
}

function modifiedFrom(plan: AiTrainingPlan) {
  const value = plan.input_summary.modified_from_plan_id;
  return typeof value === 'string' ? value : null;
}

function providerInfo(provider: string, model: string | null, fallbackUsed: boolean) {
  const modelLabel = model ? ` · ${model}` : '';
  const fallback = fallbackUsed ? ' · fallback interno' : '';
  return `${provider}${modelLabel}${fallback}`;
}

function providerSummary(plan: AiTrainingPlan) {
  return providerInfo(plan.provider, plan.model, plan.fallback_used);
}

function planDate(value: string | null) {
  return value ? new Date(value).toLocaleString('es-ES') : 'pendiente';
}

function coachFieldLabel(field: string) {
  const labels: Record<string, string> = {
    goal: 'objetivo',
    level: 'nivel',
    days_per_week: 'dias/semana',
    session_duration_minutes: 'minutos/sesion',
    available_equipment: 'equipamiento',
    priorities: 'prioridades',
    physical_limitations: 'limitaciones',
  };
  return labels[field] ?? field;
}

function intakeSummaryText(intake: AiCoachIntake | null) {
  if (!intake) {
    return 'Sin resumen todavia.';
  }
  const summary = intake.intake_summary;
  const parts = [
    ['Objetivo', summary.goal],
    ['Nivel', summary.level],
    ['Dias', summary.days_per_week],
    ['Duracion', summary.session_duration_minutes],
    ['Equipo', Array.isArray(summary.available_equipment) ? summary.available_equipment.join(', ') : null],
    ['Prioridades', Array.isArray(summary.priorities) ? summary.priorities.join(', ') : null],
  ]
    .filter(([, value]) => value !== null && value !== undefined && value !== '')
    .map(([label, value]) => `${label}: ${value}`);
  return parts.length > 0 ? parts.join(' · ') : 'Sin resumen todavia.';
}

function routineNameById(routineId: string | null, routines: Routine[]) {
  if (!routineId) {
    return 'Sesion libre';
  }
  return routines.find((routine) => routine.id === routineId)?.name ?? 'Rutina no encontrada';
}

export default function CoachScreen() {
  const { tab } = useLocalSearchParams();
  const [activeTab, setActiveTab] = useState<CoachTab>(() => tabFromParam(tab));
  const [suggestions, setSuggestions] = useState<AiSuggestion[]>([]);
  const [intake, setIntake] = useState<AiCoachIntake | null>(null);
  const [chatMessage, setChatMessage] = useState('');
  const [chatAcknowledged, setChatAcknowledged] = useState(false);
  const [chatSending, setChatSending] = useState(false);
  const [chatGeneratingPlan, setChatGeneratingPlan] = useState(false);
  const [filter, setFilter] = useState<AiSuggestionFilter>('pending');
  const [goal, setGoal] = useState<TrainingPlanGoal>('hypertrophy');
  const [level, setLevel] = useState<TrainingPlanLevel>('beginner');
  const [daysPerWeek, setDaysPerWeek] = useState('3');
  const [duration, setDuration] = useState('60');
  const [equipment, setEquipment] = useState('');
  const [priorities, setPriorities] = useState('');
  const [physicalLimitations, setPhysicalLimitations] = useState('');
  const [acknowledged, setAcknowledged] = useState(false);
  const [plans, setPlans] = useState<AiTrainingPlan[]>([]);
  const [routines, setRoutines] = useState<Routine[]>([]);
  const [sessions, setSessions] = useState<WorkoutSession[]>([]);
  const [questionType, setQuestionType] = useState<AiCoachQuestionType>('next_workout');
  const [questionRoutineId, setQuestionRoutineId] = useState<string | null>(null);
  const [questionDetail, setQuestionDetail] = useState('');
  const [questionResponse, setQuestionResponse] = useState<AiCoachQuestionResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [generating, setGenerating] = useState(false);
  const [saving, setSaving] = useState(false);
  const [asking, setAsking] = useState(false);
  const [working, setWorking] = useState<string | null>(null);
  const [modificationInputs, setModificationInputs] = useState<Record<string, string>>({});
  const [modificationAcks, setModificationAcks] = useState<Record<string, boolean>>({});
  const [expandedPlanId, setExpandedPlanId] = useState<string | null>(null);
  const [planDetails, setPlanDetails] = useState<Record<string, AiTrainingPlan>>({});
  const [planDetailLoading, setPlanDetailLoading] = useState<string | null>(null);
  const [planDetailErrors, setPlanDetailErrors] = useState<Record<string, string>>({});
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  const visibleSuggestions = filter === 'all' ? suggestions : suggestions.filter((suggestion) => suggestion.status === filter);
  const pendingSuggestions = suggestions.filter((suggestion) => suggestion.status === 'pending').length;
  const draftPlans = plans.filter((plan) => plan.status === 'draft').length;

  async function loadSuggestions() {
    const items = await getAiSuggestions();
    setSuggestions(items);
  }

  async function loadPlans() {
    const items = await getTrainingPlans();
    setPlans(items);
  }

  async function loadIntake() {
    const item = await getCoachIntake();
    setIntake(item);
    setChatAcknowledged(item.sensitive_data_acknowledged);
  }

  useEffect(() => {
    let cancelled = false;
    Promise.all([getAiSuggestions(), getTrainingPlans(), getRoutines(), getWorkoutSessions(), getCoachIntake()])
      .then(([loadedSuggestions, loadedPlans, loadedRoutines, loadedSessions, loadedIntake]) => {
        if (!cancelled) {
          setSuggestions(loadedSuggestions);
          setPlans(loadedPlans);
          setRoutines(loadedRoutines);
          setSessions(loadedSessions);
          setIntake(loadedIntake);
          setChatAcknowledged(loadedIntake.sensitive_data_acknowledged);
          setQuestionRoutineId((current) => current ?? loadedRoutines[0]?.id ?? null);
        }
      })
      .catch((caught) => {
        if (!cancelled) {
          setError(caught instanceof Error ? caught.message : 'No se pudo cargar el entrenador.');
        }
      })
      .finally(() => {
        if (!cancelled) {
          setLoading(false);
        }
      });
    return () => {
      cancelled = true;
    };
  }, []);

  async function submitGenerateSuggestions() {
    setGenerating(true);
    setError(null);
    setNotice(null);
    try {
      const generated = await generateAiSuggestions();
      await loadSuggestions();
      setNotice(generated.length > 0 ? `Se encontraron ${generated.length} sugerencias aplicables.` : 'No hay cambios aplicables con el historial actual.');
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : 'No se pudieron generar sugerencias.');
    } finally {
      setGenerating(false);
    }
  }

  async function submitAcceptSuggestion(suggestionId: string) {
    setWorking(suggestionId);
    setError(null);
    setNotice(null);
    try {
      await acceptAiSuggestion(suggestionId);
      await loadSuggestions();
      setNotice('Sugerencia aceptada. La rutina fue actualizada automaticamente.');
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : 'No se pudo aceptar la sugerencia.');
    } finally {
      setWorking(null);
    }
  }

  async function submitRejectSuggestion(suggestionId: string) {
    setWorking(suggestionId);
    setError(null);
    setNotice(null);
    try {
      await rejectAiSuggestion(suggestionId);
      await loadSuggestions();
      setNotice('Sugerencia rechazada. No se modifico la rutina.');
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : 'No se pudo rechazar la sugerencia.');
    } finally {
      setWorking(null);
    }
  }

  async function submitQuestion() {
    if (questionType === 'routine_review' && !questionRoutineId) {
      setError('Selecciona una rutina para revisar.');
      return;
    }

    setAsking(true);
    setError(null);
    setNotice(null);
    setQuestionResponse(null);
    try {
      const response = await askCoachQuestion({
        question_type: questionType,
        routine_id: questionRoutineId || null,
        detail: questionDetail.trim() || null,
      });
      setQuestionResponse(response);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : 'No se pudo responder la pregunta.');
    } finally {
      setAsking(false);
    }
  }

  async function submitGeneratePlan() {
    const parsedDays = Number(daysPerWeek);
    const parsedDuration = Number(duration);
    if (!Number.isInteger(parsedDays) || parsedDays < 1 || parsedDays > 7) {
      setError('Los dias por semana deben estar entre 1 y 7.');
      return;
    }
    if (!Number.isInteger(parsedDuration) || parsedDuration < 20 || parsedDuration > 180) {
      setError('La duracion debe estar entre 20 y 180 minutos.');
      return;
    }
    if (physicalLimitations.trim() && !acknowledged) {
      setError('Confirma el aviso de datos sensibles para usar limitaciones fisicas.');
      return;
    }

    setSaving(true);
    setError(null);
    setNotice(null);
    try {
      await generateTrainingPlan({
        goal,
        level,
        days_per_week: parsedDays,
        session_duration_minutes: parsedDuration,
        available_equipment: splitCsv(equipment),
        physical_limitations: physicalLimitations.trim() || null,
        sensitive_data_acknowledged: acknowledged,
        priorities: splitCsv(priorities),
      });
      await loadPlans();
      setNotice('Plan generado. Revisalo y aceptalo para crear las rutinas reales.');
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : 'No se pudo generar el plan.');
    } finally {
      setSaving(false);
    }
  }

  async function submitChatMessage() {
    const message = chatMessage.trim();
    if (!message) {
      return;
    }
    setChatSending(true);
    setError(null);
    setNotice(null);
    try {
      const response = await sendCoachIntakeMessage({ message, sensitive_data_acknowledged: chatAcknowledged });
      setIntake(response);
      setChatAcknowledged(response.sensitive_data_acknowledged);
      setChatMessage('');
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : 'No se pudo enviar el mensaje al coach.');
    } finally {
      setChatSending(false);
    }
  }

  async function submitGeneratePlanFromChat() {
    setChatGeneratingPlan(true);
    setError(null);
    setNotice(null);
    try {
      await generateTrainingPlanFromCoachIntake();
      await Promise.all([loadPlans(), loadIntake()]);
      setActiveTab('plans');
      setNotice('Plan generado desde el chat. Revisalo y aceptalo para crear rutinas reales.');
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : 'No se pudo generar el plan desde el chat.');
    } finally {
      setChatGeneratingPlan(false);
    }
  }

  async function submitResetChat() {
    setChatSending(true);
    setError(null);
    setNotice(null);
    try {
      const response = await resetCoachIntake();
      setIntake(response);
      setChatAcknowledged(false);
      setChatMessage('');
      setNotice('Entrevista reiniciada.');
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : 'No se pudo reiniciar el chat.');
    } finally {
      setChatSending(false);
    }
  }

  async function submitAcceptPlan(planId: string) {
    setWorking(planId);
    setError(null);
    setNotice(null);
    try {
      await acceptTrainingPlan(planId);
      await loadPlans();
      setNotice('Plan aceptado. Se crearon rutinas reales automaticamente.');
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
      await loadPlans();
      setNotice('Plan rechazado. No se crearon rutinas.');
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : 'No se pudo rechazar el plan.');
    } finally {
      setWorking(null);
    }
  }

  async function submitModifyPlan(planId: string) {
    const instruction = modificationInputs[planId]?.trim() ?? '';
    const acknowledgedSensitiveData = modificationAcks[planId] ?? false;
    if (instruction.length < 3) {
      setError('Describe que quieres cambiar del plan.');
      return;
    }
    if (includesSensitiveModification(instruction) && !acknowledgedSensitiveData) {
      setError('Confirma el aviso de datos sensibles para pedir cambios por dolor, lesion o limitaciones.');
      return;
    }

    setWorking(planId);
    setError(null);
    setNotice(null);
    try {
      await modifyTrainingPlan(planId, {
        instruction,
        sensitive_data_acknowledged: acknowledgedSensitiveData,
      });
      setModificationInputs((current) => ({ ...current, [planId]: '' }));
      setModificationAcks((current) => ({ ...current, [planId]: false }));
      await loadPlans();
      setNotice('Se genero una nueva version del plan. El plan original no cambio.');
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : 'No se pudo modificar el plan.');
    } finally {
      setWorking(null);
    }
  }

  async function togglePlanDetail(planId: string) {
    if (expandedPlanId === planId) {
      setExpandedPlanId(null);
      return;
    }

    setExpandedPlanId(planId);
    if (planDetails[planId] || planDetailLoading === planId) {
      return;
    }

    setPlanDetailLoading(planId);
    setPlanDetailErrors((current) => ({ ...current, [planId]: '' }));
    try {
      const detail = await getTrainingPlan(planId);
      setPlanDetails((current) => ({ ...current, [planId]: detail }));
    } catch (caught) {
      setPlanDetailErrors((current) => ({
        ...current,
        [planId]: caught instanceof Error ? caught.message : 'No se pudo cargar el detalle del plan.',
      }));
    } finally {
      setPlanDetailLoading(null);
    }
  }

  return (
    <ZenithScreen bottomNav={<ZenithBottomNav />}>
      <ZenithHeader title="Coach IA" subtitle="IA personal" right={<View style={styles.headerIcon}><Sparkles color={zenith.colors.primary} size={15} /></View>} />
      <Text style={styles.subtitle}>IA interna local: no envia datos fuera y no usa notas. Las sugerencias y planes solo modifican rutinas al aceptarlos.</Text>
      <View style={styles.warningBox}>
        <Text style={styles.warningTitle}>Aviso medico</Text>
        <Text style={styles.warningText}>No aceptes cambios si hay dolor, lesion, mareo o tecnica peor. Zenith no sustituye consejo medico ni profesional.</Text>
      </View>
      <View style={styles.tabs}>
        <Pressable onPress={() => setActiveTab('chat')} style={[styles.tab, activeTab === 'chat' && styles.tabActive]}>
          <Text style={[styles.tabText, activeTab === 'chat' && styles.tabTextActive]}>Chat</Text>
        </Pressable>
        <Pressable onPress={() => setActiveTab('suggestions')} style={[styles.tab, activeTab === 'suggestions' && styles.tabActive]}>
          <Text style={[styles.tabText, activeTab === 'suggestions' && styles.tabTextActive]}>Sugerencias{pendingSuggestions > 0 ? ` (${pendingSuggestions})` : ''}</Text>
        </Pressable>
        <Pressable onPress={() => setActiveTab('questions')} style={[styles.tab, activeTab === 'questions' && styles.tabActive]}>
          <Text style={[styles.tabText, activeTab === 'questions' && styles.tabTextActive]}>Preguntas</Text>
        </Pressable>
        <Pressable onPress={() => setActiveTab('plans')} style={[styles.tab, activeTab === 'plans' && styles.tabActive]}>
          <Text style={[styles.tabText, activeTab === 'plans' && styles.tabTextActive]}>Planes{draftPlans > 0 ? ` (${draftPlans})` : ''}</Text>
        </Pressable>
      </View>
      {notice && <ZenithNotice tone="success">{notice}</ZenithNotice>}
      {error && <ZenithNotice tone="danger">{error}</ZenithNotice>}

      {activeTab === 'chat' && (
        <View style={styles.sectionBlock}>
          <ZenithCard style={styles.chatBox}>
            <Text style={styles.questionTitle}>Entrenador personal</Text>
            <Text style={styles.questionText}>Responde por bloques. Zenith guarda solo un resumen estructurado y los ultimos mensajes necesarios.</Text>
            {loading && <ZenithNotice>Cargando entrevista...</ZenithNotice>}
            {intake?.assistant_message && intake.recent_messages.length === 0 && <View style={styles.assistantBubble}><Text style={styles.chatText}>{intake.assistant_message}</Text></View>}
            {intake?.recent_messages.map((message, index) => (
              <View key={`${message.role}-${index}`} style={message.role === 'user' ? styles.userBubble : styles.assistantBubble}>
                <Text style={styles.chatText}>{message.content}</Text>
              </View>
            ))}
            {intake?.safety_warning && <ZenithNotice tone="danger">{intake.safety_warning}</ZenithNotice>}
            <View style={styles.detailBox}>
              <Text style={styles.detailTitle}>Resumen actual</Text>
              <Text style={styles.detailText}>{intakeSummaryText(intake)}</Text>
              {intake && intake.missing_required_fields.length > 0 && <Text style={styles.detailText}>Falta: {intake.missing_required_fields.map(coachFieldLabel).join(', ')}</Text>}
              {intake && intake.missing_required_fields.length === 0 && intake.useful_missing_fields.length > 0 && <Text style={styles.detailText}>Opcional: {intake.useful_missing_fields.map(coachFieldLabel).join(', ')}</Text>}
            </View>
            <Field
              label="Mensaje al coach"
              maxLength={1000}
              multiline
              onChangeText={setChatMessage}
              placeholder="Ej: quiero hipertrofia, soy principiante, 3 dias, 60 minutos, tengo mancuernas..."
              value={chatMessage}
            />
            <View style={styles.sensitiveBox}>
              <Text style={styles.sensitiveTitle}>Limitaciones fisicas</Text>
              <Text style={styles.sensitiveText}>Si mencionas dolor, lesion o limitaciones, confirma el aviso para que puedan usarse al adaptar el plan. No sustituye consejo medico.</Text>
              <Pressable onPress={() => setChatAcknowledged((current) => !current)} style={[styles.checkbox, chatAcknowledged && styles.checkboxChecked]}>
                <Text style={styles.checkboxText}>{chatAcknowledged ? 'Aviso confirmado' : 'Confirmo el aviso si incluyo datos sensibles'}</Text>
              </Pressable>
            </View>
            <View style={styles.actions}>
              <ZenithButton disabled={chatSending || !chatMessage.trim()} onPress={submitChatMessage} title={chatSending ? 'Enviando...' : 'Enviar'} />
              <Pressable disabled={!intake?.ready_for_plan || chatGeneratingPlan} onPress={submitGeneratePlanFromChat} style={[styles.acceptButton, (!intake?.ready_for_plan || chatGeneratingPlan) && styles.disabled]}>
                <Text style={styles.acceptText}>{chatGeneratingPlan ? 'Generando...' : 'Generar plan revisable'}</Text>
              </Pressable>
              <Pressable disabled={chatSending} onPress={submitResetChat} style={[styles.rejectButton, chatSending && styles.disabled]}>
                <Text style={styles.rejectText}>Reiniciar entrevista</Text>
              </Pressable>
            </View>
            {intake && <Text style={styles.providerText}>Proveedor IA: {providerInfo(intake.provider, intake.model, intake.fallback_used)}</Text>}
          </ZenithCard>
        </View>
      )}

      {activeTab === 'suggestions' && (
        <View style={styles.sectionBlock}>
          <ZenithButton disabled={generating || loading} icon={<Zap color={zenith.colors.primaryForeground} fill={zenith.colors.primaryForeground} size={15} />} onPress={submitGenerateSuggestions} title={generating ? 'Analizando...' : 'Generar sugerencias'} />
          <SegmentedField
            label="Filtro"
            onValueChange={(value) => setFilter(value as AiSuggestionFilter)}
            options={FILTERS.map((item) => ({ label: aiSuggestionFilterLabel(item), value: item }))}
            selectedValue={filter}
          />
          {loading && <ZenithNotice>Cargando sugerencias...</ZenithNotice>}
          {!loading && suggestions.length === 0 && <ZenithNotice>No hay sugerencias todavia. Registra varias sesiones y genera un analisis.</ZenithNotice>}
          {!loading && suggestions.length > 0 && visibleSuggestions.length === 0 && <ZenithNotice>No hay sugerencias para este filtro.</ZenithNotice>}
          {visibleSuggestions.map((suggestion) => {
            const isPending = suggestion.status === 'pending';
            const isWorking = working === suggestion.id;
            return (
              <ZenithCard key={suggestion.id} style={styles.card}>
                <View style={styles.cardHeader}>
                  <Text style={styles.type}>{aiSuggestionTypeLabel(suggestion.type)}</Text>
                  <ZenithPill active={isPending}>{aiSuggestionStatusLabel(suggestion.status)}</ZenithPill>
                </View>
                <Text style={styles.recommendation}>{suggestion.recommendation}</Text>
                <Text style={styles.explanation}>{suggestion.explanation}</Text>
                <View style={styles.metaRow}>
                  <Text style={styles.metaPill}>{aiSuggestionProviderLabel(suggestion.input_summary)}</Text>
                  <Text style={styles.metaPill}>{aiSuggestionConfidenceLabel(suggestion.confidence)}</Text>
                </View>
                {suggestion.risk_notes && (
                  <View style={styles.riskBox}>
                    <Text style={styles.detailTitle}>Notas de riesgo</Text>
                    <Text style={styles.detailText}>{suggestion.risk_notes}</Text>
                  </View>
                )}
                <View style={styles.detailBox}>
                  <Text style={styles.detailTitle}>Que cambiara</Text>
                  <Text style={styles.detailText}>{aiSuggestionChangeSummary(suggestion)}</Text>
                </View>
                <View style={styles.detailBox}>
                  <Text style={styles.detailTitle}>Datos usados</Text>
                  <Text style={styles.detailText}>{aiSuggestionDataSummary(suggestion)}</Text>
                </View>
                <Text style={styles.privacy}>{aiSuggestionPrivacyLabel(suggestion.input_summary)}</Text>
                {isPending && (
                  <View style={styles.actions}>
                    <Pressable disabled={isWorking} onPress={() => submitAcceptSuggestion(suggestion.id)} style={[styles.acceptButton, isWorking && styles.disabled]}>
                      <Check color={zenith.colors.primaryForeground} size={13} />
                      <Text style={styles.acceptText}>{isWorking ? 'Aplicando...' : 'Aceptar y aplicar'}</Text>
                    </Pressable>
                    <Pressable disabled={isWorking} onPress={() => submitRejectSuggestion(suggestion.id)} style={[styles.rejectButton, isWorking && styles.disabled]}>
                      <X color={zenith.colors.muted} size={13} />
                      <Text style={styles.rejectText}>Rechazar</Text>
                    </Pressable>
                  </View>
                )}
              </ZenithCard>
            );
          })}
        </View>
      )}

      {activeTab === 'questions' && (
        <View style={styles.sectionBlock}>
          <ZenithCard style={styles.questionBox}>
            <Text style={styles.questionTitle}>Preguntas guiadas</Text>
            <Text style={styles.questionText}>Sin chat libre: no se guardan y no modifican rutinas, sesiones ni planes.</Text>
            <SegmentedField label="Pregunta" onValueChange={(value) => setQuestionType(value as AiCoachQuestionType)} options={QUESTION_TYPES} selectedValue={questionType} />
            <View style={styles.routineSelector}>
              <Text style={styles.routineSelectorLabel}>Rutina para contexto</Text>
              {routines.length === 0 && <Text style={styles.emptyInline}>No hay rutinas todavia.</Text>}
              {routines.slice(0, 4).map((routine) => (
                <Pressable
                  key={routine.id}
                  onPress={() => setQuestionRoutineId(routine.id)}
                  style={[styles.routineOption, questionRoutineId === routine.id && styles.routineOptionSelected]}
                >
                  <Text style={[styles.routineOptionText, questionRoutineId === routine.id && styles.routineOptionTextSelected]}>{routine.name}</Text>
                </Pressable>
              ))}
            </View>
            <Field
              label="Detalle opcional"
              maxLength={500}
              multiline
              onChangeText={setQuestionDetail}
              placeholder="Ej: quiero saber si subir peso o repetir carga"
              value={questionDetail}
            />
            <ZenithButton disabled={asking} onPress={submitQuestion} title={asking ? 'Preguntando...' : 'Preguntar'} />
            {questionResponse && (
              <View style={styles.answerBox}>
                <Text style={styles.answerTitle}>Respuesta</Text>
                <Text style={styles.cardText}>{questionResponse.answer}</Text>
                <Text style={styles.providerText}>Proveedor IA: {providerInfo(questionResponse.provider, questionResponse.model, questionResponse.fallback_used)}</Text>
                {questionResponse.key_points.map((point, index) => <Text key={`point-${index}`} style={styles.answerItem}>- {point}</Text>)}
                {questionResponse.suggested_actions.map((action, index) => <Text key={`action-${index}`} style={styles.actionItem}>Accion: {action}</Text>)}
              </View>
            )}
          </ZenithCard>
          <ZenithCard style={styles.summarySectionBox}>
            <Text style={styles.questionTitle}>Resumenes post-sesion</Text>
            <Text style={styles.questionText}>Genera o revisa resumenes IA desde el detalle de cada sesion. El resumen no modifica rutinas ni registros.</Text>
            {loading && <Text style={styles.emptyInline}>Cargando sesiones...</Text>}
            {!loading && sessions.length === 0 && <Text style={styles.emptyInline}>Todavia no hay sesiones para resumir.</Text>}
            {sessions.slice(0, 4).map((session) => (
              <ZenithCard key={session.id} style={styles.sessionSummaryCard}>
                <Text style={styles.sessionTitle}>{new Date(session.started_at).toLocaleDateString()} · {routineNameById(session.routine_id, routines)}</Text>
                <Text style={styles.cardText}>{session.sets.length} series registradas</Text>
                <Link href={{ pathname: '/session-detail', params: { sessionId: session.id } }} style={styles.summaryLink}>Abrir y generar resumen IA</Link>
              </ZenithCard>
            ))}
          </ZenithCard>
        </View>
      )}

      {activeTab === 'plans' && (
        <View style={styles.sectionBlock}>
          <ZenithCard style={styles.planForm}>
            <Text style={styles.questionTitle}>Plan adaptativo</Text>
            <Text style={styles.questionText}>La IA genera una rutina por dia disponible. Al aceptar, se crean rutinas reales en tu cuenta.</Text>
            <SegmentedField label="Objetivo" onValueChange={(value) => setGoal(value as TrainingPlanGoal)} options={GOALS} selectedValue={goal} />
            <SegmentedField label="Nivel" onValueChange={(value) => setLevel(value as TrainingPlanLevel)} options={LEVELS} selectedValue={level} />
            <View style={styles.grid}>
              <Field keyboardType="numeric" label="Dias por semana" onChangeText={setDaysPerWeek} value={daysPerWeek} />
              <Field keyboardType="numeric" label="Minutos por sesion" onChangeText={setDuration} value={duration} />
            </View>
            <Field label="Equipamiento disponible" onChangeText={setEquipment} placeholder="mancuernas, barra, polea" value={equipment} />
            <Field label="Prioridades" onChangeText={setPriorities} placeholder="pecho, fuerza, espalda" value={priorities} />
            <View style={styles.sensitiveBox}>
              <Text style={styles.sensitiveTitle}>Datos sensibles opcionales</Text>
              <Text style={styles.sensitiveText}>Las limitaciones fisicas pueden ser datos sensibles. Se usaran solo para generar este plan y no sustituyen consejo medico ni profesional. Evita anadir diagnosticos o detalles innecesarios.</Text>
              <Field label="Limitaciones fisicas opcionales" multiline onChangeText={setPhysicalLimitations} value={physicalLimitations} />
              <Pressable onPress={() => setAcknowledged((current) => !current)} style={[styles.checkbox, acknowledged && styles.checkboxChecked]}>
                <Text style={styles.checkboxText}>{acknowledged ? 'Confirmado' : 'Confirmo que entiendo el aviso de datos sensibles'}</Text>
              </Pressable>
            </View>
            <ZenithButton disabled={saving} onPress={submitGeneratePlan} title={saving ? 'Generando...' : 'Generar plan'} />
          </ZenithCard>
          <Text style={styles.section}>Mis planes</Text>
          {loading && <Text style={styles.empty}>Cargando planes...</Text>}
          {!loading && plans.length === 0 && <Text style={styles.empty}>Todavia no hay planes generados.</Text>}
          {plans.map((plan) => (
            <ZenithCard key={plan.id} style={styles.card}>
              <View style={styles.cardHeader}>
                <Text style={styles.cardTitle}>{plan.days_per_week} dias · {plan.goal}</Text>
                <ZenithPill active={plan.status === 'draft'}>{plan.status}</ZenithPill>
              </View>
              <Text style={styles.cardText}>{plan.explanation}</Text>
              {modifiedFrom(plan) && <Text style={styles.versionText}>Version modificada de otro plan.</Text>}
              <Text style={styles.providerText}>Proveedor IA: {providerSummary(plan)}</Text>
              <Pressable onPress={() => togglePlanDetail(plan.id)} style={styles.detailToggle}>
                <Text style={styles.detailToggleText}>{expandedPlanId === plan.id ? 'Ocultar detalle' : 'Ver detalle'}</Text>
              </Pressable>
              {expandedPlanId === plan.id && (
                <View style={styles.planDetailBox}>
                  {planDetailLoading === plan.id && <Text style={styles.emptyInline}>Cargando detalle...</Text>}
                  {planDetailErrors[plan.id] && <Text style={styles.risk}>{planDetailErrors[plan.id]}</Text>}
                  {planDetails[plan.id] && <PlanTechnicalDetail plan={planDetails[plan.id]} />}
                </View>
              )}
              {plan.risk_notes && <Text style={styles.risk}>{plan.risk_notes}</Text>}
              {routinesFromPlan(plan).map((routine, index) => (
                <View key={`${plan.id}-${index}`} style={styles.routineBox}>
                  <Text style={styles.routineTitle}>{textValue(routine.name) || `Dia ${index + 1}`}</Text>
                  <Text style={styles.cardText}>{exercisesFromPlanRoutine(routine).length} ejercicios</Text>
                  {exercisesFromPlanRoutine(routine).slice(0, 5).map((exercise, exerciseIndex) => (
                    <Text key={`${plan.id}-${index}-${exerciseIndex}`} style={styles.exerciseLine}>{planExerciseSummary(exercise)}</Text>
                  ))}
                </View>
              ))}
              {progressionFromPlan(plan) && <Text style={styles.progressionText}>Progresion: {progressionFromPlan(plan)}</Text>}
              {plan.status === 'draft' && (
                <View style={styles.draftBox}>
                  <Text style={styles.modifyTitle}>Pedir cambios antes de aceptar</Text>
                  <Text style={styles.modifyText}>Se creara una nueva version draft. Esta version queda disponible para comparar o aceptar.</Text>
                  <Field
                    label="Modificacion solicitada"
                    multiline
                    onChangeText={(value) => setModificationInputs((current) => ({ ...current, [plan.id]: value }))}
                    placeholder="Ej: hazlo a 4 dias, menos volumen, mas espalda"
                    value={modificationInputs[plan.id] ?? ''}
                  />
                  <Text style={styles.sensitiveText}>Si incluyes dolor, lesion o limitaciones fisicas, confirma que entiendes que son datos sensibles y que se usaran solo para generar esta version del plan.</Text>
                  <Pressable
                    onPress={() => setModificationAcks((current) => ({ ...current, [plan.id]: !current[plan.id] }))}
                    style={[styles.checkbox, modificationAcks[plan.id] && styles.checkboxChecked]}
                  >
                    <Text style={styles.checkboxText}>{modificationAcks[plan.id] ? 'Aviso confirmado' : 'Confirmo el aviso si mi cambio incluye datos sensibles'}</Text>
                  </Pressable>
                  <Pressable disabled={working === plan.id} onPress={() => submitModifyPlan(plan.id)} style={[styles.modifyButton, working === plan.id && styles.disabled]}>
                    <Text style={styles.modifyButtonText}>{working === plan.id ? 'Procesando...' : 'Generar version modificada'}</Text>
                  </Pressable>
                  <View style={styles.actions}>
                    <Pressable disabled={working === plan.id} onPress={() => submitAcceptPlan(plan.id)} style={[styles.acceptButton, working === plan.id && styles.disabled]}>
                      <Text style={styles.acceptText}>Aceptar y crear rutinas</Text>
                    </Pressable>
                    <Pressable disabled={working === plan.id} onPress={() => submitRejectPlan(plan.id)} style={[styles.rejectButton, working === plan.id && styles.disabled]}>
                      <Text style={styles.rejectText}>Rechazar</Text>
                    </Pressable>
                  </View>
                </View>
              )}
            </ZenithCard>
          ))}
        </View>
      )}
    </ZenithScreen>
  );
}

function PlanTechnicalDetail({ plan }: { plan: AiTrainingPlan }) {
  return (
    <View style={styles.planDetailContent}>
      <Text style={styles.detailTitle}>Detalle tecnico</Text>
      <Text style={styles.detailText}>Creado: {planDate(plan.created_at)}</Text>
      <Text style={styles.detailText}>Revisado: {planDate(plan.reviewed_at)}</Text>
      <Text style={styles.detailText}>Duracion: {plan.days_per_week} dias · {plan.session_duration_minutes} min/sesion</Text>
      <Text style={styles.detailText}>Equipo: {plan.available_equipment.length > 0 ? plan.available_equipment.join(', ') : 'sin preferencia'}</Text>
      <Text style={styles.detailText}>Prioridades: {plan.priorities.length > 0 ? plan.priorities.join(', ') : 'sin prioridad concreta'}</Text>
      <Text style={styles.detailText}>Confianza: {plan.confidence ?? 'no indicada'} · {providerSummary(plan)}</Text>
    </View>
  );
}

const styles = StyleSheet.create({
  headerIcon: { alignItems: 'center', backgroundColor: zenith.colors.primarySoft, borderRadius: 999, height: 38, justifyContent: 'center', width: 38 },
  subtitle: { color: zenith.colors.muted, fontFamily: zenith.font.body, fontSize: 14, lineHeight: 22 },
  warningBox: { backgroundColor: zenith.colors.dangerSoft, borderColor: 'rgba(232,64,64,0.28)', borderRadius: 14, borderWidth: 1, gap: 6, padding: 12 },
  warningTitle: { color: '#fecaca', fontFamily: zenith.font.bodyBold },
  warningText: { color: '#fca5a5', fontFamily: zenith.font.body, lineHeight: 20 },
  tabs: { borderBottomColor: zenith.colors.border, borderBottomWidth: 1, flexDirection: 'row', gap: 0 },
  tab: { alignItems: 'center', borderBottomColor: 'transparent', borderBottomWidth: 2, flex: 1, marginBottom: -1, paddingVertical: 10 },
  tabActive: { borderBottomColor: zenith.colors.primary },
  tabText: { color: zenith.colors.muted, fontFamily: zenith.font.bodyBold, fontSize: 12 },
  tabTextActive: { color: zenith.colors.primary },
  sectionBlock: { gap: 12 },
  card: { borderColor: zenith.colors.border, gap: 10 },
  cardHeader: { alignItems: 'center', flexDirection: 'row', justifyContent: 'space-between', gap: 10 },
  type: { color: zenith.colors.foreground, flex: 1, fontFamily: zenith.font.display, fontSize: 22, lineHeight: 24, textTransform: 'uppercase' },
  recommendation: { color: zenith.colors.foreground, fontFamily: zenith.font.bodyBold, fontSize: 16 },
  explanation: { color: zenith.colors.muted, fontFamily: zenith.font.body, lineHeight: 21 },
  metaRow: { flexDirection: 'row', flexWrap: 'wrap', gap: 8 },
  metaPill: { backgroundColor: zenith.colors.secondary, borderRadius: 999, color: zenith.colors.primary, fontFamily: zenith.font.mono, fontSize: 10, overflow: 'hidden', paddingHorizontal: 10, paddingVertical: 5 },
  detailBox: { backgroundColor: zenith.colors.background, borderRadius: 12, gap: 5, padding: 10 },
  riskBox: { backgroundColor: zenith.colors.dangerSoft, borderColor: 'rgba(232,64,64,0.28)', borderRadius: 12, borderWidth: 1, gap: 5, padding: 10 },
  detailTitle: { color: zenith.colors.primary, fontFamily: zenith.font.mono, fontSize: 10, textTransform: 'uppercase' },
  detailText: { color: zenith.colors.foreground, fontFamily: zenith.font.body, lineHeight: 20 },
  privacy: { color: zenith.colors.cyan, fontFamily: zenith.font.bodyMedium, fontSize: 12 },
  actions: { gap: 10 },
  acceptButton: { alignItems: 'center', backgroundColor: zenith.colors.primary, borderRadius: 12, flexDirection: 'row', gap: 7, justifyContent: 'center', padding: 12 },
  acceptText: { color: zenith.colors.primaryForeground, fontFamily: zenith.font.bodyBold },
  rejectButton: { alignItems: 'center', borderColor: zenith.colors.border, borderRadius: 12, borderWidth: 1, flexDirection: 'row', gap: 7, justifyContent: 'center', padding: 12 },
  rejectText: { color: zenith.colors.muted, fontFamily: zenith.font.bodyBold },
  questionBox: { borderColor: zenith.colors.primaryBorder, gap: 12 },
  chatBox: { borderColor: zenith.colors.primaryBorder, gap: 12 },
  assistantBubble: { alignSelf: 'flex-start', backgroundColor: zenith.colors.secondary, borderColor: zenith.colors.border, borderRadius: 16, borderWidth: 1, maxWidth: '92%', padding: 12 },
  userBubble: { alignSelf: 'flex-end', backgroundColor: zenith.colors.primarySoft, borderColor: zenith.colors.primaryBorder, borderRadius: 16, borderWidth: 1, maxWidth: '92%', padding: 12 },
  chatText: { color: zenith.colors.foreground, fontFamily: zenith.font.body, lineHeight: 20 },
  questionTitle: { color: zenith.colors.foreground, fontFamily: zenith.font.display, fontSize: 24, lineHeight: 26, textTransform: 'uppercase' },
  questionText: { color: zenith.colors.muted, fontFamily: zenith.font.body, lineHeight: 20 },
  routineSelector: { gap: 8 },
  routineSelectorLabel: { color: zenith.colors.muted, fontFamily: zenith.font.mono, fontSize: 10, letterSpacing: 1.4, textTransform: 'uppercase' },
  routineOption: { borderColor: zenith.colors.border, borderRadius: 12, borderWidth: 1, padding: 11 },
  routineOptionSelected: { backgroundColor: zenith.colors.primary, borderColor: zenith.colors.primary },
  routineOptionText: { color: zenith.colors.foreground, fontFamily: zenith.font.bodyBold },
  routineOptionTextSelected: { color: zenith.colors.primaryForeground },
  emptyInline: { color: zenith.colors.muted, fontFamily: zenith.font.body },
  answerBox: { backgroundColor: zenith.colors.background, borderRadius: 14, gap: 8, padding: 12 },
  answerTitle: { color: zenith.colors.foreground, fontFamily: zenith.font.bodyBold },
  answerItem: { color: zenith.colors.foreground, fontFamily: zenith.font.body, lineHeight: 20 },
  actionItem: { color: zenith.colors.primary, fontFamily: zenith.font.bodyBold, lineHeight: 20 },
  summarySectionBox: { gap: 12 },
  sessionSummaryCard: { backgroundColor: zenith.colors.background, gap: 6, padding: 12 },
  sessionTitle: { color: zenith.colors.foreground, fontFamily: zenith.font.bodyBold },
  summaryLink: { color: zenith.colors.primary, fontFamily: zenith.font.bodyBold },
  planForm: { borderColor: zenith.colors.primaryBorder, gap: 12 },
  grid: { gap: 12 },
  sensitiveBox: { backgroundColor: zenith.colors.dangerSoft, borderColor: 'rgba(232,64,64,0.28)', borderRadius: 16, borderWidth: 1, gap: 10, padding: 14 },
  sensitiveTitle: { color: '#fecaca', fontFamily: zenith.font.bodyBold, fontSize: 16 },
  sensitiveText: { color: '#fca5a5', fontFamily: zenith.font.body, lineHeight: 20 },
  checkbox: { alignItems: 'center', borderColor: zenith.colors.border, borderRadius: 12, borderWidth: 1, padding: 12 },
  checkboxChecked: { backgroundColor: zenith.colors.primarySoft, borderColor: zenith.colors.primary },
  checkboxText: { color: zenith.colors.foreground, fontFamily: zenith.font.bodyBold, textAlign: 'center' },
  section: { color: zenith.colors.foreground, fontFamily: zenith.font.display, fontSize: 24, lineHeight: 27, textTransform: 'uppercase' },
  cardTitle: { color: zenith.colors.foreground, flex: 1, fontFamily: zenith.font.display, fontSize: 22, lineHeight: 24, textTransform: 'uppercase' },
  cardText: { color: zenith.colors.foreground, fontFamily: zenith.font.body, lineHeight: 21 },
  risk: { color: '#fca5a5', fontFamily: zenith.font.bodyBold, lineHeight: 20 },
  versionText: { color: zenith.colors.violet, fontFamily: zenith.font.bodyBold },
  providerText: { color: zenith.colors.cyan, fontFamily: zenith.font.mono, fontSize: 11 },
  detailToggle: { alignSelf: 'flex-start', borderColor: zenith.colors.border, borderRadius: 999, borderWidth: 1, paddingHorizontal: 11, paddingVertical: 7 },
  detailToggleText: { color: zenith.colors.muted, fontFamily: zenith.font.bodyBold, fontSize: 12 },
  planDetailBox: { backgroundColor: zenith.colors.background, borderColor: zenith.colors.border, borderRadius: 12, borderWidth: 1, gap: 6, padding: 10 },
  planDetailContent: { gap: 5 },
  routineBox: { backgroundColor: zenith.colors.background, borderRadius: 12, gap: 4, padding: 10 },
  routineTitle: { color: zenith.colors.primary, fontFamily: zenith.font.bodyBold },
  exerciseLine: { color: zenith.colors.foreground, fontFamily: zenith.font.body, fontSize: 13, lineHeight: 19 },
  progressionText: { color: zenith.colors.amber, fontFamily: zenith.font.bodyBold, lineHeight: 20 },
  draftBox: { backgroundColor: zenith.colors.secondary, borderColor: zenith.colors.border, borderRadius: 14, borderWidth: 1, gap: 10, padding: 12 },
  modifyTitle: { color: zenith.colors.foreground, fontFamily: zenith.font.bodyBold, fontSize: 15 },
  modifyText: { color: zenith.colors.muted, fontFamily: zenith.font.body, lineHeight: 20 },
  modifyButton: { alignItems: 'center', backgroundColor: zenith.colors.primary, borderRadius: 12, padding: 12 },
  modifyButtonText: { color: zenith.colors.primaryForeground, fontFamily: zenith.font.bodyBold },
  disabled: { opacity: 0.55 },
  empty: { backgroundColor: zenith.colors.card, borderColor: zenith.colors.border, borderRadius: 16, borderWidth: 1, color: zenith.colors.muted, fontFamily: zenith.font.body, padding: 16 },
});
