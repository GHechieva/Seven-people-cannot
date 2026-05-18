from aiogram import Router
from .start import router as start_router
from .trips import router as trips_router
from .expenses import router as expenses_router
from .balances import router as balances_router
from .receipts import router as receipts_router
from .settings import router as settings_router

main_router = Router()
main_router.include_router(start_router)
main_router.include_router(trips_router)
main_router.include_router(expenses_router)
main_router.include_router(balances_router)
main_router.include_router(receipts_router)
main_router.include_router(settings_router)
