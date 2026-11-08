"""Envio de emails transaccionales sin dependencias externas.

Proveedores (APP_EMAIL_PROVIDER):
- console: escribe el email en el log (local y tests). Nunca usar en produccion real.
- smtp: cualquier servidor SMTP (Gmail con contrasena de aplicacion, Brevo...). Opcion de 0 EUR.
- resend: API HTTP de Resend. Necesita un dominio verificado para enviar a cualquier destinatario.
"""

import json
import logging
import smtplib
import ssl
from dataclasses import dataclass
from email.message import EmailMessage
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from app.core.config import Settings, get_settings

logger = logging.getLogger("zenith.email")


class EmailDeliveryError(Exception):
    pass


@dataclass(frozen=True)
class OutgoingEmail:
    to: str
    subject: str
    text: str


def _send_console(email: OutgoingEmail) -> None:
    logger.warning("EMAIL (console provider) to=%s subject=%s\n%s", email.to, email.subject, email.text)


def _send_smtp(email: OutgoingEmail, settings: Settings) -> None:
    message = EmailMessage()
    message["From"] = settings.email_from
    message["To"] = email.to
    message["Subject"] = email.subject
    message.set_content(email.text)
    try:
        if settings.smtp_port == 465:
            with smtplib.SMTP_SSL(
                settings.smtp_host, settings.smtp_port, timeout=15, context=ssl.create_default_context()
            ) as server:
                if settings.smtp_username:
                    server.login(settings.smtp_username, settings.smtp_password or "")
                server.send_message(message)
            return
        with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=15) as server:
            server.starttls(context=ssl.create_default_context())
            if settings.smtp_username:
                server.login(settings.smtp_username, settings.smtp_password or "")
            server.send_message(message)
    except (OSError, smtplib.SMTPException) as error:
        raise EmailDeliveryError("SMTP delivery failed.") from error


def _send_resend(email: OutgoingEmail, settings: Settings) -> None:
    payload = {"from": settings.email_from, "to": [email.to], "subject": email.subject, "text": email.text}
    request = Request(
        "https://api.resend.com/emails",
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {settings.resend_api_key}",
            "Content-Type": "application/json",
            "User-Agent": "ZenithApi/1.0",
        },
        method="POST",
    )
    try:
        with urlopen(request, timeout=15) as response:
            response.read()
    except (HTTPError, URLError, OSError) as error:
        raise EmailDeliveryError("Resend delivery failed.") from error


def send_email(email: OutgoingEmail, settings: Settings | None = None) -> None:
    settings = settings or get_settings()
    if settings.email_provider == "smtp":
        _send_smtp(email, settings)
    elif settings.email_provider == "resend":
        _send_resend(email, settings)
    else:
        _send_console(email)


def send_email_safely(email: OutgoingEmail) -> None:
    """Para tareas en segundo plano: un fallo de envio se registra, no rompe la peticion."""
    try:
        send_email(email)
    except EmailDeliveryError:
        logger.exception("Email delivery failed for subject=%s", email.subject)


def verification_email(to: str, link: str) -> OutgoingEmail:
    return OutgoingEmail(
        to=to,
        subject="Confirma tu email en Zenith",
        text=(
            "Hola,\n\nConfirma tu email para proteger tu cuenta de Zenith:\n"
            f"{link}\n\nEl enlace caduca en 48 horas. Si no creaste una cuenta, ignora este mensaje."
        ),
    )


def password_reset_email(to: str, link: str) -> OutgoingEmail:
    return OutgoingEmail(
        to=to,
        subject="Restablece tu contraseña de Zenith",
        text=(
            "Hola,\n\nHemos recibido una solicitud para restablecer tu contraseña:\n"
            f"{link}\n\nEl enlace caduca en 1 hora y solo sirve una vez. "
            "Si no lo has pedido tú, ignora este mensaje: tu contraseña no cambiará."
        ),
    )
