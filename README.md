# Data Localization Compliance Simulator

A synthetic-data pipeline and Power BI dashboard simulating data residency compliance monitoring for a Nigerian fintech, built around the CBN (Central Bank of Nigeria) data localization regulatory wave.

## Overview

This project simulates how a fintech might monitor whether customer and transaction data is being stored/processed in compliance with data residency requirements — i.e. whether data tied to a domestic bank branch is actually staying in-country, or being replicated/stored abroad.

It ties together five areas end-to-end: database design, synthetic data generation, an ETL classification pipeline, cloud storage residency simulation, and BI dashboarding.

## Tech Stack

- **PostgreSQL** — relational schema and audit logging
- **Python** (pandas, SQLAlchemy, Faker) — synthetic data generation and the classification/residency ETL pipeline
- **AWS S3** — residency simulation via buckets in two regions
- **Power BI** — compliance dashboard (overview + drill-down)

## Schema

| Table | Purpose |
|---|---|
| `bank` | Bank branches, including `b_country` (branch's home country) |
| `customer_data` | Customers, linked to `bank` via `branch_id` |
| `transaction_data` | Transactions, linked to `bank` (via `branch_id`) and `customer_data` (via `customer_id`); includes `datares_loc` (where the transaction's data is actually stored/replicated) |
| `data_class` | Lookup table mapping `(table_name, column_name)` → sensitivity classification |
| `audit_log` | Central audit trail — logs classification and residency outcomes as discrete, timestamped events rather than flag columns on the source tables |

`audit_log` is a polymorphic/shared audit table: `record_id` refers to a `customer_id` or `transc_id` depending on that row's `table_name`. Any query against it must filter on both columns together.

## How It Works

1. **Classification** — for every record in `customer_data` and `transaction_data`, each present column is looked up against `data_class`, and the record is assigned the *maximum* sensitivity level found across its fields (record-level classification, not per-field).
2. **Residency check** —
   - `transaction_data`: compares the transaction's linked branch country (`bank.b_country`) against where its data actually resides (`datares_loc`).
   - `customer_data`: has no residency field of its own — a customer is flagged as a residency risk if **any** of their linked transactions violate residency.
3. **Audit logging** — nothing is written back onto `customer_data`/`transaction_data` directly. Every classification and residency outcome is logged as a row in `audit_log`, including `old_value`/`new_value` for change tracking. The pipeline is idempotent: a new row is only inserted when a record's classification or residency flag has actually changed since the last run, so re-running the script doesn't create duplicate audit entries.
4. **S3 residency demo** — synthetic records are split and uploaded to two S3 buckets in different regions (`af-south-1` — compliant, `us-east-1` — violating) to simulate a real residency outcome outside the database.
5. **Power BI dashboard** — connects directly to Postgres and visualizes compliance rate, violation counts, and classification spread, plus a drill-down lookup by account number.

## Dashboard

**Overview page:**
- Compliance % (transaction-level: compliant transactions ÷ total transactions logged)
- Violation counts by table and residency status (compliant / violation / unknown)
- Classification breakdown (share of records by sensitivity level)

**Drill-down page:**
- Slicer on customer account number (`acc_no`)
- Table showing that customer's transactions, with individual classification and residency flags

## Known Limitations / Design Notes

- **Record-level classification collapses granularity.** Because classification takes the max sensitivity across all fields in a record, lower-sensitivity fields (e.g. a customer's name) get masked whenever a higher-sensitivity field (e.g. an account number) sits in the same row. In this dataset, that meant records only ever landed on `restricted` or `sensitive` — `public` and `internal` never surfaced at the record level, even though individual fields were classified at those levels in `data_class`.
- **Customer-level residency is a rollup, not a direct measurement.** A customer flagged as a residency "violation" doesn't mean their own record is stored non-compliantly — it means at least one of their linked transactions is. The two are tracked separately in the dashboard for this reason.
- **`audit_log.record_id` requires care.** Since it's shared across table types, any join or Power BI relationship built against it must also filter/join on `table_name` — a relationship built on `record_id` alone will silently produce wrong or incomplete results.
- AWS region constraint: AWS does not currently offer an Africa (Nigeria) region for data residency — af-south-1 (South Africa/Cape Town), the nearest available African region, was used as the stand-in for "compliant" storage in this simulation. Notably, AWS does list Lagos as a selectable time zone in account/console settings, but this is a locale setting only and does not correspond to an actual infrastructure region. In a production deployment, the real approved storage location(s) under CBN guidance would need to be confirmed with AWS or a provider with in-country infrastructure.

## Setup

1. Create the Postgres schema (`bank`, `customer_data`, `transaction_data`, `data_class`, `audit_log`).
2. Populate `data_class` with classification levels for the columns you want tracked (this is required — the pipeline fails loudly rather than defaulting silently if it's empty).
3. Generate synthetic data (Faker script) and load into `bank`, `customer_data`, `transaction_data`.
4. Run `classify_records.py` to classify records and log residency outcomes to `audit_log`.
5. Run the S3 upload script to simulate the residency outcome in cloud storage.
6. Open the Power BI file and connect to your local Postgres instance (`localhost:5432`).

## Author

Built by Bishio Ruth with Claude generative ai model as a self-study portfolio project.
