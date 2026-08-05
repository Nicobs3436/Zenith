# Modelo De Datos MVP

## Decisiones Base

- Base de datos: PostgreSQL.
- Identificadores principales con UUID.
- Pesos con valor numerico y unidad explicita.
- `kg` y `lb` no se convierten automaticamente.
- Fechas de sesiones con `started_at`, `finished_at` y `timezone` explicita.
- Borrado normal mediante soft delete en rutinas y sesiones.

## Entidades

### User

- Campos: `id`, `email`, `username`, `password_hash`, `is_active`, `created_at`, `updated_at`.
- `email` y `username` son unicos.
- `password_hash` no se expone por API.

### Exercise

- Campos: `id`, `name`, `description`, `difficulty`, `technique_notes`, `is_global`, `created_by_user_id`, `created_at`, `updated_at`.
- `is_global=true`: ejercicio seed/global.
- `is_global=false`: ejercicio propio del usuario.
- Relaciones many-to-many con `MuscleGroup` y `Equipment`.

### MuscleGroup

- Campos: `id`, `name`.
- Catalogo seed compartido.

### Equipment

- Campos: `id`, `name`.
- Catalogo seed compartido.

### Routine

- Campos: `id`, `user_id`, `name`, `description`, `goal`, `created_at`, `updated_at`, `deleted_at`.
- Rutina privada por usuario.
- `deleted_at` oculta la rutina de listados y detalle.
- Borrar rutina no borra sesiones historicas asociadas.

### RoutineExercise

- Campos: `id`, `routine_id`, `exercise_id`, `position`, `target_sets`, `target_reps_min`, `target_reps_max`, `target_weight_value`, `target_weight_unit`, `target_rpe`, `target_rir`, `rest_seconds`, `notes`.
- Define objetivos planificados usados para precargar sesiones.
- `target_weight_value` y `target_weight_unit` permiten aplicar sugerencias de sobrecarga progresiva aceptadas por el usuario.

### WorkoutSession

- Campos: `id`, `user_id`, `routine_id`, `started_at`, `finished_at`, `timezone`, `notes`, `created_at`, `deleted_at`.
- Puede referenciar una rutina o ser libre.
- Si la rutina asociada se borra, la sesion historica se conserva.
- `deleted_at` excluye la sesion de historial, estadisticas y rango.

### WorkoutSet

- Campos: `id`, `session_id`, `exercise_id`, `set_number`, `reps`, `weight_value`, `weight_unit`, `rpe`, `rir`, `rest_seconds`, `notes`.
- `weight_value` y `weight_unit` deben informarse juntos.
- `weight_unit` acepta `kg` o `lb`.

### Rank

- Campos: `id`, `name`, `description`, `min_score`, `sort_order`.
- Catalogo seed de rangos.

### UserRankProgress

- Campos: `id`, `user_id`, `rank_id`, `score`, `volume_score`, `progression_score`, `breadth_score`, `calculated_at`.
- Snapshot persistido al recalcular rango.
- El score no incluye puntos por sesiones registradas ni semanas activas.

### AiSuggestion

- Campos: `id`, `user_id`, `routine_id`, `routine_exercise_id`, `exercise_id`, `type`, `status`, `input_summary`, `recommendation`, `explanation`, `apply_payload`, `created_at`, `reviewed_at`, `applied_at`.
- Estados: `pending`, `accepted`, `rejected`, `expired`.
- Tipos: `increase_weight`, `reduce_volume`, `change_reps`, `increase_rest`, `plateau_detected`, `deload_recommended`, `exercise_swap`, `routine_goal_adjustment`.
- `input_summary` guarda datos estructurados usados sin `notes` ni datos de cuenta.
- `apply_payload` guarda el cambio validado que se aplica a la rutina cuando el usuario acepta.
- `deload_recommended` puede ajustar `target_sets`, `target_weight_value`/`target_weight_unit` y `rest_seconds`; no modifica sesiones historicas.
- `exercise_swap` reemplaza `RoutineExercise.exercise_id` por un ejercicio accesible del catalogo si el usuario acepta; no toca `WorkoutSet.exercise_id` historicos.
- `routine_goal_adjustment` alinea series, reps y descanso con el objetivo de la rutina si el usuario acepta; no usa sesiones historicas.

### AiTrainingPlan

- Campos: `id`, `user_id`, `status`, `goal`, `level`, `days_per_week`, `session_duration_minutes`, `available_equipment`, `physical_limitations`, `sensitive_data_acknowledged`, `priorities`, `plan_payload`, `explanation`, `risk_notes`, `confidence`, `input_summary`, `provider`, `model`, `fallback_used`, `created_at`, `reviewed_at`.
- Estados: `draft`, `accepted`, `rejected`.
- Genera una rutina propuesta por cada dia disponible por semana.
- Al aceptar, crea rutinas reales y ejercicios planificados; no crea sesiones.
- `physical_limitations` requiere `sensitive_data_acknowledged=true` porque puede contener datos sensibles.
- `plan_payload` guarda la propuesta estructurada y, al aceptar, los ids de rutinas creadas.
- Modificar un plan en borrador crea otro `AiTrainingPlan` en estado `draft`; el origen y la instruccion se guardan en `input_summary.modified_from_plan_id` y `input_summary.modification_instruction`.

### AiCoachIntake

- Campos: `id`, `user_id`, `status`, `intake_summary`, `recent_messages`, `missing_required_fields`, `ready_for_plan`, `sensitive_data_acknowledged`, `created_at`, `updated_at`.
- Hay un unico intake activo por usuario.
- Estados: `collecting`, `ready`, `plan_generated`.
- `intake_summary` guarda objetivo, nivel, dias por semana, duracion, equipamiento, prioridades y limitaciones solo con confirmacion.
- `recent_messages` guarda solo los ultimos mensajes necesarios para continuar la entrevista; no es historial completo.
- No crea rutinas, sesiones ni series. Solo permite generar un `AiTrainingPlan` borrador cuando faltantes obligatorios esta vacio.

### CoachProfile / CoachConversation / CoachMemoryEvent / CoachProposal / CoachPlannedSession

- Coach usa estas tablas para la experiencia visible del entrenador.
- `CoachProfile` guarda perfil estructurado: objetivo, sexo biologico, edad, altura, peso, nivel, dias, duracion, equipamiento, prioridades, ejercicios preferidos/evitados, limitaciones confirmadas y memoria resumida.
- `CoachConversation` guarda fase, ultima pregunta y ultimos mensajes necesarios; no es historial completo.
- `CoachMemoryEvent` guarda decisiones importantes resumidas.
- `CoachProposal` y `CoachPlannedSession` son legacy y se conservan hasta fase 2 de limpieza de base de datos.
- `CoachPlannedSession` guarda sesiones futuras recomendadas que no son sesiones historicas registradas.
- Coach no crea rutinas reales hasta aceptar un `AiTrainingPlan` borrador.

### AiSessionSummary

- Campos: `id`, `user_id`, `session_id`, `summary`, `improvements`, `drops`, `warnings`, `next_recommendation`, `input_summary`, `provider`, `model`, `fallback_used`, `created_at`.
- Un resumen pertenece a una sesion activa y a su usuario.
- Hay un unico resumen por sesion; regenerar actualiza el resumen existente.
- No modifica rutinas, sesiones ni series.
- `input_summary` usa solo datos estructurados de la sesion y excluye notas, email, username, tokens y credenciales.
- Los volumenes se agrupan por unidad (`kg`/`lb`) sin conversion automatica.

## Relaciones Clave

- Un usuario tiene muchas rutinas y sesiones.
- Una rutina tiene muchos ejercicios planificados.
- Una sesion contiene muchas series.
- Una serie referencia el ejercicio ejecutado.
- Una sesion puede apuntar a una rutina borrada logicamente; la historia no se elimina.
- Una sugerencia IA puede apuntar a un ejercicio planificado y se aplica solo si la rutina sigue activa y pertenece al usuario.
- Un plan IA pertenece a un usuario; al aceptarlo crea rutinas privadas de ese usuario. Una version modificada referencia el plan origen en `input_summary`.
- Un intake de Coach pertenece a un usuario y puede crear un plan IA borrador si esta listo; no crea rutinas por si solo.
- Un `CoachProfile` pertenece a un usuario; propuestas, memoria y sesiones planificadas tambien se filtran por usuario.
- Un resumen IA pertenece a una sesion del usuario; sesiones borradas o ajenas no se resumen ni se leen.

## Estadisticas Calculadas

- No hay tablas agregadas; se calculan desde sesiones y series activas.
- `total_sets`: cantidad de series.
- `total_reps`: suma de repeticiones.
- `total_volume`: `sum(reps * weight_value)` para series con peso.
- `max_weight`: peso maximo por ejercicio/unidad.
- `avg_weight`: promedio de peso por ejercicio/unidad.
- `best_estimated_1rm`: mejor estimacion usando formula de Epley.
- Series sin peso cuentan para sets/reps y no para volumen/carga/1RM.
- Unidades se agrupan separadas hasta definir una politica explicita de conversion.

## Rangos

- Volumen: volumen total con peso dividido por 100.
- Progresion: mejora porcentual de 1RM estimado por ejercicio y unidad.
- Amplitud: puntos por cantidad de ejercicios/unidad con progreso.
- Sesiones borradas no participan.

## Reglas Cubiertas Por Tests

- Auth no expone `password_hash`.
- Usuarios no acceden a rutinas, sesiones, ejercicios propios, estadisticas ni rangos de otros usuarios.
- Validacion de reps, peso, unidad, RPE/RIR, descanso y rangos objetivo.
- Estadisticas no mezclan `kg` y `lb`.
- Rangos no suman puntos por sesiones ni semanas activas.
- Soft delete oculta rutinas/sesiones segun reglas del MVP.
- Sugerencias IA guardan trazabilidad, no usan `notes`, no mezclan unidades, validan ejercicios alternativos accesibles y no modifican sesiones historicas.
- Planes IA requieren confirmacion explicita para limitaciones fisicas o modificaciones sensibles, no sustituyen consejo medico/profesional y solo crean rutinas al aceptar.
- Intake conversacional no genera planes sin objetivo, nivel, dias por semana y duracion; redacta mensajes sensibles no confirmados.
- Coach no genera vistas previas sin objetivo, sexo biologico, edad, altura, peso, nivel, dias, duracion y equipamiento; la entrevista IA pregunta por bloques y evita repetir datos conocidos.
- Resumenes post-sesion IA no usan notas, no mezclan unidades, no modifican datos historicos y respetan ownership de sesiones.
