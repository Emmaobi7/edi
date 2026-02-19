import asyncio
import uuid
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text
from dotenv import load_dotenv

load_dotenv()
from utils.constants import DATABASE_URL


async def seed(transaction_type='850'):
    """
    Seed test data for EDI conversion

    Args:
        transaction_type: '850' for Purchase Order or '810' for Invoice
    """
    engine = create_async_engine(DATABASE_URL)
    doc_id = str(uuid.uuid4())

    # Sample texts for different transaction types
    text_850 = """
On Thursday, February 22, 2024, at 8:08 AM, an EDI X12 interchange was received by 6303207447 from 925485US00. The interchange carried control number 850100160 and was identified as production data. No interchange acknowledgment was requested. Within this interchange, a functional group built according to the ASC X12 version 005010 standard was transmitted. The group contained a single transaction set identified as an 850 Purchase Order, with transaction set control number 108794.

The purchase order was issued as an original, stand-alone order dated February 22, 2024, and was assigned purchase order number 4780904642. The buyer on the order is WAL-MART DC 7026, located at 945 Highway 138 in Grantsville, with GLN 0078742050690. The supplier listed on the order is Winland Foods, Inc.

The order includes department number 00092 and merchandise type code 0020. It references a promotion or deal identified as POS REPLEN, an internal vendor number 434291921, and an associated purchase order reference 01-196. The shipment terms are collect, with routing instructions directing the shipper to call 4792734300#. The order specifies that there should be no preticketing.

The shipping window indicates that the goods must not ship before February 29, 2024, must ship no later than February 29, 2024, and must not be delivered after March 7, 2024. Payment terms provide a 2 percent discount if payment is made within 20 days of receipt of goods, with the net amount due in 35 days. The order also includes off-invoice allowances, consisting of an unsaleable merchandise allowance of $41.33, representing 0.47 percent, and a warehouse allowance of $87.95, representing 1 percent.

Two line items are included in the purchase order. The first line item requests 220 cases at a unit price of $26.63, for a total of $5,858.60. It references buyer item number 551228839, vendor item number 473044M1367, GTIN 50078742050282, a size of 70 ounces, and a pack of 6. The second line item requests 110 cases at a unit price of $26.69, for a total of $2,935.90. It references buyer item number 551228840, vendor item number 473045M1367, GTIN 50078742050534, a size of 70 ounces, and a pack of 6.

In total, the purchase order contains two line items with a combined gross value of $8,794.50. The transaction concludes with 34 included segments, confirming that one purchase order was transmitted within a single functional group and a single interchange.


    """.strip()

    text_810 = """
Target received an invoice from FreshFoods Ltd for 50 cartons of product code FF99.
Unit price is $25 per carton.
Invoice date is March 20, 2026, and invoice number is INV-12345.
Bill to Target HQ in Minnesota, shipped to Target Warehouse in Texas.
    """.strip()

    # Select the appropriate text based on transaction type
    if transaction_type == '810':
        nl_text = text_810
    else:
        nl_text = text_850

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

        # Insert edi_info record with the specified transaction type
        await conn.execute(text("""
            INSERT INTO mercury.edi_info
            (interchange_sender, edi_info_id, type, standard_version, transaction_name)
            VALUES (:sender, :id, 'EDI/X12', '004010', :transaction_type)
        """), {"sender": sender, "id": doc_id, "transaction_type": transaction_type})

        # Insert raw_processed_data record
        await conn.execute(text("""
            INSERT INTO mercury.raw_processed_data (doc_id, raw_data, data_type)
            VALUES (:doc_id, :raw, 'NL')
        """), {"doc_id": f"{doc_id}_NL", "raw": nl_text})
    
    await engine.dispose()

    print("=" * 70)
    print(f"✓ Test data seeded successfully! (Transaction Type: {transaction_type})")
    print("=" * 70)
    print(f"\nUse this payload to test the V2 API:\n")
    print(f'{{"interchange_sender":"{sender}","edi_info_id":"{doc_id}"}}')
    print(f"\nOr run this curl command:\n")
    print(f'curl -X POST http://localhost:8000/convert_text_to_edi_v2 \\')
    print(f'  -H "Content-Type: application/json" \\')
    print(f'  -d \'{{"interchange_sender":"{sender}","edi_info_id":"{doc_id}"}}\'')
    print("=" * 70)


if __name__ == "__main__":
    import sys
    # Allow passing transaction type as argument: python seed_test.py 810
    trans_type = sys.argv[1] if len(sys.argv) > 1 else '850'
    asyncio.run(seed(trans_type))
