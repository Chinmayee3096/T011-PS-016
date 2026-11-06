from decimal import Decimal
from src.models import Customer, RemittanceRequest

LRS_ANNUAL_CAP = Decimal('250000.00')
HOLD_SINGLE_LIMIT = Decimal('50000.00')
HOLD_AGGREGATE_LIMIT = Decimal('150000.00')

def validate_remittance(customer: Customer, req: RemittanceRequest, usd_equivalent: Decimal) -> tuple[str, list[str], str]:
    """
    Validates a remittance request against business rules in order of precedence:
    Residency -> Purpose & KYC -> LRS Cap -> Compliance HOLD.
    Returns: (decision_status, applied_rules, reason_if_any)
    """
    rules_applied = []

    # 1. Check Residency (BR-01)
    rules_applied.append("BR-01")
    if customer.residency != 'RESIDENT':
        return "REJECTED", rules_applied, "Non-residents cannot remit under LRS"

    # 2. Check Purpose Code & KYC (BR-02)
    rules_applied.append("BR-02")
    allowed_purposes = {'S0305', 'S1301', 'S0023', 'S0001', 'S1302'}
    if req.purpose_code not in allowed_purposes:
        return "REJECTED", rules_applied, f"Invalid purpose code: {req.purpose_code}"

    if req.purpose_code == 'S0001':  # Investment
        if customer.kyc_level != 'FULL':
            return "REJECTED", rules_applied, "Investment (S0001) requires FULL KYC"
        if usd_equivalent < Decimal('1000.00'):
            return "REJECTED", rules_applied, "Investment (S0001) requires minimum USD 1,000"

    # 3. Check LRS Cap: USD 250,000 across all purposes (BR-01)
    if (customer.fy_lrs_usd + usd_equivalent) > LRS_ANNUAL_CAP:
        return "REJECTED", rules_applied, "Exceeds annual LRS limit of USD 250,000"

    # 4. Check Compliance HOLD (BR-08)
    rules_applied.append("BR-08")
    if usd_equivalent > HOLD_SINGLE_LIMIT or (customer.fy_lrs_usd + usd_equivalent) > HOLD_AGGREGATE_LIMIT:
        return "HOLD", rules_applied, "Transfer placed on HOLD for compliance review"

    return "ACCEPTED", rules_applied, ""