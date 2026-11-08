# Producto Beta

## Estado Fase 21

Zenith queda preparado para beta gratuita con:

- Branding publico `Zenith` en app y configuracion Expo.
- Home de producto con propuesta clara y aviso medico.
- Pantallas estaticas de privacidad y terminos en frontend.
- Aceptacion explicita de privacidad, terminos y aviso medico antes de registrar cuenta.
- Aviso medico visible en entrenador IA y planes adaptativos.
- Deploy gratuito validado en Render Free, Neon Free y Vercel Free.

## Limitaciones Beta

- No es consejo medico, fisioterapeutico ni de entrenador cualificado.
- Las recomendaciones IA son revisables; solo aplican cambios al aceptar.
- Web usa `localStorage` como fallback para tokens; para producto web sensible conviene migrar a cookies `HttpOnly` o BFF.
- Exportacion de datos (JSON) y eliminacion permanente de cuenta disponibles en la pantalla Cuenta; la eliminacion pide la contrasena actual y borra todos los datos del usuario.
- El free tier puede tener cold starts, limites o interrupciones.

## Checklist Antes De Producto Publico

- Definir canal de soporte/contacto visible.
- Revisar textos legales con criterio juridico si se abre a usuarios reales.
- Decidir estrategia de tokens para web productiva.
- Anadir observabilidad basica de errores.
- Anadir tests de pantallas o E2E para flujos criticos.
- Rotar secretos si fueron expuestos durante pruebas.

## Smoke Test Beta

- Registro con aceptacion de terminos.
- Login/logout y refresh de sesion.
- Crear rutina.
- Registrar sesion.
- Ver estadisticas y rango.
- Generar sugerencias IA y aceptar/rechazar una no critica.
- Generar plan adaptativo y rechazarlo.
- Generar resumen post-sesion.
- Abrir privacidad y terminos desde home/login/registro.
