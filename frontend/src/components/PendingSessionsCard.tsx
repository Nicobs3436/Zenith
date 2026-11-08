import { CloudOff } from 'lucide-react-native';
import { useCallback, useEffect, useState } from 'react';
import { StyleSheet, Text, View } from 'react-native';

import { ZenithButton, ZenithCard, ZenithNotice } from '@/components/ZenithUI';
import { zenith } from '@/constants/zenithTheme';
import { discardPendingSession, listPendingSessions, PendingSession } from '@/storage/sessionOutbox';
import { syncPendingSessions } from '@/sync/sessionSync';
import { countLabel } from '@/utils/workoutDisplay';

// Sesiones terminadas sin conexion que esperan a enviarse. Al montarse intenta enviarlas.
export function PendingSessionsCard({ onSynced }: { onSynced?: () => void }) {
  const [items, setItems] = useState<PendingSession[]>([]);
  const [syncing, setSyncing] = useState(false);
  const [message, setMessage] = useState<string | null>(null);

  const sync = useCallback(async () => {
    setSyncing(true);
    try {
      const result = await syncPendingSessions();
      if (result.sent > 0) {
        setMessage(`${countLabel(result.sent, 'sesión enviada', 'sesiones enviadas')} al servidor.`);
        onSynced?.();
      } else if (result.pending > 0) {
        setMessage('Sigue sin conexión. Lo volveremos a intentar automáticamente.');
      }
    } finally {
      setItems(await listPendingSessions());
      setSyncing(false);
    }
  }, [onSynced]);

  useEffect(() => {
    listPendingSessions().then((pending) => {
      setItems(pending);
      if (pending.some((item) => !item.rejected)) {
        void sync();
      }
    });
  }, [sync]);

  async function discard(clientRequestId: string) {
    await discardPendingSession(clientRequestId);
    setItems(await listPendingSessions());
  }

  if (items.length === 0) {
    return message ? <ZenithNotice tone="success">{message}</ZenithNotice> : null;
  }

  return (
    <ZenithCard style={styles.card}>
      <View style={styles.header}>
        <CloudOff color={zenith.colors.amber} size={18} />
        <Text style={styles.title}>{countLabel(items.length, 'sesión guardada en el móvil', 'sesiones guardadas en el móvil')}</Text>
      </View>
      <Text style={styles.text}>Se terminaron sin conexión. No las cierres: se enviarán solas cuando vuelva la red.</Text>
      {items.map((item) => (
        <View key={item.payload.client_request_id} style={styles.row}>
          <Text style={styles.label}>{item.label}</Text>
          {item.rejected && (
            <>
              <Text style={styles.rejected}>No se pudo guardar: {item.rejected}</Text>
              <ZenithButton onPress={() => discard(item.payload.client_request_id)} title="Descartar" variant="danger" />
            </>
          )}
        </View>
      ))}
      {message && <Text style={styles.text}>{message}</Text>}
      <ZenithButton disabled={syncing} onPress={sync} title={syncing ? 'Enviando...' : 'Enviar ahora'} variant="secondary" />
    </ZenithCard>
  );
}

const styles = StyleSheet.create({
  card: { borderColor: zenith.colors.amber, gap: 10 },
  header: { alignItems: 'center', flexDirection: 'row', gap: 8 },
  title: { color: zenith.colors.foreground, flex: 1, fontFamily: zenith.font.bodyBold, fontSize: 16 },
  text: { color: zenith.colors.muted, fontFamily: zenith.font.body, fontSize: 14, lineHeight: 20 },
  row: { borderTopColor: zenith.colors.border, borderTopWidth: 1, gap: 6, paddingTop: 8 },
  label: { color: zenith.colors.foreground, fontFamily: zenith.font.bodyMedium, fontSize: 15 },
  rejected: { color: '#ffb4b4', fontFamily: zenith.font.body, fontSize: 13 },
});
