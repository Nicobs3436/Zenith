import { Link, useLocalSearchParams, useRouter } from 'expo-router';
import { useState } from 'react';
import { StyleSheet, Text, View } from 'react-native';

import { login } from '@/api/client';
import { Field } from '@/components/Field';
import { PrimaryButton } from '@/components/PrimaryButton';
import { ZenithCard, ZenithHeader, ZenithLogo, ZenithNotice } from '@/components/ZenithUI';
import { ZenithScreen } from '@/components/ZenithScreen';
import { zenith } from '@/constants/zenithTheme';
import { loginErrorMessage, SESSION_EXPIRED_NOTICE } from '@/utils/authDisplay';

export default function LoginScreen() {
  const router = useRouter();
  const { notice } = useLocalSearchParams();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const sessionNotice = notice === 'session-expired' ? SESSION_EXPIRED_NOTICE : null;

  async function submit() {
    if (!email.trim() || !password) {
      setError('Email y password son obligatorios.');
      return;
    }
    setLoading(true);
    setError(null);
    try {
      await login(email, password);
      router.replace('/dashboard');
    } catch (caught) {
      setError(loginErrorMessage(caught));
    } finally {
      setLoading(false);
    }
  }

  return (
    <ZenithScreen>
      <ZenithLogo />
      <ZenithHeader title="Entrar" subtitle="Acceso Zenith" />
      <Text style={styles.subtitle}>Continua registrando sesiones, rutinas y progreso con IA revisable.</Text>
      {sessionNotice && <ZenithNotice tone="warning">{sessionNotice}</ZenithNotice>}
      <ZenithCard style={styles.card}>
        <Field autoCapitalize="none" autoComplete="email" inputMode="email" keyboardType="email-address" label="Email" onChangeText={setEmail} textContentType="emailAddress" value={email} />
        <Field autoCapitalize="none" autoComplete="current-password" label="Contraseña" onChangeText={setPassword} onSubmitEditing={submit} returnKeyType="go" secureTextEntry textContentType="password" value={password} />
        {error && <ZenithNotice tone="danger">{error}</ZenithNotice>}
        <PrimaryButton disabled={loading} onPress={submit} title={loading ? 'Entrando...' : 'Iniciar sesión'} />
      </ZenithCard>
      <View style={styles.legalCard}>
        <Text style={styles.legalText}>Al usar Zenith aceptas el aviso médico de beta, privacidad y términos.</Text>
        <View style={styles.legalRow}>
          <Link href={'/privacy' as never} style={styles.link}>Privacidad</Link>
          <Text style={styles.separator}>/</Text>
          <Link href={'/terms' as never} style={styles.link}>Términos</Link>
        </View>
      </View>
    </ZenithScreen>
  );
}

const styles = StyleSheet.create({
  subtitle: { color: zenith.colors.muted, fontFamily: zenith.font.body, fontSize: 15, lineHeight: 22 },
  card: { gap: 14 },
  legalCard: { backgroundColor: zenith.colors.secondary, borderColor: zenith.colors.border, borderRadius: 16, borderWidth: 1, gap: 10, padding: 14 },
  legalText: {
    color: zenith.colors.muted,
    fontFamily: zenith.font.body,
    lineHeight: 20,
  },
  legalRow: { alignItems: 'center', flexDirection: 'row', gap: 8 },
  link: {
    color: zenith.colors.primary,
    fontFamily: zenith.font.bodyBold,
  },
  separator: { color: zenith.colors.muted },
});
