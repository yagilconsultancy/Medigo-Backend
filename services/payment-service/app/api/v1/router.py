from fastapi import APIRouter

from app.api.v1.earnings_endpoints import router as earnings_router
from app.api.v1.payment_method_endpoints import router as pm_router
from app.api.v1.receipt_endpoints import router as receipt_router
from app.api.v1.withdrawal_endpoints import router as withdrawal_router

router = APIRouter()

router.include_router(earnings_router, prefix="/earnings", tags=["Earnings"])
router.include_router(withdrawal_router, prefix="/withdrawals", tags=["Withdrawals"])
router.include_router(pm_router, prefix="/payment-methods", tags=["Payment Methods"])
router.include_router(receipt_router, prefix="/receipts", tags=["Receipts"])
