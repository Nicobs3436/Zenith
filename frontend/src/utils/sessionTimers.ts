// Los temporizadores se calculan desde marcas de tiempo, no sumando ticks: en segundo plano el
// sistema pausa los intervalos y un contador acumulado se quedaria atrasado.
export function secondsBetween(fromMs: number, toMs: number) {
  return Math.max(0, Math.floor((toMs - fromMs) / 1000));
}

export function secondsUntil(targetMs: number | null, nowMs: number) {
  return targetMs === null ? 0 : Math.max(0, Math.ceil((targetMs - nowMs) / 1000));
}

export function restDeadline(restSeconds: number) {
  return Date.now() + restSeconds * 1000;
}
