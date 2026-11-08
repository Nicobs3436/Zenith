import { Link } from 'expo-router';
import { StyleSheet, Text } from 'react-native';

import { ZenithCard, ZenithHeader, ZenithNotice } from '@/components/ZenithUI';
import { ZenithScreen } from '@/components/ZenithScreen';
import { zenith } from '@/constants/zenithTheme';

export default function PrivacyScreen() {
  return (
    <ZenithScreen>
      <ZenithHeader title="Privacidad" subtitle="Zenith beta" />
      <Text style={styles.text}>Zenith guarda datos de cuenta y entrenamiento para que puedas consultar rutinas, sesiones, estadísticas, rangos y recomendaciones.</Text>
      <ZenithCard style={styles.card}>
        <Text style={styles.cardTitle}>Datos que guardamos</Text>
        <Text style={styles.item}>- Email, nombre de usuario y contraseña cifrada con hash.</Text>
        <Text style={styles.item}>- Fecha en que aceptaste los términos y confirmaste tener 18 años o más.</Text>
        <Text style={styles.item}>- Ejercicios propios, rutinas, sesiones, series, pesos, unidades, RPE/RIR, descansos y notas.</Text>
        <Text style={styles.item}>- Sugerencias IA, planes adaptativos y resúmenes post-sesion generados para tu cuenta.</Text>
      </ZenithCard>
      <ZenithCard style={styles.card}>
        <Text style={styles.cardTitle}>IA y datos sensibles</Text>
        <Text style={styles.item}>- Las sugerencias de progresión usan reglas internas. El Coach usa un proveedor externo (Groq) y solo recibe tus mensajes después de que aceptes el aviso de datos personales.</Text>
        <Text style={styles.item}>- La IA nunca aplica cambios sin tu aceptación. Las notas privadas no se envian a la IA.</Text>
        <Text style={styles.item}>- Las limitaciones físicas pueden ser datos sensibles y solo se usan si confirmas el aviso.</Text>
      </ZenithCard>
      <ZenithNotice>Puedes exportar todos tus datos o eliminar tu cuenta de forma permanente desde Cuenta.</ZenithNotice>
      <Link href={'/account' as never} style={styles.link}>Ir a Cuenta</Link>
      <Link href={'/terms' as never} style={styles.link}>Ver términos</Link>
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
