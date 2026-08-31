"""
S3 residency demo — Data Localization Compliance Simulator

Reads transaction_data (joined with bank to get branch country), and for
each record:
  - COMPLIANT records (bank.b_country == datares_loc, i.e. data stayed in
    Nigeria) get uploaded to the compliant bucket (af-south-1).
  - VIOLATING records (residency mismatch) get uploaded to the
    non-compliant bucket (us-east-1) -- simulating where that data actually
    ended up.

Each upload is also logged as a new row in audit_log, so the audit trail
captures not just "this record was classified/checked" but "this record
was physically placed in bucket X".

Requires: AWS CLI already configured (aws configure) so boto3 picks up
credentials automatically -- no keys are hardcoded here.
"""

import json
import pandas as pd
import boto3
from sqlalchemy import create_engine, text

# ---------------------------------------------------------------------------
# CONFIG
# ---------------------------------------------------------------------------

DB_URL = "postgresql+psycopg2://postgres:Project.@localhost:5432/postgres"

COMPLIANT_BUCKET = "rue-comp-sim"      # af-south-1
NONCOMPLIANT_BUCKET = "rue-noncomp"    # us-east-1

BANK_TABLE = "bank"
BANK_PK = "branch_id"
BANK_COUNTRY_COL = "b_country"

AUDIT_TABLE = "audit_log"
PERFORMED_BY = "s3_upload_pipeline"


# ---------------------------------------------------------------------------
# Data loading + residency check (reuses the same logic as classify_records.py)
# ---------------------------------------------------------------------------

def load_transactions_with_residency(engine) -> pd.DataFrame:
    transaction_df = pd.read_sql("SELECT * FROM transaction_data", engine)
    bank_df = pd.read_sql(f"SELECT {BANK_PK}, {BANK_COUNTRY_COL} FROM {BANK_TABLE}", engine)
    merged = transaction_df.merge(bank_df, on=BANK_PK, how="left")
    merged["residency_violation"] = merged[BANK_COUNTRY_COL] != merged["datares_loc"]
    return merged


# ---------------------------------------------------------------------------
# S3 upload
# ---------------------------------------------------------------------------

def upload_record(s3_client, record: dict, bucket: str, key: str):
    body = json.dumps(record, default=str)  # default=str handles date/datetime fields
    s3_client.put_object(Bucket=bucket, Key=key, Body=body, ContentType="application/json")


# ---------------------------------------------------------------------------
# Audit logging
# ---------------------------------------------------------------------------

def log_upload(engine, record_id: int, bucket: str, is_violation: bool):
    insert_sql = text(
        f"""
        INSERT INTO {AUDIT_TABLE}
            (table_name, record_id, action, old_value, new_value, residency_flag, performed_by)
        VALUES
            (:table_name, :record_id, :action, :old_value, :new_value, :residency_flag, :performed_by)
        """
    )
    with engine.begin() as conn:
        conn.execute(
            insert_sql,
            {
                "table_name": "transaction_data",
                "record_id": int(record_id),
                "action": "S3_UPLOAD",
                "old_value": None,
                "new_value": bucket,
                "residency_flag": "VIOLATION" if is_violation else "COMPLIANT",
                "performed_by": PERFORMED_BY,
            },
        )


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    engine = create_engine(DB_URL)
    s3 = boto3.client("s3")  # picks up credentials from `aws configure` automatically

    df = load_transactions_with_residency(engine)

    uploaded_compliant = 0
    uploaded_violation = 0

    for _, row in df.iterrows():
        record_id = row["transc_id"]
        is_violation = bool(row["residency_violation"])
        bucket = NONCOMPLIANT_BUCKET if is_violation else COMPLIANT_BUCKET
        key = f"transaction_data/{record_id}.json"

        # Build the record to upload -- drop the helper column before writing out
        record = row.drop(labels=[BANK_COUNTRY_COL, "residency_violation"]).to_dict()

        upload_record(s3, record, bucket, key)
        log_upload(engine, record_id, bucket, is_violation)

        if is_violation:
            uploaded_violation += 1
        else:
            uploaded_compliant += 1

    print(f"Uploaded {uploaded_compliant} compliant records to {COMPLIANT_BUCKET}")
    print(f"Uploaded {uploaded_violation} violating records to {NONCOMPLIANT_BUCKET}")
    print(f"Total: {uploaded_compliant + uploaded_violation} records uploaded and logged")


if __name__ == "__main__":
    main()