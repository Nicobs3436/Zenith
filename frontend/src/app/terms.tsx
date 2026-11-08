import { Link } from 'expo-router';
import { StyleSheet, Text } from 'react-native';

import { ZenithCard, ZenithHeader, ZenithNotice } from '@/components/ZenithUI';
import { ZenithScreen } from '@/components/ZenithScreen';
import { zenith } from '@/constants/zenithTheme';

export default function TermsScreen() {
  return (
    <ZenithScreen>
      <ZenithHeader title="Términos de uso" subtitle="Zenith beta" />
      <Text style={styles.text}>Zenith es una herramienta de seguimiento y planificación de entrenamiento en beta gratuita.</Text>
      <ZenithCard style={styles.card}>
        <Text style={styles.cardTitle}>Uso responsable</Text>
        <Text style={styles.item}>- Revisa toda recomendación antes de aceptarla.</Text>
        <Text style={styles.item}>- No entrenes con dolor, mareo, pérdida clara de técnica o sintomas inusuales.</Text>
        <Text style={styles.item}>- La app no sustituye consejo médico, fisioterapeutico ni de un entrenador cualificado.</Text>
      </ZenithCard>
      <ZenithCard style={styles.card}>
        <Text style={styles.cardTitle}>IA revisable</Text>
        <Text style={styles.item}>- Las sugerencias son explicables y solo modifican rutinas al aceptarlas.</Text>
        <Text style={styles.item}>- Las sesiones historicas no se modifican por IA.</Text>
        <Text style={styles.item}>- Las preguntas al entrenador no crean cambios automaticos.</Text>
      </ZenithCard>
      <ZenithNotice tone="warning">Limitaciones de beta: el servicio gratuito puede tener interrupciones, cold starts o limites del proveedor. No uses Zenith como única copia de datos importantes.</ZenithNotice>
      <Link href={'/privacy' as never} style={styles.link}>Ver privacidad</Link>
    </ZenithScreen>
  );
}

const styles = StyleSheet.create({
  text: { color: zenith.colors.muted, fontFamily: zenith.font.body, fontSize: 16, lineHeight: 23 },
  card: { gap: 8 },
  cardTitle: { color: zenith.colors.foreground, fontFamily: zenith.font.display, fontSize: 22, lineHeight: 24, textTransform: 'uppercase' },
  item: { color: zenith.colors.foreground, fontFamily: zenith.font.body, lineHeight: 21 },
  link: { color: zenith.colors.primary, fontFamily: zenith.font.bodyBold },
});
