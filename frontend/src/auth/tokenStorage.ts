import * as SecureStore from 'expo-secure-store';
import { Platform } from 'react-native';

// Movil: access y refresh token en expo-secure-store (cifrado por el sistema).
// Web: el refresh token vive en una cookie httpOnly que pone la API (JavaScript no puede leerla) y el
// access token (30 min) solo en memoria. Al recargar la pagina se pide uno nuevo con la cookie.
const ACCESS_TOKEN_KEY = 'gym_ai_access_token';
const REFRESH_TOKEN_KEY = 'gym_ai_refresh_token';

let accessToken: string | null = null;
let refreshToken: string | null = null;

export type AuthTokens = {
  accessToken: string;
  refreshToken: string | null;
};

export const usesCookieSession = () => Platform.OS === 'web';

function clearLegacyWebStorage() {
  // Versiones anteriores guardaban ambos tokens en localStorage: se eliminan.
  try {
    localStorage.removeItem(ACCESS_TOKEN_KEY);
    localStorage.removeItem(REFRESH_TOKEN_KEY);
  } catch {
    // localStorage no disponible (modo privado estricto): nada que limpiar.
  }
}

async function secureStoreAvailable() {
  return SecureStore.isAvailableAsync();
}

export async function setAuthTokens(tokens: AuthTokens) {
  accessToken = tokens.accessToken;
  if (usesCookieSession()) {
    refreshToken = null;
    clearLegacyWebStorage();
    return;
  }

  refreshToken = tokens.refreshToken;
  if (!(await secureStoreAvailable())) {
    return;
  }
  await SecureStore.setItemAsync(ACCESS_TOKEN_KEY, tokens.accessToken);
  if (tokens.refreshToken) {
    await SecureStore.setItemAsync(REFRESH_TOKEN_KEY, tokens.refreshToken);
  }
}

export async function getAccessToken() {
  if (accessToken !== null || usesCookieSession()) {
    return accessToken;
  }
  return (await loadAuthTokens()).accessToken;
}

export async function getRefreshToken() {
  if (refreshToken !== null || usesCookieSession()) {
    return refreshToken;
  }
  return (await loadAuthTokens()).refreshToken;
}

export async function loadAuthTokens() {
  if (usesCookieSession()) {
    clearLegacyWebStorage();
    return { accessToken, refreshToken: null };
  }
  if (await secureStoreAvailable()) {
    const [storedAccess, storedRefresh] = await Promise.all([
      SecureStore.getItemAsync(ACCESS_TOKEN_KEY),
      SecureStore.getItemAsync(REFRESH_TOKEN_KEY),
    ]);
    accessToken = storedAccess;
    refreshToken = storedRefresh;
  }
  return { accessToken, refreshToken };
}

export async function clearAuthTokens() {
  accessToken = null;
  refreshToken = null;
  if (usesCookieSession()) {
    clearLegacyWebStorage();
    return;
  }
  if (await secureStoreAvailable()) {
    await SecureStore.deleteItemAsync(ACCESS_TOKEN_KEY);
    await SecureStore.deleteItemAsync(REFRESH_TOKEN_KEY);
  }
}
