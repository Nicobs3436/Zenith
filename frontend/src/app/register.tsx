import { Link, useRouter } from 'expo-router';
import { useState } from 'react';
import { StyleSheet, Text, View } from 'react-native';

import { register } from '@/api/client';
import { Field } from '@/components/Field';
import { PrimaryButton } from '@/components/PrimaryButton';
import { ZenithCard, ZenithCheckbox, ZenithHeader, ZenithLogo, ZenithNotice } from '@/components/ZenithUI';
import { ZenithScreen } from '@/components/ZenithScreen';
import { zenith } from '@/constants/zenithTheme';
import { registerErrorMessage } from '@/utils/authDisplay';

export default function RegisterScreen() {
  const router = useRouter();
  const [email, setEmail] = useState('');
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [acceptedTerms, setAcceptedTerms] = useState(false);
  const [adultConfirmed, setAdultConfirmed] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  async function submit() {
    if (!email.trim() || !username.trim() || !password) {
      setError('Email, nombre de usuario y contraseña son obligatorios.');
      return;
    }
    if (password.length < 8) {
      setError('La contraseña debe tener al menos 8 caracteres.');
      return;
    }
    if (!adultConfirmed) {
      setError('Zenith es solo para mayores de 18 años.');
      return;
    }
    if (!acceptedTerms) {
      setError('Acepta privacidad, términos y aviso médico para crear la cuenta.');
      return;
    }
    setLoading(true);
    setError(null);
    try {
      await register(email, username, password);
      router.replace('/dashboard');
    } catch (caught) {
      setError(registerErrorMessage(caught));
    } finally {
      setLoading(false);
    }
  }

  return (
    <ZenithScreen>
      <ZenithLogo />
      <ZenithHeader title="Crear cuenta" subtitle="Beta Zenith" />
      <ZenithCard style={styles.formCard}>
        <Field autoCapitalize="none" autoComplete="email" inputMode="email" keyboardType="email-address" label="Email" onChangeText={setEmail} textContentType="emailAddress" value={email} />
        <Field autoCapitalize="none" autoComplete="username" hint="Letras, números y guion bajo. Mínimo 3 caracteres." label="Nombre de usuario" onChangeText={setUsername} textContentType="username" value={username} />
        <Field autoCapitalize="none" autoComplete="new-password" hint="Mínimo 8 caracteres." label="Contraseña" onChangeText={setPassword} secureTextEntry textContentType="newPassword" value={password} />
      </ZenithCard>
      <ZenithCard style={styles.noticeBox}>
        <Text style={styles.noticeTitle}>Aviso beta</Text>
        <Text style={styles.noticeText}>Zenith no sustituye consejo médico ni profesional. Las limitaciones físicas son datos sensibles y solo deben indicarse si entiendes el aviso.</Text>
        <View style={styles.legalRow}>
          <Link href={'/privacy' as never} style={styles.link}>Privacidad</Link>
          <Text style={styles.separator}>/</Text>
          <Link href={'/terms' as never} style={styles.link}>Términos</Link>
        </View>
        <ZenithCheckbox checked={adultConfirmed} label="Confirmo que tengo 18 años o más" onChange={setAdultConfirmed} />
        <ZenithCheckbox checked={acceptedTerms} label="Acepto privacidad, términos y aviso médico" onChange={setAcceptedTerms} />
      </ZenithCard>
      {error && <ZenithNotice tone="danger">{error}</ZenithNotice>}
      <PrimaryButton disabled={loading} onPress={submit} title={loading ? 'Creando...' : 'Registrarme'} />
    </ZenithScreen>
  );
}

const styles = StyleSheet.create({
  formCard: { gap: 14 },
  noticeBox: {
    gap: 10,
  },
  noticeTitle: {
    color: zenith.colors.amber,
    fontFamily: zenith.font.bodyBold,
  },
  noticeText: {
    color: zenith.colors.foreground,
    fontFamily: zenith.font.body,
    lineHeight: 21,
  },
  legalRow: {
    alignItems: 'center',
    flexDirection: 'row',
    gap: 8,
  },
  link: {
    color: zenith.colors.primary,
    fontFamily: zenith.font.bodyBold,
  },
  separator: {
    color: zenith.colors.muted,
  },
});
