from datetime import datetime, date, time
from decimal import Decimal, ROUND_HALF_UP
from src.models import Customer, RemittanceRequest, DebitAdvice
from src.rules.validation import validate_remittance
from src.rules.rates import get_spread, compute_customer_rate, check_rate_recheck
from src.rules.charges import calculate_all_charges
from src.rules.value_date import compute_value_date
from src.output import print_debit_advice, print_fy_summary

PAISA = Decimal('0.01')
CUTOFF_TIME = time(14, 30, 0)

class RemittanceEngine:
    def __init__(self, customers: dict[str, Customer], rates: dict[tuple[date, str], Decimal], holidays: dict[str, set[date]]):
        self.customers = customers
        self.rates = rates
        self.holidays = holidays
        self.txn_counter = 1
        # In-memory store of active transactions: txn_id -> dict
        self.transactions = {}

    def process_command_file(self, command_filepath: str):
        with open(command_filepath, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith('#'):
                    continue
                parts = line.split()
                cmd = parts[0].upper()

                if cmd == 'REMIT':
                    self.handle_remit(parts[1:])
                elif cmd == 'APPROVE':
                    self.handle_approve(parts[1:])
                elif cmd == 'CANCEL':
                    self.handle_cancel(parts[1:])
                elif cmd == 'RATE_RECHECK':
                    self.handle_rate_recheck(parts[1:])
                else:
                    print(f"Unknown command: {cmd}")

        print_fy_summary(self.customers)

    def handle_remit(self, args: list[str]):
        # Format: cust_id currency fx_amount purpose_code beneficiary_country timestamp
        cust_id, currency, fx_amount_str, purpose_code, beneficiary_country, ts_str = args
        fx_amount = Decimal(fx_amount_str)
        req_dt = datetime.fromisoformat(ts_str)
        req_date = req_dt.date()
        
        txn_id = f"TXN-{req_date.strftime('%Y%m%d')}-{self.txn_counter:03d}"
        self.txn_counter += 1

        req = RemittanceRequest(
            txn_id=txn_id,
            cust_id=cust_id,
            currency=currency,
            fx_amount=fx_amount,
            purpose_code=purpose_code,
            beneficiary_country=beneficiary_country,
            timestamp=req_dt
        )

        customer = self.customers.get(cust_id)
        if not customer:
            print(f"Error: Customer {cust_id} not found.")
            return

        rate_key = (req_date, currency)
        interbank_rate = self.rates.get(rate_key)
        if not interbank_rate:
            print(f"Error: Missing exchange rate for {currency} on {req_date}.")
            return

        if currency == 'USD':
            usd_equivalent = fx_amount
        else:
            usd_rate = self.rates.get((req_date, 'USD'), Decimal('83.50'))
            usd_equivalent = (fx_amount * interbank_rate) / usd_rate

        status, applied_rules, reason = validate_remittance(customer, req, usd_equivalent)

        if status == 'REJECTED':
            advice = DebitAdvice(
                txn_id=txn_id,
                cust_id=cust_id,
                status=status,
                rule_ids=applied_rules,
                reject_reason=reason
            )
            print_debit_advice(advice, req, customer)
            return

        # Pre-calculate pricing
        applied_rules.append("BR-03")
        spread = get_spread(currency, usd_equivalent)
        cust_rate = compute_customer_rate(interbank_rate, spread)
        gross_inr = (fx_amount * cust_rate).quantize(PAISA, rounding=ROUND_HALF_UP)

        applied_rules.extend(["BR-04", "BR-05"])
        charges = calculate_all_charges(
            gross_inr=gross_inr,
            prior_fy_inr=customer.fy_tcs_inr,
            purpose_code=purpose_code,
            edu_loan=customer.edu_loan_flag
        )

        ind_hols = self.holidays.get('IND', set())
        dest_hols = self.holidays.get(beneficiary_country, set())
        val_date, vd_rules = compute_value_date(req_dt, currency, usd_equivalent, ind_hols, dest_hols)
        applied_rules.extend(vd_rules)

        # Store booking record
        txn_record = {
            "req": req,
            "customer": customer,
            "status": status,
            "interbank_rate": interbank_rate,
            "customer_rate": cust_rate,
            "gross_inr": gross_inr,
            "charges": charges,
            "value_date": val_date,
            "usd_equivalent": usd_equivalent,
            "applied_rules": applied_rules
        }
        self.transactions[txn_id] = txn_record

        if status == 'HOLD':
            advice = DebitAdvice(
                txn_id=txn_id,
                cust_id=cust_id,
                status="HOLD",
                rule_ids=applied_rules,
                reject_reason=reason
            )
            print_debit_advice(advice, req, customer)
            return

        # If ACCEPTED, commit balances
        customer.fy_lrs_usd += usd_equivalent
        customer.fy_tcs_inr = charges["updated_fy_inr"]

        advice = DebitAdvice(
            txn_id=txn_id,
            cust_id=cust_id,
            status="ACCEPTED",
            rule_ids=applied_rules,
            interbank_rate=interbank_rate,
            customer_rate=cust_rate,
            gross_inr=gross_inr,
            flat_charge=charges["flat_charge"],
            gst_flat_charge=charges["gst_flat_charge"],
            gst_conversion=charges["gst_conversion"],
            tcs_amount=charges["tcs_amount"],
            total_debit_inr=charges["total_debit_inr"],
            value_date=val_date
        )
        print_debit_advice(advice, req, customer)

    def handle_approve(self, args: list[str]):
        """BR-08: Approve a transaction currently on HOLD"""
        txn_id = args[0]
        txn = self.transactions.get(txn_id)
        if not txn or txn["status"] != "HOLD":
            print(f"APPROVE ERROR: Transaction {txn_id} not found on HOLD.")
            return

        customer = txn["customer"]
        txn["status"] = "ACCEPTED"
        customer.fy_lrs_usd += txn["usd_equivalent"]
        customer.fy_tcs_inr = txn["charges"]["updated_fy_inr"]

        print("=" * 70)
        print(f"TRANSACTION {txn_id} APPROVED BY COMPLIANCE (BR-08)")
        print(f"Customer {customer.cust_id} balances updated.")
        print("=" * 70 + "\n")

    def handle_cancel(self, args: list[str]):
        """
        BR-09: Cancellation
        - Free before 14:30 on request day
        - 1% INR penalty after 14:30
        - Not allowed after value date
        """
        txn_id, cancel_ts_str = args[0], args[1]
        cancel_dt = datetime.fromisoformat(cancel_ts_str)
        txn = self.transactions.get(txn_id)

        if not txn:
            print(f"CANCEL ERROR: Transaction {txn_id} not found.")
            return

        if cancel_dt.date() > txn["value_date"]:
            print(f"CANCEL REJECTED (BR-09): {txn_id} cannot be cancelled after value date {txn['value_date']}.")
            return

        req = txn["req"]
        is_same_day = cancel_dt.date() == req.timestamp.date()
        penalty = Decimal('0.00')

        if is_same_day and cancel_dt.time() < CUTOFF_TIME:
            msg = "Cancelled free of charge (BR-09: Before 14:30 on booking day)"
        else:
            penalty = (txn["gross_inr"] * Decimal('0.01')).quantize(PAISA, rounding=ROUND_HALF_UP)
            msg = f"Cancelled with 1% penalty: INR {penalty:,.2f} (BR-09)"

        txn["status"] = "CANCELLED"
        # Roll back customer LRS usage
        txn["customer"].fy_lrs_usd -= txn["usd_equivalent"]

        print("=" * 70)
        print(f"CANCELLATION PROCESSED: {txn_id}")
        print(f"Status: {msg}")
        print("=" * 70 + "\n")

    def handle_rate_recheck(self, args: list[str]):
        """
        BR-10: RATE_RECHECK
        If interbank rate moves > 1% against bank before value date, re-price and debit difference.
        """
        txn_id, check_date_str = args[0], args[1]
        check_date = datetime.strptime(check_date_str, '%Y-%m-%d').date()
        txn = self.transactions.get(txn_id)

        if not txn or txn["status"] != "ACCEPTED":
            print(f"RATE_RECHECK ERROR: {txn_id} is not an active accepted transaction.")
            return

        currency = txn["req"].currency
        current_rate = self.rates.get((check_date, currency))
        if not current_rate:
            print(f"RATE_RECHECK: Missing rate for {currency} on {check_date}")
            return

        booking_rate = txn["interbank_rate"]
        triggered, diff = check_rate_recheck(booking_rate, current_rate)

        print("=" * 70)
        print(f"RATE RECHECK (BR-10) FOR {txn_id}")
        print(f"Original Rate: {booking_rate:,.4f} | Current Rate: {current_rate:,.4f}")
        if triggered:
            spread = get_spread(currency, txn["usd_equivalent"])
            new_cust_rate = compute_customer_rate(current_rate, spread)
            new_gross = (txn["req"].fx_amount * new_cust_rate).quantize(PAISA, rounding=ROUND_HALF_UP)
            diff_debit = new_gross - txn["gross_inr"]
            print(f"Movement > 1% against bank! Additional Debit: INR {diff_debit:,.2f}")
        else:
            print("Movement within 1% threshold. No price adjustment required.")
        print("=" * 70 + "\n")