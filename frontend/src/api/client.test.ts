import { beforeEach, describe, expect, it, vi } from 'vitest';

const mocks = vi.hoisted(() => {
  const state: { accessToken: string | null; refreshToken: string | null } = {
    accessToken: null,
    refreshToken: null,
  };
  const tokenStorage = {
    getAccessToken: vi.fn(async () => state.accessToken),
    getRefreshToken: vi.fn(async () => state.refreshToken),
    loadAuthTokens: vi.fn(async () => ({ accessToken: state.accessToken, refreshToken: state.refreshToken })),
    setAuthTokens: vi.fn(async (tokens: { accessToken: string; refreshToken: string }) => {
      state.accessToken = tokens.accessToken;
      state.refreshToken = tokens.refreshToken;
    }),
    clearAuthTokens: vi.fn(async () => {
      state.accessToken = null;
      state.refreshToken = null;
    }),
  };
  const router = { replace: vi.fn() };

  return { state, tokenStorage, router };
});

vi.mock('@/auth/tokenStorage', () => mocks.tokenStorage);
vi.mock('expo-router', () => ({ router: mocks.router }));

function jsonResponse(body: unknown, status = 200) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { 'Content-Type': 'application/json' },
  });
}

function emptyResponse(status = 204) {
  return new Response(null, { status });
}

async function loadClient() {
  vi.resetModules();
  return import('./client');
}

describe('api client auth refresh', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mocks.state.accessToken = 'old-access-token';
    mocks.state.refreshToken = 'old-refresh-token';
  });

  it('refreshes tokens and retries an authenticated request once after 401', async () => {
    const user = { id: 'user-id', email: 'user@example.com', username: 'user' };
    const fetchMock = vi
      .fn<typeof fetch>()
      .mockResolvedValueOnce(jsonResponse({ detail: 'Unauthorized' }, 401))
      .mockResolvedValueOnce(jsonResponse({ access_token: 'new-access-token', refresh_token: 'new-refresh-token' }))
      .mockResolvedValueOnce(jsonResponse(user));
    vi.stubGlobal('fetch', fetchMock);
    const client = await loadClient();

    await expect(client.getMe()).resolves.toEqual(user);

    expect(fetchMock).toHaveBeenCalledTimes(3);
    expect(fetchMock).toHaveBeenNthCalledWith(
      1,
      'http://localhost:8000/users/me',
      expect.objectContaining({ headers: expect.objectContaining({ Authorization: 'Bearer old-access-token' }) }),
    );
    expect(fetchMock).toHaveBeenNthCalledWith(
      2,
      'http://localhost:8000/auth/refresh',
      expect.objectContaining({ body: JSON.stringify({ refresh_token: 'old-refresh-token' }) }),
    );
    expect(fetchMock).toHaveBeenNthCalledWith(
      3,
      'http://localhost:8000/users/me',
      expect.objectContaining({ headers: expect.objectContaining({ Authorization: 'Bearer new-access-token' }) }),
    );
    expect(mocks.tokenStorage.setAuthTokens).toHaveBeenCalledWith({ accessToken: 'new-access-token', refreshToken: 'new-refresh-token' });
    expect(mocks.router.replace).not.toHaveBeenCalled();
  });

  it('clears tokens and redirects when refresh fails', async () => {
    const fetchMock = vi
      .fn<typeof fetch>()
      .mockResolvedValueOnce(jsonResponse({ detail: 'Unauthorized' }, 401))
      .mockResolvedValueOnce(jsonResponse({ detail: 'Invalid refresh token.' }, 401));
    vi.stubGlobal('fetch', fetchMock);
    const client = await loadClient();

    await expect(client.getMe()).rejects.toBeInstanceOf(client.AuthExpiredError);

    expect(mocks.tokenStorage.clearAuthTokens).toHaveBeenCalledOnce();
    expect(mocks.state.accessToken).toBeNull();
    expect(mocks.state.refreshToken).toBeNull();
    expect(mocks.router.replace).toHaveBeenCalledWith({ pathname: '/login', params: { notice: 'session-expired' } });
  });

  it('keeps tokens when refresh fails because of the network', async () => {
    const fetchMock = vi
      .fn<typeof fetch>()
      .mockResolvedValueOnce(jsonResponse({ detail: 'Unauthorized' }, 401))
      .mockRejectedValueOnce(new TypeError('Network request failed'));
    vi.stubGlobal('fetch', fetchMock);
    const client = await loadClient();

    await expect(client.getMe()).rejects.toThrow('Network request failed');

    expect(mocks.tokenStorage.clearAuthTokens).not.toHaveBeenCalled();
    expect(mocks.state.refreshToken).toBe('old-refresh-token');
    expect(mocks.router.replace).not.toHaveBeenCalled();
  });

  it('keeps tokens when refresh fails with a server error', async () => {
    const fetchMock = vi
      .fn<typeof fetch>()
      .mockResolvedValueOnce(jsonResponse({ detail: 'Unauthorized' }, 401))
      .mockResolvedValueOnce(jsonResponse({ detail: 'Service unavailable' }, 503));
    vi.stubGlobal('fetch', fetchMock);
    const client = await loadClient();

    await expect(client.getMe()).rejects.toBeInstanceOf(client.ApiError);

    expect(mocks.tokenStorage.clearAuthTokens).not.toHaveBeenCalled();
    expect(mocks.state.refreshToken).toBe('old-refresh-token');
  });

  it('revokes refresh token remotely and clears local tokens on logout', async () => {
    const fetchMock = vi.fn<typeof fetch>().mockResolvedValueOnce(emptyResponse());
    vi.stubGlobal('fetch', fetchMock);
    const client = await loadClient();

    await client.logout();

    expect(fetchMock).toHaveBeenCalledWith(
      'http://localhost:8000/auth/logout',
      expect.objectContaining({
        method: 'POST',
        body: JSON.stringify({ refresh_token: 'old-refresh-token' }),
      }),
    );
    expect(mocks.tokenStorage.clearAuthTokens).toHaveBeenCalledOnce();
    expect(mocks.state.accessToken).toBeNull();
    expect(mocks.state.refreshToken).toBeNull();
  });

  it('calls ranks catalog endpoint', async () => {
    const ranks = [{ id: 'rank-1', name: 'Bronce', description: 'Inicio', min_score: '0.00', sort_order: 1 }];
    const fetchMock = vi.fn<typeof fetch>().mockResolvedValueOnce(jsonResponse(ranks));
    vi.stubGlobal('fetch', fetchMock);
    const client = await loadClient();

    await expect(client.getRanks()).resolves.toEqual(ranks);

    expect(fetchMock).toHaveBeenCalledWith('http://localhost:8000/ranks', expect.objectContaining({ method: 'GET' }));
  });

  it('calls AI coach suggestion endpoints', async () => {
    const suggestion = {
      id: 'suggestion-1',
      user_id: 'user-1',
      routine_id: 'routine-1',
      routine_exercise_id: 'routine-exercise-1',
      exercise_id: 'exercise-1',
      type: 'increase_weight',
      status: 'pending',
      input_summary: {},
      recommendation: 'Sube peso',
      explanation: 'Progresión estable',
      risk_notes: null,
      confidence: 'high',
      apply_payload: {},
      created_at: '2026-07-08T10:00:00Z',
      reviewed_at: null,
      applied_at: null,
    };
    const fetchMock = vi
      .fn<typeof fetch>()
      .mockResolvedValueOnce(jsonResponse([suggestion]))
      .mockResolvedValueOnce(jsonResponse([suggestion]))
      .mockResolvedValueOnce(jsonResponse([suggestion]))
      .mockResolvedValueOnce(jsonResponse({ ...suggestion, status: 'accepted' }))
      .mockResolvedValueOnce(jsonResponse({ ...suggestion, status: 'rejected' }));
    vi.stubGlobal('fetch', fetchMock);
    const client = await loadClient();

    await expect(client.generateAiSuggestions()).resolves.toEqual([suggestion]);
    await expect(client.getAiSuggestions()).resolves.toEqual([suggestion]);
    await expect(client.analyzeRoutineGoal('routine-1')).resolves.toEqual([suggestion]);
    await expect(client.acceptAiSuggestion('suggestion-1')).resolves.toEqual({ ...suggestion, status: 'accepted' });
    await expect(client.rejectAiSuggestion('suggestion-1')).resolves.toEqual({ ...suggestion, status: 'rejected' });

    expect(fetchMock).toHaveBeenNthCalledWith(1, 'http://localhost:8000/ai/suggestions/generate', expect.objectContaining({ method: 'POST' }));
    expect(fetchMock).toHaveBeenNthCalledWith(2, 'http://localhost:8000/ai/suggestions', expect.objectContaining({ method: 'GET' }));
    expect(fetchMock).toHaveBeenNthCalledWith(3, 'http://localhost:8000/ai/routines/routine-1/analyze-goal', expect.objectContaining({ method: 'POST' }));
    expect(fetchMock).toHaveBeenNthCalledWith(4, 'http://localhost:8000/ai/suggestions/suggestion-1/accept', expect.objectContaining({ method: 'POST' }));
    expect(fetchMock).toHaveBeenNthCalledWith(5, 'http://localhost:8000/ai/suggestions/suggestion-1/reject', expect.objectContaining({ method: 'POST' }));
  });

  it('calls AI training plan endpoints', async () => {
    const plan = {
      id: 'plan-1',
      user_id: 'user-1',
      status: 'draft',
      goal: 'hypertrophy',
      level: 'beginner',
      days_per_week: 3,
      session_duration_minutes: 60,
      available_equipment: [],
      physical_limitations: null,
      sensitive_data_acknowledged: false,
      priorities: [],
      plan_payload: { routines: [] },
      explanation: 'Plan',
      risk_notes: null,
      confidence: 'medium',
      input_summary: {},
      provider: 'internal',
      model: 'rules',
      fallback_used: false,
      created_at: '2026-07-08T10:00:00Z',
      reviewed_at: null,
    };
    const fetchMock = vi
      .fn<typeof fetch>()
      .mockResolvedValueOnce(jsonResponse(plan))
      .mockResolvedValueOnce(jsonResponse([plan]))
      .mockResolvedValueOnce(jsonResponse(plan))
      .mockResolvedValueOnce(jsonResponse({ ...plan, status: 'accepted' }))
      .mockResolvedValueOnce(jsonResponse({ ...plan, status: 'rejected' }))
      .mockResolvedValueOnce(jsonResponse({ ...plan, id: 'plan-2', input_summary: { modified_from_plan_id: 'plan-1' } }));
    vi.stubGlobal('fetch', fetchMock);
    const client = await loadClient();

    await expect(client.generateTrainingPlan({
      goal: 'hypertrophy',
      level: 'beginner',
      days_per_week: 3,
      session_duration_minutes: 60,
      available_equipment: [],
      physical_limitations: null,
      sensitive_data_acknowledged: false,
      priorities: [],
    })).resolves.toEqual(plan);
    await expect(client.getTrainingPlans()).resolves.toEqual([plan]);
    await expect(client.getTrainingPlan('plan-1')).resolves.toEqual(plan);
    await expect(client.acceptTrainingPlan('plan-1')).resolves.toEqual({ ...plan, status: 'accepted' });
    await expect(client.rejectTrainingPlan('plan-1')).resolves.toEqual({ ...plan, status: 'rejected' });
    await expect(client.modifyTrainingPlan('plan-1', { instruction: 'Hazlo a 4 días', sensitive_data_acknowledged: false })).resolves.toEqual({
      ...plan,
      id: 'plan-2',
      input_summary: { modified_from_plan_id: 'plan-1' },
    });

    expect(fetchMock).toHaveBeenNthCalledWith(1, 'http://localhost:8000/ai/training-plans/generate', expect.objectContaining({ method: 'POST' }));
    expect(fetchMock).toHaveBeenNthCalledWith(2, 'http://localhost:8000/ai/training-plans', expect.objectContaining({ method: 'GET' }));
    expect(fetchMock).toHaveBeenNthCalledWith(3, 'http://localhost:8000/ai/training-plans/plan-1', expect.objectContaining({ method: 'GET' }));
    expect(fetchMock).toHaveBeenNthCalledWith(4, 'http://localhost:8000/ai/training-plans/plan-1/accept', expect.objectContaining({ method: 'POST' }));
    expect(fetchMock).toHaveBeenNthCalledWith(5, 'http://localhost:8000/ai/training-plans/plan-1/reject', expect.objectContaining({ method: 'POST' }));
    expect(fetchMock).toHaveBeenNthCalledWith(
      6,
      'http://localhost:8000/ai/training-plans/plan-1/modify',
      expect.objectContaining({ method: 'POST', body: JSON.stringify({ instruction: 'Hazlo a 4 días', sensitive_data_acknowledged: false }) }),
    );
  });

  it('calls Coach endpoints', async () => {
    const plan = {
      id: 'plan-1',
      user_id: 'user-1',
      status: 'draft',
      goal: 'hypertrophy',
      level: 'intermediate',
      days_per_week: 4,
      session_duration_minutes: 60,
      available_equipment: ['mancuernas'],
      physical_limitations: null,
      sensitive_data_acknowledged: false,
      priorities: [],
      plan_payload: { version: 3, source: 'coach', schema_version: 1, routines: [] },
      explanation: 'Plan Coach',
      risk_notes: null,
      confidence: 'medium',
      input_summary: { created_by: 'coach' },
      provider: 'groq',
      model: 'llama-3.3-70b-versatile',
      fallback_used: false,
      created_at: '2026-07-08T10:00:00Z',
      reviewed_at: null,
    };
    const state = {
      profile: {
        id: 'profile-1',
        user_id: 'user-1',
        goal: 'hypertrophy',
        secondary_goal: null,
        plan_horizon_weeks: null,
        biological_sex: 'male',
        age: 29,
        height_cm: 180,
        weight_kg: 80,
        experience_level: 'intermediate',
        training_age_months: null,
        days_per_week: 4,
        session_duration_minutes: 60,
        equipment: ['mancuernas'],
        priorities: [],
        preferred_exercises: [],
        avoided_exercises: [],
        physical_limitations: null,
        sleep_quality: null,
        stress_level: null,
        current_fatigue: null,
        personal_data_acknowledged: true,
        sensitive_data_acknowledged: false,
        memory_summary: null,
        updated_at: '2026-07-08T10:00:00Z',
      },
      phase: 'ready_for_plan',
      recent_messages: [],
      assistant_message: 'Listo',
      known_facts: ['Objetivo hipertrofia'],
      missing_critical: [],
      missing_useful: ['sueno'],
      estimated_fields: ['volumen inicial'],
      misunderstanding_corrections: [],
      safety_flags: [],
      ready_for_plan: true,
      draft_plans: [plan],
      accepted_plan: null,
      privacy_notice: 'Privacidad',
      safety_notice: 'Seguridad',
      next_action: 'generate_plan_preview',
    };
    const fetchMock = vi
      .fn<typeof fetch>()
      .mockResolvedValueOnce(jsonResponse(state))
      .mockResolvedValueOnce(jsonResponse(state))
      .mockResolvedValueOnce(jsonResponse(plan))
      .mockResolvedValueOnce(jsonResponse({ ...plan, status: 'accepted' }))
      .mockResolvedValueOnce(jsonResponse({ ...plan, status: 'rejected' }))
      .mockResolvedValueOnce(jsonResponse({ ...plan, id: 'plan-2' }))
      .mockResolvedValueOnce(jsonResponse({ ...state, phase: 'onboarding', draft_plans: [] }));
    vi.stubGlobal('fetch', fetchMock);
    const client = await loadClient();

    await expect(client.getCoachState()).resolves.toEqual(state);
    await expect(client.sendCoachMessage({ message: 'Hola', personal_data_acknowledged: true, sensitive_data_acknowledged: false })).resolves.toEqual(state);
    await expect(client.generateCoachPlanDraft()).resolves.toEqual(plan);
    await expect(client.acceptCoachPlanDraft('plan-1')).resolves.toEqual({ ...plan, status: 'accepted' });
    await expect(client.rejectCoachPlanDraft('plan-1')).resolves.toEqual({ ...plan, status: 'rejected' });
    await expect(client.reviseCoachPlanDraft('plan-1', { instruction: 'Cambia pecho', sensitive_data_acknowledged: false })).resolves.toEqual({ ...plan, id: 'plan-2' });
    await expect(client.resetCoach()).resolves.toEqual({ ...state, phase: 'onboarding', draft_plans: [] });

    expect(fetchMock).toHaveBeenNthCalledWith(1, 'http://localhost:8000/ai/coach', expect.objectContaining({ method: 'GET' }));
    expect(fetchMock).toHaveBeenNthCalledWith(2, 'http://localhost:8000/ai/coach/messages', expect.objectContaining({ method: 'POST' }));
    expect(fetchMock).toHaveBeenNthCalledWith(3, 'http://localhost:8000/ai/coach/plan-drafts', expect.objectContaining({ method: 'POST' }));
    expect(fetchMock).toHaveBeenNthCalledWith(4, 'http://localhost:8000/ai/coach/plan-drafts/plan-1/accept', expect.objectContaining({ method: 'POST' }));
    expect(fetchMock).toHaveBeenNthCalledWith(5, 'http://localhost:8000/ai/coach/plan-drafts/plan-1/reject', expect.objectContaining({ method: 'POST' }));
    expect(fetchMock).toHaveBeenNthCalledWith(6, 'http://localhost:8000/ai/coach/plan-drafts/plan-1/revise', expect.objectContaining({ method: 'POST' }));
    expect(fetchMock).toHaveBeenNthCalledWith(7, 'http://localhost:8000/ai/coach/reset', expect.objectContaining({ method: 'POST' }));
  });

  it('calls AI session summary endpoints', async () => {
    const summary = {
      id: 'summary-1',
      user_id: 'user-1',
      session_id: 'session-1',
      summary: 'Resumen',
      improvements: ['Mejora'],
      drops: ['Caida'],
      warnings: ['Warning'],
      next_recommendation: 'Siguiente',
      input_summary: {},
      provider: 'internal',
      model: 'rules',
      fallback_used: false,
      created_at: '2026-07-08T10:00:00Z',
    };
    const fetchMock = vi
      .fn<typeof fetch>()
      .mockResolvedValueOnce(jsonResponse(summary))
      .mockResolvedValueOnce(jsonResponse(summary));
    vi.stubGlobal('fetch', fetchMock);
    const client = await loadClient();

    await expect(client.generateSessionSummary('session-1')).resolves.toEqual(summary);
    await expect(client.getSessionSummary('session-1')).resolves.toEqual(summary);

    expect(fetchMock).toHaveBeenNthCalledWith(1, 'http://localhost:8000/ai/session-summaries/session-1/generate', expect.objectContaining({ method: 'POST' }));
    expect(fetchMock).toHaveBeenNthCalledWith(2, 'http://localhost:8000/ai/session-summaries/session-1', expect.objectContaining({ method: 'GET' }));
  });

  it('calls stats overview endpoint with filters', async () => {
    const overview = {
      period: 'week',
      kpis: { total_sets: 1, session_count: 1, training_hours: '1.00', pr_count: 1 },
      volume_by_unit: [{ weight_unit: 'kg', total_volume: '500.00' }],
      volume_points: [],
      muscle_groups: [],
      top_exercises: [],
    };
    const fetchMock = vi.fn<typeof fetch>().mockResolvedValueOnce(jsonResponse(overview));
    vi.stubGlobal('fetch', fetchMock);
    const client = await loadClient();

    await expect(client.getStatsOverview('30d', { period: 'week', weightUnit: 'kg' })).resolves.toEqual(overview);

    expect(fetchMock).toHaveBeenCalledWith(
      expect.stringContaining('http://localhost:8000/stats/overview?'),
      expect.objectContaining({ method: 'GET' }),
    );
    const url = fetchMock.mock.calls[0][0] as string;
    expect(url).toContain('period=week');
    expect(url).toContain('weight_unit=kg');
    expect(url).toContain('start_date=');
  });
});

describe('account endpoints', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mocks.state.accessToken = 'access-token';
    mocks.state.refreshToken = 'refresh-token';
  });

  it('exports data and deletes the account clearing local tokens', async () => {
    const fetchMock = vi
      .fn<typeof fetch>()
      .mockResolvedValueOnce(jsonResponse({ format_version: 1, routines: [] }))
      .mockResolvedValueOnce(emptyResponse());
    vi.stubGlobal('fetch', fetchMock);
    const client = await loadClient();

    await expect(client.exportAccountData()).resolves.toMatchObject({ format_version: 1 });
    await client.deleteAccount('password123');

    expect(fetchMock).toHaveBeenNthCalledWith(1, 'http://localhost:8000/users/me/export', expect.objectContaining({ method: 'GET' }));
    expect(fetchMock).toHaveBeenNthCalledWith(
      2,
      'http://localhost:8000/users/me',
      expect.objectContaining({ method: 'DELETE', body: JSON.stringify({ password: 'password123' }) }),
    );
    expect(mocks.state.refreshToken).toBeNull();
  });

  it('keeps the session when the password is wrong', async () => {
    vi.stubGlobal('fetch', vi.fn<typeof fetch>().mockResolvedValueOnce(jsonResponse({ detail: 'Contraseña incorrecta.' }, 403)));
    const client = await loadClient();

    await expect(client.deleteAccount('wrong')).rejects.toThrow('Contraseña incorrecta.');
    expect(mocks.state.refreshToken).toBe('refresh-token');
  });
});
