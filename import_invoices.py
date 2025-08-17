import os
import pandas as pd
from datetime import datetime
from sqlalchemy.exc import IntegrityError
from app import app, db, Invoice, InvoiceService
import uuid

def import_excel_to_mysql(excel_path):
    with app.app_context():
        try:
            # Read the Excel file
            df = pd.read_excel(excel_path)
            
            # Drop any rows where 'Invoice Number' is missing
            df.dropna(subset=['Invoice Number'], inplace=True)
            
            # Group data by Invoice Number to handle multiple services per invoice
            invoices = df.groupby('Invoice Number')

            for invoice_number, invoice_group in invoices:
                # Check if the invoice already exists to prevent duplicates
                existing_invoice = Invoice.query.filter_by(invoice_number=invoice_number).first()
                if existing_invoice:
                    print(f"Skipping existing invoice: {invoice_number}")
                    continue
                
                # Get the first row of the group to create the Invoice entry
                first_row = invoice_group.iloc[0]

                # Create the Invoice entry
                invoice_id = str(uuid.uuid4()) # Generate a unique ID for the invoice
                invoice = Invoice(
                    id=invoice_id,
                    invoice_number=invoice_number,
                    customer_name=first_row['Customer Name'].strip(),
                    customer_address=first_row['Customer Address'].strip(),
                    customer_phone=str(first_row['Customer Phone']).strip(),
                    invoice_date=datetime.strptime(first_row['Invoice Date'], '%Y-%m-%d').date(),
                    due_date=datetime.strptime(first_row['Due Date'], '%Y-%m-%d').date(),
                    total_amount=first_row['Total Amount'],
                    advance_amount=first_row['Advance Amount'],
                    due_amount=first_row['Due Amount'],
                    created_at=datetime.utcnow()
                )
                db.session.add(invoice)

                # Now add all the services associated with this invoice
                for index, row in invoice_group.iterrows():
                    service = InvoiceService(
                        invoice_id=invoice_id,
                        description=row['Service Description'],
                        amount=row['Service Amount']
                    )
                    db.session.add(service)

            db.session.commit()
            print("✅ Data imported successfully!")

        except IntegrityError as e:
            db.session.rollback()
            print(f"❌ Database integrity error. Check for duplicate entries. {e}")
        except Exception as e:
            db.session.rollback()
            print(f"❌ An error occurred during import: {e}")
        finally:
            db.session.close()

if __name__ == "__main__":
    # CHANGE THIS TO THE PATH OF YOUR EXCEL FILE
    excel_file_path = "invoices_20250817_164414.xlsx"
    import_excel_to_mysql(excel_file_path)