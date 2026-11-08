import { ChevronDown, ChevronUp } from 'lucide-react-native';
import { useState } from 'react';
import { Pressable, StyleSheet, Text, View } from 'react-native';

import { Field } from '@/components/Field';
import { SegmentedField } from '@/components/SegmentedField';
import { zenith } from '@/constants/zenithTheme';
import { RoutineExerciseRow } from '@/utils/routineForm';

type RoutineExerciseFieldsProps = {
  row: RoutineExerciseRow;
  onChange: (patch: Partial<RoutineExerciseRow>) => void;
};

const UNIT_OPTIONS = [
  { label: 'kg', value: 'kg' },
  { label: 'lb', value: 'lb' },
];

function hasAdvancedValues(row: RoutineExerciseRow) {
  return Boolean(row.target_rpe || row.target_rir || row.notes);
}

// Campos de un ejercicio planificado. Lo esencial (series, reps, peso, descanso) va en una rejilla
// de dos columnas; RPE, RIR y notas quedan plegados para no alargar el formulario (divulgacion progresiva).
export function RoutineExerciseFields({ row, onChange }: RoutineExerciseFieldsProps) {
  const [showAdvanced, setShowAdvanced] = useState(() => hasAdvancedValues(row));

  return (
    <View style={styles.container}>
      <View style={styles.grid}>
        <View style={styles.cell}>
          <Field keyboardType="number-pad" label="Series" onChangeText={(target_sets) => onChange({ target_sets })} value={row.target_sets} />
        </View>
        <View style={styles.cell}>
          <Field keyboardType="number-pad" label="Descanso (s)" onChangeText={(rest_seconds) => onChange({ rest_seconds })} placeholder="90" value={row.rest_seconds} />
        </View>
        <View style={styles.cell}>
          <Field keyboardType="number-pad" label="Reps mín." onChangeText={(target_reps_min) => onChange({ target_reps_min })} value={row.target_reps_min} />
        </View>
        <View style={styles.cell}>
          <Field keyboardType="number-pad" label="Reps máx." onChangeText={(target_reps_max) => onChange({ target_reps_max })} value={row.target_reps_max} />
        </View>
        <View style={styles.cell}>
          <Field keyboardType="decimal-pad" label="Peso objetivo" onChangeText={(target_weight_value) => onChange({ target_weight_value })} placeholder="Opcional" value={row.target_weight_value} />
        </View>
        <View style={styles.cell}>
          <SegmentedField
            label="Unidad"
            onValueChange={(target_weight_unit) => onChange({ target_weight_unit: target_weight_unit as 'kg' | 'lb' })}
            options={UNIT_OPTIONS}
            selectedValue={row.target_weight_unit}
          />
        </View>
      </View>

      <Pressable
        accessibilityRole="button"
        accessibilityState={{ expanded: showAdvanced }}
        onPress={() => setShowAdvanced((current) => !current)}
        style={styles.toggle}
      >
        <Text style={styles.toggleText}>{showAdvanced ? 'Ocultar RPE, RIR y notas' : 'Más opciones: RPE, RIR y notas'}</Text>
        {showAdvanced ? <ChevronUp color={zenith.colors.primary} size={16} /> : <ChevronDown color={zenith.colors.primary} size={16} />}
      </Pressable>

      {showAdvanced && (
        <View style={styles.container}>
          <View style={styles.grid}>
            <View style={styles.cell}>
              <Field hint="Esfuerzo 1-10" keyboardType="decimal-pad" label="RPE objetivo" onChangeText={(target_rpe) => onChange({ target_rpe })} value={row.target_rpe} />
            </View>
            <View style={styles.cell}>
              <Field hint="Reps en reserva" keyboardType="number-pad" label="RIR objetivo" onChangeText={(target_rir) => onChange({ target_rir })} value={row.target_rir} />
            </View>
          </View>
          <Field label="Notas del ejercicio" multiline onChangeText={(notes) => onChange({ notes })} value={row.notes} />
        </View>
      )}
    </View>
  );
}

const styles = StyleSheet.create({
  container: { gap: 12 },
  grid: { columnGap: 12, flexDirection: 'row', flexWrap: 'wrap', rowGap: 12 },
  cell: { flexBasis: '47%', flexGrow: 1, minWidth: 130 },
  toggle: { alignItems: 'center', flexDirection: 'row', gap: 6, minHeight: 44 },
  toggleText: { color: zenith.colors.primary, fontFamily: zenith.font.bodyBold, fontSize: 14 },
});
