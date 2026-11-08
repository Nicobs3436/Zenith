import { describe, expect, it } from 'vitest';

import { loginErrorMessage, registerErrorMessage, SESSION_EXPIRED_NOTICE } from './authDisplay';

describe('authDisplay', () => {
  it('exposes a stable session expired notice', () => {
    expect(SESSION_EXPIRED_NOTICE).toBe('Tu sesión ha caducado. Vuelve a iniciar sesión.');
  });

  it('formats invalid login credentials', () => {
    expect(loginErrorMessage(new Error('Invalid email or password.'))).toBe('Email o password incorrectos.');
  });

  it('formats auth rate limiting errors', () => {
    expect(loginErrorMessage(new Error('Too many attempts. Try again later.'))).toBe('Demasiados intentos. Espera un momento y vuelve a probar.');
    expect(registerErrorMessage(new Error('Request failed with status 429'))).toBe('Demasiados intentos. Espera un momento y vuelve a probar.');
  });

  it('formats duplicate email registration errors', () => {
    expect(registerErrorMessage(new Error('User with this email already exists.'))).toBe('Ya existe una cuenta con ese email.');
  });

  it('formats duplicate username registration errors', () => {
    expect(registerErrorMessage(new Error('User with this username already exists.'))).toBe('Ya existe una cuenta con ese username.');
  });

  it('formats validation errors for password, username and email', () => {
    expect(registerErrorMessage(new Error('password: String should have at least 8 characters'))).toBe('El password debe tener al menos 8 caracteres.');
    expect(registerErrorMessage(new Error('username: String should have at least 3 characters'))).toBe('El username debe tener al menos 3 caracteres.');
    expect(registerErrorMessage(new Error('username: String should match pattern'))).toBe('El username solo puede usar letras, numeros y guion bajo.');
    expect(registerErrorMessage(new Error('email: value is not a valid email address'))).toBe('Revisa que el email sea válido.');
  });

  it('keeps unknown backend messages when no mapping matches', () => {
    expect(loginErrorMessage(new Error('Backend unavailable'))).toBe('Backend unavailable');
  });

  it('uses fallback for non-error values', () => {
    expect(loginErrorMessage('bad')).toBe('No se pudo iniciar sesión.');
    expect(registerErrorMessage('bad')).toBe('No se pudo crear la cuenta.');
  });
});
