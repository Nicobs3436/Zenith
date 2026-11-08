import { beforeEach, describe, expect, it, vi } from 'vitest';

const mocks = vi.hoisted(() => {
  const secureStoreValues = new Map<string, string>();
  const platform = { OS: 'web' };
  const secureStore = {
    isAvailableAsync: vi.fn(async () => true),
    setItemAsync: vi.fn(async (key: string, value: string) => {
      secureStoreValues.set(key, value);
    }),
    getItemAsync: vi.fn(async (key: string) => secureStoreValues.get(key) ?? null),
    deleteItemAsync: vi.fn(async (key: string) => {
      secureStoreValues.delete(key);
    }),
  };

  return { platform, secureStore, secureStoreValues };
});

vi.mock('react-native', () => ({ Platform: mocks.platform }));
vi.mock('expo-secure-store', () => mocks.secureStore);

function installLocalStorage() {
  const values = new Map<string, string>();
  const localStorageMock = {
    getItem: vi.fn((key: string) => values.get(key) ?? null),
    setItem: vi.fn((key: string, value: string) => {
      values.set(key, value);
    }),
    removeItem: vi.fn((key: string) => {
      values.delete(key);
    }),
    clear: vi.fn(() => {
      values.clear();
    }),
  };

  vi.stubGlobal('localStorage', localStorageMock);
  return localStorageMock;
}

describe('tokenStorage', () => {
  beforeEach(() => {
    vi.resetModules();
    vi.clearAllMocks();
    mocks.platform.OS = 'web';
    mocks.secureStoreValues.clear();
    installLocalStorage();
  });

  it('keeps the access token only in memory on web and never stores a refresh token', async () => {
    const legacy = installLocalStorage();
    legacy.setItem('gym_ai_refresh_token', 'legacy-refresh');
    const storage = await import('./tokenStorage');

    await storage.setAuthTokens({ accessToken: 'access-token', refreshToken: 'refresh-token' });

    expect(await storage.getAccessToken()).toBe('access-token');
    expect(await storage.getRefreshToken()).toBeNull();
    expect(legacy.getItem('gym_ai_refresh_token')).toBeNull();
    expect(legacy.setItem).toHaveBeenCalledTimes(1);

    const reloadedStorage = await import('./tokenStorage');
    vi.resetModules();
    const freshStorage = await import('./tokenStorage');
    expect(await freshStorage.loadAuthTokens()).toEqual({ accessToken: null, refreshToken: null });

    await reloadedStorage.clearAuthTokens();
    expect(await reloadedStorage.getAccessToken()).toBeNull();
  });

  it('stores, loads and clears access and refresh tokens with SecureStore on native', async () => {
    mocks.platform.OS = 'ios';
    const storage = await import('./tokenStorage');

    await storage.setAuthTokens({ accessToken: 'native-access-token', refreshToken: 'native-refresh-token' });

    expect(await storage.getAccessToken()).toBe('native-access-token');
    expect(await storage.getRefreshToken()).toBe('native-refresh-token');
    expect(mocks.secureStore.setItemAsync).toHaveBeenCalledTimes(2);

    await storage.clearAuthTokens();

    expect(await storage.getAccessToken()).toBeNull();
    expect(await storage.getRefreshToken()).toBeNull();
    expect(mocks.secureStore.deleteItemAsync).toHaveBeenCalledTimes(2);
  });
});
