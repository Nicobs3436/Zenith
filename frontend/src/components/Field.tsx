import { Text, TextInput, TextInputProps, StyleSheet, View } from 'react-native';

import { zenith } from '@/constants/zenithTheme';

type FieldProps = TextInputProps & {
  label: string;
  hint?: string;
};

export function Field({ label, hint, keyboardType, multiline, returnKeyType, selectTextOnFocus, style, ...props }: FieldProps) {
  const numericKeyboard = keyboardType === 'numeric' || keyboardType === 'number-pad' || keyboardType === 'decimal-pad';

  return (
    <View style={styles.container}>
      <Text style={styles.label}>{label}</Text>
      <TextInput
        keyboardType={keyboardType}
        multiline={multiline}
        placeholderTextColor={zenith.colors.muted}
        returnKeyType={returnKeyType ?? (multiline ? 'default' : 'next')}
        selectTextOnFocus={selectTextOnFocus ?? numericKeyboard}
        style={[styles.input, multiline && styles.multiline, style]}
        accessibilityLabel={label}
        accessibilityHint={hint}
        {...props}
      />
      {hint && <Text style={styles.hint}>{hint}</Text>}
    </View>
  );
}

const styles = StyleSheet.create({
  hint: {
    color: zenith.colors.muted,
    fontFamily: zenith.font.body,
    fontSize: 13,
    lineHeight: 18,
  },
  container: {
    gap: 8,
  },
  label: {
    color: zenith.colors.muted,
    fontFamily: zenith.font.mono,
    fontSize: 11,
    letterSpacing: 1.4,
    textTransform: 'uppercase',
  },
  input: {
    backgroundColor: zenith.colors.secondary,
    borderColor: zenith.colors.border,
    borderRadius: 16,
    borderWidth: 1,
    color: zenith.colors.foreground,
    fontFamily: zenith.font.body,
    fontSize: 16,
    padding: 14,
  },
  multiline: {
    minHeight: 92,
    textAlignVertical: 'top',
  },
});
