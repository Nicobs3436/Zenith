export const SESSION_EXPIRED_NOTICE = 'Tu sesión ha caducado. Vuelve a iniciar sesión.';

export function loginErrorMessage(error: unknown) {
  return friendlyAuthErrorMessage(error, 'No se pudo iniciar sesión.');
}

export function registerErrorMessage(error: unknown) {
  return friendlyAuthErrorMessage(error, 'No se pudo crear la cuenta.');
}

function friendlyAuthErrorMessage(error: unknown, fallback: string) {
  const message = error instanceof Error ? error.message : fallback;
  const normalized = message.toLowerCase();

  if (normalized.includes('invalid email or password')) {
    return 'Email o password incorrectos.';
  }
  if (normalized.includes('too many attempts') || normalized.includes('status 429')) {
    return 'Demasiados intentos. Espera un momento y vuelve a probar.';
  }
  if (normalized.includes('user with this email already exists')) {
    return 'Ya existe una cuenta con ese email.';
  }
  if (normalized.includes('user with this username already exists')) {
    return 'Ya existe una cuenta con ese username.';
  }
  if (normalized.includes('password') && normalized.includes('at least 8')) {
    return 'El password debe tener al menos 8 caracteres.';
  }
  if (normalized.includes('username') && normalized.includes('string should have at least 3')) {
    return 'El username debe tener al menos 3 caracteres.';
  }
  if (normalized.includes('username') && normalized.includes('string should match pattern')) {
    return 'El username solo puede usar letras, numeros y guion bajo.';
  }
  if (normalized.includes('email')) {
    return 'Revisa que el email sea válido.';
  }

  return message || fallback;
}
