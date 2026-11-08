import { Picker } from '@react-native-picker/picker';
import { StyleSheet, Text, View } from 'react-native';

import { zenith } from '@/constants/zenithTheme';

type PickerOption = {
  label: string;
  value: string;
};

type PickerFieldProps = {
  label: string;
  options: PickerOption[];
  selectedValue: string;
  onValueChange: (value: string) => void;
};

export function PickerField({ label, options, selectedValue, onValueChange }: PickerFieldProps) {
  return (
    <View style={styles.container}>
      <Text style={styles.label}>{label}</Text>
      <View style={styles.pickerFrame}>
        <Picker dropdownIconColor={zenith.colors.primary} selectedValue={selectedValue} onValueChange={(value) => onValueChange(String(value))}>
          {options.map((option) => (
            <Picker.Item key={option.value} color={zenith.colors.primaryForeground} label={option.label} value={option.value} />
          ))}
        </Picker>
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  container: { gap: 8 },
  label: { color: zenith.colors.muted, fontFamily: zenith.font.mono, fontSize: 11, letterSpacing: 1.4, textTransform: 'uppercase' },
  pickerFrame: {
    backgroundColor: zenith.colors.primary,
    borderColor: zenith.colors.primaryBorder,
    borderRadius: 16,
    borderWidth: 1,
    overflow: 'hidden',
  },
});
