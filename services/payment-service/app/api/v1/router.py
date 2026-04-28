from fastapi import APIRouter

from app.api.v1.admin_dispute_endpoints import router as admin_dispute_router  # Temporarily disabled
from app.api.v1.admin_payout_endpoints import router as admin_payout_router
from app.api.v1.admin_refund_endpoints import router as admin_refund_router
from app.api.v1.admin_revenue_endpoints import router as admin_revenue_router
from app.api.v1.admin_transaction_endpoints import router as admin_tx_router
from app.api.v1.cancellation_policy_endpoints import router as cancellation_router
from app.api.v1.commission_endpoints import router as commission_router
from app.api.v1.earnings_endpoints import router as earnings_router
from app.api.v1.fare_config_endpoints import router as fare_config_router
from app.api.v1.fare_estimate_endpoints import router as fare_estimate_router
from app.api.v1.mobile_payment_endpoints import router as mobile_payment_router
from app.api.v1.payment_method_endpoints import router as pm_router
from app.api.v1.pricing_config_endpoints import router as pricing_config_router
from app.api.v1.pricing_dashboard_endpoints import router as pricing_dashboard_router
from app.api.v1.pricing_log_endpoints import router as pricing_log_router
from app.api.v1.rate_card_endpoints import router as rate_card_router
from app.api.v1.receipt_endpoints import router as receipt_router
from app.api.v1.ride_package_endpoints import router as ride_package_router
from app.api.v1.ride_type_endpoints import router as ride_type_router
from app.api.v1.surcharge_rule_endpoints import router as surcharge_router
from app.api.v1.webhook_endpoints import router as webhook_router
from app.api.v1.withdrawal_endpoints import router as withdrawal_router

router = APIRouter()

router.include_router(fare_estimate_router, tags=["Fare Estimate"])
router.include_router(earnings_router, prefix="/earnings", tags=["Earnings"])
router.include_router(withdrawal_router, prefix="/withdrawals", tags=["Withdrawals"])
router.include_router(pm_router, prefix="/payment-methods", tags=["Payment Methods"])
router.include_router(mobile_payment_router, prefix="/mobile", tags=["Mobile Payments"])
router.include_router(rate_card_router, prefix="/rate-cards", tags=["Rate Cards"])
router.include_router(receipt_router, prefix="/receipts", tags=["Receipts"])
router.include_router(webhook_router, prefix="/webhooks", tags=["Webhooks"])

# Admin dashboard endpoints
router.include_router(admin_tx_router, prefix="/admin", tags=["Admin Transactions"])
router.include_router(admin_revenue_router, prefix="/admin", tags=["Admin Revenue"])
router.include_router(admin_payout_router, prefix="/admin", tags=["Admin Payouts"])
router.include_router(admin_refund_router, prefix="/admin", tags=["Admin Refunds"])
router.include_router(admin_dispute_router, prefix="/admin", tags=["Admin Disputes"])  # Temporarily disabled
router.include_router(ride_type_router, tags=["Ride Types"])

# Pricing management endpoints
router.include_router(pricing_dashboard_router, prefix="/pricing", tags=["Pricing Dashboard"])
router.include_router(fare_config_router, prefix="/pricing", tags=["Fare Configuration"])
router.include_router(surcharge_router, prefix="/pricing", tags=["Surcharges"])
router.include_router(ride_package_router, prefix="/pricing", tags=["Ride Packages"])
router.include_router(pricing_config_router, prefix="/pricing", tags=["Pricing Configuration"])
router.include_router(pricing_log_router, prefix="/pricing", tags=["Pricing Logs"])
router.include_router(commission_router, prefix="/pricing", tags=["Commission Settings"])
router.include_router(cancellation_router, prefix="/pricing", tags=["Cancellation Policy"])
