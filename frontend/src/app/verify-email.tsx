import { Link, useLocalSearchParams } from 'expo-router';
import { useEffect, useState } from 'react';
import { StyleSheet } from 'react-native';

import { verifyEmail } from '@/api/client';
import { ZenithCard, ZenithHeader, ZenithLogo, ZenithNotice } from '@/components/ZenithUI';
import { ZenithScreen } from '@/components/ZenithScreen';
import { zenith } from '@/constants/zenithTheme';

function paramValue(value: string | string[] | undefined) {
  return Array.isArray(value) ? value[0] : value;
}

type Status = 'checking' | 'verified' | 'failed';

export default function VerifyEmailScreen() {
  const token = paramValue(useLocalSearchParams().token) ?? '';
  const [status, setStatus] = useState<Status>(token ? 'checking' : 'failed');

  useEffect(() => {
    if (!token) {
      return;
    }
    verifyEmail(token)
      .then(() => setStatus('verified'))
      .catch(() => setStatus('failed'));
  }, [token]);

  return (
    <ZenithScreen>
      <ZenithLogo />
      <ZenithHeader title="Verificar email" subtitle="Cuenta Zenith" />
      <ZenithCard style={styles.card}>
        {status === 'checking' && <ZenithNotice>Comprobando el enlace...</ZenithNotice>}
        {status === 'verified' && <ZenithNotice tone="success">Email verificado. Tu cuenta ya está protegida.</ZenithNotice>}
        {status === 'failed' && (
          <ZenithNotice tone="danger">El enlace no es válido o ha caducado. Desde Inicio puedes pedir uno nuevo.</ZenithNotice>
        )}
        <Link accessibilityRole="link" href="/dashboard" style={styles.link}>Ir a Inicio</Link>
      </ZenithCard>
    </ZenithScreen>
  );
}

const styles = StyleSheet.create({
  card: { gap: 14 },
  link: { alignSelf: 'center', color: zenith.colors.primary, fontFamily: zenith.font.bodyBold, paddingVertical: 12 },
});
