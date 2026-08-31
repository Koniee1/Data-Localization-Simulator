

import csv
import random
from datetime import date, timedelta
from faker import Faker

fake = Faker()
random.seed(38)  # remove/change this if you want different data each run


# Reference data 

NIGERIAN_BANKS = [
    "GTBank", "Zenith Bank", "Access Bank", "UBA", "First Bank",
    "Fidelity Bank", "Union Bank", "Stanbic IBTC", "Wema Bank",
    "Sterling Bank", "Ecobank", "FCMB", "Polaris Bank",
]

NIGERIAN_CITIES_REGIONS = [
    ("Lagos", "Lagos"), ("Ikeja", "Lagos"), ("Abuja", "FCT"),
    ("Kano", "Kano"), ("Ibadan", "Oyo"), ("Port Harcourt", "Rivers"),
    ("Benin City", "Edo"), ("Kaduna", "Kaduna"), ("Enugu", "Enugu"),
    ("Jos", "Plateau"), ("Owerri", "Imo"), ("Uyo", "Akwa Ibom"),
    ("Cross-River", "Calabar"), ("Ondo", "Akure"),
]

NIGERIAN_FIRST_NAMES = [
    "Amari", "Chinedu", "Adaeze", "Oluwaseun", "Yayock", "Amina", "Emeka", "Ngozi", "Ibrahim",
    "Folake", "Katurak", "Chukwuemeka", "Tissan", "Aisha", "Tunde", "Blessing", "Yusuf", "Earnest", "Tolani",
    "Chiamaka", "Babajide", "Halima", "Obinna", "Zainab", "Femi", "Grace", "Zhea", "Kasham",
    "Kuyet", "Shim", "Faith", "Koni","Pelumi", "Nabari", "Aisha", "Joshua", "Micheal", "Fortunatus",
    "Adunni", "Abasi", "Itoro", "Ifunanya", "Kachio", "Matteo", 
]
NIGERIAN_LAST_NAMES = [
    "Okafor", "Adeyemi", "Balogun", "Eze", "Mohammed", "Nwosu", "Bello", "Ameh", "Ikuponiyi", "Oni",
    "Okonkwo", "Abubakar", "Adebayo", "Chukwu", "Suleiman", "Nnamdi", "Ibrahim", "Akanbi", "Bishio",
    "Ogunleye", "Danjuma", "Ibe", "Okoro", "Sani", "Uzo", "Garba", "Aminu", "Obaje", "McCarthy",
    "Suleiman", "Daloba", "Musa", "Kator", "Tony", "Adenuga", "Yambuat", "Munir", "Igwe",
]

CUSTOMER_TYPES = ["Individual", "Corporate", "SME"]
ACC_TYPES = ["Savings", "Current", "Fixed Deposit", "Domiciliary"]
INVEST_TYPES = ["Treasury Bills", "Mutual Fund", "Fixed Deposit", "None", "Bonds"]

# Data residency locations 
DATA_RES_LOCATIONS = (
    ["Nigeria"] * 7          # compliant, weighted heavier
    + ["United States"] * 2  # violation candidate (common cloud region)
    + ["Ireland"]            # violation candidate (EU cloud region)
)

N_BANKS = 18
N_CUSTOMERS = 800
N_TRANSACTIONS = 2500

# Generate banks

banks = []
for branch_id in range(1, N_BANKS + 1):
    bank_name = random.choice(NIGERIAN_BANKS)
    city, region = random.choice(NIGERIAN_CITIES_REGIONS)
    banks.append({
        "branch_id": branch_id,
        "b_code": f"{bank_name[:3].upper()}{branch_id:03d}",
        "b_city": city,
        "b_region": region,
        "b_country": "Nigeria",
        "created_at": fake.date_time_between(start_date="-1y", end_date="now"),
    })

with open("bank.csv", "w", newline="") as f:
    writer = csv.DictWriter(f, fieldnames=["branch_id", "b_code", "b_city", "b_region", "b_country", "created_at"])
    writer.writeheader()
    writer.writerows(banks)


# Generate customer_data

customers = []
for customer_id in range(1, N_CUSTOMERS + 1):
    city, region = random.choice(NIGERIAN_CITIES_REGIONS)
    name = f"{random.choice(NIGERIAN_FIRST_NAMES)} {random.choice(NIGERIAN_LAST_NAMES)}"
    created = fake.date_time_between(start_date="-1y", end_date="now")
    customers.append({
        "customer_id": customer_id,
        "branch_id": random.randint(1, N_BANKS),   # <-- NEW: home branch assigned here
        "acc_no": fake.unique.numerify(text="##########"),
        "customer_name": name,
        "age": random.randint(18, 80),
        "customer_type": random.choice(CUSTOMER_TYPES),
        "city": city,
        "region": region,
        "created_at": created,
        "updated_at": created,
    })

with open("customer_data.csv", "w", newline="") as f:
    writer = csv.DictWriter(f, fieldnames=[
        "customer_id", "branch_id", "acc_no", "customer_name", "age",  # <-- add branch_id here too
        "customer_type", "city", "region", "created_at", "updated_at",
    ])
    writer.writeheader()
    writer.writerows(customers)

# Generate transaction_data #


start_date = date(2025, 1, 1)
end_date = date(2026, 8, 1)
date_range_days = (end_date - start_date).days

transactions = []
for transc_id in range(1, N_TRANSACTIONS + 1):
    total_bal = random.randint(5_000, 50_000_000)
    customer_id = random.randint(1, N_CUSTOMERS)
    customer_branch = customers[customer_id - 1]["branch_id"]  # <-- lookup, not random

    transactions.append({
        "transc_id": transc_id,
        "transc_ref": fake.unique.bothify(text="TRX-########"),
        "customer_id": customer_id,
        "branch_id": customer_branch,  # <-- was random.randint(1, N_BANKS)
        "acc_type": random.choice(ACC_TYPES),
        "total_bal": total_bal,
        "transc_amount": random.randint(100, 5_000_000),
        "invest_amount": random.choice([0, random.randint(1000, 2_000_000)]),
        "invest_type": random.choice(INVEST_TYPES),
        "transac_date": start_date + timedelta(days=random.randint(0, date_range_days)),
        "datares_loc": random.choice(DATA_RES_LOCATIONS),
        "created_at": fake.date_time_between(start_date="-1y", end_date="now"),
    })

with open("transaction_data.csv", "w", newline="") as f:
    writer = csv.DictWriter(f, fieldnames=[
        "transc_id", "transc_ref", "customer_id", "branch_id", "acc_type",
        "total_bal", "transc_amount", "invest_amount", "invest_type",
        "transac_date", "datares_loc", "created_at",
    ])
    writer.writeheader()
    writer.writerows(transactions)

print(f"Generated: {len(banks)} banks, {len(customers)} customers, {len(transactions)} transactions")
print("Files written: bank.csv, customer_data.csv, transaction_data.csv")