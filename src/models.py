from dataclasses import dataclass
from decimal import Decimal
from datetime import datetime, date
from typing import Optional

@dataclass
class Customer:
    cust_id: str
    name: str
    pan: str
    residency: str          # 'RESIDENT' or 'NON_RESIDENT'
    kyc_level: str          # 'FULL' or 'MINIMUM'
    fy_lrs_usd: Decimal     # Total USD remitted in this FY
    fy_tcs_inr: Decimal     # Total INR remitted in this FY for TCS tracking
    edu_loan_flag: bool

@dataclass
class RemittanceRequest:
    txn_id: str
    cust_id: str
    currency: str
    fx_amount: Decimal
    purpose_code: str       # S0305, S1301, S0023, S0001, S1302
    beneficiary_country: str
    timestamp: datetime
    inr_amount: Optional[Decimal] = None

@dataclass
class DebitAdvice:
    txn_id: str
    cust_id: str
    status: str             # 'ACCEPTED', 'REJECTED', 'HOLD'
    rule_ids: list[str]
    reject_reason: Optional[str] = None
    interbank_rate: Optional[Decimal] = None
    customer_rate: Optional[Decimal] = None
    gross_inr: Optional[Decimal] = None
    flat_charge: Optional[Decimal] = None
    gst_flat_charge: Optional[Decimal] = None
    gst_conversion: Optional[Decimal] = None
    tcs_amount: Optional[Decimal] = None
    total_debit_inr: Optional[Decimal] = None
    value_date: Optional[date] = None