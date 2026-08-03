# Arquitectura

## Objetivo

Aplicacion movil/web para gestionar rutinas de gimnasio, registrar sesiones, consultar estadisticas y asistir la progresion. La IA produce sugerencias explicables y solo aplica cambios cuando el usuario acepta.

## Stack

- Backend: Python 3.12 + FastAPI.
- Base de datos: PostgreSQL.
- Persistencia: SQLAlchemy 2.
- Migraciones: Alembic.
- Validacion/DTOs: Pydantic v2.
- Tests backend: pytest.
- Frontend: Expo React Native + TypeScript + Expo Router.

## Capas Backend

- `domain`: schemas Pydantic y reglas de validacion de entrada/salida.
- `application`: casos de uso y orquestacion de rutinas, sesiones, estadisticas y rangos.
- `api`: routers FastAPI y traduccion a errores HTTP.
- `infrastructure`: modelos SQLAlchemy, repositorios, migraciones, configuracion y seeds.

## Modulos Backend Actuales

- `app/api/auth.py`: registro y login.
- `app/api/users.py`: usuario actual y dependencia de auth.
- `app/api/exercises.py`: ejercicios globales, propios y catalogos.
- `app/api/routines.py`: rutinas, sesiones, edicion y soft delete.
- `app/api/stats.py`: estadisticas por ejercicio y periodo.
- `app/api/ranks.py`: rangos y recalculo manual.
- `app/api/ai.py`: Coach V2, sugerencias de progresion, entrevista legacy, planes adaptativos, resumenes post-sesion y preguntas guiadas legacy.
- `app/application/routine_service.py`: creacion, reemplazo completo, borrado logico y recalculo de rango tras cambios de sesion.
- `app/application/stats_service.py`: agregaciones de sets/reps/volumen/carga.
- `app/application/rank_service.py`: score, rango actual, siguiente rango y snapshots.
- `app/application/ai_coach_service.py`: entrenador interno/local, reglas de progresion y aplicacion validada de sugerencias aceptadas.
- `app/application/ai_coach_intake_service.py`: entrevista conversacional con persistencia minima, resumen estructurado y generacion de plan cuando el intake esta listo.
- `app/application/coach_v2_service.py`: entrenador conversacional continuo, perfil profesional, memoria resumida, propuestas automaticas, planes y sesiones recomendadas.
- `app/application/ai_coach_question_service.py`: respuestas stateless a preguntas guiadas con contexto estructurado y sin persistencia.
- `app/application/ai_training_plan_service.py`: creador de planes adaptativos, validacion de estructura, enriquecimiento IA opcional y creacion de rutinas reales al aceptar.
- `app/application/ai_session_summary_service.py`: resumenes post-sesion con metricas estructuradas, privacidad y fallback IA.
- `app/infrastructure/db/seed.py`: seeds idempotentes.

## Frontend Actual

- `frontend/src/app/`: rutas Expo Router.
- `frontend/src/api/client.ts`: cliente HTTP, auth, errores legibles y API del MVP.
- `frontend/src/auth/tokenStorage.ts`: access y refresh token con `expo-secure-store`; fallback web con `localStorage`.
- Pantallas principales: login, registro, dashboard, ejercicios, rutinas, sesiones, detalle de sesion, estadisticas, rango, entrenador IA y entrenador personal.
- Formularios largos usan `Screen` con scroll y validacion previa local; backend mantiene la validacion final.

## Autenticacion Y Seguridad

- Passwords hasheadas con Argon2.
- JWT Bearer para access token y refresh tokens opacos rotativos.
- `password_hash` nunca se devuelve.
- Datos privados se filtran por usuario en repositorios/servicios.
- Tests API usan SQLite en memoria con override de `get_db`.
- Migraciones se verifican contra PostgreSQL local.
- El cliente refresca sesion automaticamente y revoca refresh token al cerrar sesion.

## Rutinas Y Sesiones

- Rutinas privadas por usuario.
- Rutinas requieren al menos un ejercicio planificado.
- Sesiones pueden tener rutina opcional o ser libres.
- Edicion actual usa reemplazo completo: `PUT` reemplaza lista de ejercicios planificados o series.
- Borrar rutina aplica soft delete y no borra sesiones historicas asociadas.
- Borrar sesion aplica soft delete y la excluye de historial, estadisticas y rango.

## Estadisticas

- Se calculan bajo demanda desde sesiones y series activas.
- `total_volume = sum(reps * weight_value)` solo para series con peso.
- Series sin peso cuentan para sets/reps y quedan en `weight_unit=null`.
- `kg` y `lb` se devuelven separados; no hay conversion implicita.
- Backend soporta `start_date`, `end_date`, `weight_unit` y periodos `day`, `week`, `month` para detalle.
- Frontend ofrece filtros `7d`, `30d`, `90d`, `all` calculando `start_date`.

## Rangos

- Score = volumen con peso + mejora de 1RM estimado + amplitud de ejercicios progresados.
- No hay puntos por sesiones registradas ni semanas activas.
- Series sin peso no suben rango.
- `kg` y `lb` no se comparan entre si para progresion.
- El rango se recalcula automaticamente al crear, editar o borrar sesiones.
- `GET /users/me/rank` devuelve rango actual, siguiente rango y puntos faltantes.
- `POST /users/me/rank/recalculate` persiste un snapshot manual.

## IA

- Fase 18C mantiene el entrenador interno/local y anade proveedor opcional Ollama local.
- No envia datos fuera del backend.
- Excluye `notes`, email, username y credenciales del contexto usado.
- Genera sugerencias trazables para subir peso, bajar volumen, cambiar reps, aumentar descanso o detectar estancamiento.
- Evita duplicar sugerencias pendientes identicas y expira sugerencias pendientes obsoletas al generar un nuevo analisis.
- Guarda regla disparada, metricas resumidas y cambio aplicable en la trazabilidad.
- En sugerencias, resumenes y preguntas, Ollama enriquece textos/listas bajo validacion; en planes adaptativos puede proponer estructura completa validada por backend.
- Si Ollama falla o devuelve JSON invalido, se usa fallback interno y se traza.
- Generar una sugerencia no modifica datos.
- Aceptar una sugerencia aplica un cambio validado sobre la rutina; rechazar solo cambia el estado.
- Las sesiones historicas no se modifican.
- El entrenador personal genera planes adaptativos con una rutina por dia disponible; aceptar crea rutinas reales, rechazar no modifica datos. Con Ollama local, la IA puede proponer la estructura completa del plan usando el catalogo accesible; el backend valida ejercicios, volumen, rangos, coherencia, privacidad y usa fallback interno si la propuesta no es valida.
- La entrevista conversacional del Coach guarda un unico `AiCoachIntake` por usuario con resumen estructurado, ultimos mensajes necesarios, campos faltantes y estado `ready_for_plan`; no guarda historial completo ni modifica datos por si sola.
- El plan desde intake solo se genera si estan completos objetivo, nivel, dias por semana y duracion; despues sigue el mismo flujo de borrador revisable y aceptacion explicita.
- Coach V2 reemplaza el frontend visible del entrenador: requiere perfil cientifico minimo con sexo biologico, edad, altura, peso, objetivo, nivel, dias, duracion y equipamiento; guarda memoria resumida y puede proponer revisiones automaticas o sesiones futuras.
- El resumen post-sesion analiza solo datos estructurados de una sesion activa propia; excluye notas y no modifica datos historicos.
- Las preguntas guiadas al entrenador (`next_workout`, `progression`, `fatigue`, `routine_review`, `stats_explanation`) responden sin persistir historial, sin chat libre y sin modificar datos.
- En preguntas guiadas, el detalle libre no se envia a proveedores ni se incluye en `input_summary`; solo se usa contexto estructurado propio.
- Las limitaciones fisicas introducidas por el usuario requieren confirmacion explicita por ser datos sensibles y no sustituyen consejo medico.
- Ver `docs/ai-privacy.md` para la decision de privacidad.
- Proveedores remotos quedan pendientes de decision explicita de privacidad/coste.

## Principios Operativos

- Validar toda entrada de usuario antes de persistir.
- No enviar datos sensibles a IA sin decision explicita de privacidad.
- No mezclar unidades en estadisticas ni progresion.
- No borrar fisicamente historial de entrenamiento en operaciones normales.
- Documentacion ejecutable y scripts tienen prioridad sobre planes antiguos.
