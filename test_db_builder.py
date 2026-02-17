"""
Test the DB-driven builder by building individual segments and comparing to expected output.
"""
import asyncio
from engine.edi_builder_v2 import DBDrivenEDIBuilder


async def test_segment_structure():
    """Test that we can query segment structure correctly."""
    builder = DBDrivenEDIBuilder()
    await builder.initialize()
    
    try:
        # Test BIG segment structure
        print("=== BIG Segment Structure ===")
        big_structure = await builder.get_segment_structure('BIG', 'X', '004010')
        for elem in big_structure[:10]:  # First 10 elements
            print(f"Pos {elem['position']:2}: {elem['element_id']} - {elem['description']} ({elem['requirement_designator']})")
        
        print("\n=== N1 Segment Structure ===")
        n1_structure = await builder.get_segment_structure('N1', 'X', '004010')
        for elem in n1_structure:
            print(f"Pos {elem['position']:2}: {elem['element_id']} - {elem['description']} ({elem['requirement_designator']})")
        
        print("\n=== IT1 Segment Structure ===")
        it1_structure = await builder.get_segment_structure('IT1', 'X', '004010')
        for elem in it1_structure[:15]:  # First 15 elements
            print(f"Pos {elem['position']:2}: {elem['element_id']} - {elem['description']} ({elem['requirement_designator']})")
        
        print("\n=== LM Segment Structure ===")
        lm_structure = await builder.get_segment_structure('LM', 'X', '004010')
        for elem in lm_structure:
            print(f"Pos {elem['position']:2}: {elem['element_id']} - {elem['description']} ({elem['requirement_designator']})")
        
        print("\n=== LQ Segment Structure ===")
        lq_structure = await builder.get_segment_structure('LQ', 'X', '004010')
        for elem in lq_structure:
            print(f"Pos {elem['position']:2}: {elem['element_id']} - {elem['description']} ({elem['requirement_designator']})")
        
        print("\n=== FA1 Segment Structure ===")
        fa1_structure = await builder.get_segment_structure('FA1', 'X', '004010')
        for elem in fa1_structure:
            print(f"Pos {elem['position']:2}: {elem['element_id']} - {elem['description']} ({elem['requirement_designator']})")
        
        print("\n=== FA2 Segment Structure ===")
        fa2_structure = await builder.get_segment_structure('FA2', 'X', '004010')
        for elem in fa2_structure:
            print(f"Pos {elem['position']:2}: {elem['element_id']} - {elem['description']} ({elem['requirement_designator']})")
        
        print("\n=== CAD Segment Structure ===")
        cad_structure = await builder.get_segment_structure('CAD', 'X', '004010')
        for elem in cad_structure:
            print(f"Pos {elem['position']:2}: {elem['element_id']} - {elem['description']} ({elem['requirement_designator']})")
        
        print("\n=== SAC Segment Structure ===")
        sac_structure = await builder.get_segment_structure('SAC', 'X', '004010')
        for elem in sac_structure[:10]:  # First 10
            print(f"Pos {elem['position']:2}: {elem['element_id']} - {elem['description']} ({elem['requirement_designator']})")
        
    finally:
        await builder.dispose()


async def test_build_segments():
    """Test building individual segments to match boss's output."""
    builder = DBDrivenEDIBuilder()
    await builder.initialize()
    
    try:
        print("\n=== Testing Segment Building ===\n")
        
        # Test BIG segment
        # Expected: BIG*20240827*6GYNT 2*****PP*00
        print("Test BIG segment:")
        big_data = {
            1: '20240827',      # Date
            2: '6GYNT 2',       # Invoice Number
            3: '',              # PO Date
            4: '',              # PO Number
            5: '',              # Release Number
            6: '',              # Change Order Sequence
            7: 'PP',            # Transaction Type Code (prepaid)
            8: '00',            # Transaction Purpose Code
        }
        big_result = await builder.build_segment('BIG', big_data)
        print(f"Result:   {big_result}")
        print(f"Expected: BIG*20240827*6GYNT 2*****PP*00~")
        print()
        
        # Test N1 segment (BT)
        # Expected: N1*BT**10*WWWWWW**TO
        print("Test N1 (BT) segment:")
        n1_bt_data = {
            1: 'BT',            # Entity Identifier Code
            2: '',              # Name
            3: '10',            # Identification Code Qualifier (DODAAC)
            4: 'WWWWWW',        # Identification Code
            5: '',              # Entity Relationship Code
            6: 'TO',            # Entity Identifier Code (Message To)
        }
        n1_bt_result = await builder.build_segment('N1', n1_bt_data)
        print(f"Result:   {n1_bt_result}")
        print(f"Expected: N1*BT**10*WWWWWW**TO~")
        print()
        
        # Test N1 segment (II)
        # Expected: N1*II**M4*AJ2**FR
        print("Test N1 (II) segment:")
        n1_ii_data = {
            1: 'II',            # Entity Identifier Code (Issuer)
            2: '',              # Name
            3: 'M4',            # Identification Code Qualifier
            4: 'AJ2',           # Identification Code
            5: '',              # Entity Relationship Code
            6: 'FR',            # Entity Identifier Code (Message From)
        }
        n1_ii_result = await builder.build_segment('N1', n1_ii_data)
        print(f"Result:   {n1_ii_result}")
        print(f"Expected: N1*II**M4*AJ2**FR~")
        print()
        
        # Test LM segment
        # Expected: LM*DF
        print("Test LM segment:")
        lm_data = {
            1: 'DF',            # Agency Qualifier Code (Department of Defense)
        }
        lm_result = await builder.build_segment('LM', lm_data)
        print(f"Result:   {lm_result}")
        print(f"Expected: LM*DF~")
        print()
        
        # Test LQ segment
        # Expected: LQ*0*FS2
        print("Test LQ segment:")
        lq_data = {
            1: '0',             # Code List Qualifier Code
            2: 'FS2',           # Industry Code
        }
        lq_result = await builder.build_segment('LQ', lq_data)
        print(f"Result:   {lq_result}")
        print(f"Expected: LQ*0*FS2~")
        print()
        
        # Test FA1 segment
        # Expected: FA1*DZ
        print("Test FA1 segment:")
        fa1_data = {
            1: 'DZ',            # Agency Qualifier Code
        }
        fa1_result = await builder.build_segment('FA1', fa1_data)
        print(f"Result:   {fa1_result}")
        print(f"Expected: FA1*DZ~")
        print()
        
        # Test FA2 segment
        # Expected: FA2*58*97X12345678
        print("Test FA2 segment:")
        fa2_data = {
            1: '58',                # Breakdown Structure Detail Code
            2: '97X12345678',       # Financial Information Code
        }
        fa2_result = await builder.build_segment('FA2', fa2_data)
        print(f"Result:   {fa2_result}")
        print(f"Expected: FA2*58*97X12345678~")
        print()
        
        # Test IT1 segment
        # Expected: IT1*1*5*PK*362.34*ST*FS*6515015616204
        print("Test IT1 segment:")
        it1_data = {
            1: '1',                 # Line Item Number
            2: '5',                 # Quantity
            3: 'PK',                # Unit of Measure (Package)
            4: '362.34',            # Unit Price
            5: 'ST',                # Basis of Unit Price (Standard)
            6: 'FS',                # Product ID Qualifier (Federal Supply)
            7: '6515015616204',     # Product ID (NSN without dashes)
        }
        it1_result = await builder.build_segment('IT1', it1_data)
        print(f"Result:   {it1_result}")
        print(f"Expected: IT1*1*5*PK*362.34*ST*FS*6515015616204~")
        print()
        
        # Test CAD segment
        # Expected: CAD*****Z
        print("Test CAD segment:")
        cad_data = {
            1: '',              # Transportation Method Code
            2: '',              # Equipment Initial
            3: '',              # Equipment Number
            4: '',              # Standard Carrier Alpha Code
            5: 'Z',             # Routing
        }
        cad_result = await builder.build_segment('CAD', cad_data)
        print(f"Result:   {cad_result}")
        print(f"Expected: CAD*****Z~")
        print()
        
        # Test SAC segment
        # Expected: SAC*C*D350***181170
        print("Test SAC segment:")
        sac_data = {
            1: 'C',             # Allowance or Charge Indicator (Charge)
            2: 'D350',          # Service/Charge Code
            3: '',              # Agency Qualifier
            4: '',              # Agency Service Code
            5: '181170',        # Amount (in cents)
        }
        sac_result = await builder.build_segment('SAC', sac_data)
        print(f"Result:   {sac_result}")
        print(f"Expected: SAC*C*D350***181170~")
        print()
        
        # Test TDS segment
        # Expected: TDS*181170
        print("Test TDS segment:")
        tds_data = {
            1: '181170',        # Amount
        }
        tds_result = await builder.build_segment('TDS', tds_data)
        print(f"Result:   {tds_result}")
        print(f"Expected: TDS*181170~")
        print()
        
        # Test CTT segment
        # Expected: CTT*1
        print("Test CTT segment:")
        ctt_data = {
            1: '1',             # Number of Line Items
        }
        ctt_result = await builder.build_segment('CTT', ctt_data)
        print(f"Result:   {ctt_result}")
        print(f"Expected: CTT*1~")
        
    finally:
        await builder.dispose()


if __name__ == "__main__":
    print("=" * 70)
    print("Testing DB-Driven EDI Builder")
    print("=" * 70)
    
    asyncio.run(test_segment_structure())
    asyncio.run(test_build_segments())
