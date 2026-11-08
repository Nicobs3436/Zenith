import { Pressable, StyleSheet, Text, View } from 'react-native';

import { zenith } from '@/constants/zenithTheme';

type SegmentedOption = {
  label: string;
  value: string;
};

type SegmentedFieldProps = {
  label: string;
  options: SegmentedOption[];
  selectedValue: string;
  onValueChange: (value: string) => void;
};

export function SegmentedField({ label, options, selectedValue, onValueChange }: SegmentedFieldProps) {
  return (
    <View style={styles.container}>
      <Text style={styles.label}>{label}</Text>
      <View accessibilityLabel={label} accessibilityRole="radiogroup" style={styles.segmented}>
        {options.map((option) => {
          const selected = option.value === selectedValue;
          return (
            <Pressable accessibilityLabel={`${label}: ${option.label}`} accessibilityRole="radio" accessibilityState={{ checked: selected }}
              key={option.value}
              onPress={() => onValueChange(option.value)}
              style={[styles.option, selected && styles.optionSelected]}
            >
              <Text style={[styles.optionText, selected && styles.optionTextSelected]}>{option.label}</Text>
            </Pressable>
          );
        })}
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  container: { gap: 8 },
  label: { color: zenith.colors.foreground, fontFamily: zenith.font.mono, fontSize: 11, letterSpacing: 1.2, textTransform: 'uppercase' },
  segmented: { backgroundColor: zenith.colors.background, borderColor: zenith.colors.border, borderRadius: 14, borderWidth: 1, flexDirection: 'row', gap: 6, padding: 4 },
  option: { alignItems: 'center', borderRadius: 10, flex: 1, justifyContent: 'center', minHeight: 44, paddingVertical: 11 },
  optionSelected: { backgroundColor: zenith.colors.primary },
  optionText: { color: zenith.colors.muted, fontFamily: zenith.font.bodyBold },
  optionTextSelected: { color: zenith.colors.primaryForeground },
});
