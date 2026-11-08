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

import { zenith } from '@/constants/zenithTheme';

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
      <Stack.Screen name="session-active" options={{ title: 'Sesion activa' }} />
      <Stack.Screen name="session-new" options={{ title: 'Nueva sesion' }} />
      <Stack.Screen name="session-detail" options={{ title: 'Detalle sesion' }} />
      <Stack.Screen name="session-edit" options={{ title: 'Editar sesion' }} />
      <Stack.Screen name="stats" options={{ headerShown: false, title: 'Estadisticas' }} />
      <Stack.Screen name="coach" options={{ headerShown: false, title: 'Entrenador IA' }} />
      <Stack.Screen name="account" options={{ title: 'Cuenta' }} />
      <Stack.Screen name="privacy" options={{ title: 'Privacidad' }} />
      <Stack.Screen name="terms" options={{ title: 'Terminos' }} />
    </Stack>
    </>
  );
}
