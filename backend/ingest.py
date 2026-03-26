"""
Data ingestion script: reads JSONL files from sap-o2c-data/ and loads into SQLite.
"""

import json
import os
import sqlite3
import os
from pathlib import Path

DATA_DIR = Path(os.environ.get("DATA_DIR", Path(__file__).resolve().parent.parent / "sap-o2c-data"))
DB_PATH = Path(os.environ.get("DB_PATH", Path(__file__).resolve().parent / "data" / "o2c.db"))

# Map directory names to table names
TABLE_MAP = {
    "sales_order_headers": "sales_order_headers",
    "sales_order_items": "sales_order_items",
    "sales_order_schedule_lines": "sales_order_schedule_lines",
    "outbound_delivery_headers": "outbound_delivery_headers",
    "outbound_delivery_items": "outbound_delivery_items",
    "billing_document_headers": "billing_document_headers",
    "billing_document_items": "billing_document_items",
    "billing_document_cancellations": "billing_document_cancellations",
    "journal_entry_items_accounts_receivable": "journal_entry_items_ar",
    "payments_accounts_receivable": "payments_ar",
    "business_partners": "business_partners",
    "business_partner_addresses": "business_partner_addresses",
    "customer_company_assignments": "customer_company_assignments",
    "customer_sales_area_assignments": "customer_sales_area_assignments",
    "products": "products",
    "product_descriptions": "product_descriptions",
    "product_plants": "product_plants",
    "product_storage_locations": "product_storage_locations",
    "plants": "plants",
}


def read_jsonl_dir(dir_path: Path) -> list[dict]:
    """Read all JSONL files in a directory and return a list of records."""
    records = []
    for f in sorted(dir_path.glob("*.jsonl")):
        with open(f, "r") as fp:
            for line in fp:
                line = line.strip()
                if line:
                    records.append(json.loads(line))
    return records


def create_table_and_insert(conn: sqlite3.Connection, table_name: str, records: list[dict]):
    """Create a table from records and insert all data."""
    if not records:
        print(f"  WARNING: No records for {table_name}")
        return

    columns = list(records[0].keys())
    col_defs = ", ".join(f'"{c}" TEXT' for c in columns)
    create_sql = f'CREATE TABLE IF NOT EXISTS "{table_name}" ({col_defs})'
    conn.execute(f'DROP TABLE IF EXISTS "{table_name}"')
    conn.execute(create_sql)

    placeholders = ", ".join("?" for _ in columns)
    insert_sql = f'INSERT INTO "{table_name}" ({", ".join(f"{c!r}" for c in columns)}) VALUES ({placeholders})'
    # Fix quoting for column names in INSERT
    col_names = ", ".join(f'"{c}"' for c in columns)
    insert_sql = f'INSERT INTO "{table_name}" ({col_names}) VALUES ({placeholders})'

    rows = []
    for rec in records:
        rows.append(tuple(str(rec.get(c, "")) if rec.get(c) is not None else None for c in columns))

    conn.executemany(insert_sql, rows)
    print(f"  {table_name}: {len(rows)} rows, {len(columns)} columns")


def create_indexes(conn: sqlite3.Connection):
    """Create indexes for common query patterns."""
    indexes = [
        ("idx_soh_salesorder", "sales_order_headers", "salesOrder"),
        ("idx_soh_soldtoparty", "sales_order_headers", "soldToParty"),
        ("idx_soi_salesorder", "sales_order_items", "salesOrder"),
        ("idx_soi_material", "sales_order_items", "material"),
        ("idx_sosl_salesorder", "sales_order_schedule_lines", "salesOrder"),
        ("idx_odh_delivery", "outbound_delivery_headers", "deliveryDocument"),
        ("idx_odi_delivery", "outbound_delivery_items", "deliveryDocument"),
        ("idx_odi_refsd", "outbound_delivery_items", "referenceSdDocument"),
        ("idx_bdh_billing", "billing_document_headers", "billingDocument"),
        ("idx_bdh_soldto", "billing_document_headers", "soldToParty"),
        ("idx_bdh_acctdoc", "billing_document_headers", "accountingDocument"),
        ("idx_bdi_billing", "billing_document_items", "billingDocument"),
        ("idx_bdi_refsd", "billing_document_items", "referenceSdDocument"),
        ("idx_bdi_material", "billing_document_items", "material"),
        ("idx_bdc_billing", "billing_document_cancellations", "billingDocument"),
        ("idx_jeiar_acctdoc", "journal_entry_items_ar", "accountingDocument"),
        ("idx_jeiar_customer", "journal_entry_items_ar", "customer"),
        ("idx_jeiar_refdoc", "journal_entry_items_ar", "referenceDocument"),
        ("idx_par_acctdoc", "payments_ar", "accountingDocument"),
        ("idx_par_customer", "payments_ar", "customer"),
        ("idx_par_salesdoc", "payments_ar", "salesDocument"),
        ("idx_bp_partner", "business_partners", "businessPartner"),
        ("idx_bp_customer", "business_partners", "customer"),
        ("idx_bpa_partner", "business_partner_addresses", "businessPartner"),
        ("idx_cca_customer", "customer_company_assignments", "customer"),
        ("idx_csaa_customer", "customer_sales_area_assignments", "customer"),
        ("idx_prod_product", "products", "product"),
        ("idx_pd_product", "product_descriptions", "product"),
        ("idx_pp_product", "product_plants", "product"),
        ("idx_pp_plant", "product_plants", "plant"),
        ("idx_psl_product", "product_storage_locations", "product"),
        ("idx_psl_plant", "product_storage_locations", "plant"),
        ("idx_plants_plant", "plants", "plant"),
    ]

    for idx_name, table, column in indexes:
        try:
            conn.execute(f'CREATE INDEX IF NOT EXISTS "{idx_name}" ON "{table}" ("{column}")')
        except sqlite3.OperationalError as e:
            print(f"  WARNING: Could not create index {idx_name}: {e}")


def main():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)

    if DB_PATH.exists():
        DB_PATH.unlink()
        print(f"Removed existing database: {DB_PATH}")

    conn = sqlite3.connect(str(DB_PATH))
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")

    print(f"Data directory: {DATA_DIR}")
    print(f"Database: {DB_PATH}\n")

    for dir_name, table_name in TABLE_MAP.items():
        dir_path = DATA_DIR / dir_name
        if not dir_path.exists():
            print(f"  SKIP: {dir_name} (directory not found)")
            continue

        print(f"Processing {dir_name}...")
        records = read_jsonl_dir(dir_path)
        create_table_and_insert(conn, table_name, records)

    print("\nCreating indexes...")
    create_indexes(conn)

    conn.commit()
    conn.close()
    print(f"\nDone! Database created at {DB_PATH}")


if __name__ == "__main__":
    main()
