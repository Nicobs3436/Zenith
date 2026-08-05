# Frontend

App Expo React Native + TypeScript para el cliente movil de gestion de rutinas.

## Requisitos

- Node 22 o superior.
- npm.

## Comandos

- `npm install` — instala dependencias.
- `npm run start` — arranca Expo.
- `npm run start:lan` — arranca Expo en LAN, modo offline de Expo CLI y limpiando cache.
- `npm run start:tunnel` — arranca Expo con tunnel limpiando cache.
- `npm run android` — arranca Expo para Android.
- `npm run ios` — arranca Expo para iOS.
- `npm run web` — arranca Expo web.
- `npm run web:export` — genera build web estatico en `dist/` para Vercel.
- `npm run lint` — ejecuta lint.
- `npm run test` — ejecuta tests de helpers con Vitest.
- `npx tsc --noEmit` — ejecuta typecheck.

## Configuracion

- `EXPO_PUBLIC_API_URL` define la URL del backend.
- Valor por defecto actual: `http://localhost:8000`.
- En builds productivos, `EXPO_PUBLIC_API_URL` es obligatoria para evitar publicar apuntando a `localhost`.
- Para dispositivo fisico, usar la IP local del equipo en vez de `localhost`.
- No subas archivos `.env` ni credenciales al repositorio.

### Ejemplos De API URL

- Web local: `EXPO_PUBLIC_API_URL=http://localhost:8000`.
- Expo Go en LAN: `EXPO_PUBLIC_API_URL=http://192.168.1.44:8000`.
- Staging: `EXPO_PUBLIC_API_URL=https://api-staging.example.com`.
- Produccion: `EXPO_PUBLIC_API_URL=https://api.example.com`.

### Web Local

- Backend: `uv run uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload` desde `backend/`.
- Frontend: `npm run web` desde `frontend/`.

### Expo Go

Ejemplo con PC en `192.168.1.44`:

- Backend: `uv run uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload`.
- Frontend PowerShell: `$env:EXPO_PUBLIC_API_URL="http://192.168.1.44:8000"`.
- Expo: `npm run start:lan`.
- Verificar desde el movil: `http://192.168.1.44:8000/health`.
- `npm run start:lan` usa `expo start --offline --clear` para evitar fallos de la API de Expo al generar el manifest local.
- Si aparece `failed to download remote update`, revisar firewall/red o probar `npm run start:tunnel`.

## Estado

- Expo Router configurado en `src/app/`.
- Pantallas actuales: inicio, login, registro, dashboard, rango, ejercicios, rutinas, crear/editar rutina, sesiones, crear/editar/detalle de sesion, estadisticas, entrenador IA y entrenador personal.
- Nombre publico configurado: Zenith.
- Home, registro, privacidad y terminos preparados para beta Zenith.
- Token persistido con `expo-secure-store` en nativo y fallback web con `localStorage`.
- Tests frontend configurados con Vitest para helpers de formularios, progresion, formato stats/rank y mensajes auth; tests de pantallas todavia no configurados.

## Seguridad De Sesion

- El access token y el refresh token se guardan con `expo-secure-store` en Android/iOS.
- En web se usa `localStorage` como fallback de desarrollo.
- `logout()` revoca el refresh token en backend y borra los tokens locales.
- Si una request autenticada devuelve `401`, el cliente intenta `/auth/refresh`, guarda el nuevo par de tokens y reintenta una vez.
- Si el refresh falla, el cliente borra tokens locales y redirige a login con aviso de sesion caducada.

## Producto Beta

- La home muestra aviso medico y enlaces a privacidad/terminos.
- El registro exige aceptar privacidad, terminos y aviso medico.
- `src/app/privacy.tsx` describe datos guardados, IA y limitaciones beta.
- `src/app/terms.tsx` describe uso responsable, IA revisable y limites del free tier.
- La app no sustituye consejo medico ni profesional.

## Entrenador IA

- Ruta: `src/app/coach.tsx`.
- Usa endpoints `/ai/suggestions`.
- Muestra sugerencias explicables con estado y resumen de privacidad.
- Muestra nuevos deloads recomendados como sugerencias aceptables/rechazables.
- Muestra cambios de ejercicio propuestos con el nombre del nuevo ejercicio cuando esta disponible.
- Desde `src/app/routines.tsx` permite analizar el objetivo de una rutina y revisar los ajustes generados en Entrenador IA.
- Permite filtrar por estado y ver datos usados y cambio aplicable antes de aceptar.
- Muestra proveedor/modelo, confianza, notas de riesgo y si hubo fallback interno.
- Aceptar aplica la sugerencia sobre la rutina en backend.
- Rechazar no modifica la rutina.

## Entrenador Personal

- Ruta: `src/app/coach.tsx`.
- Genera planes adaptativos con objetivo, nivel, dias por semana, duracion, equipamiento y prioridades.
- Permite limitaciones fisicas opcionales con aviso de datos sensibles; se envian solo tras confirmacion y se usan para generar el plan.
- Permite pedir modificaciones sobre planes en borrador; cada cambio genera una nueva version revisable.
- Coach usa conversacion natural por bloques y genera vistas previas revisables antes de crear rutinas.
- Muestra evidencia PubMed utilizada por el borrador cuando el backend la recupera.
- Las respuestas guiadas muestran puntos clave, acciones sugeridas y proveedor/modelo/fallback; no modifican rutinas, sesiones ni planes.
- Muestra accesos a sesiones recientes para abrir el detalle y generar o revisar resumenes IA post-sesion.
- Muestra cada rutina del plan con ejercicios, series, reps, descanso, RPE y RIR planificados.
- Muestra proveedor/modelo IA y si el plan uso fallback interno.
- Aceptar un plan crea rutinas reales automaticamente.
- Rechazar un plan no crea rutinas.

## Resumenes Post-Sesion

- Ruta: `src/app/session-detail.tsx`.
- Permite generar o regenerar resumen IA de la sesion.
- Muestra resumen, mejoras, caidas, warnings, proxima recomendacion y proveedor/modelo/fallback.
- No modifica rutinas ni sesiones.
