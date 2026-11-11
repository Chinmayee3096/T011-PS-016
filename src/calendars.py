import csv
from datetime import datetime, date
from decimal import Decimal
from src.models import Customer


def load_customers(filepath: str) -> dict[str, Customer]:
    customers = {}
    with open(filepath, mode='r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            cid = (row.get('customer_id') or row.get('cust_id') or '').strip()
            if not cid:
                continue

            name = (row.get('customer_name') or row.get('name') or '').strip()
            pan = (row.get('pan') or row.get('PAN') or '').strip()
            residency = (row.get('residency') or row.get('Residency') or '').strip()
            kyc_level = (row.get('kyc_level') or row.get('KYC_Level') or '').strip()

            raw_lrs = row.get('fy_lrs_usd') or row.get('lrs_spent') or '0.0'
            raw_tcs = row.get('fy_tcs_inr') or row.get('tcs_paid') or '0.0'
            raw_edu = row.get('edu_loan_flag') or 'FALSE'

            customers[cid] = Customer(
                cust_id=cid,
                name=name,
                pan=pan,
                residency=residency,
                kyc_level=kyc_level,
                fy_lrs_usd=Decimal(str(raw_lrs).strip()),
                fy_tcs_inr=Decimal(str(raw_tcs).strip()),
                edu_loan_flag=str(raw_edu).strip().upper() == 'TRUE',
            )
    return customers


def load_rates(filepath: str) -> dict[tuple[date, str], Decimal]:
    rates = {}
    with open(filepath, mode='r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            d_str = (row.get('date') or row.get('Date') or row.get('rate_date') or '').strip()
            cur = (row.get('currency') or row.get('Currency') or row.get('ccy') or '').strip().upper()
            rate_val = (row.get('interbank_rate') or row.get('rate') or row.get('Rate') or '').strip()

            if not d_str or not cur or not rate_val:
                continue

            d = datetime.strptime(d_str, '%Y-%m-%d').date()
            rates[(d, cur)] = Decimal(rate_val)
    return rates


def load_holidays(filepath: str) -> dict[str, set[date]]:
    holidays = {}
    with open(filepath, mode='r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            country = (row.get('country') or row.get('country_code') or '').strip().upper()
            date_str = (row.get('holiday_date') or row.get('date') or '').strip()

            if not country or not date_str:
                continue

            h_date = datetime.strptime(date_str, '%Y-%m-%d').date()
            holidays.setdefault(country, set()).add(h_date)
    return holidays