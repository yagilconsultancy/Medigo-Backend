from fastapi import APIRouter

from app.api.v1.admin_payout_endpoints import router as admin_payout_router
from app.api.v1.admin_refund_endpoints import router as admin_refund_router
from app.api.v1.admin_revenue_endpoints import router as admin_revenue_router
from app.api.v1.admin_transaction_endpoints import router as admin_tx_router
from app.api.v1.earnings_endpoints import router as earnings_router
from app.api.v1.payment_method_endpoints import router as pm_router
from app.api.v1.rate_card_endpoints import router as rate_card_router
from app.api.v1.receipt_endpoints import router as receipt_router
from app.api.v1.webhook_endpoints import router as webhook_router
from app.api.v1.withdrawal_endpoints import router as withdrawal_router

router = APIRouter()

router.include_router(earnings_router, prefix="/earnings", tags=["Earnings"])
router.include_router(withdrawal_router, prefix="/withdrawals", tags=["Withdrawals"])
router.include_router(pm_router, prefix="/payment-methods", tags=["Payment Methods"])
router.include_router(rate_card_router, prefix="/rate-cards", tags=["Rate Cards"])
router.include_router(receipt_router, prefix="/receipts", tags=["Receipts"])
router.include_router(webhook_router, prefix="/webhooks", tags=["Webhooks"])

# Admin dashboard endpoints
router.include_router(admin_tx_router, prefix="/admin", tags=["Admin Transactions"])
router.include_router(admin_revenue_router, prefix="/admin", tags=["Admin Revenue"])
router.include_router(admin_payout_router, prefix="/admin", tags=["Admin Payouts"])
router.include_router(admin_refund_router, prefix="/admin", tags=["Admin Refunds"])
