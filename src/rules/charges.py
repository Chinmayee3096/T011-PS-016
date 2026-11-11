from decimal import Decimal, ROUND_HALF_UP

PAISA = Decimal('0.01')

def calculate_conversion_gst(gross_inr: Decimal) -> Decimal:
    """
    BR-05: GST on currency conversion value slab:
    - Up to 1 Lakh: 0.18% (min Rs 45)
    - 1 to 10 Lakh: Rs 180 + 0.09% of excess over 1 Lakh
    - Above 10 Lakh: Rs 990 + 0.018% of excess over 10 Lakh (max Rs 10,800)
    """
    one_lakh = Decimal('100000')
    ten_lakh = Decimal('1000000')

    if gross_inr <= one_lakh:
        gst = gross_inr * Decimal('0.0018')
        gst = max(gst, Decimal('45.00'))
    elif gross_inr <= ten_lakh:
        excess = gross_inr - one_lakh
        gst = Decimal('180.00') + (excess * Decimal('0.0009'))
    else:
        excess = gross_inr - ten_lakh
        gst = Decimal('990.00') + (excess * Decimal('0.00018'))
        gst = min(gst, Decimal('10800.00'))

    return gst.quantize(PAISA, rounding=ROUND_HALF_UP)

def calculate_tcs(gross_inr: Decimal, prior_fy_inr: Decimal, purpose_code: str, edu_loan: bool) -> tuple[Decimal, Decimal]:
    """
    BR-04: TCS cumulative calculation
    - Nil up to Rs 10 Lakh aggregate
    - Education funded by loan: 0.5%
    - Education / Medical without loan: 5%
    - All other purposes: 20%
    """
    threshold = Decimal('1000000.00')
    current_total = prior_fy_inr + gross_inr

    # Under threshold: no TCS
    if current_total <= threshold:
        return Decimal('0.00'), current_total

    # Crossed threshold in this transaction or already crossed prior
    if prior_fy_inr >= threshold:
        taxable_inr = gross_inr
    else:
        taxable_inr = current_total - threshold

    # Determine tax rate based on purpose code
    if purpose_code == 'S0305' and edu_loan:
        tax_rate = Decimal('0.005')  # 0.5%
    elif purpose_code in ['S0305', 'S1302']:
        tax_rate = Decimal('0.05')   # 5%
    else:
        tax_rate = Decimal('0.20')   # 20%

    tcs = (taxable_inr * tax_rate).quantize(PAISA, rounding=ROUND_HALF_UP)
    return tcs, current_total

def calculate_all_charges(gross_inr: Decimal, prior_fy_inr: Decimal, purpose_code: str, edu_loan: bool) -> dict:
    flat_charge = Decimal('500.00')
    gst_flat_charge = Decimal('90.00')  # 18% of 500
    conv_gst = calculate_conversion_gst(gross_inr)
    tcs, updated_fy_inr = calculate_tcs(gross_inr, prior_fy_inr, purpose_code, edu_loan)

    total_debit = gross_inr + flat_charge + gst_flat_charge + conv_gst + tcs
    return {
        "flat_charge": flat_charge,
        "gst_flat_charge": gst_flat_charge,
        "gst_conversion": conv_gst,
        "tcs_amount": tcs,
        "total_debit_inr": total_debit,
        "updated_fy_inr": updated_fy_inr
    }