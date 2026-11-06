from datetime import datetime, date, time, timedelta
from decimal import Decimal

# Cut-off time strictly at 14:30:00 (BR-06)
CUTOFF_TIME = time(14, 30, 0)


def is_business_day(target_date: date, holidays: set[date]) -> bool:
    """Returns True if the date is not a weekend (Sat/Sun) and not in the holiday list."""
    if target_date.weekday() >= 5:
        return False
    return target_date not in holidays


def add_business_days(start_date: date, days: int, holidays: set[date]) -> date:
    """Adds a given number of working business days, skipping weekends and holidays."""
    cur = start_date
    added = 0
    while added < days:
        cur += timedelta(days=1)
        if is_business_day(cur, holidays):
            added += 1
    return cur


def compute_value_date(
    req_dt: datetime,
    currency: str,
    fx_amount_usd: Decimal,
    ind_holidays: set[date],
    dest_holidays: set[date]
) -> tuple[date, list[str]]:
    """
    Computes the settlement value date:
      1. Indian cut-off logic (14:30:00) and Indian banking calendar (BR-06)
      2. USD correspondent banking rule (> USD 10,000 carries T+1) (BR-07)
      3. Destination calendar roll: pushed forward while on destination holiday/weekend
    """
    rules = ["BR-06"]
    cur_date = req_dt.date()

    # Step A: Cut-off logic on Indian business day
    if req_dt.time() >= CUTOFF_TIME or not is_business_day(cur_date, ind_holidays):
        cur_date = add_business_days(cur_date, 1, ind_holidays)

    # Step B: USD correspondent banking rule (BR-07)
    # Strictly > USD 10,000 carries an additional correspondent business day
    if currency.upper() == 'USD' and fx_amount_usd > Decimal('10000.00'):
        rules.append("BR-07")
        cur_date = add_business_days(cur_date, 1, ind_holidays)

    # Step C: Destination country holiday / weekend roll
    # Value date is pushed forward while it falls on a destination holiday or weekend
    while not is_business_day(cur_date, dest_holidays):
        cur_date += timedelta(days=1)

    return cur_date, rules