"""CronJob: send the queued feedback acknowledgements. Keeps SMTP (and its timeouts) out of the request."""
import asyncio

from app.core.config_core import get_settings
from app.core.db_core import SessionLocal, engine
from app.services.email_services import smtp_transport
from app.services.feedback_services import drain


async def main() -> None:
    st = get_settings()
    send = smtp_transport(st.SMTP_HOST, st.SMTP_PORT, st.SMTP_USER, st.SMTP_PASSWORD, st.EMAIL_REPLY_TO)
    total = 0
    async with SessionLocal() as s:
        while (n := await drain(s, send)):                 # 20 at a time until the queue is empty
            total += n
    await engine.dispose()
    print(f"feedback acknowledgements sent: {total}")


if __name__ == "__main__":
    asyncio.run(main())
