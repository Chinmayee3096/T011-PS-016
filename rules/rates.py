from decimal import Decimal, ROUND_HALF_UP

FOUR_DEC = Decimal('0.0001')
PAISA = Decimal('0.01')

def get_spread(currency: str, fx_amount_usd: Decimal) -> Decimal:
    """
    BR-03: Spread logic
    - USD, EUR, GBP: 0.50%
    - AED, SGD: 0.75%
    - Others: 1.25%
    - Discount: reduced by 0.1 points (0.0010) if remittance >= USD 25,000
    """
    if currency in ['USD', 'EUR', 'GBP']:
        spread = Decimal('0.0050')
    elif currency in ['AED', 'SGD']:
        spread = Decimal('0.0075')
    else:
        spread = Decimal('0.0125')

    if fx_amount_usd >= Decimal('25000.00'):
        spread -= Decimal('0.0010')

    return spread

def compute_customer_rate(interbank_rate: Decimal, spread: Decimal) -> Decimal:
    """Quotes customer rate to 4 decimal places."""
    rate = interbank_rate * (Decimal('1.0000') + spread)
    return rate.quantize(FOUR_DEC, rounding=ROUND_HALF_UP)

def check_rate_recheck(booking_rate: Decimal, current_rate: Decimal) -> tuple[bool, Decimal]:
    """
    BR-10: RATE_RECHECK
    If interbank rate moves > 1% against the bank between booking and value date,
    re-price and debit difference. Moves in bank's favour are not passed back.
    """
    move_ratio = (current_rate - booking_rate) / booking_rate
    if move_ratio > Decimal('0.0100'):
        rate_diff = current_rate - booking_rate
        return True, rate_diff
    return False, Decimal('0.0000')