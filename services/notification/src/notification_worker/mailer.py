import logging
from email.message import EmailMessage

import aiosmtplib

log = logging.getLogger(__name__)


class Mailer:
    """Sends email over SMTP. Without an SMTP host it only logs (dry-run)."""

    def __init__(self, host: str | None, port: int, sender: str, timeout: float) -> None:
        self._host = host
        self._port = port
        self._sender = sender
        self._timeout = timeout

    async def send(self, to: str, subject: str, body: str) -> None:
        message = EmailMessage()
        message["From"] = self._sender
        message["To"] = to
        message["Subject"] = subject
        message.set_content(body)

        if not self._host:
            log.info("dry-run email", extra={"to": to, "subject": subject})
            return
        await aiosmtplib.send(message, hostname=self._host, port=self._port, timeout=self._timeout)
