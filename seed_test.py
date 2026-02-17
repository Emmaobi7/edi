import asyncio
import uuid
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text
from dotenv import load_dotenv

load_dotenv()
from utils.constants import DATABASE_URL


async def seed():
    engine = create_async_engine(DATABASE_URL)
    doc_id = str(uuid.uuid4())
    
    nl_text = """
Target received an invoice from FreshFoods Ltd for 50 cartons of product code FF99.
Unit price is $25 per carton.
Invoice date is March 20, 2026, and invoice number is INV-12345.
Bill to Target HQ in Minnesota, shipped to Target Warehouse in Texas.
    """.strip()
    
    sender = "TESTNEW"
    
    async with engine.begin() as conn:
        # Clean up old test data first
        await conn.execute(text("""
            DELETE FROM mercury.raw_processed_data 
            WHERE doc_id LIKE (SELECT edi_info_id || '%' FROM mercury.edi_info WHERE interchange_sender = :sender LIMIT 1)
        """), {"sender": sender})
        
        await conn.execute(text("""
            DELETE FROM mercury.edi_info 
            WHERE interchange_sender = :sender
        """), {"sender": sender})
        
        print(f"✓ Cleaned up old test data for sender '{sender}'")
        
        # Insert edi_info record
        await conn.execute(text("""
            INSERT INTO mercury.edi_info 
            (interchange_sender, edi_info_id, type, standard_version, transaction_name)
            VALUES (:sender, :id, 'EDI/X12', '004010', '850')
        """), {"sender": sender, "id": doc_id})
        
        # Insert raw_processed_data record
        await conn.execute(text("""
            INSERT INTO mercury.raw_processed_data (doc_id, raw_data, data_type)
            VALUES (:doc_id, :raw, 'NL')
        """), {"doc_id": f"{doc_id}_NL", "raw": nl_text})
    
    await engine.dispose()
    
    print("=" * 70)
    print("✓ Test data seeded successfully!")
    print("=" * 70)
    print(f"\nUse this payload to test the API:\n")
    print(f'{{"interchange_sender":"{sender}","edi_info_id":"{doc_id}"}}')
    print(f"\nOr run this curl command:\n")
    print(f'curl -X POST http://localhost:8000/convert_text_to_edi \\')
    print(f'  -H "Content-Type: application/json" \\')
    print(f'  -d \'{{"interchange_sender":"{sender}","edi_info_id":"{doc_id}"}}\'')
    print("=" * 70)


if __name__ == "__main__":
    asyncio.run(seed())
