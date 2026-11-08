import { Link } from 'expo-router';
import { useState } from 'react';
import { StyleSheet, Text } from 'react-native';

import { requestPasswordReset } from '@/api/client';
import { Field } from '@/components/Field';
import { PrimaryButton } from '@/components/PrimaryButton';
import { ZenithCard, ZenithHeader, ZenithLogo, ZenithNotice } from '@/components/ZenithUI';
import { ZenithScreen } from '@/components/ZenithScreen';
import { zenith } from '@/constants/zenithTheme';

export default function ForgotPasswordScreen() {
  const [email, setEmail] = useState('');
  const [sent, setSent] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  async function submit() {
    if (!email.trim()) {
      setError('Escribe el email de tu cuenta.');
      return;
    }
    setLoading(true);
    setError(null);
    try {
      await requestPasswordReset(email.trim());
      setSent(true);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : 'No se pudo enviar el enlace.');
    } finally {
      setLoading(false);
    }
  }

  return (
    <ZenithScreen>
      <ZenithLogo />
      <ZenithHeader title="Recuperar contraseña" subtitle="Acceso Zenith" />
      <Text style={styles.text}>Te enviaremos un enlace para crear una contraseña nueva. Caduca en 1 hora.</Text>
      <ZenithCard style={styles.card}>
        <Field autoCapitalize="none" autoComplete="email" inputMode="email" keyboardType="email-address" label="Email" onChangeText={setEmail} onSubmitEditing={submit} returnKeyType="send" textContentType="emailAddress" value={email} />
        {sent && <ZenithNotice tone="success">Si ese email está registrado, te hemos enviado el enlace. Revisa también la carpeta de spam.</ZenithNotice>}
        {error && <ZenithNotice tone="danger">{error}</ZenithNotice>}
        <PrimaryButton disabled={loading} onPress={submit} title={loading ? 'Enviando...' : sent ? 'Enviar de nuevo' : 'Enviar enlace'} />
      </ZenithCard>
      <Link accessibilityRole="link" href="/login" style={styles.link}>Volver a iniciar sesión</Link>
    </ZenithScreen>
  );
}

const styles = StyleSheet.create({
  text: { color: zenith.colors.muted, fontFamily: zenith.font.body, fontSize: 15, lineHeight: 22 },
  card: { gap: 14 },
  link: { alignSelf: 'center', color: zenith.colors.primary, fontFamily: zenith.font.bodyBold, paddingVertical: 12 },
});
