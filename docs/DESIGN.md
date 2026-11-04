# Design Document: Outward Forex Remittance Engine (PS-016)

**Team ID:** T011  
**Problem Statement:** PS-016 · Outward Forex Remittance Engine with LRS Limits, TCS and Rate Spreads  
**Domain:** BFSI — Forex  

---

## 1. System Architecture & Pipeline Precedence (BR-11)

The engine enforces strict precedence for processing outward remittance requests:
---

## 2. Business Rules Specification

### BR-01: LRS Limit & Residency
* **Cap:** USD 250,000 per financial year (April 1 – March 31) across all purposes per resident individual.
* Non-resident individuals are rejected outright.
* Non-USD transactions are converted to USD equivalent at the day's interbank rate to verify the cap.

### BR-02: Purpose Codes & Permitted Activity
* Permitted Purpose Codes:
  * `S0305`: Education
  * `S1301`: Family Maintenance / Gift
  * `S0023`: Travel
  * `S0001`: Investment
  * `S1302`: Medical Treatment
* `S0001` (Investment) requires `FULL` customer KYC and a minimum amount of USD 1,000.

### BR-03: Exchange Rates & Spreads
* Customer Rate = $\text{Interbank Rate} \times (1 + \text{Spread})$
* Base Spreads:
  * USD, EUR, GBP: `0.50%` (`0.0050`)
  * AED, SGD: `0.75%` (`0.0075`)
  * All other currencies: `1.25%` (`0.0125`)
* High-volume discount: Spread is reduced by `0.10` percentage points (`-0.0010`) for remittances $\ge \text{USD } 25,000$.
* Quoted to 4 decimal places (`ROUND_HALF_UP`). Gross INR rounded to paisa (2 decimals).

### BR-04: Cumulative Financial-Year TCS (Tax Collected at Source)
* TCS applies exclusively on the remittance INR amount (excluding bank charges/GST).
* Exemption limit: Cumulative remittances up to ₹10,00,000 in the FY attract `0%` TCS.
* Excess above ₹10,00,000:
  * Education funded by loan (`edu_loan_flag = True`): `0.5%`
  * Education or Medical without loan: `5.0%`
  * All other purposes (gifts, travel, investments): `20.0%`

### BR-05: Bank Charges & GST Slabs
* Flat Service Charge: ₹500.00 + 18% GST (₹90.00) = ₹590.00.
* GST on Currency Conversion Slabs:
  * Gross $\le ₹1,00,000$: 0.18% of value (minimum ₹45.00).
  * $₹1,00,000 < \text{Gross} \le ₹10,00,000$: ₹180.00 + 0.09% of excess over ₹1,00,000.
  * Gross $> ₹10,00,000$: ₹990.00 + 0.018% of excess over ₹10,00,000 (maximum cap ₹10,800.00).

### BR-06 & BR-07: Value Date & Cut-Off Logic
* Cut-off time: `14:30:00` on Indian business days.
* Requests before 14:30 receive same-day base $T$; requests on or after 14:30 roll to the next Indian business day.
* USD transfers $> \text{USD } 10,000$ carry an additional $+1$ business day for correspondent banking (BR-07).
* Value date rolls forward past any destination-country weekend or public holiday.

### BR-08: Compliance HOLD
* Single remittance $> \text{USD } 50,000$ or aggregate FY remittance $> \text{USD } 150,000$ triggers `HOLD`.
* Clears with `APPROVE <txn_id>` or auto-rejects after 2 business days.

### BR-09: Cancellations
* Requests cancelled before 14:30 on the booking day: Free cancellation.
* Requests cancelled after 14:30 on booking day: 1% penalty on Gross INR.
* Cancellations are rejected if requested after the value date.

### BR-10: Rate Recheck (RATE_RECHECK)
* If market interbank rate increases $> 1.00\%$ against the bank before the value date, the trade is re-priced and the customer is debited the differential. Moves in the customer's favor are not credited back.