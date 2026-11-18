# Architectural & Engineering Decision Log (Team T011 – PS-016)

This document records the key architectural, financial, and implementation decisions made while building the **Forex Outward Remittance Engine**.

---

## 1. Fixed-Point Arithmetic via `Decimal` Instead of `float`
* **Context:** Outward forex conversions, progressive TCS tax slabs (Section 206C(1G)), and tiered GST calculations involve multi-step multiplication and division across currencies.
* **Decision:** Enforced Python's `decimal.Decimal` across all monetary values, exchange rates, spreads, and tax thresholds, applying explicit `ROUND_HALF_UP` rounding at ledger boundaries (`0.01` for INR/FX).
* **Rationale:** Standard IEEE 754 floating-point numbers introduce binary representation drift (e.g., `0.1 + 0.2 != 0.3`), which is unacceptable in BFSI compliance and audit trails.

## 2. Modular Rule Engine Architecture (`src/rules/`)
* **Context:** RBI LRS regulations, tax slabs, and bank holiday rules change frequently and have strict evaluation precedence.
* **Decision:** Separated domain logic into dedicated, stateless modules (`validation.py`, `rates.py`, `charges.py`, `value_date.py`) orchestrated by `src/engine.py`.
* **Rationale:** Decoupling business rules from CSV ingestion and command execution makes individual rules easy to unit-test in isolation and allows tax slabs or spread tiers to be updated without touching the core execution loop.

## 3. Precedence-Driven Validation & Compliance HOLD Workflow
* **Context:** A remittance request can violate multiple rules simultaneously (e.g., non-resident status, invalid purpose code, LRS cap breach, or high-value compliance review).
* **Decision:** Implemented short-circuit precedence in `validate_remittance()` (`Residency -> Purpose & KYC -> Annual LRS Cap -> Compliance HOLD`). Requests exceeding USD 50,000 per transaction or USD 150,000 cumulative FY utilisation are placed on `HOLD` rather than auto-rejected, deferring FY quota deduction until an explicit `APPROVE` command is processed.
* **Rationale:** Ensures accurate rejection reasons, prevents premature quota consumption for unapproved high-value transfers, and mirrors real-world bank compliance queues.

## 4. Dual-Country Banking Holiday & Cutoff Routing
* **Context:** Cross-border settlements depend on working days in both India (remitting bank) and the beneficiary country, as well as daily treasury cutoff times.
* **Decision:** Built a calendar resolver (`src/calendars.py` + `src/rules/value_date.py`) that shifts requests submitted after the 14:30 IST cutoff to the next business day and skips weekends plus country-specific holidays from `data/holidays.csv`.
* **Rationale:** Prevents invalid settlement value dates on non-working days in either jurisdiction.

## 5. Pipe-Delimited (`|`) Batch Command Processor
* **Context:** The engine must process a deterministic sequence of transactions, compliance approvals, rate rechecks, cancellations, and reporting commands while maintaining stateful customer FY balances.
* **Decision:** Designed `RemittanceEngine` to parse pipe-delimited (`|`) commands from `data/commands.txt`, supporting both FX-denominated and INR-denominated remittance inputs and recording immutable `DebitAdvice` audit objects for every transaction.
* **Rationale:** Provides an auditable, replayable execution trail (`output_run.txt`) with exact rule IDs (`BR-01` through `BR-10`) stamped on every advice.

## 6. Standard `src/` Layout & Zero-Dependency `unittest` Suite
* **Context:** The codebase needs to run reliably across team machines and evaluation environments without complex environment setup.
* **Decision:** Organized the codebase into a clean `src/` package layout with `main.py` at the root and wrote unit tests using Python's built-in `unittest` framework (`tests/test_rules.py`).
* **Rationale:** Eliminates third-party dependency issues and ensures evaluators can clone the repository and immediately verify both tests and batch execution.