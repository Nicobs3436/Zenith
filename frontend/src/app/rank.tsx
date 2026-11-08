import { RefreshCw, Trophy } from 'lucide-react-native';
import { useEffect, useState } from 'react';
import { Pressable, StyleSheet, Text, View } from 'react-native';

import { getRank, getRanks, Rank, RankProgress, recalculateRank } from '@/api/client';
import { ZenithBottomNav, ZenithButton, ZenithCard, ZenithHeader, ZenithNotice } from '@/components/ZenithUI';
import { ZenithScreen } from '@/components/ZenithScreen';
import { routineAccents, zenith } from '@/constants/zenithTheme';
import { formatNextRank, formatRankCalculatedAt, formatRankScore, rankExplanationLines } from '@/utils/rankDisplay';

export default function RankScreen() {
  const [rank, setRank] = useState<RankProgress | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [showRankScale, setShowRankScale] = useState(false);
  const [ranks, setRanks] = useState<Rank[]>([]);
  const [loadingRanks, setLoadingRanks] = useState(false);
  const [ranksError, setRanksError] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  useEffect(() => {
    getRank()
      .then(setRank)
      .catch((caught) => setError(caught instanceof Error ? caught.message : 'Error'))
      .finally(() => setLoading(false));
  }, []);

  async function submitRecalculate() {
    setSaving(true);
    setError(null);
    setNotice(null);
    try {
      setRank(await recalculateRank());
      setNotice('Rango recalculado.');
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : 'No se pudo recalcular el rango.');
    } finally {
      setSaving(false);
    }
  }

  async function toggleRankScale() {
    const nextVisible = !showRankScale;
    setShowRankScale(nextVisible);
    if (!nextVisible || ranks.length > 0 || loadingRanks) {
      return;
    }

    setLoadingRanks(true);
    setRanksError(null);
    try {
      const items = await getRanks();
      setRanks([...items].sort((left, right) => left.sort_order - right.sort_order));
    } catch (caught) {
      setRanksError(caught instanceof Error ? caught.message : 'No se pudo cargar la escala de rangos.');
    } finally {
      setLoadingRanks(false);
    }
  }

  const scoreNumber = rank ? Number(rank.score) : 0;
  const progress = Math.max(8, Math.min(100, scoreNumber > 0 ? scoreNumber % 100 : 8));
  const scoreParts = rank ? [
    { label: 'Volumen', value: rank.volume_score, color: routineAccents[0] },
    { label: 'Progresión', value: rank.progression_score, color: routineAccents[1] },
    { label: 'Amplitud', value: rank.breadth_score, color: routineAccents[2] },
  ] : [];

  return (
    <ZenithScreen bottomNav={<ZenithBottomNav />}>
      <ZenithHeader title="Rango" subtitle="Progresión" />
      {loading && <ZenithNotice>Cargando rango...</ZenithNotice>}
      {notice && <ZenithNotice tone="success">{notice}</ZenithNotice>}
      {error && <ZenithNotice tone="danger">{error}</ZenithNotice>}
      {rank && (
        <>
          <ZenithCard style={styles.hero}>
            <Text style={styles.watermark}>{Math.round(scoreNumber)}</Text>
            <View style={styles.heroContent}>
              <View style={styles.trophy}><Trophy color={zenith.colors.primary} size={34} /></View>
              <View style={styles.rankInfo}>
                <Text style={styles.kicker}>Rango actual</Text>
                <Text style={styles.rank}>{rank.rank.name}</Text>
                <View style={styles.scoreLine}>
                  <Text style={styles.score}>{formatRankScore(rank.score)}</Text>
                </View>
              </View>
            </View>
            {rank.rank.description && <Text style={styles.note}>{rank.rank.description}</Text>}
            <View style={styles.progressBlock}>
              <View style={styles.progressLabels}>
                <Text style={styles.progressLabel}>{rank.rank.name}</Text>
                <Text style={styles.progressLabel}>{rank.next_rank?.name ?? 'Máximo'}</Text>
              </View>
              <View style={styles.progressTrack}><View style={[styles.progressFill, { width: `${progress}%` }]} /></View>
            </View>
            <Text style={styles.next}>{formatNextRank(rank)}</Text>
          </ZenithCard>

          <ZenithCard style={styles.card}>
            <Text style={styles.sectionTitle}>Composicion del score</Text>
            {scoreParts.map((part) => (
              <View key={part.label} style={styles.breakdownItem}>
                <View style={styles.breakdownTop}>
                  <Text style={styles.breakdownLabel}>{part.label}</Text>
                  <Text style={[styles.breakdownValue, { color: part.color }]}>{part.value}</Text>
                </View>
                <View style={styles.smallTrack}><View style={[styles.smallFill, { backgroundColor: part.color, width: `${Math.min(100, Number(part.value))}%` }]} /></View>
              </View>
            ))}
            <Text style={styles.note}>Ultimo calculo persistido: {formatRankCalculatedAt(rank.calculated_at)}</Text>
          </ZenithCard>

          <ZenithCard style={styles.card}>
            <Text style={styles.sectionTitle}>Como se calcula</Text>
            {rankExplanationLines.map((line) => <Text key={line} style={styles.note}>{line}</Text>)}
            <Pressable accessibilityRole="button" onPress={toggleRankScale} style={styles.secondaryAction}>
              <Text style={styles.secondaryActionText}>{showRankScale ? 'Ocultar escala de rangos' : 'Ver escala de rangos'}</Text>
            </Pressable>
            {showRankScale && (
              <View style={styles.rankScale}>
                {loadingRanks && <Text style={styles.note}>Cargando escala...</Text>}
                {ranksError && <Text style={styles.errorText}>{ranksError}</Text>}
                {!loadingRanks && !ranksError && ranks.map((item) => (
                  <View key={item.id} style={styles.rankScaleRow}>
                    <View style={styles.rankScaleHeader}>
                      <Text style={styles.rankScaleName}>{item.name}</Text>
                      <Text style={styles.rankScaleScore}>{item.min_score} pts</Text>
                    </View>
                    {item.description && <Text style={styles.note}>{item.description}</Text>}
                  </View>
                ))}
              </View>
            )}
          </ZenithCard>

          <ZenithButton disabled={saving} icon={<RefreshCw color={zenith.colors.primaryForeground} size={14} />} onPress={submitRecalculate} title={saving ? 'Recalculando...' : 'Recalcular ahora'} />
        </>
      )}
    </ZenithScreen>
  );
}

const styles = StyleSheet.create({
  hero: { backgroundColor: '#131318', borderColor: zenith.colors.primaryBorder, gap: 14, overflow: 'hidden', padding: 20 },
  watermark: { color: 'rgba(255,255,255,0.04)', fontFamily: zenith.font.display, fontSize: 110, lineHeight: 110, position: 'absolute', right: 12, top: -8 },
  heroContent: { alignItems: 'center', flexDirection: 'row', gap: 14 },
  trophy: { alignItems: 'center', backgroundColor: zenith.colors.primarySoft, borderRadius: 18, height: 58, justifyContent: 'center', width: 58 },
  rankInfo: { flex: 1 },
  kicker: { color: zenith.colors.muted, fontFamily: zenith.font.mono, fontSize: 11, letterSpacing: 1.5, textTransform: 'uppercase' },
  rank: { color: zenith.colors.foreground, fontFamily: zenith.font.display, fontSize: 36, lineHeight: 38, textTransform: 'uppercase' },
  scoreLine: { alignItems: 'baseline', flexDirection: 'row', gap: 6 },
  score: { color: zenith.colors.primary, fontFamily: zenith.font.display, fontSize: 34, lineHeight: 36 },
  note: { color: zenith.colors.muted, fontFamily: zenith.font.body, fontSize: 12, lineHeight: 19 },
  progressBlock: { gap: 6 },
  progressLabels: { flexDirection: 'row', justifyContent: 'space-between' },
  progressLabel: { color: zenith.colors.muted, fontFamily: zenith.font.mono, fontSize: 11 },
  progressTrack: { backgroundColor: zenith.colors.secondary, borderRadius: 999, height: 8, overflow: 'hidden' },
  progressFill: { backgroundColor: zenith.colors.primary, borderRadius: 999, height: '100%' },
  next: { color: zenith.colors.primary, fontFamily: zenith.font.bodyBold, fontSize: 13 },
  card: { gap: 12 },
  sectionTitle: { color: zenith.colors.foreground, fontFamily: zenith.font.display, fontSize: 22, textTransform: 'uppercase' },
  secondaryAction: { alignSelf: 'flex-start', borderColor: zenith.colors.border, borderRadius: 999, borderWidth: 1, paddingHorizontal: 12, paddingVertical: 8 },
  secondaryActionText: { color: zenith.colors.muted, fontFamily: zenith.font.bodyBold, fontSize: 12 },
  rankScale: { borderTopColor: zenith.colors.border, borderTopWidth: 1, gap: 10, paddingTop: 12 },
  rankScaleRow: { gap: 4 },
  rankScaleHeader: { alignItems: 'center', flexDirection: 'row', justifyContent: 'space-between' },
  rankScaleName: { color: zenith.colors.foreground, fontFamily: zenith.font.bodyBold },
  rankScaleScore: { color: zenith.colors.primary, fontFamily: zenith.font.mono, fontSize: 11 },
  errorText: { color: zenith.colors.danger, fontFamily: zenith.font.body },
  breakdownItem: { gap: 6 },
  breakdownTop: { alignItems: 'center', flexDirection: 'row', justifyContent: 'space-between' },
  breakdownLabel: { color: zenith.colors.foreground, fontFamily: zenith.font.bodyMedium, fontSize: 13 },
  breakdownValue: { fontFamily: zenith.font.display, fontSize: 22, lineHeight: 24 },
  smallTrack: { backgroundColor: zenith.colors.secondary, borderRadius: 999, height: 6, overflow: 'hidden' },
  smallFill: { borderRadius: 999, height: '100%' },
});
