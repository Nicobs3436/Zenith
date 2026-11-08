import {
  BarlowCondensed_700Bold,
  BarlowCondensed_800ExtraBold,
} from '@expo-google-fonts/barlow-condensed';
import {
  DMSans_400Regular,
  DMSans_500Medium,
  DMSans_700Bold,
} from '@expo-google-fonts/dm-sans';
import {
  JetBrainsMono_400Regular,
  JetBrainsMono_500Medium,
} from '@expo-google-fonts/jetbrains-mono';
import { useFonts } from 'expo-font';
import { Stack } from 'expo-router';
import { StatusBar } from 'expo-status-bar';
import { useEffect } from 'react';

import { zenith } from '@/constants/zenithTheme';
import { initSentry } from '@/observability/sentry';
import { syncPendingSessions } from '@/sync/sessionSync';

initSentry();

const SYNC_INTERVAL_MS = 60_000;

function usePendingSessionSync() {
  useEffect(() => {
    const run = () => {
      syncPendingSessions().catch(() => undefined);
    };
    run();
    const timer = setInterval(run, SYNC_INTERVAL_MS);
    const hasWindowEvents = typeof window !== 'undefined' && typeof window.addEventListener === 'function';
    if (hasWindowEvents) {
      window.addEventListener('online', run);
    }
    return () => {
      clearInterval(timer);
      if (hasWindowEvents) {
        window.removeEventListener('online', run);
      }
    };
  }, []);
}

export default function RootLayout() {
  const [fontsLoaded] = useFonts({
    BarlowCondensed_700Bold,
    BarlowCondensed_800ExtraBold,
    DMSans_400Regular,
    DMSans_500Medium,
    DMSans_700Bold,
    JetBrainsMono_400Regular,
    JetBrainsMono_500Medium,
  });

  usePendingSessionSync();

  if (!fontsLoaded) {
    return null;
  }

  return (
    <>
    <StatusBar style="light" />
    <Stack screenOptions={{ headerStyle: { backgroundColor: zenith.colors.background }, headerTintColor: zenith.colors.foreground, contentStyle: { backgroundColor: zenith.colors.background } }}>
      <Stack.Screen name="index" options={{ headerShown: false, title: 'Zenith' }} />
      <Stack.Screen name="login" options={{ title: 'Login' }} />
      <Stack.Screen name="register" options={{ title: 'Registro' }} />
      <Stack.Screen name="dashboard" options={{ headerShown: false, title: 'Inicio' }} />
      <Stack.Screen name="rank" options={{ headerShown: false, title: 'Rango' }} />
      <Stack.Screen name="exercises" options={{ headerShown: false, title: 'Ejercicios' }} />
      <Stack.Screen name="exercise-new" options={{ title: 'Nuevo ejercicio' }} />
      <Stack.Screen name="exercise-detail" options={{ title: 'Detalle ejercicio' }} />
      <Stack.Screen name="routines" options={{ headerShown: false, title: 'Rutinas' }} />
      <Stack.Screen name="routine-new" options={{ title: 'Nueva rutina' }} />
      <Stack.Screen name="routine-edit" options={{ title: 'Editar rutina' }} />
      <Stack.Screen name="sessions" options={{ title: 'Sesiones' }} />
      <Stack.Screen name="session-active" options={{ title: 'Sesión activa' }} />
      <Stack.Screen name="session-new" options={{ title: 'Nueva sesión' }} />
      <Stack.Screen name="session-detail" options={{ title: 'Detalle sesión' }} />
      <Stack.Screen name="session-edit" options={{ title: 'Editar sesión' }} />
      <Stack.Screen name="stats" options={{ headerShown: false, title: 'Estadísticas' }} />
      <Stack.Screen name="coach" options={{ headerShown: false, title: 'Entrenador IA' }} />
      <Stack.Screen name="account" options={{ title: 'Cuenta' }} />
      <Stack.Screen name="forgot-password" options={{ title: 'Recuperar contraseña' }} />
      <Stack.Screen name="reset-password" options={{ title: 'Nueva contraseña' }} />
      <Stack.Screen name="verify-email" options={{ title: 'Verificar email' }} />
      <Stack.Screen name="privacy" options={{ title: 'Privacidad' }} />
      <Stack.Screen name="terms" options={{ title: 'Términos' }} />
    </Stack>
    </>
  );
}
