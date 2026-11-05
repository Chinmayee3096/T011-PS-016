# PS-016 – Outward Forex Remittance Engine with LRS Limits, TCS and Rate Spreads — Sample Data Pack

Prepared by 10 SECONDS for Team T011.

## Files

| File | What it holds | Row count |
|---|---|---|
| `customers.csv` | 10 customers with PAN, residency, KYC and FY 2025-26 opening LRS / INR aggregate | 10 data rows |
| `rates.csv` | Interbank rate per Indian business day for USD, EUR, GBP, AED, SGD, THB | 192 data rows |
| `holidays.csv` | Holiday calendars for IN and destination countries US, GB, AE, TH (others: weekends only) | 12 data rows |
| `commands.txt` | REMIT / APPROVE / CANCEL / RATE_RECHECK events and print commands | 110 command lines (excluding comments) |

Row numbers quoted below are 1-based data-row numbers (the header is row 0). Line numbers for `commands.txt` are physical line numbers including comment lines.

## Column reference

Conventions: dates `YYYY-MM-DD`; timestamps `YYYY-MM-DD HH:MM:SS` (24h, IST, no timezone suffix); money in Rs as plain decimals with 2 places (no commas, no symbol); percentages as plain numbers (12.5 means 12.5%); booleans `true`/`false`; IDs uppercase with a fixed prefix.

### `customers.csv`

| Column | Type | Units / format | Allowed values | Notes |
|---|---|---|---|---|
| customer_id | string | CUS-nnn | — | — |
| customer_name | string | — | — | — |
| pan | string | AAAPA9999A | — | fake but well-formed |
| residency | enum | — | RESIDENT, NON_RESIDENT | — |
| kyc_level | enum | — | FULL, MIN | S0001 needs FULL |
| fy_opening | string | YYYY-YY | 2025-26 | FY of the opening balances |
| fy_lrs_used_usd | decimal | USD | — | LRS used so far in that FY |
| fy_inr_aggregate | decimal | Rs | — | INR remitted so far in that FY (TCS base) |
| education_loan_flag | bool | — | — | — |
| education_loan_amount_inr | decimal | Rs | — | sanctioned education loan |

### `rates.csv`

| Column | Type | Units / format | Allowed values | Notes |
|---|---|---|---|---|
| rate_date | date | — | — | Indian business days only |
| currency | enum | — | USD, EUR, GBP, AED, SGD, THB | — |
| interbank_rate | decimal | Rs per unit, 4 dp | — | — |

### `holidays.csv`

| Column | Type | Units / format | Allowed values | Notes |
|---|---|---|---|---|
| country_code | enum | — | IN, US, GB, AE, TH | — |
| holiday_date | date | — | — | — |
| description | string | — | — | — |

## Command file format

`commands.txt` holds one command per line in the form `COMMAND_NAME|arg1|arg2|...`. Commands must be processed strictly in file order. Lines starting with `#` are comments and blank lines are ignored. Every command used in this pack:

| Command | Arguments (in order) | Meaning |
|---|---|---|
| `LOAD_CUSTOMERS` | `file` |  |
| `LOAD_RATES` | `file` |  |
| `LOAD_HOLIDAYS` | `file` |  |
| `REMIT` | `request_id|customer_id|currency|amount_type|amount|purpose_code|beneficiary_country|loan_funded_inr|request_ts` | amount_type FX = amount in currency, INR = INR amount to convert; loan_funded_inr = part funded by an education loan (0.00 otherwise) |
| `APPROVE` | `request_id|ts` | Clear a HOLD |
| `CANCEL` | `request_id|ts` | Cancel a booking |
| `RATE_RECHECK` | `request_id|date` | Compare that date's interbank rate with the booking rate |
| `PRINT_ADVICE` | `request_id` | Debit advice |
| `PRINT_FY_STATEMENT` | `customer_id|fy` | LRS and TCS statement for the FY |

## Planted scenarios

Every edge case in the brief, mapped to the exact record where it occurs, followed by extra traps.

- **EC-01 Remittance that lands FY aggregate exactly at USD 2,50,000**
  - CUS-001 opens FY 2025-26 with USD 2,30,000.00 used; RQ-0005 for USD 20,000.00 lands exactly on USD 2,50,000.00 → within the cap (allowed); aggregate > 1,50,000 → HOLD, cleared by APPROVE next day — `commands.txt lines 9, 11`
- **EC-02 FY boundary: request on 31 March after cut-off with value date 1 April**
  - CUS-004 has FY 2025-26 INR aggregate 9,80,000; RQ-0027 (INR 1,50,000, GBP) at 2026-03-31 15:10 is after cut-off → value date 2026-04-01 → belongs to FY 2026-27 → aggregate restarts, TCS nil (in FY 2025-26 it would have been 20% on 1,30,000) — `commands.txt line 34`
- **EC-03 INR amount making cumulative exactly Rs 10,00,000**
  - CUS-003 has INR aggregate 7,50,000; RQ-0011 for exactly INR 2,50,000 makes the cumulative exactly 10,00,000 → TCS nil; the next one (RQ-0014, INR 40,000) is fully above the threshold → 20% — `commands.txt lines 16, 19`
- **EC-04 Request at 14:30:00**
  - CUS-005: RQ-0008 at 2026-03-12 14:30:00 is NOT before 14:30 → value date next Indian business day 2026-03-13; RQ-0007 at 14:29:59 → same day — `commands.txt lines 13, 12`
- **EC-05 USD 10,000 exactly (T vs T+1 rule)**
  - CUS-006: RQ-0012 USD 10,000.00 → value date T (not above 10,000); RQ-0013 USD 10,000.01 → T+1 — `commands.txt lines 17, 18`
- **EC-06 Destination holiday on the computed value date plus Indian holiday the next day**
  - CUS-007: RQ-0037 THB to Thailand on Fri 2026-04-10 16:05 → next Indian business day Mon 2026-04-13 = TH Songkran → 2026-04-14 = TH Songkran AND Indian holiday → 2026-04-15 = TH Songkran → value date 2026-04-16 — `commands.txt line 48; holidays.csv TH 2026-04-13..15, IN 2026-04-14`
- **EC-07 Rate moves exactly 1.00%**
  - CUS-008: RQ-0017 USD 30,000 booked 2026-03-23 at interbank 83.2500 (value date T+1); RATE_RECHECK on 2026-03-24 with interbank 84.0825 = exactly +1.00% → not MORE than 1% → no re-pricing. Contrast RQ-0019 USD 12,000 (T+1) booked 2026-03-25 at 84.1000, recheck 2026-03-26 at 84.9500 (+1.0107%) → re-priced, customer debited the difference — `commands.txt lines 22, 23, 25, 27; rates.csv USD 2026-03-23 .. 2026-03-26`
- **EC-08 Education remittance where loan flag covers only part of the amount**
  - CUS-009 (education loan 6,00,000): RQ-0016 education S0305 for INR 9,00,000 with loan_funded_inr 6,00,000; aggregate 4,00,000 → 13,00,000, taxable excess 3,00,000 split pro-rata: 2,00,000 at 0.5% and 1,00,000 at 5% — `commands.txt line 21`
- **Extra traps (not in the brief, but realistic):**
  - CUS-002 at USD 2,40,000 used: RQ-0006 USD 10,000.01 → would exceed 2,50,000 → REJECT (LRS cap before HOLD) — `commands.txt line 10`
  - CUS-010 is NON_RESIDENT → REJECT (residency checked first) — `commands.txt line 14`
  - S0001 investment: RQ-0021 by MIN-KYC CUS-005 → REJECT; RQ-0022 USD 1,000.00 exactly → allowed; RQ-0023 USD 999.99 → REJECT — `commands.txt lines 28, 29, 30`
  - RQ-0031 USD 25,000.00 exactly → spread 0.5% − 0.1 = 0.4% — `commands.txt line 40`
  - RQ-0032 single remittance USD 60,000 > 50,000 → HOLD; no APPROVE follows → auto-REJECT after 2 business days — `commands.txt line 41`
  - CANCEL at 14:29 on the request day → free (RQ-0034); CANCEL at 15:30 → 1% of INR amount (RQ-0035); CANCEL after the value date → not allowed (RQ-0026) — `commands.txt lines 45, 46, 35`
  - RQ-0015 requested on 2026-03-19 (Ugadi, Indian holiday) → value date is the next Indian business day 2026-03-20, which is an AE holiday → 2026-03-23 is AE holiday → 2026-03-24 — `commands.txt line 20`
  - CANCEL for an unknown request RQ-9999 → error line — `commands.txt line 36`

## What is NOT in this pack

Expected outputs are not provided for this set. Validate your engine with your own test suite against the rules in your brief (BR-01 … BR-11). A separate hidden input set with the same schema will be used at final evaluation; outputs are compared field-for-field, so follow the column formats above exactly in your own output.

## Output format expected at evaluation

Produce these CSV files (header row, same conventions as above, rows sorted as stated). Where the brief is silent on a format detail the choice below is binding for evaluation.

### `advices.csv`

One row per PRINT_ADVICE.

Columns, in order: `request_id`, `customer_id`, `decision`, `currency`, `fx_amount`, `usd_equivalent`, `interbank_rate`, `spread_pct`, `customer_rate`, `inr_amount`, `service_charge`, `service_gst`, `conversion_gst`, `tcs`, `total_debit`, `booking_date`, `value_date`, `fy`, `repricing_debit`, `cancellation_charge`, `rule_ids`

### `fy_statements.csv`

One row per PRINT_FY_STATEMENT.

Columns, in order: `customer_id`, `fy`, `lrs_used_usd`, `lrs_remaining_usd`, `inr_aggregate`, `tcs_collected`, `remittances_count`

### `errors.csv`

Rejected commands.

Columns, in order: `line_no`, `command`, `reference_id`, `reason`

Binding choices: a remittance belongs to the FY of its VALUE DATE (both LRS and TCS). USD equivalent = fx_amount × interbank(ccy) / interbank(USD) of the booking date, 2 dp. customer_rate = interbank × (1 + spread/100) rounded to 4 dp; INR = fx × customer_rate to paisa; for amount_type INR, fx = INR / customer_rate rounded to 2 dp. Booking date = request date if it is an Indian business day and the time is before 14:30:00, else the next Indian business day. Value date = booking date (+1 Indian business day for USD above 10,000), then pushed forward until it is a business day in BOTH India and the destination. Conversion GST slabs apply to the excess over the slab start (180 + 0.09% of INR above 1,00,000; 990 + 0.018% of INR above 10,00,000). TCS on a partly loan-funded education remittance: the taxable excess is split pro-rata loan / non-loan. HOLD auto-rejects at the end of the 2nd Indian business day after booking. Rate move % = (recheck − booking interbank) / booking interbank × 100; re-price only when strictly above 1.00. `decision` ACCEPT, REJECT, HOLD, CANCELLED.
