# Forex Outward Remittance Engine (PS-016)

A BFSI regulatory compliance and transaction engine that automates outward remittance requests in accordance with RBI Liberalised Remittance Scheme (LRS) limits, TCS tax slabs, currency conversion GST, and settlement calendars.

## Key Features
- **LRS Cap Verification (BR-01 & BR-02):** Validates eligibility, KYC level, and enforces the USD 250,000 annual limit.
- **Dynamic Margins & Pricing (BR-03):** Computes customer exchange rates with tier-based spreads.
- **Taxation & Charges (BR-04 & BR-05):** Applies flat processing fees, statutory 18% GST tiers, and progressive TCS rates under Section 206C(1G).
- **Holiday & Value Date Calculation (BR-06 & BR-07):** Evaluates multi-country banking holidays and cutoff times.
- **Lifecycle Management (BR-08, BR-09, BR-10):** Compliance HOLD/APPROVAL flow, same-day vs late cancellation penalties, and rate movement re-checks.

## Project Structure
```text
├── data/              # CSV profiles, rate matrices, holidays, commands
├── docs/              # Architectural design document
├── src/               # Core business logic, engine, and models
├── tests/             # Unit test suite
└── main.py            # Entry point for batch processing