"""Start the bot: python -m harness.main"""
import logging
import sys

from .config import ROOT, Settings
from .telegram_io import build_app


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s",
                        handlers=[logging.StreamHandler(), logging.FileHandler(ROOT / "bot.log")])
    logging.getLogger("httpx").setLevel(logging.WARNING)
    settings = Settings.from_env()
    if not settings.telegram_token:
        sys.exit("TELEGRAM_BOT_TOKEN is missing. Copy .env.example to .env and fill it in (see README).")
    build_app(settings).run_polling(allowed_updates=["message", "callback_query"])


if __name__ == "__main__":
    main()
