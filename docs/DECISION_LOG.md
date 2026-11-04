# Decision Log: Edge-Case Interpretations

This document records architectural decisions and boundary interpretations implemented in the engine.

| Decision ID | Edge Case Scenario | Interpretation & Implementation | Rule Reference |
| :--- | :--- | :--- | :--- |
| **DEC-01** | Cut-off at `14:30:00` | Exact `14:30:00` is considered *at/past* cut-off. It rolls to the next Indian business day ($T+1$). | BR-06 |
| **DEC-02** | Exact USD 10,000 | The correspondent banking $+1$ day rule applies strictly to amounts *strictly greater than* USD 10,000 (`> 10000`). USD 10,000.00 receives same-day processing ($T$). | BR-07 |
| **DEC-03** | Exact ₹10,00,000 TCS Boundary | TCS applies *only on the excess* above ₹10,00,000. A cumulative total of exactly ₹10,00,000 incurs ₹0.00 TCS. | BR-04 |
| **DEC-04** | Exact 1.00% Rate Movement | Recheck triggers only if rate move is *strictly greater than* 1.00% (`move > 0.0100`). Exactly 1.0000% triggers no price adjustment. | BR-10 |
| **DEC-05** | Exact USD 250,000 LRS Cap | An aggregate reaching exactly USD 250,000.00 is allowed (`<= 250000`). Any transaction pushing cumulative above USD 250,000.00 is rejected. | BR-01 |
| **DEC-06** | Financial Year Split on March 31 | A transaction requested on March 31 after 14:30 gets a Value Date in the new FY (April 1). The transaction's quota is accounted against the FY of the request timestamp. | BR-01, BR-06 |
| **DEC-07** | Floating Point Safety | All currency, rate, and fee calculations use Python's `decimal.Decimal` with explicit `ROUND_HALF_UP` to eliminate floating-point precision errors. | General |