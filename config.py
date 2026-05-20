import os
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN: str = os.environ["BOT_TOKEN"]
DATABASE_URL: str = os.getenv("DATABASE_URL", "sqlite+aiosqlite:///./data/tripbot.db")
OCR_SPACE_API_KEY: str | None = os.getenv("OCR_SPACE_API_KEY")
EXCHANGE_RATE_API_KEY: str | None = os.getenv("EXCHANGE_RATE_API_KEY")
EXCHANGE_RATE_BASE_URL: str = "https://v6.exchangerate-api.com/v6"
OPEN_EXCHANGE_URL: str = "https://open.exchangerate-api.com/v6/latest"
DEBUG: bool = os.getenv("DEBUG", "false").lower() == "true"

SUPPORTED_CURRENCIES: list[str] = ["RUB", "USD", "CNY", "VND"]
CURRENCY_NAMES: dict[str, str] = {
    "RUB": "🇷🇺 Рубль",
    "USD": "🇺🇸 Доллар",
    "CNY": "🇨🇳 Юань",
    "VND": "🇻🇳 Донг",
}
