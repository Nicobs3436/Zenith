# Privacidad IA

## Decision Actual

- Fase implementada: entrenador interno con proveedor opcional Ollama local para sugerencias, entrevista conversacional, planes, resumenes y preguntas guiadas.
- Proveedor por defecto: reglas locales dentro del backend.
- Proveedor opcional: Ollama local configurado con `APP_AI_PROVIDER=ollama`.
- Modelo por defecto Ollama: `llama3.2`.
- Coste: 0 si se usa proveedor interno u Ollama local.
- Datos enviados fuera del sistema: ninguno con proveedor interno; con Ollama local los datos estructurados se envian solo al servidor local configurado.
- `notes` de rutinas, sesiones y series quedan excluidas del contexto usado por IA.
- Email, username, password hash y tokens no se usan como contexto.

## Datos Usados

- Rutina activa del usuario y ejercicios planificados.
- Objetivos estructurados: series, reps, peso/unidad, RPE/RIR y descanso.
- Sesiones activas no borradas.
- Series estructuradas: reps, peso/unidad, RPE/RIR y descanso.
- Para planes adaptativos: objetivo, nivel, dias disponibles, duracion, equipamiento disponible, prioridades, catalogo estructurado de ejercicios accesibles y limitaciones fisicas si el usuario las confirma explicitamente.
- Para entrevista conversacional del Coach: resumen estructurado de objetivo, nivel, dias, duracion, equipamiento, prioridades y limitaciones solo con confirmacion; se guardan solo los ultimos mensajes necesarios, no el historial completo.
- Para modificar planes adaptativos: la instruccion libre del usuario, el resumen estructurado del plan original y los mismos campos de planificacion; no se usan notas, email, username ni tokens.
- Para resumenes post-sesion: fecha, rutina asociada si existe, series estructuradas, reps, peso/unidad, RPE/RIR, descanso y agregados por ejercicio/unidad; no se usan notas.
- Para preguntas guiadas al entrenador: tipo de pregunta, ids opcionales de rutina/ejercicio/sesion, rutinas activas, sesiones recientes, metricas agregadas y sugerencias pendientes; el detalle libre solo marca `detail_present` y no se envia al proveedor ni se guarda.

## Trazabilidad

Cada sugerencia guarda:

- datos estructurados usados en `input_summary`.
- recomendacion generada.
- explicacion legible.
- cambio aplicable en `apply_payload`.
- regla interna disparada en `rule_triggered`.
- metricas resumidas: reps promedio, peso maximo, unidad, RPE/RIR promedio y caida de reps.
- ventana de analisis usada.
- proveedor/modelo usado, fallback y resumen de prompt en `ai_provider`.
- notas de riesgo y confianza cuando el proveedor las entrega.
- estado de revision: `pending`, `accepted`, `rejected` o `expired`.
- fechas de creacion, revision y aplicacion.

## Aplicacion

- La IA no modifica datos directamente al generar sugerencias.
- Al aceptar, el backend aplica el `apply_payload` validado sobre el ejercicio planificado de la rutina.
- Las sesiones historicas no se modifican.
- Rechazar solo cambia el estado de la sugerencia.
- Generar un nuevo analisis no duplica sugerencias pendientes identicas.
- Las sugerencias pendientes que ya no aplican se marcan como `expired`.
- El proveedor generativo no puede cambiar `apply_payload`; si propone otro cambio, se ignora porque el cambio validado ya viene de reglas internas.
- Si Ollama falla, agota timeout o devuelve JSON invalido, se usa fallback interno y se marca `fallback_used=true`.
- Al aceptar un plan adaptativo, se crean rutinas reales; no se crean sesiones.
- Rechazar un plan no modifica rutinas ni sesiones.
- Modificar un plan adaptativo en borrador crea una nueva version `draft`; no sobrescribe el plan original ni crea rutinas.
- La nueva version guarda `modified_from_plan_id` y `modification_instruction` en `input_summary` para trazabilidad.
- En planes adaptativos, Ollama puede proponer la estructura completa del plan: dias, ejercicios del catalogo accesible, series, repeticiones, RPE/RIR, descansos, explicacion y progresion.
- El backend valida el `plan_payload` completo antes de persistirlo, exige ejercicios accesibles y rangos seguros, rechaza planes redundantes o con volumen incoherente y reintenta una reparacion antes de usar fallback interno.
- La entrevista conversacional `POST /ai/coach/intake/messages` persiste un unico intake activo por usuario con resumen estructurado, ultimos mensajes, campos faltantes y estado `ready_for_plan`; no crea rutinas ni sesiones.
- `POST /ai/coach/intake/generate-plan` solo genera un plan borrador si el intake contiene objetivo, nivel, dias por semana y duracion; reutiliza la validacion estricta de planes adaptativos.
- Generar un resumen post-sesion crea o actualiza `AiSessionSummary`; no modifica sesiones, series ni rutinas.
- En resumenes post-sesion, Ollama solo puede enriquecer textos/listas del resumen; no aplica cambios.
- Las preguntas guiadas `POST /ai/coach/questions` son stateless: no se persisten, no crean sugerencias y no modifican rutinas, sesiones, series ni planes.
- En preguntas guiadas, Ollama solo puede enriquecer `answer`, `key_points` y `suggested_actions`; el backend conserva contexto estructurado y fallback interno.

## Limitaciones Fisicas

- `physical_limitations` puede contener datos sensibles.
- Frontend muestra un aviso y exige confirmacion antes de enviarlas.
- Backend rechaza limitaciones fisicas si `sensitive_data_acknowledged` no es `true`.
- Backend rechaza instrucciones de modificacion con senales de dolor, lesion o limitacion si `sensitive_data_acknowledged` no es `true`.
- En la entrevista conversacional, si se detectan posibles limitaciones sin confirmacion, el backend no guarda el texto sensible como mensaje reciente ni lo usa como `physical_limitations`.
- El texto de limitaciones se normaliza antes de guardar el plan y se usa solo para generar o ajustar la propuesta.
- El texto de limitaciones no se copia a `plan_payload`, `input_summary`, rutinas reales, sesiones ni notas.
- Si el usuario escribe solo espacios, se trata como ausencia de limitaciones.
- La app no sustituye consejo medico ni profesional.

## Reglas Internas 18B

- `reduce_volume`: baja una serie si RPE es alto o RIR muy bajo.
- `increase_rest`: aumenta descanso si hay caida fuerte de reps entre series.
- `plateau_detected`: ajusta reps si hay estancamiento con mismo peso y reps durante varias sesiones.
- `change_reps`: ajusta el rango si el usuario no llega al objetivo pero no hay fatiga extrema.
- `increase_weight`: sube peso objetivo de forma conservadora si se cumple el rango alto con margen.
- `deload_recommended`: recomienda descarga si hay fatiga repetida, RPE alto/RIR bajo, caida de reps o bajada de volumen; al aceptar puede reducir series/peso objetivo o aumentar descanso.
- `exercise_swap`: recomienda cambiar el ejercicio planificado por una alternativa accesible con musculo/equipamiento/dificultad compatibles; no modifica sesiones historicas.
- `routine_goal_adjustment`: analiza objetivos planificados de una rutina contra su `goal`; no usa historial ni notas y solo ajusta series/reps/descanso al aceptar.

## Ollama Local

- Instala Ollama fuera del proyecto.
- Descarga el modelo: `ollama pull llama3.2`.
- Arranca Ollama: `ollama serve`.
- Configura backend: `APP_AI_PROVIDER=ollama`.
- Endpoint usado: `POST /api/generate` con `stream=false` y `format=json`.
- No se anade dependencia obligatoria al proyecto; el backend usa HTTP de la libreria estandar.
- Para planes, el prompt incluye catalogo estructurado de ejercicios accesibles con ids, nombres, musculos, equipamiento y dificultad para que Ollama elija la rutina. No incluye notas, email, username, tokens ni credenciales.
- Para entrevista conversacional, el prompt incluye resumen estructurado, ultimos mensajes necesarios y el ultimo mensaje del usuario solo si no contiene senales sensibles sin confirmar. No incluye notas, email, username, tokens ni credenciales.
- El texto de limitaciones fisicas solo se envia a Ollama si el usuario marco `sensitive_data_acknowledged=true`; no se copia a rutinas, sesiones, notas ni `input_summary`.
- Para resumenes post-sesion, el prompt no incluye notas de sesion/series, email, username, tokens ni credenciales.
- Para preguntas guiadas, el prompt no incluye notas, email, username, tokens, credenciales ni texto libre de `detail`; solo contexto estructurado y metricas.

## Futuras Integraciones

Antes de usar un proveedor remoto distinto de Ollama local hay que decidir explicitamente:

- proveedor.
- coste esperado.
- datos enviados.
- retencion del proveedor.
- consentimiento del usuario.
- estrategia de anonimizado/minimizacion.
