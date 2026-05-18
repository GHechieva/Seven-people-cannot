import asyncio
import aiohttp
import logging
from datetime import datetime, timedelta
import config

logger = logging.getLogger(__name__)

# Simple in-memory cache: {base_currency: (rates_dict, fetched_at)}
_rate_cache: dict[str, tuple[dict[str, float], datetime]] = {}
_CACHE_TTL = timedelta(hours=6)


async def get_exchange_rates(base: str = "EUR") -> dict[str, float]:
    cached = _rate_cache.get(base)
    if cached and datetime.utcnow() - cached[1] < _CACHE_TTL:
        return cached[0]

    rates = await _fetch_rates(base)
    if rates:
        _rate_cache[base] = (rates, datetime.utcnow())
    return rates


async def _fetch_rates(base: str) -> dict[str, float]:
    # Try paid API first if key exists
    if config.EXCHANGE_RATE_API_KEY:
        url = f"{config.EXCHANGE_RATE_BASE_URL}/{config.EXCHANGE_RATE_API_KEY}/latest/{base}"
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        if data.get("result") == "success":
                            return data["conversion_rates"]
        except Exception as e:
            logger.warning(f"Paid exchange rate API failed: {e}")

    # Fallback to free API
    url = f"{config.OPEN_EXCHANGE_URL}/{base}"
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    return data.get("rates", {})
    except Exception as e:
        logger.warning(f"Free exchange rate API failed: {e}")

    # Last resort: return 1:1
    logger.error("All exchange rate APIs failed, returning identity rates")
    return {c: 1.0 for c in config.SUPPORTED_CURRENCIES}


async def convert_amount(amount: float, from_currency: str, to_currency: str) -> float:
    if from_currency == to_currency:
        return amount
    rates = await get_exchange_rates(from_currency)
    rate = rates.get(to_currency)
    if rate is None:
        logger.warning(f"No rate found for {from_currency}->{to_currency}, using 1.0")
        return amount
    return round(amount * rate, 4)
