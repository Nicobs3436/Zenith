# MVP

## Objetivo

Permitir que un usuario gestione ejercicios, cree rutinas, registre sesiones reales, consulte historial, vea estadisticas basicas, progrese en rangos y reciba sugerencias internas de progresion y planes adaptativos revisables.

## Implementado

- Registro e inicio de sesion con JWT Bearer.
- `GET /users/me` protegido.
- Ejercicios globales seed y ejercicios propios por usuario.
- Catalogos de musculos y equipamiento.
- Rutinas privadas con multiples ejercicios planificados.
- Campos planificados por ejercicio: series, reps min/max, RPE, RIR, descanso y notas.
- Sesiones privadas con rutina opcional.
- Series registradas con ejercicio, reps, peso, unidad, RPE, RIR, descanso y notas.
- Precarga de series desde rutina usando `target_sets`.
- Historial y detalle de sesiones.
- Estadisticas por ejercicio, fechas y unidad.
- Filtros frontend de estadisticas: `7d`, `30d`, `90d`, `all`.
- Rangos basados en volumen con peso, mejora de 1RM estimado y amplitud de ejercicios progresados.
- Entrenador IA interno/local con sugerencias explicables, deload inteligente, cambios de ejercicio, analisis de objetivo por rutina, trazabilidad, deduplicacion, expiracion y aceptacion/rechazo.
- Entrenador personal IA que genera planes adaptativos, permite pedir modificaciones revisables y crea rutinas reales al aceptar.
- Resumenes IA post-sesion con mejoras, caidas, warnings y proxima recomendacion sin modificar datos.
- Preguntas guiadas al entrenador IA sin persistencia, sin chat libre y sin modificar datos.
- Recalculo automatico de rango al crear, editar o borrar sesiones.
- Soft delete de rutinas y sesiones.
- UX minima: loading, estados vacios, bloqueo de doble submit, avisos y errores legibles.

## Criterios De Aceptacion Cubiertos

- Un usuario puede autenticarse y ver solo sus datos.
- Un usuario puede crear, editar y borrar logicamente rutinas privadas.
- Un usuario puede registrar, editar, consultar detalle y borrar logicamente sesiones.
- El backend rechaza datos invalidos como pesos negativos, repeticiones negativas o RPE fuera de rango.
- El historial permite consultar sesiones anteriores activas.
- Las estadisticas se calculan de forma reproducible y testeada.
- `kg` y `lb` se mantienen separados.
- Borrar una rutina no borra sesiones historicas asociadas.
- Borrar una sesion la excluye de historial, estadisticas y rango.

## Fuera Del MVP

- Proveedor IA remoto distinto de Ollama local.
- IA que modifique planes sin aceptacion del usuario.
- Roles/admin.
- Conversion automatica entre `kg` y `lb`.
- Social, comunidad o comparativas publicas.
- Integracion con wearables.
- Pagos o suscripciones.
- Notificaciones.
- Modo offline completo.
- Tests frontend automatizados.
- Restaurar elementos borrados.

## Endpoints MVP

- Auth: `POST /auth/register`, `POST /auth/login`.
- Usuario: `GET /users/me`.
- Ejercicios: `GET /exercises`, `GET /exercises/{exercise_id}`, `POST /exercises`.
- Catalogos: `GET /muscle-groups`, `GET /equipment`.
- Rutinas: `POST /routines`, `GET /routines`, `GET /routines/{routine_id}`, `PUT /routines/{routine_id}`, `DELETE /routines/{routine_id}`.
- Sesiones: `POST /workout-sessions`, `GET /workout-sessions`, `GET /workout-sessions/{session_id}`, `PUT /workout-sessions/{session_id}`, `DELETE /workout-sessions/{session_id}`.
- Estadisticas: `GET /stats/exercises`, `GET /stats/exercises/{exercise_id}`.
- Rangos: `GET /ranks`, `GET /users/me/rank`, `POST /users/me/rank/recalculate`.
- IA: `POST /ai/suggestions/generate`, `GET /ai/suggestions`, `POST /ai/suggestions/{suggestion_id}/accept`, `POST /ai/suggestions/{suggestion_id}/reject`.
- Analisis IA: `POST /ai/routines/{routine_id}/analyze-goal`.
- Planes IA: `POST /ai/training-plans/generate`, `GET /ai/training-plans`, `GET /ai/training-plans/{plan_id}`, `POST /ai/training-plans/{plan_id}/accept`, `POST /ai/training-plans/{plan_id}/reject`, `POST /ai/training-plans/{plan_id}/modify`.
- Resumenes IA: `POST /ai/session-summaries/{session_id}/generate`, `GET /ai/session-summaries/{session_id}`.
- Coach IA conversacional: `GET /ai/coach`, `POST /ai/coach/messages` y vistas previas en `/ai/coach/plan-drafts`.

## QA MVP

- Backend: `uv run pytest`.
- Frontend: `npm run lint` y `npx tsc --noEmit`.
- Migraciones: `uv run alembic upgrade head` contra PostgreSQL local.
- Seeds: `uv run python -m app.infrastructure.db.seed`.
