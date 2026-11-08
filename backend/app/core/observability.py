"""Informes de errores con Sentry (plan gratuito). Desactivado si no hay APP_SENTRY_DSN."""

from typing import Any

from app.core.config import Settings

SENSITIVE_KEYS = {"authorization", "cookie", "set-cookie", "password", "new_password", "token", "refresh_token"}


def _scrub(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            key: ("[Filtered]" if str(key).lower() in SENSITIVE_KEYS else _scrub(item)) for key, item in value.items()
        }
    if isinstance(value, list):
        return [_scrub(item) for item in value]
    return value


def before_send(event: dict[str, Any], _hint: dict[str, Any]) -> dict[str, Any]:
    """No enviar nunca cuerpos de peticion (datos de entrenamiento/salud), cookies ni credenciales."""
    request = event.get("request")
    if isinstance(request, dict):
        request.pop("data", None)
        request.pop("cookies", None)
        request.pop("query_string", None)
        if "headers" in request:
            request["headers"] = _scrub(request["headers"])
    if "user" in event and isinstance(event["user"], dict):
        # Solo el id interno; nunca email ni IP.
        event["user"] = {key: value for key, value in event["user"].items() if key == "id"}
    for key in ("extra", "contexts"):
        if key in event:
            event[key] = _scrub(event[key])
    return event


def init_sentry(settings: Settings) -> bool:
    if not settings.sentry_dsn:
        return False
    import sentry_sdk

    sentry_sdk.init(
        dsn=settings.sentry_dsn,
        environment=settings.environment,
        send_default_pii=False,
        traces_sample_rate=settings.sentry_traces_sample_rate,
        before_send=before_send,
        max_request_body_size="never",
    )
    return True
