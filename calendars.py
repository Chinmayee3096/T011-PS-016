import csv
from datetime import datetime, date
from decimal import Decimal
from src.models import Customer

def load_customers(filepath: str) -> dict[str, Customer]:
    customers = {}
    with open(filepath, mode='r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            cid = row['cust_id'].strip()
            customers[cid] = Customer(
                cust_id=cid,
                name=row['name'].strip(),
                pan=row['pan'].strip(),
                residency=row['residency'].strip(),
                kyc_level=row['kyc_level'].strip(),
                fy_lrs_usd=Decimal(row['fy_lrs_usd']),
                fy_tcs_inr=Decimal(row['fy_tcs_inr']),
                edu_loan_flag=row['edu_loan_flag'].strip().upper() == 'TRUE'
            )
    return customers

def load_rates(filepath: str) -> dict[tuple[date, str], Decimal]:
    rates = {}
    with open(filepath, mode='r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            d = datetime.strptime(row['date'].strip(), '%Y-%m-%d').date()
            cur = row['currency'].strip().upper()
            rates[(d, cur)] = Decimal(row['interbank_rate'])
    return rates

def load_holidays(filepath: str) -> dict[str, set[date]]:
    holidays = {}
    with open(filepath, mode='r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            country = row['country'].strip().upper()
            h_date = datetime.strptime(row['holiday_date'].strip(), '%Y-%m-%d').date()
            holidays.setdefault(country, set()).add(h_date)
    return holidays