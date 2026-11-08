import { RankProgress } from '@/api/client';

export const rankExplanationLines = [
  'Suma volumen con peso, mejora de 1RM estimado y amplitud de ejercicios progresados.',
  'No hay puntos por sesiones registradas ni semanas activas.',
  'kg y lb se mantienen separados; no hay conversion automática.',
];

export function formatRankScore(score: string) {
  return `${score} pts`;
}

export function formatNextRank(rank: Pick<RankProgress, 'next_rank' | 'points_to_next_rank'>) {
  if (!rank.next_rank) {
    return 'Rango máximo alcanzado.';
  }
  return `Siguiente: ${rank.next_rank.name} · faltan ${rank.points_to_next_rank} pts`;
}

export function formatRankCalculatedAt(calculatedAt: string | null) {
  return calculatedAt ? new Date(calculatedAt).toLocaleString('es-ES') : 'pendiente';
}
