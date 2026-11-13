import asyncio
from datetime import UTC, datetime

from app.core.config_core import get_settings
from app.core.db_core import SessionLocal, engine
from app.services.digest_services import send_weekly
from app.services.email_services import EmailSender, smtp_transport


async def main() -> None:
    cfg = get_settings()
    transport = smtp_transport(
        cfg.SMTP_HOST, cfg.SMTP_PORT, cfg.SMTP_USER, cfg.SMTP_PASSWORD, cfg.EMAIL_REPLY_TO
    )
    async with SessionLocal() as s:
        sent = await send_weekly(
            s, EmailSender(s, cfg.EMAIL_FROM, transport), now=datetime.now(UTC), top_n=20
        )
    await engine.dispose()
    print(f"sent {sent} digests")


if __name__ == "__main__":
    asyncio.run(main())
