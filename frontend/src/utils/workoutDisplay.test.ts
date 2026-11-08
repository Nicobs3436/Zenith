import { describe, expect, it } from 'vitest';

import { countLabel } from './workoutDisplay';

describe('countLabel', () => {
  it('uses singular only for exactly one item', () => {
    expect(countLabel(1, 'serie', 'series')).toBe('1 serie');
    expect(countLabel(0, 'serie', 'series')).toBe('0 series');
    expect(countLabel(3, 'ejercicio', 'ejercicios')).toBe('3 ejercicios');
  });
});
