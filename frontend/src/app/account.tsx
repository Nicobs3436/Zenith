import { useRouter } from 'expo-router';
import { Download, Trash2 } from 'lucide-react-native';
import { useEffect, useState } from 'react';
import { Platform, Share, StyleSheet, Text } from 'react-native';

import { deleteAccount, exportAccountData, getMe, User } from '@/api/client';
import { Field } from '@/components/Field';
import { ZenithButton, ZenithCard, ZenithCheckbox, ZenithHeader, ZenithNotice } from '@/components/ZenithUI';
import { ZenithScreen } from '@/components/ZenithScreen';
import { zenith } from '@/constants/zenithTheme';
import { clearWorkoutDraft } from '@/storage/workoutDraft';

function exportFileName(now = new Date()) {
  return `zenith-datos-${now.toISOString().slice(0, 10)}.json`;
}

async function deliverExport(data: Record<string, unknown>) {
  const json = JSON.stringify(data, null, 2);
  if (Platform.OS === 'web') {
    const url = URL.createObjectURL(new Blob([json], { type: 'application/json' }));
    const link = document.createElement('a');
    link.href = url;
    link.download = exportFileName();
    link.click();
    URL.revokeObjectURL(url);
    return;
  }
  await Share.share({ title: exportFileName(), message: json });
}

export default function AccountScreen() {
  const router = useRouter();
  const [user, setUser] = useState<User | null>(null);
  const [exporting, setExporting] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const [password, setPassword] = useState('');
  const [confirmed, setConfirmed] = useState(false);
  const [notice, setNotice] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    getMe()
      .then(setUser)
      .catch((caught) => setError(caught instanceof Error ? caught.message : 'No se pudo cargar la cuenta.'));
  }, []);

  async function submitExport() {
    setExporting(true);
    setError(null);
    setNotice(null);
    try {
      await deliverExport(await exportAccountData());
      setNotice('Exportación lista: incluye rutinas, sesiones, series, ejercicios propios y datos del Coach.');
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : 'No se pudo exportar.');
    } finally {
      setExporting(false);
    }
  }

  async function submitDelete() {
    if (!confirmed || !password) {
      setError('Escribe tu contraseña y confirma que entiendes que el borrado es permanente.');
      return;
    }
    setDeleting(true);
    setError(null);
    try {
      await deleteAccount(password);
      await clearWorkoutDraft();
      router.replace('/');
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : 'No se pudo eliminar la cuenta.');
      setDeleting(false);
    }
  }

  return (
    <ZenithScreen>
      <ZenithHeader title="Cuenta" subtitle={user ? `${user.username} · ${user.email}` : 'Tus datos'} />
      {notice && <ZenithNotice tone="success">{notice}</ZenithNotice>}
      {error && <ZenithNotice tone="danger">{error}</ZenithNotice>}

      <ZenithCard style={styles.card}>
        <Text style={styles.cardTitle}>Exportar mis datos</Text>
        <Text style={styles.text}>Descarga una copia en JSON de todo lo que Zenith guarda de ti. No incluye tu contraseña.</Text>
        <ZenithButton
          disabled={exporting}
          icon={<Download color={zenith.colors.primaryForeground} size={16} />}
          onPress={submitExport}
          title={exporting ? 'Preparando...' : 'Exportar datos'}
        />
      </ZenithCard>

      <ZenithCard style={styles.card}>
        <Text style={styles.cardTitle}>Eliminar cuenta</Text>
        <Text style={styles.text}>Borra para siempre tu cuenta, rutinas, sesiones, estadísticas, rango y conversaciones del Coach. No se puede deshacer: exporta antes si quieres conservar una copia.</Text>
        <Field
          autoCapitalize="none"
          autoComplete="current-password"
          label="Contraseña actual"
          onChangeText={setPassword}
          secureTextEntry
          value={password}
        />
        <ZenithCheckbox checked={confirmed} label="Entiendo que el borrado es permanente" onChange={setConfirmed} tone="danger" />
        <ZenithButton
          disabled={deleting || !confirmed || !password}
          icon={<Trash2 color={zenith.colors.foreground} size={16} />}
          onPress={submitDelete}
          title={deleting ? 'Eliminando...' : 'Eliminar mi cuenta'}
          variant="danger"
        />
      </ZenithCard>
    </ZenithScreen>
  );
}

const styles = StyleSheet.create({
  card: { gap: 12 },
  cardTitle: { color: zenith.colors.foreground, fontFamily: zenith.font.display, fontSize: 22, lineHeight: 24, textTransform: 'uppercase' },
  text: { color: zenith.colors.muted, fontFamily: zenith.font.body, fontSize: 15, lineHeight: 22 },
});
