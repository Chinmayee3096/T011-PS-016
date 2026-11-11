import sys
from src.calendars import load_customers, load_rates, load_holidays
from src.engine import RemittanceEngine

def main():
    customers_file = "data/customers.csv"
    rates_file = "data/rates.csv"
    holidays_file = "data/holidays.csv"
    commands_file = "data/commands.txt"

    print("======================================================================")
    print("      INITIALIZING FOREX OUTWARD REMITTANCE ENGINE (PS-016)           ")
    print("======================================================================\n")

    # Load input data
    customers = load_customers(customers_file)
    rates = load_rates(rates_file)
    holidays = load_holidays(holidays_file)

    # Run the engine
    engine = RemittanceEngine(customers, rates, holidays)
    engine.process_command_file(commands_file)

if __name__ == "__main__":
    main()