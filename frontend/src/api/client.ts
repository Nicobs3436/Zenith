import { router } from 'expo-router';

import { clearAuthTokens, getAccessToken, getRefreshToken, loadAuthTokens, setAuthTokens } from '@/auth/tokenStorage';
import { API_URL } from '@/config/env';
import { SESSION_EXPIRED_NOTICE } from '@/utils/authDisplay';

type RequestOptions = {
  method?: 'GET' | 'POST' | 'PUT' | 'DELETE';
  body?: unknown;
  auth?: boolean;
};

type ApiErrorDetail = string | { msg?: string; loc?: (string | number)[] }[] | { detail?: unknown };
type ApiValidationError = { msg?: string; loc?: (string | number)[] };

const API_TIMEOUT_MS = 20_000;
const API_TIMEOUT_MESSAGE = 'La API tardo demasiado en responder. Intentalo de nuevo.';

type TokenResponse = {
  access_token: string;
  refresh_token: string;
};

let refreshInFlight: Promise<boolean> | null = null;

export class AuthExpiredError extends Error {
  constructor() {
    super(SESSION_EXPIRED_NOTICE);
    this.name = 'AuthExpiredError';
  }
}

export type User = {
  id: string;
  email: string;
  username: string;
};

export type Rank = { id: string; name: string; description: string | null; min_score: string; sort_order: number };

export type RankProgress = {
  rank: Rank;
  next_rank: Rank | null;
  score: string;
  volume_score: string;
  progression_score: string;
  breadth_score: string;
  points_to_next_rank: string | null;
  calculated_at: string | null;
};

export type NamedReference = {
  id: string;
  name: string;
};

export type Exercise = {
  id: string;
  name: string;
  description: string | null;
  difficulty: string | null;
  technique_notes: string | null;
  is_global: boolean;
  created_by_user_id: string | null;
  muscle_groups: NamedReference[];
  equipment: NamedReference[];
  created_at: string;
  updated_at: string;
};

export type ExercisePayload = {
  name: string;
  description?: string | null;
  difficulty?: 'beginner' | 'intermediate' | 'advanced' | null;
  technique_notes?: string | null;
  muscle_group_ids: string[];
  equipment_ids: string[];
};

export type Routine = {
  id: string;
  name: string;
  goal: string | null;
  description: string | null;
  exercises: RoutineExercise[];
};

export type RoutineExercise = {
  id?: string;
  exercise_id: string;
  position: number;
  target_sets: number | null;
  target_reps_min: number | null;
  target_reps_max: number | null;
  target_weight_value?: string | null;
  target_weight_unit?: 'kg' | 'lb' | null;
  target_rpe?: string | null;
  target_rir?: number | null;
  rest_seconds?: number | null;
  notes?: string | null;
};

export type AiSuggestionType =
  | 'increase_weight'
  | 'reduce_volume'
  | 'change_reps'
  | 'increase_rest'
  | 'plateau_detected'
  | 'deload_recommended'
  | 'exercise_swap'
  | 'routine_goal_adjustment';
export type AiSuggestionStatus = 'pending' | 'accepted' | 'rejected' | 'expired';
export type AiCoachQuestionType = 'next_workout' | 'progression' | 'fatigue' | 'routine_review' | 'stats_explanation';

export type AiSuggestion = {
  id: string;
  user_id: string;
  routine_id: string | null;
  routine_exercise_id: string | null;
  exercise_id: string | null;
  type: AiSuggestionType;
  status: AiSuggestionStatus;
  input_summary: Record<string, unknown>;
  recommendation: string;
  explanation: string;
  risk_notes: string | null;
  confidence: 'low' | 'medium' | 'high' | null;
  apply_payload: Record<string, unknown>;
  created_at: string;
  reviewed_at: string | null;
  applied_at: string | null;
};

export type AiCoachQuestionRequest = {
  question_type: AiCoachQuestionType;
  routine_id?: string | null;
  exercise_id?: string | null;
  session_id?: string | null;
  detail?: string | null;
};

export type AiCoachQuestionResponse = {
  question_type: AiCoachQuestionType;
  answer: string;
  key_points: string[];
  related_metrics: Record<string, unknown>;
  suggested_actions: string[];
  provider: string;
  model: string | null;
  fallback_used: boolean;
  input_summary: Record<string, unknown>;
};

export type AiCoachIntakeMessage = {
  role: 'user' | 'assistant';
  content: string;
};

export type AiCoachIntake = {
  id: string;
  user_id: string;
  status: 'collecting' | 'ready' | 'plan_generated';
  intake_summary: Record<string, unknown>;
  recent_messages: AiCoachIntakeMessage[];
  missing_required_fields: string[];
  useful_missing_fields: string[];
  ready_for_plan: boolean;
  sensitive_data_acknowledged: boolean;
  assistant_message: string | null;
  safety_warning: string | null;
  provider: string;
  model: string | null;
  fallback_used: boolean;
  updated_at: string;
};

export type AiCoachIntakeMessageRequest = {
  message: string;
  sensitive_data_acknowledged: boolean;
};

export type CoachV2Profile = {
  id: string;
  user_id: string;
  goal: string | null;
  secondary_goal: string | null;
  plan_horizon_weeks: number | null;
  biological_sex: 'male' | 'female' | null;
  age: number | null;
  height_cm: number | null;
  weight_kg: number | null;
  experience_level: string | null;
  training_age_months: number | null;
  days_per_week: number | null;
  session_duration_minutes: number | null;
  equipment: string[];
  priorities: string[];
  preferred_exercises: string[];
  avoided_exercises: string[];
  physical_limitations: string | null;
  sleep_quality: string | null;
  stress_level: string | null;
  current_fatigue: string | null;
  personal_data_acknowledged: boolean;
  sensitive_data_acknowledged: boolean;
  memory_summary: string | null;
  updated_at: string;
};

export type CoachV2Message = { role: 'user' | 'assistant'; content: string };

export type CoachV2Conversation = {
  id: string;
  user_id: string;
  phase: 'onboarding' | 'plan_ready' | 'training_active' | 'progress_review' | 'fatigue_review' | 'adjustment_review';
  last_question: string | null;
  recent_messages: CoachV2Message[];
  conversation_summary: string | null;
  updated_at: string;
};

export type CoachMemoryEvent = { id: string; event_type: string; summary: string; payload: Record<string, unknown>; created_at: string };
export type CoachProposal = { id: string; type: string; status: 'pending' | 'accepted' | 'rejected' | 'expired'; recommendation: string; explanation: string; payload: Record<string, unknown>; created_at: string; reviewed_at: string | null };
export type CoachPlannedSession = { id: string; status: string; title: string; session_payload: Record<string, unknown>; rationale: string; created_at: string; completed_at: string | null };

export type CoachV2State = {
  profile: CoachV2Profile;
  conversation: CoachV2Conversation;
  assistant_message: string;
  missing_required_fields: string[];
  ready_for_plan: boolean;
  memory_events: CoachMemoryEvent[];
  proposals: CoachProposal[];
  planned_sessions: CoachPlannedSession[];
  privacy_notice: string;
  next_action: string | null;
};

export type CoachV2MessageRequest = {
  message: string;
  personal_data_acknowledged: boolean;
  sensitive_data_acknowledged: boolean;
};

export type TrainingPlanGoal = 'strength' | 'hypertrophy' | 'fat_loss' | 'general_health' | 'endurance';
export type TrainingPlanLevel = 'beginner' | 'intermediate' | 'advanced';
export type TrainingPlanStatus = 'draft' | 'accepted' | 'rejected';

export type AiTrainingPlanGenerateRequest = {
  goal: TrainingPlanGoal;
  level: TrainingPlanLevel;
  days_per_week: number;
  session_duration_minutes: number;
  available_equipment: string[];
  physical_limitations?: string | null;
  sensitive_data_acknowledged: boolean;
  priorities: string[];
};

export type AiTrainingPlanModifyRequest = {
  instruction: string;
  sensitive_data_acknowledged: boolean;
};

export type AiTrainingPlan = {
  id: string;
  user_id: string;
  status: TrainingPlanStatus;
  goal: string;
  level: string;
  days_per_week: number;
  session_duration_minutes: number;
  available_equipment: string[];
  physical_limitations: string | null;
  sensitive_data_acknowledged: boolean;
  priorities: string[];
  plan_payload: Record<string, unknown>;
  explanation: string;
  risk_notes: string | null;
  confidence: string | null;
  input_summary: Record<string, unknown>;
  provider: string;
  model: string | null;
  fallback_used: boolean;
  created_at: string;
  reviewed_at: string | null;
};

export type AiSessionSummary = {
  id: string;
  user_id: string;
  session_id: string;
  summary: string;
  improvements: string[];
  drops: string[];
  warnings: string[];
  next_recommendation: string;
  input_summary: Record<string, unknown>;
  provider: string;
  model: string | null;
  fallback_used: boolean;
  created_at: string;
};

export type RoutinePayload = {
  name: string;
  description?: string | null;
  goal?: string | null;
  exercises: RoutineExercise[];
};

export type WorkoutSession = {
  id: string;
  routine_id: string | null;
  started_at: string;
  finished_at: string | null;
  timezone: string;
  notes: string | null;
  sets: WorkoutSet[];
};

export type WorkoutSet = {
  id?: string;
  exercise_id: string;
  set_number: number;
  reps: number;
  weight_value?: string | null;
  weight_unit?: 'kg' | 'lb' | null;
  rpe?: string | null;
  rir?: number | null;
  rest_seconds?: number | null;
  notes?: string | null;
};

export type WorkoutSessionPayload = {
  routine_id?: string | null;
  started_at: string;
  finished_at?: string | null;
  timezone: string;
  notes?: string | null;
  sets: WorkoutSet[];
};

export type ExerciseStats = {
  exercise_id: string;
  exercise_name: string;
  weight_unit: string | null;
  total_sets: number;
  total_reps: number;
  total_volume: string | null;
  max_weight: string | null;
  avg_weight: string | null;
  best_estimated_1rm: string | null;
  first_session_at: string | null;
  last_session_at: string | null;
};

export type StatsPeriodFilter = '7d' | '30d' | '90d' | 'all';
export type StatsGroupingPeriod = 'day' | 'week' | 'month';
export type StatsWeightUnit = 'kg' | 'lb';

export type ExerciseStatsPoint = {
  period_start: string;
  weight_unit: string | null;
  total_sets: number;
  total_reps: number;
  total_volume: string | null;
  max_weight: string | null;
  avg_weight: string | null;
  best_estimated_1rm: string | null;
};

export type ExerciseStatsDetail = {
  exercise_id: string;
  exercise_name: string;
  period: StatsGroupingPeriod;
  points: ExerciseStatsPoint[];
};

export type StatsOverview = {
  period: StatsGroupingPeriod;
  kpis: {
    total_sets: number;
    session_count: number;
    training_hours: string;
    pr_count: number;
  };
  volume_by_unit: { weight_unit: string | null; total_volume: string | null }[];
  volume_points: {
    period_start: string;
    weight_unit: string | null;
    total_volume: string | null;
    total_sets: number;
    session_count: number;
  }[];
  muscle_groups: { name: string; total_sets: number }[];
  top_exercises: {
    exercise_id: string;
    exercise_name: string;
    weight_unit: string | null;
    total_volume: string | null;
    max_weight: string | null;
    best_estimated_1rm: string | null;
  }[];
};

function appendStatsRange(params: URLSearchParams, periodFilter: StatsPeriodFilter) {
  const days = periodFilter === '7d' ? 7 : periodFilter === '30d' ? 30 : periodFilter === '90d' ? 90 : null;
  if (days !== null) {
    params.set('start_date', new Date(Date.now() - days * 24 * 60 * 60 * 1000).toISOString());
  }
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null;
}

function stringValue(value: unknown, fallback = '') {
  return typeof value === 'string' ? value : fallback;
}

function nullableStringValue(value: unknown) {
  return typeof value === 'string' ? value : null;
}

function numberValue(value: unknown, fallback = 0) {
  return typeof value === 'number' && Number.isFinite(value) ? value : fallback;
}

function nullableNumberValue(value: unknown) {
  return typeof value === 'number' && Number.isFinite(value) ? value : null;
}

function normalizeNamedReferences(value: unknown): NamedReference[] {
  if (!Array.isArray(value)) {
    return [];
  }
  return value.flatMap((item) => {
    if (!isRecord(item) || typeof item.id !== 'string' || typeof item.name !== 'string') {
      return [];
    }
    return [{ id: item.id, name: item.name }];
  });
}

function normalizeExercise(value: unknown): Exercise | null {
  if (!isRecord(value) || typeof value.id !== 'string' || typeof value.name !== 'string') {
    return null;
  }
  return {
    id: value.id,
    name: value.name,
    description: nullableStringValue(value.description),
    difficulty: nullableStringValue(value.difficulty),
    technique_notes: nullableStringValue(value.technique_notes),
    is_global: typeof value.is_global === 'boolean' ? value.is_global : false,
    created_by_user_id: nullableStringValue(value.created_by_user_id),
    muscle_groups: normalizeNamedReferences(value.muscle_groups),
    equipment: normalizeNamedReferences(value.equipment),
    created_at: stringValue(value.created_at),
    updated_at: stringValue(value.updated_at),
  };
}

function normalizeExercises(value: unknown): Exercise[] {
  if (!Array.isArray(value)) {
    return [];
  }
  return value.flatMap((item) => normalizeExercise(item) ?? []);
}

function normalizeRoutineExercise(value: unknown): RoutineExercise | null {
  if (!isRecord(value) || typeof value.exercise_id !== 'string') {
    return null;
  }
  return {
    id: nullableStringValue(value.id) ?? undefined,
    exercise_id: value.exercise_id,
    position: numberValue(value.position, 1),
    target_sets: nullableNumberValue(value.target_sets),
    target_reps_min: nullableNumberValue(value.target_reps_min),
    target_reps_max: nullableNumberValue(value.target_reps_max),
    target_weight_value: nullableStringValue(value.target_weight_value),
    target_weight_unit: value.target_weight_unit === 'kg' || value.target_weight_unit === 'lb' ? value.target_weight_unit : null,
    target_rpe: nullableStringValue(value.target_rpe),
    target_rir: nullableNumberValue(value.target_rir),
    rest_seconds: nullableNumberValue(value.rest_seconds),
    notes: nullableStringValue(value.notes),
  };
}

function normalizeRoutineExercises(value: unknown): RoutineExercise[] {
  if (!Array.isArray(value)) {
    return [];
  }
  return value.flatMap((item) => normalizeRoutineExercise(item) ?? []);
}

function normalizeRoutine(value: unknown): Routine | null {
  if (!isRecord(value) || typeof value.id !== 'string') {
    return null;
  }
  return {
    id: value.id,
    name: stringValue(value.name, 'Rutina sin nombre'),
    goal: nullableStringValue(value.goal),
    description: nullableStringValue(value.description),
    exercises: normalizeRoutineExercises(value.exercises),
  };
}

function normalizeRoutines(value: unknown): Routine[] {
  if (!Array.isArray(value)) {
    return [];
  }
  return value.flatMap((item) => normalizeRoutine(item) ?? []);
}

function normalizeWorkoutSet(value: unknown): WorkoutSet | null {
  if (!isRecord(value) || typeof value.exercise_id !== 'string') {
    return null;
  }
  return {
    id: nullableStringValue(value.id) ?? undefined,
    exercise_id: value.exercise_id,
    set_number: numberValue(value.set_number, 1),
    reps: numberValue(value.reps, 0),
    weight_value: nullableStringValue(value.weight_value),
    weight_unit: value.weight_unit === 'kg' || value.weight_unit === 'lb' ? value.weight_unit : null,
    rpe: nullableStringValue(value.rpe),
    rir: nullableNumberValue(value.rir),
    rest_seconds: nullableNumberValue(value.rest_seconds),
    notes: nullableStringValue(value.notes),
  };
}

function normalizeWorkoutSets(value: unknown): WorkoutSet[] {
  if (!Array.isArray(value)) {
    return [];
  }
  return value.flatMap((item) => normalizeWorkoutSet(item) ?? []);
}

function normalizeWorkoutSession(value: unknown): WorkoutSession | null {
  if (!isRecord(value) || typeof value.id !== 'string' || typeof value.started_at !== 'string') {
    return null;
  }
  return {
    id: value.id,
    routine_id: nullableStringValue(value.routine_id),
    started_at: value.started_at,
    finished_at: nullableStringValue(value.finished_at),
    timezone: stringValue(value.timezone, 'UTC'),
    notes: nullableStringValue(value.notes),
    sets: normalizeWorkoutSets(value.sets),
  };
}

function normalizeWorkoutSessions(value: unknown): WorkoutSession[] {
  if (!Array.isArray(value)) {
    return [];
  }
  return value.flatMap((item) => normalizeWorkoutSession(item) ?? []);
}

async function request<T>(path: string, options: RequestOptions = {}, retryOnUnauthorized = true): Promise<T> {
  const headers: Record<string, string> = { 'Content-Type': 'application/json' };
  const token = await getAccessToken();
  if (options.auth && token) {
    headers.Authorization = `Bearer ${token}`;
  }

  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), API_TIMEOUT_MS);
  let response: Response;
  try {
    response = await fetch(`${API_URL}${path}`, {
      method: options.method ?? 'GET',
      headers,
      body: options.body ? JSON.stringify(options.body) : undefined,
      signal: controller.signal,
    });
  } catch (error) {
    if (isAbortError(error)) {
      throw new Error(API_TIMEOUT_MESSAGE);
    }
    throw error;
  } finally {
    clearTimeout(timeoutId);
  }

  if (!response.ok) {
    if (response.status === 401 && options.auth) {
      if (retryOnUnauthorized && (await refreshSession())) {
        return request<T>(path, options, false);
      }
      await expireSession();
      throw new AuthExpiredError();
    }
    throw new Error(await formatErrorMessage(response));
  }

  if (response.status === 204) {
    return undefined as T;
  }

  return response.json() as Promise<T>;
}

function isAbortError(error: unknown) {
  return typeof error === 'object' && error !== null && 'name' in error && error.name === 'AbortError';
}

async function refreshSession() {
  refreshInFlight ??= refreshAccessToken().finally(() => {
    refreshInFlight = null;
  });
  return refreshInFlight;
}

async function refreshAccessToken() {
  const refreshToken = await getRefreshToken();
  if (!refreshToken) {
    return false;
  }

  try {
    const token = await request<TokenResponse>(
      '/auth/refresh',
      {
        method: 'POST',
        body: { refresh_token: refreshToken },
      },
      false,
    );
    await setAuthTokens({ accessToken: token.access_token, refreshToken: token.refresh_token });
    return true;
  } catch {
    return false;
  }
}

async function expireSession() {
  await clearAuthTokens();
  router.replace({ pathname: '/login', params: { notice: 'session-expired' } });
}

async function formatErrorMessage(response: Response) {
  const fallback = `Request failed with status ${response.status}`;
  const body = await response.text();
  if (!body) {
    return fallback;
  }

  try {
    const parsed = JSON.parse(body) as ApiErrorDetail;
    const detail = typeof parsed === 'object' && parsed !== null && 'detail' in parsed ? parsed.detail : parsed;
    if (typeof detail === 'string') {
      return detail;
    }
    if (Array.isArray(detail)) {
      return (detail as ApiValidationError[])
        .map((item) => {
          const field = item.loc?.filter((part: string | number) => part !== 'body').join('.') ?? 'campo';
          return item.msg ? `${field}: ${item.msg}` : null;
        })
        .filter(Boolean)
        .join('\n');
    }
  } catch {
    return body;
  }

  return fallback;
}

export async function login(email: string, password: string) {
  const token = await request<TokenResponse>('/auth/login', {
    method: 'POST',
    body: { email, password },
  });
  await setAuthTokens({ accessToken: token.access_token, refreshToken: token.refresh_token });
}

export async function register(email: string, username: string, password: string) {
  await request<User>('/auth/register', {
    method: 'POST',
    body: { email, username, password },
  });
  await login(email, password);
}

export function getMe() {
  return request<User>('/users/me', { auth: true });
}

export async function restoreSession() {
  const tokens = await loadAuthTokens();
  if (!tokens.accessToken && !tokens.refreshToken) {
    return null;
  }
  if (!tokens.accessToken && !(await refreshSession())) {
    return null;
  }
  try {
    return await getMe();
  } catch (error) {
    if (error instanceof AuthExpiredError) {
      return null;
    }
    throw error;
  }
}

export async function logout() {
  const refreshToken = await getRefreshToken();
  try {
    if (refreshToken) {
      await request<void>(
        '/auth/logout',
        {
          method: 'POST',
          body: { refresh_token: refreshToken },
        },
        false,
      );
    }
  } catch {
    // Local logout should not be blocked by a transient network/backend failure.
  } finally {
    await clearAuthTokens();
  }
}

export function getRank() {
  return request<RankProgress>('/users/me/rank', { auth: true });
}

export function getRanks() {
  return request<Rank[]>('/ranks');
}

export function recalculateRank() {
  return request<RankProgress>('/users/me/rank/recalculate', { method: 'POST', auth: true });
}

export function getExercises() {
  return request<unknown>('/exercises', { auth: true }).then(normalizeExercises);
}

export function getExercise(exerciseId: string) {
  return request<unknown>(`/exercises/${exerciseId}`, { auth: true }).then((item) => {
    const exercise = normalizeExercise(item);
    if (!exercise) {
      throw new Error('El ejercicio recibido no es valido.');
    }
    return exercise;
  });
}

export function createExercise(payload: ExercisePayload) {
  return request<Exercise>('/exercises', { method: 'POST', auth: true, body: payload });
}

export function getMuscleGroups() {
  return request<NamedReference[]>('/muscle-groups');
}

export function getEquipment() {
  return request<NamedReference[]>('/equipment');
}

export function getRoutines() {
  return request<unknown>('/routines', { auth: true }).then(normalizeRoutines);
}

export function getRoutine(routineId: string) {
  return request<unknown>(`/routines/${routineId}`, { auth: true }).then((item) => {
    const routine = normalizeRoutine(item);
    if (!routine) {
      throw new Error('La rutina recibida no es valida.');
    }
    return routine;
  });
}

export function createRoutine(payload: RoutinePayload) {
  return request<Routine>('/routines', {
    method: 'POST',
    auth: true,
    body: payload,
  });
}

export function updateRoutine(routineId: string, payload: RoutinePayload) {
  return request<Routine>(`/routines/${routineId}`, {
    method: 'PUT',
    auth: true,
    body: payload,
  });
}

export function deleteRoutine(routineId: string) {
  return request<void>(`/routines/${routineId}`, { method: 'DELETE', auth: true });
}

export function generateAiSuggestions() {
  return request<AiSuggestion[]>('/ai/suggestions/generate', { method: 'POST', auth: true });
}

export function getAiSuggestions() {
  return request<AiSuggestion[]>('/ai/suggestions', { auth: true });
}

export function acceptAiSuggestion(suggestionId: string) {
  return request<AiSuggestion>(`/ai/suggestions/${suggestionId}/accept`, { method: 'POST', auth: true });
}

export function rejectAiSuggestion(suggestionId: string) {
  return request<AiSuggestion>(`/ai/suggestions/${suggestionId}/reject`, { method: 'POST', auth: true });
}

export function analyzeRoutineGoal(routineId: string) {
  return request<AiSuggestion[]>(`/ai/routines/${routineId}/analyze-goal`, { method: 'POST', auth: true });
}

export function askCoachQuestion(payload: AiCoachQuestionRequest) {
  return request<AiCoachQuestionResponse>('/ai/coach/questions', { method: 'POST', auth: true, body: payload });
}

export function getCoachIntake() {
  return request<AiCoachIntake>('/ai/coach/intake', { auth: true });
}

export function sendCoachIntakeMessage(payload: AiCoachIntakeMessageRequest) {
  return request<AiCoachIntake>('/ai/coach/intake/messages', { method: 'POST', auth: true, body: payload });
}

export function generateTrainingPlanFromCoachIntake() {
  return request<AiTrainingPlan>('/ai/coach/intake/generate-plan', { method: 'POST', auth: true });
}

export function resetCoachIntake() {
  return request<AiCoachIntake>('/ai/coach/intake/reset', { method: 'POST', auth: true });
}

export function getCoachV2State() {
  return request<CoachV2State>('/ai/coach/v2', { auth: true });
}

export function sendCoachV2Message(payload: CoachV2MessageRequest) {
  return request<CoachV2State>('/ai/coach/v2/messages', { method: 'POST', auth: true, body: payload });
}

export function generateCoachV2Plan() {
  return request<AiTrainingPlan>('/ai/coach/v2/generate-plan', { method: 'POST', auth: true });
}

export function generateCoachV2PlannedSession() {
  return request<CoachPlannedSession>('/ai/coach/v2/planned-sessions/generate', { method: 'POST', auth: true });
}

export function acceptCoachV2Proposal(proposalId: string) {
  return request<CoachProposal>(`/ai/coach/v2/proposals/${proposalId}/accept`, { method: 'POST', auth: true });
}

export function rejectCoachV2Proposal(proposalId: string) {
  return request<CoachProposal>(`/ai/coach/v2/proposals/${proposalId}/reject`, { method: 'POST', auth: true });
}

export function resetCoachV2() {
  return request<CoachV2State>('/ai/coach/v2/reset', { method: 'POST', auth: true });
}

export function generateTrainingPlan(payload: AiTrainingPlanGenerateRequest) {
  return request<AiTrainingPlan>('/ai/training-plans/generate', { method: 'POST', auth: true, body: payload });
}

export function getTrainingPlans() {
  return request<AiTrainingPlan[]>('/ai/training-plans', { auth: true });
}

export function getTrainingPlan(planId: string) {
  return request<AiTrainingPlan>(`/ai/training-plans/${planId}`, { auth: true });
}

export function acceptTrainingPlan(planId: string) {
  return request<AiTrainingPlan>(`/ai/training-plans/${planId}/accept`, { method: 'POST', auth: true });
}

export function rejectTrainingPlan(planId: string) {
  return request<AiTrainingPlan>(`/ai/training-plans/${planId}/reject`, { method: 'POST', auth: true });
}

export function modifyTrainingPlan(planId: string, payload: AiTrainingPlanModifyRequest) {
  return request<AiTrainingPlan>(`/ai/training-plans/${planId}/modify`, { method: 'POST', auth: true, body: payload });
}

export function generateSessionSummary(sessionId: string) {
  return request<AiSessionSummary>(`/ai/session-summaries/${sessionId}/generate`, { method: 'POST', auth: true });
}

export function getSessionSummary(sessionId: string) {
  return request<AiSessionSummary>(`/ai/session-summaries/${sessionId}`, { auth: true });
}

export function getWorkoutSessions() {
  return request<unknown>('/workout-sessions', { auth: true }).then(normalizeWorkoutSessions);
}

export function getWorkoutSession(sessionId: string) {
  return request<unknown>(`/workout-sessions/${sessionId}`, { auth: true }).then((item) => {
    const session = normalizeWorkoutSession(item);
    if (!session) {
      throw new Error('La sesion recibida no es valida.');
    }
    return session;
  });
}

export function createWorkoutSession(payload: WorkoutSessionPayload) {
  return request<WorkoutSession>('/workout-sessions', {
    method: 'POST',
    auth: true,
    body: payload,
  });
}

export function updateWorkoutSession(sessionId: string, payload: WorkoutSessionPayload) {
  return request<WorkoutSession>(`/workout-sessions/${sessionId}`, {
    method: 'PUT',
    auth: true,
    body: payload,
  });
}

export function deleteWorkoutSession(sessionId: string) {
  return request<void>(`/workout-sessions/${sessionId}`, { method: 'DELETE', auth: true });
}

export function getExerciseStats(periodFilter: StatsPeriodFilter = 'all', weightUnit?: StatsWeightUnit) {
  const params = new URLSearchParams();
  appendStatsRange(params, periodFilter);
  if (weightUnit) {
    params.set('weight_unit', weightUnit);
  }
  const query = params.toString();
  return request<ExerciseStats[]>(`/stats/exercises${query ? `?${query}` : ''}`, { auth: true });
}

export function getStatsOverview(
  periodFilter: StatsPeriodFilter = '30d',
  options: { period?: StatsGroupingPeriod; weightUnit?: StatsWeightUnit } = {},
) {
  const params = new URLSearchParams();
  params.set('period', options.period ?? 'week');
  appendStatsRange(params, periodFilter);
  if (options.weightUnit) {
    params.set('weight_unit', options.weightUnit);
  }
  return request<StatsOverview>(`/stats/overview?${params.toString()}`, { auth: true });
}

export function getExerciseStatsDetail(
  exerciseId: string,
  options: { periodFilter?: StatsPeriodFilter; period?: StatsGroupingPeriod; weightUnit?: StatsWeightUnit } = {},
) {
  const params = new URLSearchParams();
  params.set('period', options.period ?? 'week');
  appendStatsRange(params, options.periodFilter ?? 'all');
  if (options.weightUnit) {
    params.set('weight_unit', options.weightUnit);
  }
  return request<ExerciseStatsDetail>(`/stats/exercises/${exerciseId}?${params.toString()}`, { auth: true });
}
