# Backend

API FastAPI para la gestion de rutinas de gimnasio, registros de entrenamiento y futuras sugerencias de progresion con IA.

## Requisitos

- Python 3.12 o superior.
- `uv` como gestor de entorno y dependencias.
- Docker con Docker Compose para PostgreSQL local.

## Comandos

- `uv sync` — crea/sincroniza el entorno local del backend.
- `docker compose up -d` — arranca PostgreSQL local.
- `uv run alembic upgrade head` — aplica migraciones pendientes.
- `uv run python -m app.infrastructure.db.seed` — carga seeds idempotentes de catalogo.
- `uv run uvicorn app.main:app --reload` — arranca la API en desarrollo.
- `uv run pytest` — ejecuta los tests del backend.
- `docker build .` — valida la imagen productiva desde `backend/`.

## Estructura

- `app/main.py` — factory de FastAPI y registro de routers.
- `app/api/` — endpoints HTTP.
- `app/core/` — configuracion base.
- `app/domain/` — reglas puras del dominio de gimnasio.
- `app/application/` — casos de uso.
- `app/infrastructure/db/` — base SQLAlchemy, engine y sesiones.
- `alembic/` — entorno de migraciones.
- `tests/` — tests automatizados.

## Configuracion Local

- Copia `backend/.env.example` a `backend/.env` si necesitas cambiar valores locales.
- `APP_DATABASE_URL` usa por defecto `postgresql+psycopg://gym_app:gym_app@localhost:5432/gym_app`.
- `APP_SECRET_KEY` tiene un valor local por defecto; cambialo en staging y production.
- Si `APP_ENVIRONMENT` es `production` o `prod`, la API falla al arrancar si `APP_SECRET_KEY` conserva el valor local.
- `APP_ACCESS_TOKEN_EXPIRE_MINUTES` controla la duracion del JWT de acceso.
- `APP_REFRESH_TOKEN_EXPIRE_DAYS` controla la duracion del refresh token rotativo.
- `APP_AUTH_LOGIN_RATE_LIMIT_ATTEMPTS` y `APP_AUTH_LOGIN_RATE_LIMIT_WINDOW_SECONDS` limitan login por IP/email.
- `APP_AUTH_REGISTER_RATE_LIMIT_ATTEMPTS` y `APP_AUTH_REGISTER_RATE_LIMIT_WINDOW_SECONDS` limitan registro por IP.
- `APP_AI_PROVIDER` acepta `internal` u `ollama`; por defecto `internal`.
- `APP_AI_OLLAMA_BASE_URL`, `APP_AI_OLLAMA_MODEL` y `APP_AI_TIMEOUT_SECONDS` configuran Ollama local.
- `APP_AI_EXTERNAL_DATA_ENABLED` debe ser `true` en production para usar un proveedor no interno.
- No subas `.env` ni credenciales reales al repositorio.

### Entornos

- Local web: `APP_ENVIRONMENT=local`, `APP_DATABASE_URL=postgresql+psycopg://gym_app:gym_app@localhost:5432/gym_app`, CORS con `http://localhost:8081` y `http://127.0.0.1:8081`.
- Local LAN/Expo Go: anade el origen LAN de Expo a `APP_CORS_ORIGINS`, por ejemplo `http://192.168.1.44:8081`.
- Staging: `APP_ENVIRONMENT=staging`, base de datos de staging, `APP_SECRET_KEY` unico, y CORS apuntando al frontend de staging. El valor local de `APP_SECRET_KEY` se rechaza tambien en staging.
- Production: `APP_ENVIRONMENT=production`, base de datos de produccion, `APP_SECRET_KEY` unico y fuerte, y CORS limitado al frontend publico real.
- El rate limiter actual vive en memoria del proceso y es suficiente para MVP/local; en production multiinstancia debe reemplazarse por Redis o un storage compartido.

## Endpoints Iniciales

- `GET /health` — comprueba que la API responde.
- `GET /ready` — comprueba que la API puede conectar con la base de datos.
- `POST /auth/register` — crea un usuario con email, username y password.
- `POST /auth/login` — devuelve un token Bearer.
- `GET /users/me` — devuelve el usuario autenticado.
- `GET /exercises` — lista ejercicios globales y, con token, tambien los propios del usuario.
- `GET /exercises/{exercise_id}` — detalle de ejercicio global o propio accesible.
- `POST /exercises` — crea un ejercicio propio del usuario autenticado.
- `GET /muscle-groups` — lista grupos musculares.
- `GET /equipment` — lista equipamiento.
- `POST /routines` — crea una rutina privada con ejercicios planificados.
- `GET /routines` — lista rutinas del usuario autenticado.
- `GET /routines/{routine_id}` — detalle de una rutina propia.
- `POST /workout-sessions` — registra una sesion con series.
- `GET /workout-sessions` — lista sesiones del usuario autenticado.
- `GET /workout-sessions/{session_id}` — detalle de una sesion propia.
- `GET /stats/exercises` — estadisticas agregadas por ejercicio del usuario autenticado.
- `GET /stats/exercises/{exercise_id}` — estadisticas por periodo de un ejercicio accesible.
- `GET /ranks` — lista rangos disponibles.
- `GET /users/me/rank` — calcula el rango actual del usuario autenticado.
- `POST /users/me/rank/recalculate` — recalcula y guarda snapshot del rango.
- `POST /ai/suggestions/generate` — genera sugerencias internas de progresion.
- `GET /ai/suggestions` — lista sugerencias del usuario.
- `POST /ai/suggestions/{suggestion_id}/accept` — acepta y aplica la sugerencia sobre la rutina.
- `POST /ai/suggestions/{suggestion_id}/reject` — rechaza la sugerencia sin modificar la rutina.
- `POST /ai/routines/{routine_id}/analyze-goal` — analiza si una rutina esta alineada con su objetivo y genera ajustes revisables.
- `POST /ai/training-plans/generate` — genera un plan adaptativo en borrador.
- `GET /ai/training-plans` — lista planes adaptativos del usuario.
- `GET /ai/training-plans/{plan_id}` — detalle de un plan propio.
- `POST /ai/training-plans/{plan_id}/accept` — acepta el plan y crea rutinas reales.
- `POST /ai/training-plans/{plan_id}/reject` — rechaza el plan sin crear rutinas.
- `POST /ai/training-plans/{plan_id}/modify` — crea una nueva version borrador del plan con la instruccion del usuario.
- `POST /ai/session-summaries/{session_id}/generate` — genera o actualiza un resumen IA de una sesion propia.
- `GET /ai/session-summaries/{session_id}` — obtiene el resumen IA generado de una sesion propia.
- `POST /ai/coach/questions` — responde una pregunta guiada al entrenador sin persistir historial ni modificar datos.

## Auth

- Las contrasenas se guardan hasheadas con Argon2 mediante `pwdlib`.
- El login devuelve access token JWT Bearer y refresh token opaco.
- Los access tokens se firman con `APP_SECRET_KEY`.
- Los refresh tokens se guardan como HMAC/SHA-256 y rotan en cada `/auth/refresh`.
- `/auth/logout` revoca el refresh token actual.

## Ejercicios

- Los ejercicios globales son publicos de lectura.
- Los usuarios autenticados pueden crear ejercicios propios; no pueden crear globales desde la API publica.
- Musculos y equipamiento se modelan como tablas relacionales many-to-many.
- `uv run python -m app.infrastructure.db.seed` carga datos iniciales sin duplicarlos.

## Rutinas Y Sesiones

- Las rutinas son privadas por usuario.
- Una rutina contiene ejercicios planificados con objetivos opcionales de sets, reps, RPE/RIR y descanso.
- Una sesion registra series reales con reps, peso/unidad, RPE/RIR, descanso y notas.

## Estadisticas

- Las estadisticas se calculan desde sesiones y series; no hay tablas agregadas todavia.
- El volumen usa `reps * weight_value` solo cuando hay peso.
- Las series sin peso cuentan para sets/reps, pero no para volumen/carga.
- `kg` y `lb` se mantienen separados; no hay conversion automatica.
- El 1RM estimado inicial usa formula Epley: `weight * (1 + reps / 30)`.

## Rangos

- El score se basa en volumen con peso, mejora de 1RM estimado y progreso en varios ejercicios.
- No hay puntos por sesiones registradas ni por semanas activas.
- `kg` y `lb` no se convierten ni se comparan entre si para progresion.

## Entrenador IA

- La fase actual usa reglas internas/locales, sin proveedor externo y coste 0.
- Puede usar Ollama local opcional con `APP_AI_PROVIDER=ollama`; no es dependencia obligatoria.
- No usa `notes` como contexto.
- Genera sugerencias explicables y trazables, incluidos `deload_recommended` ante fatiga acumulada y `exercise_swap` para alternativas compatibles.
- Analiza objetivos de rutina con `routine_goal_adjustment` para alinear series/reps/descanso sin usar notas ni historial.
- Evita duplicados pendientes identicos y expira sugerencias pendientes obsoletas.
- Guarda regla disparada, metricas resumidas y cambio aplicable.
- Ollama solo enriquece recomendacion, explicacion, notas de riesgo y confianza; no modifica `apply_payload`.
- Si Ollama falla, se usa fallback interno.
- Aceptar una sugerencia aplica cambios validados sobre la rutina.
- Aceptar un deload puede reducir series/peso objetivo o aumentar descanso; no toca sesiones historicas.
- Aceptar un cambio de ejercicio reemplaza el ejercicio planificado en la rutina; no toca sesiones historicas.
- Aceptar un plan adaptativo crea rutinas reales, una por dia disponible.
- Modificar un plan adaptativo crea una nueva version `draft` con trazabilidad; no cambia el original ni crea rutinas.
- En planes adaptativos, Ollama puede generar la estructura completa del plan usando el catalogo accesible de ejercicios; el backend valida ids, volumen, rangos, coherencia y privacidad antes de guardar.
- Los resumenes post-sesion devuelven resumen, mejoras, caidas, warnings y proxima recomendacion; no modifican rutinas ni sesiones.
- Las preguntas guiadas al entrenador responden `next_workout`, `progression`, `fatigue`, `routine_review` y `stats_explanation`; no se persisten, no crean sugerencias y no aplican cambios.
- En preguntas guiadas, el detalle libre no se envia a Ollama ni se incluye en trazabilidad; solo se usa contexto estructurado propio.
- Rechazar una sugerencia no modifica datos de entrenamiento.
- Las sesiones historicas no se modifican.
- Las limitaciones fisicas requieren confirmacion explicita porque pueden ser datos sensibles.
- El texto de limitaciones se usa solo para generar el plan y no se copia a rutinas, sesiones, notas ni `input_summary`.
### Ollama Local Opcional

- Instalar Ollama fuera del proyecto.
- Descargar modelo: `ollama pull llama3.2`.
- Arrancar servicio: `ollama serve`.
- Configurar `.env`: `APP_AI_PROVIDER=ollama`.
- Para planes personalizados, Ollama recibe objetivo, nivel, dias, duracion, equipamiento, prioridades, catalogo estructurado de ejercicios accesibles y limitaciones fisicas solo si fueron confirmadas como dato sensible.
