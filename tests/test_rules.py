import unittest
from decimal import Decimal
from datetime import datetime, date, time
from src.rules.charges import calculate_conversion_gst, calculate_tcs
from src.rules.rates import get_spread, compute_customer_rate, check_rate_recheck
from src.rules.value_date import compute_value_date, CUTOFF_TIME
from src.models import Customer, RemittanceRequest
from src.rules.validation import validate_remittance

class TestForexRemittanceEngine(unittest.TestCase):

    # 1. Edge Case: Request at exactly 14:30:00
    def test_cutoff_time_exact_1430(self):
        req_dt = datetime(2026, 10, 15, 14, 30, 0)
        hols_ind = set()
        hols_dest = set()
        # 14:30:00 is on or past cut-off, so it should roll to next Indian business day (16th)
        val_date, rules = compute_value_date(req_dt, 'EUR', Decimal('5000'), hols_ind, hols_dest)
        self.assertEqual(val_date, date(2026, 10, 16))

    # 2. Edge Case: USD 10,000 exactly (T vs T+1 rule)
    def test_usd_exactly_10000(self):
        req_dt = datetime(2026, 10, 15, 11, 0, 0)
        hols_ind = set()
        hols_dest = set()
        # Rule says > 10,000 triggers T+1. Exactly 10,000 should get same day T (15th)
        val_date, rules = compute_value_date(req_dt, 'USD', Decimal('10000.00'), hols_ind, hols_dest)
        self.assertEqual(val_date, date(2026, 10, 15))
        self.assertNotIn("BR-07", rules)

        # 10,000.01 should trigger BR-07 (T+1)
        val_date_plus, rules_plus = compute_value_date(req_dt, 'USD', Decimal('10000.01'), hols_ind, hols_dest)
        self.assertEqual(val_date_plus, date(2026, 10, 16))
        self.assertIn("BR-07", rules_plus)

    # 3. Edge Case: INR aggregate making cumulative exactly Rs 10,00,000
    def test_cumulative_inr_exactly_10_lakh(self):
        prior_inr = Decimal('700000.00')
        gross_inr = Decimal('300000.00')  # Exactly reaches 10 Lakh
        tcs, updated_total = calculate_tcs(gross_inr, prior_inr, 'S1301', False)
        # Up to 10 Lakh is nil TCS
        self.assertEqual(tcs, Decimal('0.00'))
        self.assertEqual(updated_total, Decimal('1000000.00'))

    # 4. Edge Case: Rate moves exactly 1.00%
    def test_rate_moves_exactly_one_percent(self):
        booking = Decimal('80.0000')
        # Exactly 1% move = 80.8000
        current = Decimal('80.8000')
        # Rule: moves MORE than 1% triggers recheck (> 1.00%)
        triggered, diff = check_rate_recheck(booking, current)
        self.assertFalse(triggered)

        # 1.01% move = 80.8081
        current_above = Decimal('80.8100')
        triggered_above, diff_above = check_rate_recheck(booking, current_above)
        self.assertTrue(triggered_above)

    # 5. Edge Case: Destination holiday on value date + Indian holiday next day
    def test_destination_and_indian_holidays(self):
        req_dt = datetime(2026, 10, 15, 11, 0, 0) # Thursday
        ind_hols = {date(2026, 10, 16)}            # Friday is IND holiday
        dest_hols = {date(2026, 10, 15)}           # Thursday is US holiday
        # Request on 15th before cut-off -> Base date 15th.
        # But 15th is US holiday -> rolls to 16th.
        # 16th is working in US -> value date settles on 16th.
        val_date, _ = compute_value_date(req_dt, 'EUR', Decimal('5000'), ind_hols, dest_hols)
        self.assertEqual(val_date, date(2026, 10, 16))

    # 6. Edge Case: Exactly USD 250,000 LRS annual cap
    def test_exact_lrs_limit_boundary(self):
        cust = Customer("C999", "Test", "ABC1234", "RESIDENT", "FULL", Decimal('240000.00'), Decimal('0'), False)
        req = RemittanceRequest("TXN-TEST", "C999", "USD", Decimal('10000.00'), "S1301", "USA", datetime.now())
        # Exactly 250k should be accepted (or routed to hold if > 150k cumulative)
        status, rules, _ = validate_remittance(cust, req, Decimal('10000.00'))
        self.assertIn(status, ["ACCEPTED", "HOLD"])
        self.assertNotIn("REJECTED", status)

if __name__ == '__main__':
    unittest.main()