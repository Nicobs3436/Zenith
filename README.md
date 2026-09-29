# Zenith

Aplicacion para gestionar rutinas de gimnasio, registrar entrenamientos y medir progresion con historial, estadisticas, rangos e IA revisable.

## Estado Del MVP

MVP funcional con backend FastAPI y frontend Expo Router:

- Auth con registro, login, JWT Bearer, refresh tokens rotativos y `GET /users/me`.
- Catalogo global seed de musculos, equipamiento y ejercicios.
- Ejercicios propios por usuario autenticado.
- Rutinas privadas con ejercicios planificados, series/reps objetivo, RPE/RIR, descanso y notas.
- Sesiones privadas con rutina opcional, multiples series, peso/unidad, RPE/RIR, descanso y notas.
- Historial y detalle de sesiones.
- Estadisticas por ejercicio con filtros `7d`, `30d`, `90d` y `all` desde frontend.
- Rangos por volumen con peso, mejora de 1RM estimado y amplitud de ejercicios progresados.
- Entrenador IA con proveedor `internal` por defecto, `ollama` como opcion local y `groq` como proveedor remoto para Coach V3 en staging/produccion; incluye sugerencias explicables, deload inteligente, cambios de ejercicio, analisis de objetivo por rutina, deduplicacion, expiracion y aplicacion solo al aceptar.
- Coach como entrenador personal IA conversacional: entrevista natural por bloques, memoria resumida, datos obligatorios para plan, vista previa revisable y creacion de rutinas solo al aceptar.
- Resumenes IA post-sesion con mejoras, caidas, warnings y proxima recomendacion sin modificar datos.
- Preguntas guiadas al entrenador IA sin persistencia ni cambios automaticos.
- Pantallas beta de privacidad y terminos, aviso medico visible y aceptacion antes de registro.
- Soft delete de rutinas y sesiones.
- UX minima con loading, estados vacios, avisos y errores legibles.

## Stack

- Backend: Python 3.12 + FastAPI.
- Base de datos: PostgreSQL.
- ORM y migraciones: SQLAlchemy 2 + Alembic.
- Validacion: Pydantic v2.
- Tests backend: pytest.
- Frontend: Expo React Native + TypeScript + Expo Router.
- Tokens frontend: `expo-secure-store`; fallback web con `localStorage`.

## Arranque Local

Backend desde `backend/`:

- `uv sync` — crea/sincroniza el entorno local.
- `docker compose up -d` — arranca PostgreSQL local.
- `uv run alembic upgrade head` — aplica migraciones.
- `uv run python -m app.infrastructure.db.seed` — carga seeds idempotentes.
- `uv run uvicorn app.main:app --reload` — arranca la API.
- `uv run pytest` — ejecuta tests backend.

Frontend desde `frontend/`:

- `npm install` — instala dependencias.
- `npm run start` — arranca Expo.
- `npm run start:lan` — arranca Expo en LAN, modo offline de Expo CLI y limpiando cache.
- `npm run start:tunnel` — arranca Expo con tunnel limpiando cache.
- `npm run web` — arranca target web.
- `npm run web:export` — genera build web estatico para Vercel.
- `npm run android` — arranca target Android.
- `npm run ios` — arranca target iOS.
- `npm run lint` — ejecuta lint.
- `npm run test` — ejecuta tests frontend.
- `npx tsc --noEmit` — ejecuta typecheck.

Configurar API del frontend con `EXPO_PUBLIC_API_URL` si no se usa el default local. En dispositivo fisico no usar `localhost` para apuntar al backend del ordenador.

## Deploy Gratis

Fase 20 prepara deploy con coste 0:

- Backend: Render Free usando `backend/Dockerfile` y `render.yaml`.
- DB: Neon Free PostgreSQL.
- Frontend web/PWA: Vercel Free usando `frontend/vercel.json`.
- CI: GitHub Actions en `.github/workflows/ci.yml`.
- IA en staging/produccion: `APP_AI_PROVIDER=groq` para Coach V3 con `APP_AI_EXTERNAL_DATA_ENABLED=true`.

Ver `docs/deploy.md` para variables, migraciones, seeds, rollback y limitaciones del free tier.

## Producto Beta

Fase 21 prepara Zenith para beta gratuita:

- branding final Zenith.
- onboarding con propuesta de valor y aviso medico.
- privacidad y terminos estaticos en frontend.
- aceptacion explicita de avisos antes de crear cuenta.
- checklist de producto en `docs/product-beta.md`.

## Desarrollo Web Local

Terminal 1, desde `backend/`:

- `docker compose up -d`
- `uv run alembic upgrade head`
- `uv run python -m app.infrastructure.db.seed`
- `uv run uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload`

Terminal 2, desde `frontend/`:

- `npm run web`

Verificar backend en `http://localhost:8000/health`. Si el navegador muestra `Failed to fetch`, comprobar que la API esta levantada y que `APP_CORS_ORIGINS` incluye el origen de Expo web.

## Expo Go En Dispositivo Fisico

El movil no puede usar `localhost` para llegar al backend del ordenador. Usa la IP LAN del PC.

Ejemplo con IP `192.168.1.44`:

Terminal 1, desde `backend/`:

- `uv run uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload`

Terminal 2, desde `frontend/` en PowerShell:

- `$env:EXPO_PUBLIC_API_URL="http://192.168.1.44:8000"`
- `npm run start:lan`

Antes de escanear el QR, abrir desde el movil `http://192.168.1.44:8000/health`. Si no carga, revisar firewall, VPN, red invitada o que PC y movil esten en la misma red. `npm run start:lan` usa `expo start --offline --clear` para evitar fallos de la API de Expo al generar el manifest local. Si Expo Go sigue mostrando `failed to download remote update`, probar que el movil puede alcanzar el servidor Expo del PC o ejecutar `npm run start:tunnel`.

## Flujo Funcional MVP

1. Registrar usuario o iniciar sesion.
2. Ver ejercicios seed y crear ejercicios propios si hace falta.
3. Crear rutina con varios ejercicios y objetivos.
4. Registrar sesion desde rutina o libremente.
5. Editar rutinas o sesiones.
6. Revisar historial y detalle de sesiones.
7. Consultar estadisticas por periodo.
8. Consultar rango y desglose.
9. Borrar rutinas o sesiones con soft delete.

## Decisiones Importantes

- `kg` y `lb` no se convierten automaticamente.
- Estadisticas y progresion separan unidades.
- Borrar una rutina no borra sesiones historicas asociadas.
- Borrar una sesion la excluye de historial, estadisticas y rango.
- El rango se recalcula automaticamente al crear, editar o borrar una sesion.
- No hay puntos por sesiones registradas ni semanas activas.
- La IA admite `internal` como proveedor local por defecto, `ollama` como opcion local y `groq` como proveedor remoto cuando se habilita explicitamente el envio externo de datos; no usa notas y solo modifica rutinas cuando el usuario acepta una sugerencia o plan validado.
- Coach es la experiencia principal del entrenador; guarda perfil/memoria resumida y ultimos mensajes necesarios, no historial completo.
- Para generar una vista previa, Coach requiere objetivo, sexo biologico, edad, altura, peso, nivel, dias por semana, duracion y equipamiento.
- Las limitaciones fisicas opcionales se tratan como dato sensible: requieren confirmacion y no sustituyen consejo medico/profesional.
- La beta no incluye eliminacion/exportacion automatica de cuenta; queda pendiente antes de producto publico.

## Documentacion

- `docs/architecture.md` — arquitectura y decisiones tecnicas.
- `docs/data-model.md` — modelo de datos actual.
- `docs/mvp.md` — alcance del MVP.
- `docs/ai-privacy.md` — decision de privacidad y trazabilidad IA.
- `docs/product-beta.md` — estado beta, limitaciones y checklist antes de producto publico.
- `AGENTS.md` — instrucciones operativas para agentes.
