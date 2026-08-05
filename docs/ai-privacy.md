# Privacidad IA

## Decision Actual

- Fase implementada: Coach en `/ai/coach` con conversacion natural, entrevista por bloques y planes IA revisables.
- Proveedor por defecto local: reglas locales dentro del backend.
- Proveedor publico para Coach V3: Groq configurado con `APP_AI_PROVIDER=groq` y `APP_AI_EXTERNAL_DATA_ENABLED=true`.
- Proveedor opcional local: Ollama configurado con `APP_AI_PROVIDER=ollama`.
- Modelo por defecto Ollama: `llama3.2`.
- Modelo por defecto Groq: `llama-3.3-70b-versatile`.
- Coste: 0 con proveedor interno, Ollama local o cuota gratuita de Groq mientras sus limites lo permitan.
- Datos enviados fuera del sistema: ninguno con proveedor interno; con Ollama local los datos estructurados se envian solo al servidor local configurado; con Groq se envia contexto estructurado minimo al API remoto de Groq.
- `notes` de rutinas, sesiones y series quedan excluidas del contexto usado por IA.
- Email, username, password hash y tokens no se usan como contexto.

## Datos Usados

- Rutina activa del usuario y ejercicios planificados.
- Objetivos estructurados: series, reps, peso/unidad, RPE/RIR y descanso.
- Sesiones activas no borradas.
- Series estructuradas: reps, peso/unidad, RPE/RIR y descanso.
- Para planes adaptativos legacy: objetivo, nivel, dias disponibles, duracion, equipamiento disponible, prioridades, catalogo estructurado de ejercicios accesibles y limitaciones fisicas si el usuario las confirma explicitamente.
- Para Coach: objetivo, sexo biologico, edad, altura, peso, nivel, dias, duracion, equipamiento, prioridades, ejercicios evitados, resumen estructurado, ultimos mensajes necesarios y limitaciones fisicas solo si el usuario las confirma; la IA puede proponer ejercicios fuera del catalogo y el backend los crea como privados solo al aceptar.
- Para revisar planes del Coach: la instruccion libre del usuario, el resumen estructurado del plan original y los mismos campos de planificacion; no se usan notas, email, username ni tokens.
- Para resumenes post-sesion: fecha, rutina asociada si existe, series estructuradas, reps, peso/unidad, RPE/RIR, descanso y agregados por ejercicio/unidad; no se usan notas.

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
- En planes adaptativos legacy, Ollama o Groq pueden proponer la estructura completa del plan: dias, ejercicios, series, repeticiones, RPE/RIR, descansos, explicacion y progresion.
- En Coach V3, Groq u Ollama generan `plan_payload` version 3 con blueprint, volumen semanal, progresion, rutinas, razones por ejercicio y efectos al aceptar. No hay fallback interno para Coach V3.
- El backend valida el `plan_payload` completo antes de persistirlo, exige rangos seguros, rechaza planes redundantes o con volumen incoherente y reintenta una reparacion con el proveedor configurado. Los ejercicios inexistentes quedan pendientes y se crean como privados del usuario solo al aceptar.
- `POST /ai/coach/messages` persiste perfil estructurado, resumen y ultimos mensajes necesarios; no crea rutinas ni sesiones.
- `POST /ai/coach/plan-drafts` solo genera una vista previa si el perfil contiene los datos imprescindibles. El plan sigue siendo revisable y solo crea rutinas reales al aceptar.
- `POST /ai/coach/plan-drafts/{id}/revise` crea una nueva version con trazabilidad; no sobrescribe ni aplica rutinas.
- Las tablas legacy de Coach V2/intake se conservan hasta fase 2 de limpieza segura de base de datos, pero no forman parte del flujo activo.
- Generar un resumen post-sesion crea o actualiza `AiSessionSummary`; no modifica sesiones, series ni rutinas.
- En resumenes post-sesion, Ollama solo puede enriquecer textos/listas del resumen; no aplica cambios.

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
- Para Coach, el prompt incluye perfil estructurado, memoria resumida, ultimos mensajes necesarios y el ultimo mensaje del usuario. No incluye notas, email, username, tokens ni credenciales.
- El texto de limitaciones fisicas solo se envia a Ollama si el usuario marco `sensitive_data_acknowledged=true`; no se copia a rutinas, sesiones, notas ni `input_summary`.
- Para resumenes post-sesion, el prompt no incluye notas de sesion/series, email, username, tokens ni credenciales.

## Groq Remoto

- Configura `APP_AI_PROVIDER=groq`, `APP_AI_GROQ_API_KEY`, `APP_AI_GROQ_MODEL` y `APP_AI_EXTERNAL_DATA_ENABLED=true`.
- Endpoint usado: `POST /openai/v1/chat/completions` con `response_format={"type":"json_object"}`.
- No se anade SDK obligatorio; el backend usa HTTP de la libreria estandar.
- La clave de Groq se guarda solo como variable de entorno/secreto del despliegue y no se versiona.
- El prompt no incluye email, username, password hash, tokens, credenciales ni notas privadas.
- Para Coach se envia el perfil estructurado minimo necesario para entrevistar y crear la vista previa; limitaciones fisicas solo si `sensitive_data_acknowledged=true`.
- Las respuestas de Groq se validan antes de guardarse; si no pasan validacion tras reparacion, no se crea plan.

## Futuras Integraciones

Antes de usar otro proveedor remoto distinto de Groq hay que decidir explicitamente:

- proveedor.
- coste esperado.
- datos enviados.
- retencion del proveedor.
- consentimiento del usuario.
- estrategia de anonimizado/minimizacion.
