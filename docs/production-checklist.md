# Checklist de producción (presupuesto 0 €)

Fase 1 de bloqueantes. La parte de código está hecha; lo que sigue son pasos de configuración en paneles
de servicios gratuitos que solo puede hacer la persona responsable del despliegue.

## 1. Emails (recuperar contraseña y verificar cuenta)

Sin dominio propio (cuesta dinero), la opción de 0 € es SMTP:

- **Gmail**: activar verificación en dos pasos y crear una "contraseña de aplicación".
  Límite aproximado de 500 correos/día.
  - `APP_EMAIL_PROVIDER=smtp`
  - `APP_SMTP_HOST=smtp.gmail.com`, `APP_SMTP_PORT=587`
  - `APP_SMTP_USERNAME=<cuenta>@gmail.com`, `APP_SMTP_PASSWORD=<contraseña de aplicación>` (secreto)
  - `APP_EMAIL_FROM=Zenith <cuenta@gmail.com>`
- **Brevo** (plan gratuito, ~300 correos/día): mismo esquema con `smtp-relay.brevo.com` y sus credenciales SMTP.
- **Resend** (`APP_EMAIL_PROVIDER=resend`, `APP_RESEND_API_KEY`): solo cuando haya un dominio verificado;
  sin dominio solo envía a la dirección de la propia cuenta.
- `APP_FRONTEND_BASE_URL=https://zenith.vercel.app` (los enlaces de los emails apuntan aquí).
- En local, `APP_EMAIL_PROVIDER=console` escribe los emails en el log de la API.

## 2. Web: cookie httpOnly a través del proxy de Vercel

- `frontend/vercel.json` reenvía `/api/*` a `https://zenith-api-9gf7.onrender.com/*` y compila la web con
  `EXPO_PUBLIC_API_URL=/api`. La API queda en el mismo origen que la web, así que la cookie del refresh
  token es de primera parte (funciona también en Safari, que bloquea cookies de terceros).
- Si cambia la URL de Render, actualizar `frontend/vercel.json`.
- La app móvil sigue llamando a Render directamente (`eas.json`) y guarda el refresh token en SecureStore.
- Variables de la API: `APP_REFRESH_COOKIE_SECURE=true` (por defecto) y `APP_REFRESH_COOKIE_SAMESITE=strict`.
- Límites por IP: con el proxy, la IP real llega en `x-vercel-forwarded-for`. Esa cabecera se puede
  falsear llamando a Render directamente, por eso el login tiene además un límite por email
  (`APP_AUTH_LOGIN_EMAIL_RATE_LIMIT_ATTEMPTS`, 20 cada 15 min).

## 3. Render Free sin "arranque en frío"

Render Free apaga el servicio tras 15 min sin tráfico y el primer usuario espera 30-60 s.

- Crear un monitor gratuito en **UptimeRobot** (o similar) que llame a
  `https://zenith-api-9gf7.onrender.com/health` cada 5 minutos.
- Además sirve de aviso por email si la API se cae.
- Un servicio despierto 24/7 consume ~744 h/mes: cabe en las 750 h gratuitas de Render si es el único.

## 4. Errores en producción (Sentry, plan gratuito)

- Crear cuenta y dos proyectos (Python/FastAPI y React Native).
- API: `APP_SENTRY_DSN=<dsn>` en Render.
- App: `EXPO_PUBLIC_SENTRY_DSN=<dsn>` en Vercel y en `eas.json` (el DSN no es secreto).
- Antes de enviar se eliminan cuerpos de petición, cookies, cabeceras de autenticación, emails e IPs:
  nunca salen datos de entrenamiento ni de salud.
- `SENTRY_DISABLE_AUTO_UPLOAD=true` en EAS evita que la compilación falle sin token de Sentry.

## 5. Backups de la base de datos (Neon Free)

- Neon Free permite restaurar a un punto reciente (ventana corta de historial). Comprobar en el panel la
  ventana disponible y hacer una restauración de prueba en una rama de Neon.
- Antes de cada migración importante: `pg_dump "$APP_DATABASE_URL" > backup.sql` desde local.
  No subir nunca los dumps al repositorio (contienen datos personales).

## 6. Legal (RGPD) con recursos gratuitos

Zenith trata datos de salud (peso, lesiones, limitaciones), que el RGPD considera categoría especial.

- Edad mínima de 18 años: el registro exige confirmarla y el Coach no guarda edades menores.
- Los consentimientos (términos y mayoría de edad) se guardan con fecha en la tabla `users`.
- Herramienta gratuita de la AEPD **Facilita RGPD** para generar el registro de actividades y textos base.
- Revisar los términos de Groq como encargado del tratamiento (transferencia a EE. UU.) y reflejarlo en la
  política de privacidad.
- Hacer una evaluación de impacto (EIPD) sencilla con las guías gratuitas de la AEPD.
- Riesgo pendiente: sin revisión profesional, los textos legales son orientativos.

## 7. Comprobación tras desplegar

1. Registrar una cuenta con un email real y abrir el enlace de verificación.
2. Pedir "¿Has olvidado tu contraseña?", cambiarla y comprobar que la sesión anterior se cierra.
3. En la web, recargar la página: la sesión debe mantenerse (cookie) y en DevTools no debe aparecer
   ningún token en `localStorage`.
4. Terminar una sesión con el móvil en modo avión: debe quedar "guardada en el móvil" y enviarse sola al
   recuperar la conexión, sin duplicarse.
5. Provocar un error y verlo en Sentry sin datos personales.
