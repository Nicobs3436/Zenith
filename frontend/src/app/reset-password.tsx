import { Link, useLocalSearchParams } from 'expo-router';
import { useState } from 'react';
import { StyleSheet, Text } from 'react-native';

import { confirmPasswordReset } from '@/api/client';
import { Field } from '@/components/Field';
import { PrimaryButton } from '@/components/PrimaryButton';
import { ZenithCard, ZenithHeader, ZenithLogo, ZenithNotice } from '@/components/ZenithUI';
import { ZenithScreen } from '@/components/ZenithScreen';
import { zenith } from '@/constants/zenithTheme';

function paramValue(value: string | string[] | undefined) {
  return Array.isArray(value) ? value[0] : value;
}

export default function ResetPasswordScreen() {
  const token = paramValue(useLocalSearchParams().token) ?? '';
  const [password, setPassword] = useState('');
  const [repeat, setRepeat] = useState('');
  const [done, setDone] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  async function submit() {
    if (password.length < 8) {
      setError('La contraseña debe tener al menos 8 caracteres.');
      return;
    }
    if (password !== repeat) {
      setError('Las contraseñas no coinciden.');
      return;
    }
    setLoading(true);
    setError(null);
    try {
      await confirmPasswordReset(token, password);
      setDone(true);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : 'No se pudo cambiar la contraseña.');
    } finally {
      setLoading(false);
    }
  }

  if (!token) {
    return (
      <ZenithScreen>
        <ZenithHeader title="Enlace no válido" subtitle="Recuperar contraseña" />
        <ZenithNotice tone="danger">Falta el código del enlace. Abre el enlace completo del email o pide uno nuevo.</ZenithNotice>
        <Link accessibilityRole="link" href={'/forgot-password' as never} style={styles.link}>Pedir un enlace nuevo</Link>
      </ZenithScreen>
    );
  }

  return (
    <ZenithScreen>
      <ZenithLogo />
      <ZenithHeader title="Nueva contraseña" subtitle="Recuperar contraseña" />
      {done ? (
        <ZenithCard style={styles.card}>
          <ZenithNotice tone="success">Contraseña cambiada. Por seguridad hemos cerrado tus otras sesiones.</ZenithNotice>
          <Link accessibilityRole="link" href="/login" style={styles.link}>Iniciar sesión</Link>
        </ZenithCard>
      ) : (
        <ZenithCard style={styles.card}>
          <Text style={styles.text}>Elige una contraseña nueva de al menos 8 caracteres.</Text>
          <Field autoCapitalize="none" autoComplete="new-password" label="Contraseña nueva" onChangeText={setPassword} secureTextEntry textContentType="newPassword" value={password} />
          <Field autoCapitalize="none" autoComplete="new-password" label="Repite la contraseña" onChangeText={setRepeat} onSubmitEditing={submit} returnKeyType="go" secureTextEntry textContentType="newPassword" value={repeat} />
          {error && <ZenithNotice tone="danger">{error}</ZenithNotice>}
          <PrimaryButton disabled={loading} onPress={submit} title={loading ? 'Guardando...' : 'Cambiar contraseña'} />
        </ZenithCard>
      )}
    </ZenithScreen>
  );
}

const styles = StyleSheet.create({
  text: { color: zenith.colors.muted, fontFamily: zenith.font.body, fontSize: 15, lineHeight: 22 },
  card: { gap: 14 },
  link: { alignSelf: 'center', color: zenith.colors.primary, fontFamily: zenith.font.bodyBold, paddingVertical: 12 },
});
