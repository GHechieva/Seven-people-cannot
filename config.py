import os
from dotenv import load_dotenv

load_dotenv()

# Telegram
BOT_TOKEN: str = os.environ["BOT_TOKEN"]

# Database
DATABASE_URL: str = os.getenv("DATABASE_URL", "sqlite+aiosqlite:///./data/tripbot.db")

# OCR
OCR_SPACE_API_KEY: str | None = os.getenv("OCR_SPACE_API_KEY")

# Exchange rates
EXCHANGE_RATE_API_KEY: str | None = os.getenv("EXCHANGE_RATE_API_KEY")
EXCHANGE_RATE_BASE_URL: str = "https://v6.exchangerate-api.com/v6"

# Fallback free API (no key required)
OPEN_EXCHANGE_URL: str = "https://open.exchangerate-api.com/v6/latest"

# Debug
DEBUG: bool = os.getenv("DEBUG", "false").lower() == "true"

# Supported currencies
SUPPORTED_CURRENCIES: list[str] = [
    "EUR", "USD", "GBP", "JPY", "CHF", "AUD", "CAD",
    "SEK", "NOK", "DKK", "PLN", "CZK", "HUF", "RON",
    "BGN", "HRK", "TRY", "RUB", "CNY", "INR", "THB",
]
