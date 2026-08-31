"""
Classification + residency check — Data Localization Compliance Simulator

For each record in customer_data and transaction_data:
  1. Look up the classification of every field present, via data_class.
     Take the MAX sensitivity across those fields -> record-level classification.
  2. Check data residency:
       - transaction_data: compare bank.b_country (via branch_id) to the
         transaction's own datares_loc.
       - customer_data: has no residency field of its own, so a customer is
         flagged if ANY of their linked transactions violate residency.
  3. Nothing is written back onto customer_data/transaction_data. Every
     record's result (classification + residency outcome) is logged as a
     row in audit_log instead.

Adjust CONFIG and column names below to match your schema if it changes.
"""

import pandas as pd
from sqlalchemy import create_engine, text

# ---------------------------------------------------------------------------
# CONFIG
# ---------------------------------------------------------------------------

import os
DB_URL = os.environ.get("DB_URL", "postgresql+psycopg2://postgres:Project.@localhost:5432/postgres")

# Order matters: index = sensitivity rank (higher = more sensitive).
# Edit this to match whatever values you've actually used in data_class.data_classification.
CLASSIFICATION_ORDER = ["public", "internal", "restricted", "sensitive"]

DATA_CLASS_TABLE = "data_class"
DATA_CLASS_TABLE_COL = "table_name"
DATA_CLASS_COLUMN_COL = "column_name"
DATA_CLASS_LEVEL_COL = "data_classification"

BANK_TABLE = "bank"
BANK_PK = "branch_id"
BANK_COUNTRY_COL = "b_country"

AUDIT_TABLE = "audit_log"
PERFORMED_BY = "classification_pipeline"


# ---------------------------------------------------------------------------
# Classification
# ---------------------------------------------------------------------------

def load_classification_lookup(engine) -> dict:
    """Returns {(table_name, column_name): data_classification}."""
    df = pd.read_sql(f"SELECT * FROM {DATA_CLASS_TABLE}", engine)

    if df.empty:
        raise RuntimeError(
            f"{DATA_CLASS_TABLE} is empty — every record would silently be "
            f"classified as 'public' with no way to tell from the output. "
            f"Populate {DATA_CLASS_TABLE} before running classification."
        )

    return {
        (row[DATA_CLASS_TABLE_COL], row[DATA_CLASS_COLUMN_COL]): row[DATA_CLASS_LEVEL_COL]
        for _, row in df.iterrows()
    }


_warned_tables = set()  # tracks which tables we've already warned about, so we don't spam per-row


def record_classification(table_name: str, row: pd.Series, lookup: dict) -> str:
    """Max sensitivity across all columns present in this record for this table."""
    levels_present = [
        lookup[(table_name, col)] for col in row.index if (table_name, col) in lookup
    ]
    if not levels_present:
        if table_name not in _warned_tables:
            print(
                f"WARNING: no columns of '{table_name}' matched any entry in "
                f"{DATA_CLASS_TABLE} — every record in this table will default to 'public'. "
                f"Check that {DATA_CLASS_TABLE}.table_name values match the real table names."
            )
            _warned_tables.add(table_name)
        return "public"  # default when nothing in data_class matches
    ranked = sorted(levels_present, key=lambda l: CLASSIFICATION_ORDER.index(l))
    return ranked[-1]


# ---------------------------------------------------------------------------
# Residency checks
# ---------------------------------------------------------------------------

def check_transaction_residency(engine, transaction_df: pd.DataFrame) -> pd.DataFrame:
    """Adds a residency_violation bool column: bank.b_country != transaction's datares_loc."""
    bank_df = pd.read_sql(f"SELECT {BANK_PK}, {BANK_COUNTRY_COL} FROM {BANK_TABLE}", engine)
    merged = transaction_df.merge(bank_df, on=BANK_PK, how="left")
    merged["residency_violation"] = merged[BANK_COUNTRY_COL] != merged["datares_loc"]
    return merged


def check_customer_residency(customer_df: pd.DataFrame, transaction_df_checked: pd.DataFrame) -> pd.DataFrame:
    """A customer is flagged if ANY of their linked transactions violate residency.
    Customers with no transactions on record get residency_violation = None (unknown)."""
    per_customer = (
        transaction_df_checked.groupby("customer_id")["residency_violation"]
        .any()
        .rename("residency_violation")
    )
    merged = customer_df.merge(per_customer, on="customer_id", how="left")
    return merged


# ---------------------------------------------------------------------------
# Audit logging
# ---------------------------------------------------------------------------

def get_previous_state(engine, table_name: str, record_id):
    """Most recent (classification, residency_flag) previously logged for this record, if any."""
    row = pd.read_sql(
        text(
            f"""
            SELECT new_value, residency_flag FROM {AUDIT_TABLE}
            WHERE table_name = :table_name AND record_id = :record_id AND action = 'CLASSIFY_AND_CHECK'
            ORDER BY logged_at DESC
            LIMIT 1
            """
        ),
        engine,
        params={"table_name": table_name, "record_id": record_id},
    )
    if row.empty:
        return None, None
    return row["new_value"].iloc[0], row["residency_flag"].iloc[0]


def residency_flag_label(value) -> str:
    if value is True:
        return "VIOLATION"
    if value is False:
        return "COMPLIANT"
    return "UNKNOWN"


def log_records(engine, table_name: str, df: pd.DataFrame, pk: str):
    insert_sql = text(
        f"""
        INSERT INTO {AUDIT_TABLE}
            (table_name, record_id, action, old_value, new_value, residency_flag, performed_by)
        VALUES
            (:table_name, :record_id, :action, :old_value, :new_value, :residency_flag, :performed_by)
        """
    )
    skipped = 0
    logged = 0
    with engine.begin() as conn:
        for _, row in df.iterrows():
            record_id = row[pk]
            new_value = row["classification_level"]
            new_flag = residency_flag_label(row["residency_violation"])
            old_value, old_flag = get_previous_state(engine, table_name, record_id)

            if old_value == new_value and old_flag == new_flag:
                skipped += 1
                continue  # nothing changed, don't re-log

            conn.execute(
                insert_sql,
                {
                    "table_name": table_name,
                    "record_id": int(record_id),
                    "action": "CLASSIFY_AND_CHECK",
                    "old_value": old_value,
                    "new_value": new_value,
                    "residency_flag": new_flag,
                    "performed_by": PERFORMED_BY,
                },
            )
            logged += 1
    print(f"{table_name}: {logged} rows logged, {skipped} unchanged (skipped)")

# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    engine = create_engine(DB_URL)
    lookup = load_classification_lookup(engine)

    transaction_df = pd.read_sql("SELECT * FROM transaction_data", engine)
    customer_df = pd.read_sql("SELECT * FROM customer_data", engine)

    # Classification (in-memory, not persisted onto the tables)
    transaction_df["classification_level"] = transaction_df.apply(
        lambda row: record_classification("transaction_data", row, lookup), axis=1
    )
    customer_df["classification_level"] = customer_df.apply(
        lambda row: record_classification("customer_data", row, lookup), axis=1
    )

    # Residency
    transaction_df = check_transaction_residency(engine, transaction_df)
    customer_df = check_customer_residency(customer_df, transaction_df)

    # Log everything to audit_log
    log_records(engine, "transaction_data", transaction_df, pk="transc_id")
    log_records(engine, "customer_data", customer_df, pk="customer_id")

    txn_violations = transaction_df["residency_violation"].sum()
    cust_violations = customer_df["residency_violation"].fillna(False).sum()
    print(f"transaction_data: {len(transaction_df)} records logged, {txn_violations} residency violations")
    print(f"customer_data: {len(customer_df)} records logged, {cust_violations} residency violations")


if __name__ == "__main__":
    main()