# AplicacionDesarrolladaAgentesIAGimnasio
Aplicacion para gestionar rutinas de gimnasio, registrar entrenamientos y asistir la progresion con IA. Pensada para usuarios que quieren planificar, medir y ajustar sus entrenamientos con historial, estadisticas y sugerencias automaticas.

## Stack
- Backend decidido: Python + FastAPI.
- Version Python decidida: 3.12.
- Base de datos decidida: PostgreSQL.
- Persistencia: SQLAlchemy 2 + Alembic.
- Validacion: Pydantic v2.
- Frontend: Expo React Native + TypeScript + Expo Router.
- Tests: pytest para backend; Vitest para helpers frontend.
- IA actual: entrenador interno/local de progresion, planes adaptativos, resumenes post-sesion y preguntas guiadas con proveedor opcional Ollama local, coste 0, sin proveedor remoto, con deduplicacion/expiracion de sugerencias.

## Comandos
- Backend: ejecutar comandos desde `backend/`.
- `uv sync` — crea/sincroniza el entorno local del backend.
- `docker compose up -d` — arranca PostgreSQL local.
- `uv run alembic upgrade head` — aplica migraciones pendientes.
- `uv run python -m app.infrastructure.db.seed` — carga seeds idempotentes de musculos, equipamiento, ejercicios globales y rangos.
- `uv run uvicorn app.main:app --reload` — arranca la API en desarrollo.
- `uv run pytest` — ejecuta los tests del backend.
- Tests de auth/API usan SQLite en memoria con override de `get_db`; migraciones se verifican contra PostgreSQL local.
- Frontend: ejecutar comandos desde `frontend/`.
- `npm install` — instala dependencias del frontend.
- `npm run start` — arranca Expo.
- `npm run android` / `npm run ios` / `npm run web` — arranca targets Expo.
- `npm run lint` — ejecuta lint del frontend.
- `npm run test` — ejecuta tests frontend con Vitest.
- `npx tsc --noEmit` — ejecuta typecheck frontend.
- Tests frontend actuales cubren helpers de formularios, progresion, formato stats/rank, mensajes auth y cliente API; tests de pantallas todavia no configurados.
- Frontend persiste access y refresh token con `expo-secure-store`; fallback web actual usa `localStorage`.
- Pendiente backend: lint, format, typecheck y build todavia no estan configurados.
- Deploy fase 20: coste 0 con Render Free para backend Docker, Neon Free para PostgreSQL, Vercel Free para web/PWA, GitHub Actions Free para CI e IA `internal` en staging/produccion.
- Producto fase 21: beta gratuita Zenith con branding, privacidad/terminos estaticos, aviso medico visible y aceptacion antes de registro; eliminacion/exportacion automatica queda pendiente.

## Estructura del proyecto
- `backend/` — API FastAPI, SQLAlchemy/Alembic, PostgreSQL local, estructura por capas y tests.
- `frontend/` — app Expo React Native + TypeScript con Expo Router.
- `docs/` — arquitectura inicial, modelo de datos, alcance MVP y futuras decisiones tecnicas.

## Dominio previsto
- Base global de ejercicios con musculos, equipo, dificultad, tecnica y variantes.
- Ejercicios actuales: globales publicos de lectura y propios por usuario autenticado; sin roles/admin todavia.
- Rutinas y sesiones actuales: privadas por usuario, con ejercicios planificados y series registradas.
- Estadisticas actuales: volumen/carga por ejercicio, periodo y filtros `7d`/`30d`/`90d`/`all`; `kg` y `lb` no se convierten automaticamente.
- Estadisticas previstas: progresion por rutina, musculo y periodo.
- Rangos actuales: score por volumen con peso, mejora de 1RM estimado y amplitud de ejercicios progresados; sin puntos por sesiones ni semanas activas.
- Soft delete actual: borrar rutina no borra sesiones historicas; borrar sesion la excluye de historial, estadisticas y rango.
- Anotaciones por sesion y por ejercicio.
- IA actual sugiere sobrecarga progresiva, deload inteligente, cambios de ejercicio, ajustes de volumen/reps/descanso, analisis de objetivo por rutina y estancamiento; en planes adaptativos Ollama puede proponer la estructura completa usando el catalogo accesible y backend valida antes de guardar; solo modifica rutinas al aceptar una sugerencia o un plan adaptativo.
- El entrenador personal puede crear planes adaptativos; con Ollama local la IA propone la estructura y el backend valida ids, volumen, rangos, coherencia y privacidad; al aceptar crea rutinas reales, no sesiones.
- Los resumenes post-sesion generan resumen, mejoras, caidas, warnings y proxima recomendacion; no modifican rutinas, sesiones ni series.
- Las preguntas guiadas al entrenador no se persisten, no crean sugerencias y no modifican rutinas, sesiones, series ni planes; el texto libre de detalle no se envia a proveedores.

## Convenciones
- Antes de implementar, separar dominio de gimnasio, persistencia, API e integraciones externas.
- Validar toda entrada de usuario antes de guardarla o usarla en sugerencias de IA.
- No devolver nunca `password_hash`; auth usa Argon2 y JWT Bearer.
- Tratar pesos, unidades, fechas y zonas horarias como decisiones explicitas; no asumir defaults silenciosos.
- En estadisticas, no mezclar `kg` y `lb`; mantener grupos separados hasta definir conversiones.
- Las recomendaciones de IA deben ser explicables y revisables por el usuario; solo aplicar cambios al aceptar, nunca modificar sesiones historicas.
- Los tests deben cubrir reglas de progresion, calculos estadisticos y validaciones de registros de entrenamiento.

## No hagas
- No inventar comandos, carpetas o dependencias: si no existen, marcarlos como pendientes.
- No instalar dependencias sin avisar y justificar por que son necesarias.
- No subir archivos `.env*`, claves de API, tokens ni credenciales.
- `backend/.env.example` si puede versionarse; `backend/.env` no.
- No conectar MCPs o herramientas de base de datos a produccion sin permiso explicito.
- No usar datos personales o de salud en prompts de IA sin una decision explicita de privacidad.
- Las limitaciones fisicas son datos sensibles: solo usarlas si el usuario confirma el aviso y documentar que no sustituyen consejo medico.
- No guardar tokens adicionales o datos sensibles en frontend sin decision explicita de seguridad.
- No hacer que la IA modifique planes sin trazabilidad y aprobacion del usuario.

## Flujo de trabajo
- Antes de una tarea no trivial, propon un plan y espera mi OK.
- Una tarea a la vez; al terminar, dime que cambiaste para que lo revise.
- Si no estas seguro al 80%, pregunta. No inventes.
- Si la documentacion contradice los scripts o configuraciones ejecutables, confia en lo ejecutable y actualiza este archivo.
- Mantener este archivo compacto: solo anadir reglas que un agente probablemente pasaria por alto.

## MCPs y herramientas
- Context7: usarlo para consultar documentacion actualizada de FastAPI, React Native, Expo, Next.js, PostgreSQL, Prisma/SQLAlchemy u otras librerias elegidas.
- MCP de base de datos: usar solo con permiso explicito, preferiblemente contra entornos locales o de desarrollo.
- MCP de archivos/repositorio: respetar cambios no propios; no revertir trabajo del usuario sin permiso.
- Para decisiones de arquitectura, priorizar fuentes del repo: `README*`, manifiestos, configs, lockfiles, CI e instrucciones existentes.

## Documentacion
- `README.md`: vision, stack decidido y estado del proyecto.
- `docs/architecture.md`: arquitectura inicial y decisiones tecnicas.
- `docs/data-model.md`: entidades y relaciones del MVP.
- `docs/mvp.md`: alcance funcional del primer MVP.
- `docs/deploy.md`: deploy gratuito, variables, migraciones, seeds, rollback y limitaciones.
- `docs/product-beta.md`: estado beta, limitaciones y checklist antes de producto publico.
- Documentar nuevas decisiones importantes en `docs/`, especialmente privacidad de IA y reglas de progresion.
- Este `AGENTS.md` es la referencia operativa para futuras sesiones de OpenCode.
