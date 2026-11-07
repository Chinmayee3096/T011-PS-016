from decimal import Decimal
from src.models import DebitAdvice, Customer, RemittanceRequest

def print_debit_advice(advice: DebitAdvice, req: RemittanceRequest, customer: Customer):
    print("=" * 70)
    print("                     OUTWARD FOREX DEBIT ADVICE                       ")
    print("=" * 70)
    print(f"Transaction ID    : {advice.txn_id}")
    print(f"Customer ID       : {advice.cust_id} ({customer.name})")
    print(f"PAN               : {customer.pan}")
    print(f"Timestamp         : {req.timestamp.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Status            : {advice.status} [Rules: {', '.join(advice.rule_ids)}]")
    
    if advice.status == "REJECTED":
        print(f"Reason            : {advice.reject_reason}")
        print(f"Total Debit Amount: INR 0.00")
        print("=" * 70)
        print()
        return

    if advice.status == "HOLD":
        print(f"Notice            : {advice.reject_reason}")
        print("Value Date        : PENDING COMPLIANCE CLEARANCE")
        print("=" * 70)
        print()
        return

    print("\nTRANSACTION DETAILS:")
    print("-" * 70)
    print(f"Currency / Amount : {req.currency} {req.fx_amount:,.2f}")
    print(f"Purpose Code      : {req.purpose_code}")
    print(f"Beneficiary Ctry  : {req.beneficiary_country}")
    print(f"Interbank Rate    : {advice.interbank_rate:,.4f} INR")
    print(f"Customer Rate     : {advice.customer_rate:,.4f} INR")
    print(f"Value Date        : {advice.value_date}")

    print("\nDEBIT BREAKDOWN (INR):")
    print("-" * 70)
    print(f"Gross Remittance  : INR {advice.gross_inr:>12,.2f}")
    print(f"Flat Bank Charges : INR {advice.flat_charge:>12,.2f}")
    print(f"GST on Bank Fee   : INR {advice.gst_flat_charge:>12,.2f}")
    print(f"Conversion GST    : INR {advice.gst_conversion:>12,.2f}")
    print(f"TCS Collected     : INR {advice.tcs_amount:>12,.2f}")
    print("-" * 70)
    print(f"TOTAL DEBIT AMOUNT: INR {advice.total_debit_inr:>12,.2f}")
    print("=" * 70)
    print()

def print_fy_summary(customers: dict[str, Customer]):
    print("=" * 70)
    print("               ANNUAL LRS & TCS SUMMARY (FY 2026-27)                  ")
    print("=" * 70)
    lrs_cap = Decimal('250000.00')
    for cid, cust in customers.items():
        remaining_lrs = max(Decimal('0.00'), lrs_cap - cust.fy_lrs_usd)
        print(f"Customer ID        : {cust.cust_id}")
        print(f"Customer Name      : {cust.name}")
        print(f"PAN                : {cust.pan}")
        print(f"Residency          : {cust.residency}")
        print(f"LRS Limit Permitted: USD {lrs_cap:>12,.2f}")
        print(f"LRS Total Utilised : USD {cust.fy_lrs_usd:>12,.2f}")
        print(f"LRS Remaining Quota: USD {remaining_lrs:>12,.2f}")
        print(f"FY Cumulative INR  : INR {cust.fy_tcs_inr:>12,.2f}")
        print("-" * 70)
    print("=" * 70)