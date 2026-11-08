import { describe, expect, it } from 'vitest';

import { formatNextRank, formatRankCalculatedAt, formatRankScore, rankExplanationLines } from './rankDisplay';

describe('rankDisplay', () => {
  it('formats rank score with points suffix', () => {
    expect(formatRankScore('125.50')).toBe('125.50 pts');
  });

  it('formats next rank progress', () => {
    expect(formatNextRank({ next_rank: { id: 'rank-2', name: 'Intermedio', description: null, min_score: '300', sort_order: 2 }, points_to_next_rank: '42.00' })).toBe('Siguiente: Intermedio · faltan 42.00 pts');
  });

  it('formats max rank state', () => {
    expect(formatNextRank({ next_rank: null, points_to_next_rank: null })).toBe('Rango máximo alcanzado.');
  });

  it('formats pending calculation date', () => {
    expect(formatRankCalculatedAt(null)).toBe('pendiente');
  });

  it('formats persisted calculation date', () => {
    const value = '2026-07-08T12:30:00Z';

    expect(formatRankCalculatedAt(value)).toBe(new Date(value).toLocaleString('es-ES'));
  });

  it('exposes stable explanation lines', () => {
    expect(rankExplanationLines).toEqual([
      'Suma volumen con peso, mejora de 1RM estimado y amplitud de ejercicios progresados.',
      'No hay puntos por sesiones registradas ni semanas activas.',
      'kg y lb se mantienen separados; no hay conversion automática.',
    ]);
  });
});
