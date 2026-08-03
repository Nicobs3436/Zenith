# Deploy Gratis

## Objetivo

Desplegar Zenith con coste 0 para staging/beta inicial:

- Backend: Render Free con Docker.
- Base de datos: Neon Free PostgreSQL.
- Frontend web/PWA: Vercel Free.
- CI: GitHub Actions Free.
- IA en staging/produccion: `internal`.

No se incluye publicacion en App Store o Google Play porque no es coste 0.

## URLs

- Frontend Vercel: `https://<vercel-project>.vercel.app`.
- Ejemplo si esta disponible: `https://zenith.vercel.app`.
- Backend Render: `https://<render-service>.onrender.com`.

Actualizar estas URLs reales en las variables de entorno cuando existan.

## Backend Render Free

Archivos relevantes:

- `render.yaml`.
- `backend/Dockerfile`.
- `backend/.dockerignore`.
- `backend/app/api/health.py` con `/health` y `/ready`.

Variables Render:

- `APP_APP_NAME=zenith-api`.
- `APP_ENVIRONMENT=staging`.
- `APP_DATABASE_URL=<neon-postgres-url>`.
- `APP_SECRET_KEY=<secret-largo-unico>`.
- `APP_CORS_ORIGINS=https://<vercel-project>.vercel.app`.
- `APP_AI_PROVIDER=internal`.
- `APP_AI_EXTERNAL_DATA_ENABLED=false`.

Notas:

- `APP_SECRET_KEY` no puede usar el valor local en `staging` ni `production`.
- Render Free puede dormir por inactividad; la primera request puede tardar mas.
- Render ejecuta `alembic upgrade head` al arrancar el contenedor antes de iniciar Uvicorn. En cambios criticos, revisar logs de Render tras el deploy.

## Base De Datos Neon Free

1. Crear proyecto PostgreSQL en Neon Free.
2. Copiar connection string compatible con SQLAlchemy/psycopg.
3. Usar formato aproximado:

```text
postgresql+psycopg://USER:PASSWORD@HOST/DBNAME?sslmode=require
```

4. Guardar esa URL en Render como `APP_DATABASE_URL`.

## Migraciones Y Seeds

Render aplica migraciones al arrancar el backend. Si necesitas ejecutarlas manualmente desde `backend/`, apuntando a Neon:

```powershell
$env:APP_DATABASE_URL="postgresql+psycopg://USER:PASSWORD@HOST/DBNAME?sslmode=require"
$env:APP_SECRET_KEY="secret-temporal-local-para-comandos"
uv run alembic upgrade head
uv run python -m app.infrastructure.db.seed
```

Los seeds son idempotentes.

## Frontend Vercel Free

Archivos relevantes:

- `frontend/vercel.json`.
- `frontend/app.json` con nombre publico `Zenith`.
- `frontend/.env.example`.

Configuracion Vercel:

- Root directory: `frontend`.
- Install command: `npm ci`.
- Build command: `npm run web:export`.
- Output directory: `dist`.
- Environment variable: `EXPO_PUBLIC_API_URL=https://<render-service>.onrender.com`.

El frontend falla en builds productivos si `EXPO_PUBLIC_API_URL` no esta definido, para evitar publicar apuntando a `localhost`.

## CI GitHub Actions

Archivo: `.github/workflows/ci.yml`.

Valida:

- Backend tests con `uv run pytest`.
- Migraciones con PostgreSQL de CI.
- Build Docker del backend.
- Frontend tests, lint, typecheck y export web.

## Checklist Primer Deploy

1. Crear DB Neon Free.
2. Crear servicio Render desde repo usando `render.yaml`.
3. Configurar secrets de Render.
4. Ejecutar migraciones y seeds contra Neon.
5. Verificar `GET /health` y `GET /ready` en Render.
6. Crear proyecto Vercel con root `frontend`.
7. Configurar `EXPO_PUBLIC_API_URL` en Vercel.
8. Actualizar `APP_CORS_ORIGINS` en Render con el dominio real de Vercel.
9. Redeploy Render si cambiaste CORS.
10. Probar registro, login, rutinas, sesiones, estadisticas e IA interna desde la URL de Vercel.

## Rollback

- Frontend: usar rollback de deployment en Vercel.
- Backend: redeploy de commit anterior en Render.
- DB: no hacer downgrade automatico de Alembic en produccion sin revisar datos. Para cambios destructivos, crear backup antes.

## Backups

En free tier, revisar limites de Neon. Antes de cambios importantes:

- Exportar backup desde Neon si el plan lo permite.
- O usar `pg_dump` desde local con credenciales de Neon.

## Limitaciones Free Tier

- Render Free puede dormir y tener cold starts.
- Neon Free tiene limites de almacenamiento/compute.
- Vercel Free es adecuado para web/PWA inicial.
- Ollama no se despliega gratis de forma estable; mantener `APP_AI_PROVIDER=internal`.
- Publicar apps nativas en tiendas no entra en presupuesto 0.

## Antes De Producto

- Decidir politicas legales: privacidad, terminos, eliminacion/exportacion de cuenta y disclaimer medico.
- Sustituir rate limit en memoria por Redis/edge si hay multiinstancia o abuso.
- Si se publica web como producto, revisar estrategia de tokens; `localStorage` es solo fallback de desarrollo.
- Anadir observabilidad basica: logs, alertas y tracking de errores.
