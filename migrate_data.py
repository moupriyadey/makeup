import os
import pandas as pd
from sqlalchemy import create_engine
from app import Booking, Invoice, InvoiceService, db as local_db

# Configuration
LOCAL_MYSQL_URI = 'mysql+pymysql://root:15416761@localhost/mou_makeup_db'
SUPABASE_POSTGRES_URI = 'postgresql://postgres:15416761@db.nhjwjkficlnfuiujjrdc.supabase.co:5432/postgres'

def migrate_data():
    try:
        # Create engine for local MySQL database
        local_engine = create_engine(LOCAL_MYSQL_URI)

        # Create engine for remote Supabase database
        supabase_engine = create_engine(SUPABASE_POSTGRES_URI)

        # Connect to local database
        with local_engine.connect() as local_conn:
            print("Connected to local MySQL database. Starting data migration...")

            # --- Migrate Booking table ---
            booking_df = pd.read_sql_table('booking', local_conn)
            booking_df.to_sql('booking', supabase_engine, if_exists='append', index=False)
            print("✅ Booking table migrated.")

            # --- Migrate Invoice table ---
            invoice_df = pd.read_sql_table('invoice', local_conn)
            invoice_df.to_sql('invoice', supabase_engine, if_exists='append', index=False)
            print("✅ Invoice table migrated.")

            # --- Migrate InvoiceService table ---
            invoiceservice_df = pd.read_sql_table('invoice_service', local_conn)
            invoiceservice_df.to_sql('invoice_service', supabase_engine, if_exists='append', index=False)
            print("✅ InvoiceService table migrated.")

            print("\n🎉 All data migrated successfully!")

    except Exception as e:
        print(f"❌ An error occurred during migration: {e}")

if __name__ == "__main__":
    migrate_data()