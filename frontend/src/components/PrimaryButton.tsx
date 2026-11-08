import { Pressable, StyleSheet, Text } from 'react-native';

import { zenith } from '@/constants/zenithTheme';

type PrimaryButtonProps = {
  title: string;
  onPress: () => void;
  disabled?: boolean;
};

export function PrimaryButton({ title, onPress, disabled }: PrimaryButtonProps) {
  return (
    <Pressable
      accessibilityRole="button"
      accessibilityState={{ disabled: Boolean(disabled) }}
      disabled={disabled}
      onPress={onPress}
      style={({ pressed }) => [styles.button, disabled && styles.disabled, pressed && !disabled && styles.pressed]}
    >
      <Text style={styles.text}>{title}</Text>
    </Pressable>
  );
}

const styles = StyleSheet.create({
  button: {
    alignItems: 'center',
    backgroundColor: zenith.colors.primary,
    borderRadius: 18,
    justifyContent: 'center',
    minHeight: 52,
    padding: 15,
  },
  pressed: {
    opacity: 0.85,
    transform: [{ scale: 0.99 }],
  },
  disabled: {
    opacity: 0.55,
  },
  text: {
    color: zenith.colors.primaryForeground,
    fontFamily: zenith.font.bodyBold,
    fontSize: 16,
    fontWeight: '900',
  },
});
