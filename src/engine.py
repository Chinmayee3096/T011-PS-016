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
        # In-memory store: request_id/txn_id -> dict
        self.transactions = {}
        # Stores debit advice objects: request_id/txn_id -> (DebitAdvice, RemittanceRequest, Customer)
        self.advices = {}

    def process_command_file(self, command_filepath: str):
        with open(command_filepath, 'r', encoding='utf-8') as f:
            for raw_line in f:
                line = raw_line.strip()
                if not line or line.startswith('#'):
                    continue
                
                # Split using pipe delimiter '|'
                parts = [p.strip() for p in line.split('|')]
                cmd = parts[0].upper()

                if cmd == 'REMIT':
                    self.handle_remit(parts[1:])
                elif cmd == 'APPROVE':
                    self.handle_approve(parts[1:])
                elif cmd == 'CANCEL':
                    self.handle_cancel(parts[1:])
                elif cmd == 'RATE_RECHECK':
                    self.handle_rate_recheck(parts[1:])
                elif cmd == 'PRINT_ADVICE':
                    self.handle_print_advice(parts[1:])
                elif cmd == 'PRINT_FY_STATEMENT':
                    self.handle_print_fy_statement(parts[1:])
                elif cmd in ('LOAD_CUSTOMERS', 'LOAD_RATES', 'LOAD_HOLIDAYS'):
                    # Data already loaded in main.py, skip safely
                    continue
                else:
                    print(f"Unknown command: {cmd}")

        print_fy_summary(self.customers)

    def handle_remit(self, args: list[str]):
        # Format:
        # req_id, cust_id, currency, amt_type, amount, purpose_code, beneficiary_country, prior_lrs, date_str
        if len(args) == 9:
            req_id, cust_id, currency, amt_type, amt_str, purpose_code, beneficiary_country, _, date_str = args
        elif len(args) == 6:
            cust_id, currency, amt_str, purpose_code, beneficiary_country, date_str = args
            req_id = f"RQ-{self.txn_counter:04d}"
            amt_type = "FX"
        else:
            print(f"REMIT: unexpected arguments count {len(args)}: {args}")
            return

        amount = Decimal(amt_str)
        try:
            req_dt = datetime.fromisoformat(date_str)
        except ValueError:
            req_dt = datetime.strptime(date_str, '%Y-%m-%d')
        req_date = req_dt.date()

        txn_id = req_id
        self.txn_counter += 1

        customer = self.customers.get(cust_id)
        if not customer:
            print(f"Error: Customer {cust_id} not found.")
            return

        rate_key = (req_date, currency)
        interbank_rate = self.rates.get(rate_key)
        if not interbank_rate:
            print(f"Error: Missing exchange rate for {currency} on {req_date}.")
            return

        usd_rate = self.rates.get((req_date, 'USD'), Decimal('83.50'))

        # Resolve FX vs INR amount
        if amt_type.upper() == 'INR':
            gross_inr = amount.quantize(PAISA, rounding=ROUND_HALF_UP)
            spread = get_spread(currency, Decimal('0.00'))
            cust_rate = compute_customer_rate(interbank_rate, spread)
            fx_amount = (gross_inr / cust_rate).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
        else:
            fx_amount = amount
            spread = get_spread(currency, fx_amount if currency == 'USD' else (fx_amount * interbank_rate) / usd_rate)
            cust_rate = compute_customer_rate(interbank_rate, spread)
            gross_inr = (fx_amount * cust_rate).quantize(PAISA, rounding=ROUND_HALF_UP)

        if currency == 'USD':
            usd_equivalent = fx_amount
        else:
            usd_equivalent = (fx_amount * interbank_rate) / usd_rate

        req = RemittanceRequest(
            txn_id=txn_id,
            cust_id=cust_id,
            currency=currency,
            fx_amount=fx_amount,
            purpose_code=purpose_code,
            beneficiary_country=beneficiary_country,
            timestamp=req_dt,
            inr_amount=gross_inr
        )

        status, applied_rules, reason = validate_remittance(customer, req, usd_equivalent)

        if status == 'REJECTED':
            advice = DebitAdvice(
                txn_id=txn_id,
                cust_id=cust_id,
                status=status,
                rule_ids=applied_rules,
                reject_reason=reason
            )
            self.advices[txn_id] = (advice, req, customer)
            return

        applied_rules.append("BR-03")
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
            self.advices[txn_id] = (advice, req, customer)
            return

        # Commit balances for ACCEPTED
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
        self.advices[txn_id] = (advice, req, customer)

    def handle_approve(self, args: list[str]):
        txn_id = args[0]
        txn = self.transactions.get(txn_id)
        if not txn or txn["status"] != "HOLD":
            print(f"APPROVE ERROR: Transaction {txn_id} not found on HOLD.")
            return

        customer = txn["customer"]
        txn["status"] = "ACCEPTED"
        customer.fy_lrs_usd += txn["usd_equivalent"]
        customer.fy_tcs_inr = txn["charges"]["updated_fy_inr"]

        # Update advice to ACCEPTED
        advice = DebitAdvice(
            txn_id=txn_id,
            cust_id=customer.cust_id,
            status="ACCEPTED",
            rule_ids=txn["applied_rules"],
            interbank_rate=txn["interbank_rate"],
            customer_rate=txn["customer_rate"],
            gross_inr=txn["gross_inr"],
            flat_charge=txn["charges"]["flat_charge"],
            gst_flat_charge=txn["charges"]["gst_flat_charge"],
            gst_conversion=txn["charges"]["gst_conversion"],
            tcs_amount=txn["charges"]["tcs_amount"],
            total_debit_inr=txn["charges"]["total_debit_inr"],
            value_date=txn["value_date"]
        )
        self.advices[txn_id] = (advice, txn["req"], customer)

    def handle_cancel(self, args: list[str]):
        txn_id, cancel_ts_str = args[0], args[1]
        try:
            cancel_dt = datetime.fromisoformat(cancel_ts_str)
        except ValueError:
            cancel_dt = datetime.strptime(cancel_ts_str, '%Y-%m-%d')

        txn = self.transactions.get(txn_id)
        if not txn:
            print(f"CANCEL ERROR: Transaction {txn_id} not found.")
            return

        if cancel_dt.date() > txn["value_date"]:
            print(f"CANCEL REJECTED (BR-09): {txn_id} cannot be cancelled after value date {txn['value_date']}.")
            return

        txn["status"] = "CANCELLED"
        txn["customer"].fy_lrs_usd -= txn["usd_equivalent"]

    def handle_rate_recheck(self, args: list[str]):
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

        if triggered:
            spread = get_spread(currency, txn["usd_equivalent"])
            new_cust_rate = compute_customer_rate(current_rate, spread)
            new_gross = (txn["req"].fx_amount * new_cust_rate).quantize(PAISA, rounding=ROUND_HALF_UP)
            diff_debit = new_gross - txn["gross_inr"]
            txn["gross_inr"] = new_gross
            txn["charges"]["total_debit_inr"] += diff_debit

    def handle_print_advice(self, args: list[str]):
        req_id = args[0]
        advice_tuple = self.advices.get(req_id)
        if advice_tuple:
            advice, req, customer = advice_tuple
            print_debit_advice(advice, req, customer)
        else:
            print(f"ADVICE ERROR: No advice found for {req_id}")

    def handle_print_fy_statement(self, args: list[str]):
        cust_id = args[0]
        fy = args[1] if len(args) > 1 else "2026-27"
        customer = self.customers.get(cust_id)
        if customer:
            print("=" * 70)
            print(f"           ANNUAL STATEMENT FOR {cust_id} (FY {fy})           ")
            print("=" * 70)
            print(f"Customer Name : {customer.name}")
            print(f"PAN           : {customer.pan}")
            print(f"LRS Utilised  : USD {customer.fy_lrs_usd:>10,.2f}")
            print(f"Cumulative INR: INR {customer.fy_tcs_inr:>10,.2f}")
            print("=" * 70 + "\n")