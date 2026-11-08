import { Link, useRouter } from 'expo-router';
import { useEffect, useState } from 'react';
import { StyleSheet, Text, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';

import { restoreSession } from '@/api/client';
import { zenith } from '@/constants/zenithTheme';

export default function IndexScreen() {
  const router = useRouter();
  const [checking, setChecking] = useState(true);

  useEffect(() => {
    restoreSession()
      .then((user) => {
        if (user) {
          router.replace('/dashboard');
        }
      })
      // Sin red al arrancar: se conservan los tokens y el usuario puede reintentar al iniciar sesion.
      .catch(() => undefined)
      .finally(() => setChecking(false));
  }, [router]);

  return (
    <SafeAreaView style={styles.container}>
      <View style={styles.hero}>
        <Text accessibilityRole="header" style={styles.brand}>ZENITH</Text>
        <Text style={styles.tagline}>Planifica tus rutinas, registra cada serie y progresa con un Coach con IA.</Text>
        {checking && <View style={styles.checkingDot} />}
      </View>
      <View style={styles.actions}>
        <Link href="/login" style={styles.primaryLink}>Iniciar sesión</Link>
        <Link href="/register" style={styles.secondaryLink}>Crear cuenta</Link>
      </View>
      <View style={styles.legalLinks}>
        <Link href={'/privacy' as never} style={styles.legalLink}>Privacidad</Link>
        <Text style={styles.legalSeparator}>/</Text>
        <Link href={'/terms' as never} style={styles.legalLink}>Términos y condiciones</Link>
      </View>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: {
    backgroundColor: zenith.colors.background,
    flex: 1,
    justifyContent: 'space-between',
    padding: zenith.spacing.page,
  },
  hero: { alignItems: 'center', flex: 1, justifyContent: 'center' },
  brand: { color: zenith.colors.foreground, fontFamily: zenith.font.display, fontSize: 76, fontWeight: '900', letterSpacing: 8, lineHeight: 82 },
  tagline: { color: zenith.colors.muted, fontFamily: zenith.font.body, fontSize: 17, lineHeight: 24, marginTop: 12, maxWidth: 320, textAlign: 'center' },
  checkingDot: { backgroundColor: zenith.colors.primary, borderRadius: 999, height: 7, marginTop: 12, width: 7 },
  actions: {
    gap: 12,
    marginBottom: 22,
  },
  primaryLink: {
    backgroundColor: zenith.colors.primary,
    borderRadius: 16,
    color: zenith.colors.primaryForeground,
    fontFamily: zenith.font.bodyBold,
    fontSize: 17,
    fontWeight: '800',
    padding: 16,
    textAlign: 'center',
  },
  secondaryLink: {
    borderColor: zenith.colors.border,
    borderRadius: 16,
    borderWidth: 1,
    color: zenith.colors.foreground,
    fontFamily: zenith.font.bodyBold,
    fontSize: 17,
    fontWeight: '800',
    padding: 16,
    textAlign: 'center',
  },
  legalLinks: {
    alignItems: 'center',
    flexDirection: 'row',
    gap: 8,
    justifyContent: 'center',
    paddingBottom: 8,
  },
  legalLink: {
    color: zenith.colors.muted,
    fontFamily: zenith.font.bodyBold,
    fontWeight: '800',
  },
  legalSeparator: {
    color: zenith.colors.muted,
  },
});
