"""
Test full transaction building with complete extracted data matching boss's invoice.
"""
import asyncio
from engine.edi_builder_v2 import DBDrivenEDIBuilder
from utils.schemas import (
    ExtractedTransaction, LineItem, Party, CodeList, CodePair, FinancialAccounting, FinancialBreakdown,
    CarrierDetail, ServiceCharge, DateReference, Reference
)


async def test_full_810_invoice():
    """Build complete 810 invoice matching boss's output."""
    
    # Create extracted data matching the boss's invoice
    data = ExtractedTransaction(
        transaction_type='810',
        transaction_purpose='00',
        transaction_type_code='PP',  # Prepaid
        invoice_number='6GYNT 2',
        invoice_date='20240827',
        
        # Bill-to party (BT)
        bill_to=Party(
            entity_code='BT',
            id_qualifier='10',  # DODAAC
            identifier='WWWWWW'
        ),
        
        # Issuer party (II)
        issuer=Party(
            entity_code='II',
            id_qualifier='M4',
            identifier='AJ2'
        ),
        
        # Line items
        items=[
            LineItem(
                line_number=1,
                quantity=5.0,
                unit_of_measure='PK',
                unit_price=362.34,
                nsn='6515-01-561-6204',
                extended_amount=1811.70
            )
        ],
        
        # Code lists (LM/LQ)
        code_lists=[
            CodeList(
                agency_code='DF',  # Department of Defense
                codes=[
                    CodePair(qualifier='0', industry_code='FS2')
                ]
            )
        ],
        
        # Financial accounting (FA1/FA2)
        financial_accounting=FinancialAccounting(
            agency_code='DZ',
            breakdown_codes=[
                FinancialBreakdown(breakdown_code='58', financial_code='97X12345678'),
                FinancialBreakdown(breakdown_code='18', financial_code='2142020')
            ]
        ),
        
        # References
        references=[
            Reference(
                qualifier='TN',
                identifier='WWWWWW42290001'
            )
        ],
        
        # Dates
        dates=[
            DateReference(
                qualifier='168',  # Service date
                date_value='20240827'
            )
        ],
        
        # Carrier detail
        carrier_detail=CarrierDetail(
            routing='Z'
        ),
        
        # Service charges
        service_charges=[
            ServiceCharge(
                indicator='C',  # Charge
                code='D350',
                amount=1811.70
            )
        ],
        
        total_amount=1811.70,
        number_of_line_items=1
    )
    
    # Build the transaction
    builder = DBDrivenEDIBuilder()
    await builder.initialize()
    
    try:
        segments = await builder.build_transaction(data)
        
        # Expected output from boss
        expected = [
            "BIG*20240827*6GYNT 2*****PP*00",
            "N1*BT**10*WWWWWW**TO",
            "N1*II**M4*AJ2**FR",
            "N1*II**10",
            "LM*DF",
            "LQ*0*FS2",
            "FA1*DZ",
            "FA2*58*97X12345678",
            "FA2*18*2142020",
            "IT1*1*5*PK*362.34*ST*FS*6515015616204",
            "REF*TN*WWWWWW42290001",
            "DTM*168*20240827",
            "CAD*****Z",
            "SAC*C*D350***181170",
            # "LM*DF",  # Second LM block - needs more context
            # "LQ*0*FA2",
            # "LQ*DE*J",
            # "LQ*DG*7G",
            # "LQ*A9*WQQQQQ",
            "TDS*181170",
            "CTT*1"
        ]
        
        print("=" * 70)
        print("GENERATED EDI SEGMENTS:")
        print("=" * 70)
        for i, seg in enumerate(segments, 1):
            print(f"{i:2}. {seg}")
        
        print("\n" + "=" * 70)
        print("EXPECTED EDI SEGMENTS (from boss):")
        print("=" * 70)
        for i, seg in enumerate(expected, 1):
            print(f"{i:2}. {seg}~")
        
        print("\n" + "=" * 70)
        print("COMPARISON:")
        print("=" * 70)
        
        # Compare each segment
        matches = 0
        for i, (gen, exp) in enumerate(zip(segments, expected), 1):
            gen_clean = gen.rstrip('~')
            exp_clean = exp.rstrip('~')
            match = "✓" if gen_clean == exp_clean else "✗"
            print(f"{i:2}. {match} {gen_clean}")
            if gen_clean == exp_clean:
                matches += 1
            else:
                print(f"     Expected: {exp_clean}")
        
        print("\n" + "=" * 70)
        print(f"RESULT: {matches}/{len(expected)} segments match")
        print("=" * 70)
        
    finally:
        await builder.dispose()


if __name__ == "__main__":
    asyncio.run(test_full_810_invoice())
