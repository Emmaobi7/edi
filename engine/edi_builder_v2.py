"""
DB-driven EDI builder that dynamically constructs segments based on mercury schema.
Uses elementusagedefs and segmentusage tables to build accurate EDI expressions.
"""
from typing import Dict, List, Optional, Any
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text
from utils.schemas import ExtractedTransaction
from utils.constants import DATABASE_URL


class DBDrivenEDIBuilder:
    """Builds EDI segments by querying DB for structure and rules."""
    
    def __init__(self):
        self.engine = None
        self.segment_cache = {}
        self.element_cache = {}
    
    async def initialize(self):
        """Create async engine for DB queries."""
        if not self.engine:
            self.engine = create_async_engine(
                DATABASE_URL,
                echo=False,
                pool_pre_ping=True,
                pool_recycle=3600
            )
    
    async def dispose(self):
        """Clean up engine connection."""
        if self.engine:
            await self.engine.dispose()
            self.engine = None
    
    async def get_segment_structure(self, segment_id: str, agency: str = 'X', version: str = '004010') -> List[Dict]:
        """
        Get element structure for a segment from elementusagedefs table.
        Returns list of elements in position order with metadata.
        """
        cache_key = f"{segment_id}_{agency}_{version}"
        if cache_key in self.element_cache:
            return self.element_cache[cache_key]
        
        async with self.engine.begin() as conn:
            # Try custom table first
            result = await conn.execute(text("""
                SELECT position, element_id, description, requirement_designator, 
                       type, minimum_length, maximum_length, composite_element
                FROM mercury.custom_elementusagedefs 
                WHERE segment_id=:seg AND agency=:agency AND version=:version
                ORDER BY position ASC
            """), {"seg": segment_id, "agency": agency, "version": version})
            
            rows = result.fetchall()
            
            # Fallback to base table if custom not found
            if not rows:
                result = await conn.execute(text("""
                    SELECT position, element_id, description, requirement_designator, 
                           type, minimum_length, maximum_length, composite_element
                    FROM mercury.elementusagedefs 
                    WHERE segment_id=:seg AND agency=:agency AND version=:version
                    ORDER BY position ASC
                """), {"seg": segment_id, "agency": agency, "version": version})
                rows = result.fetchall()
            
            elements = [dict(r._mapping) for r in rows]
            self.element_cache[cache_key] = elements
            return elements
    
    async def get_transaction_segments(self, transaction_id: str, agency: str = 'X', version: str = '004010') -> List[Dict]:
        """
        Get ordered list of segments for a transaction from segmentusage table.
        Returns segments in position order with usage metadata.
        """
        cache_key = f"{transaction_id}_{agency}_{version}"
        if cache_key in self.segment_cache:
            return self.segment_cache[cache_key]
        
        async with self.engine.begin() as conn:
            # Try custom table first
            result = await conn.execute(text("""
                SELECT position, segmentid, requirementdesignator, maximumusage, 
                       maximumlooprepeat, loopid, section
                FROM mercury.custom_segmentusage 
                WHERE transactionsetid=:txn AND agency=:agency AND version=:version
                ORDER BY position ASC
            """), {"txn": transaction_id, "agency": agency, "version": version})
            
            rows = result.fetchall()
            
            # Fallback to base table
            if not rows:
                result = await conn.execute(text("""
                    SELECT position, segmentid, requirementdesignator, maximumusage, 
                           maximumlooprepeat, loopid, section
                    FROM mercury.segmentusage 
                    WHERE transactionsetid=:txn AND agency=:agency AND version=:version
                    ORDER BY position ASC
                """), {"txn": transaction_id, "agency": agency, "version": version})
                rows = result.fetchall()
            
            segments = [dict(r._mapping) for r in rows]
            self.segment_cache[cache_key] = segments
            return segments
    
    def _format_element(self, value: Any, element_spec: Dict) -> str:
        """Format a single element value according to its specification."""
        if value is None or value == "":
            return ""
        
        # Convert to string
        value_str = str(value)
        
        # Handle date formatting (DT type should be YYYYMMDD)
        if element_spec['type'] == 'DT' and len(value_str) == 8:
            return value_str
        
        # Handle numeric types
        if element_spec['type'] in ('N0', 'N2', 'R'):
            # For whole numbers, remove decimal point
            if isinstance(value, float) and value.is_integer():
                value_str = str(int(value))
            elif element_spec['type'] == 'N0':
                value_str = value_str.replace('.', '')
            return value_str
        
        # Truncate to max length if needed
        max_len = element_spec['maximum_length']
        if len(value_str) > max_len:
            value_str = value_str[:max_len]
        
        return value_str
    
    async def build_segment(self, segment_id: str, data_map: Dict[int, Any], 
                           agency: str = 'X', version: str = '004010') -> str:
        """
        Build a segment dynamically based on DB structure.
        
        Args:
            segment_id: Segment identifier (e.g., 'BIG', 'N1', 'IT1')
            data_map: Dict mapping position number to value
            agency: Agency code (default 'X')
            version: EDI version (default '004010')
        
        Returns:
            Formatted EDI segment string with element separator
        """
        structure = await self.get_segment_structure(segment_id, agency, version)
        
        if not structure:
            raise ValueError(f"No structure found for segment {segment_id}")
        
        # Start with segment ID
        parts = [segment_id]
        
        # Build elements in position order
        max_position = structure[-1]['position']
        
        for pos in range(1, max_position + 1):
            # Find element spec for this position
            element_spec = next((e for e in structure if e['position'] == pos), None)
            
            if not element_spec:
                # No spec for this position, leave empty
                parts.append("")
                continue
            
            # Get value from data map
            value = data_map.get(pos)
            
            # Check if required
            is_required = element_spec['requirement_designator'] == 'M'
            
            if value is None or value == "":
                if is_required:
                    # Required but missing - this is an error but we'll add empty
                    parts.append("")
                else:
                    # Optional and missing - add empty
                    parts.append("")
            else:
                # Format and add the value
                formatted = self._format_element(value, element_spec)
                parts.append(formatted)
        
        # Remove trailing empty elements
        while len(parts) > 1 and parts[-1] == "":
            parts.pop()
        
        return "*".join(parts) + "~"
    
    async def build_transaction(self, data: ExtractedTransaction, 
                               agency: str = 'X', version: str = '004010') -> List[str]:
        """
        Build complete EDI transaction from extracted data.
        Routes to transaction-specific builder based on type.
        
        Returns:
            List of EDI segment strings
        """
        transaction_id = data.transaction_type
        
        if transaction_id == '810':
            return await self._build_810_transaction(data, agency, version)
        elif transaction_id == '850':
            return await self._build_850_transaction(data, agency, version)
        else:
            raise ValueError(f"Unsupported transaction type: {transaction_id}")
    
    async def _build_810_transaction(self, data: ExtractedTransaction, 
                                     agency: str, version: str) -> List[str]:
        """Build 810 Invoice transaction - data-driven based on what exists."""
        segments = []
        
        # BIG - Beginning segment for invoice
        big_seg = await self._build_BIG(data, agency, version)
        if big_seg:
            segments.append(big_seg)
        
        # N1 loops - data-driven (handles BT/II/II or RE/BT/ST patterns)
        n1_segs = await self._build_N1_loops_810(data, agency, version)
        segments.extend(n1_segs)
        
        # LM/LQ - Code source information (before IT1 in DoD pattern)
        lm_segs = await self._build_LM_loops(data, agency, version)
        segments.extend(lm_segs)
        
        # FA1/FA2 - Financial accounting (after LM, before IT1 in DoD pattern)
        fa_segs = await self._build_FA_loops(data, agency, version)
        segments.extend(fa_segs)
        
        # IT1 - Line items (data-driven for NSN vs BP/VP structure)
        it1_segs = await self._build_IT1_loops(data, agency, version)
        segments.extend(it1_segs)
        
        # REF - Reference identification (after IT1)
        ref_segs = await self._build_REF_loops(data, agency, version)
        segments.extend(ref_segs)
        
        # DTM - Date/time reference
        dtm_segs = await self._build_DTM_loops(data, agency, version)
        segments.extend(dtm_segs)
        
        # ITD - Payment terms (only if present)
        if data.payment_terms:
            itd_seg = await self._build_ITD(data, agency, version)
            if itd_seg:
                segments.append(itd_seg)
        
        # Carrier - CAD if carrier_detail exists, TD5 if carrier_info exists
        if data.carrier_detail:
            cad_seg = await self._build_CAD(data, agency, version)
            if cad_seg:
                segments.append(cad_seg)
        elif data.carrier_info:
            td5_seg = await self._build_TD5(data, agency, version)
            if td5_seg:
                segments.append(td5_seg)
        
        # SAC - Service charges
        sac_segs = await self._build_SAC_loops(data, agency, version)
        segments.extend(sac_segs)
        
        # Second LM/LQ block (after SAC in DoD pattern)
        lm_segs_2 = await self._build_LM_loops_2(data, agency, version)
        segments.extend(lm_segs_2)
        
        # TDS - Final total monetary value
        tds_seg = await self._build_TDS(data, agency, version)
        if tds_seg:
            segments.append(tds_seg)
        
        # CTT - Transaction totals
        ctt_seg = await self._build_CTT(data, agency, version)
        if ctt_seg:
            segments.append(ctt_seg)
        
        return segments
    
    async def _build_850_transaction(self, data: ExtractedTransaction,
                                     agency: str, version: str) -> List[str]:
        """Build 850 Purchase Order transaction."""
        segments = []

        # BEG - Beginning segment for PO
        beg_seg = await self._build_BEG(data, agency, version)
        if beg_seg:
            segments.append(beg_seg)

        # CUR - Currency (always include, defaults to USD)
        cur_seg = await self._build_CUR(data, agency, version)
        if cur_seg:
            segments.append(cur_seg)

        # REF - Reference identification
        ref_segs = await self._build_REF_loops(data, agency, version)
        segments.extend(ref_segs)

        # FOB - Shipping terms (if present)
        if data.fob_terms:
            fob_seg = await self._build_FOB(data, agency, version)
            if fob_seg:
                segments.append(fob_seg)

        # SAC - Service charges/allowances (if present)
        if data.service_charges:
            sac_segs = await self._build_SAC_loops(data, agency, version)
            segments.extend(sac_segs)

        # ITD - Payment terms (if present)
        if data.payment_terms:
            itd_seg = await self._build_ITD(data, agency, version)
            if itd_seg:
                segments.append(itd_seg)

        # DTM - Date/time reference
        dtm_segs = await self._build_DTM_loops(data, agency, version)
        segments.extend(dtm_segs)

        # TD5 - Carrier details (if present)
        if data.carrier_info:
            td5_seg = await self._build_TD5(data, agency, version)
            if td5_seg:
                segments.append(td5_seg)

        # N9/MTX - Special instructions and notes (if present)
        if data.special_instructions:
            n9_mtx_segs = await self._build_N9_MTX_loops(data, agency, version)
            segments.extend(n9_mtx_segs)

        # N1 loops - parties in specific order for 850: BY, SE, BT, ST, SF
        n1_segs = await self._build_N1_loops_850(data, agency, version)
        segments.extend(n1_segs)

        # PO1 - Line items (includes PO4 and AMT for each item)
        po1_segs = await self._build_PO1_loops(data, agency, version)
        segments.extend(po1_segs)

        # CTT - Transaction totals
        ctt_seg = await self._build_CTT(data, agency, version)
        if ctt_seg:
            segments.append(ctt_seg)

        # AMT - Total amount (if present)
        if data.total_amount:
            amt_seg = await self._build_AMT_total(data, agency, version)
            if amt_seg:
                segments.append(amt_seg)

        return segments
    
    async def _build_BIG(self, data: ExtractedTransaction, agency: str, version: str) -> str:
        """Build BIG (Beginning Segment for Invoice) segment."""
        data_map = {
            1: data.invoice_date,  # Date
            2: data.invoice_number,  # Invoice Number
            3: data.po_date,  # Purchase Order Date (optional)
            4: data.po_number,  # Purchase Order Number (optional)
            5: None,  # Release Number
            6: None,  # Change Order Sequence Number
            7: data.transaction_type_code,  # Transaction Type Code (PP for prepaid)
            8: data.transaction_purpose,  # Transaction Set Purpose Code
            9: None,  # Action Code
        }
        return await self.build_segment('BIG', data_map, agency, version)
    
    async def _build_BEG(self, data: ExtractedTransaction, agency: str, version: str) -> str:
        """Build BEG (Beginning Segment for Purchase Order) segment."""
        data_map = {
            1: data.transaction_purpose,  # Transaction Set Purpose Code (00=Original)
            2: data.transaction_type_code or 'NE',  # Purchase Order Type (NE=New Order)
            3: data.po_number,  # Purchase Order Number
            4: None,  # Release Number
            5: data.po_date,  # Date
        }
        return await self.build_segment('BEG', data_map, agency, version)
    
    async def _build_N1_loops_810(self, data: ExtractedTransaction, agency: str, version: str) -> List[str]:
        """Build N1 loops for 810 invoices - data-driven based on what parties exist."""
        segments = []
        
        # Map contacts by function code
        contact_map = {}
        for contact in data.contacts:
            contact_map[contact.function_code] = contact
        
        # Determine party structure based on what exists
        # Pattern 1: BT + II (DoD style) - bill_to and issuer exist
        # Pattern 2: RE + BT + ST (commercial style) - remit_to, bill_to, ship_to exist
        
        if data.bill_to:
            # BT - Bill-to party with TO message indicator if no addresses
            n1_data = {
                1: 'BT',
                2: data.bill_to.name,
                3: data.bill_to.id_qualifier,
                4: data.bill_to.identifier,
            }
            # Add TO indicator if no address data (DoD pattern)
            if not data.bill_to_address:
                n1_data[6] = 'TO'
            segments.append(await self.build_segment('N1', n1_data, agency, version))
            
            # Address if present
            if data.bill_to_address:
                if data.bill_to_address.street_line_1 or data.bill_to_address.street_line_2:
                    segments.append(await self.build_segment('N3', {
                        1: data.bill_to_address.street_line_1,
                        2: data.bill_to_address.street_line_2,
                    }, agency, version))
                if data.bill_to_address.city or data.bill_to_address.state:
                    segments.append(await self.build_segment('N4', {
                        1: data.bill_to_address.city,
                        2: data.bill_to_address.state,
                        3: data.bill_to_address.postal_code,
                        4: data.bill_to_address.country_code,
                    }, agency, version))
            
            # Contact for BT (BD function code)
            if 'BD' in contact_map:
                segments.append(await self._build_PER_segment(contact_map['BD'], agency, version))
        
        # II - Issuer party (DoD pattern) with FR message indicator
        if data.issuer:
            n1_data = {
                1: 'II',
                2: data.issuer.name,
                3: data.issuer.id_qualifier,
                4: data.issuer.identifier,
            }
            # Add FR indicator if no name (DoD pattern)
            if not data.issuer.name:
                n1_data[6] = 'FR'
            segments.append(await self.build_segment('N1', n1_data, agency, version))
            
            # Second II with different qualifier (DoD pattern)
            if data.bill_to:  # Only if BT exists
                segments.append(await self.build_segment('N1', {
                    1: 'II',
                    2: None,
                    3: '10',  # DODAAC
                    4: None,
                }, agency, version))
        
        # RE - Remit-to party (commercial pattern)
        if data.remit_to and not data.issuer:  # Only if not using II pattern
            n1_data = {
                1: 'RE',
                2: data.remit_to.name,
                3: data.remit_to.id_qualifier,
                4: data.remit_to.identifier,
            }
            segments.append(await self.build_segment('N1', n1_data, agency, version))
            
            # Address and contact for RE
            if data.remit_to_address:
                if data.remit_to_address.street_line_1 or data.remit_to_address.street_line_2:
                    segments.append(await self.build_segment('N3', {
                        1: data.remit_to_address.street_line_1,
                        2: data.remit_to_address.street_line_2,
                    }, agency, version))
                if data.remit_to_address.city or data.remit_to_address.state:
                    segments.append(await self.build_segment('N4', {
                        1: data.remit_to_address.city,
                        2: data.remit_to_address.state,
                        3: data.remit_to_address.postal_code,
                        4: data.remit_to_address.country_code,
                    }, agency, version))
            
            if 'AP' in contact_map:
                segments.append(await self._build_PER_segment(contact_map['AP'], agency, version))
        
        # ST - Ship-to party (commercial pattern)
        if data.ship_to and not data.issuer:  # Only if not using II pattern
            n1_data = {
                1: 'ST',
                2: data.ship_to.name,
                3: data.ship_to.id_qualifier,
                4: data.ship_to.identifier,
            }
            segments.append(await self.build_segment('N1', n1_data, agency, version))
            
            # Address and contact for ST
            if data.ship_to_address:
                if data.ship_to_address.street_line_1 or data.ship_to_address.street_line_2:
                    segments.append(await self.build_segment('N3', {
                        1: data.ship_to_address.street_line_1,
                        2: data.ship_to_address.street_line_2,
                    }, agency, version))
                if data.ship_to_address.city or data.ship_to_address.state:
                    segments.append(await self.build_segment('N4', {
                        1: data.ship_to_address.city,
                        2: data.ship_to_address.state,
                        3: data.ship_to_address.postal_code,
                        4: data.ship_to_address.country_code,
                    }, agency, version))
            
            if 'SR' in contact_map:
                segments.append(await self._build_PER_segment(contact_map['SR'], agency, version))
        
        return segments
    
    async def _build_PER_segment(self, contact, agency: str, version: str) -> str:
        """Build a single PER segment from contact data."""
        per_data = {1: contact.function_code, 2: contact.name}
        pos = 3
        if contact.phone:
            per_data[pos] = 'TE'
            per_data[pos + 1] = contact.phone
            pos += 2
        if contact.email:
            per_data[pos] = 'EM'
            per_data[pos + 1] = contact.email
            pos += 2
        if contact.fax:
            per_data[pos] = 'FX'
            per_data[pos + 1] = contact.fax
        return await self.build_segment('PER', per_data, agency, version)
    
    async def _build_N1_loops_850(self, data: ExtractedTransaction, agency: str, version: str) -> List[str]:
        """Build N1 loops for 850 purchase orders in standard hierarchy."""
        segments = []
        
        # Standard 850 N1 hierarchy: BY → SE → BT → ST → SF
        n1_hierarchy = [
            ('BY', data.buyer, data.buyer_address),
            ('SE', data.seller, data.seller_address),
            ('BT', data.bill_to, data.bill_to_address),
            ('ST', data.ship_to, data.ship_to_address),
            ('SF', data.ship_from, None)
        ]
        
        for entity_code, party, address in n1_hierarchy:
            if party:
                # N1 segment
                n1_data = {
                    1: entity_code,
                    2: party.name,
                    3: party.id_qualifier,
                    4: party.identifier,
                }
                segments.append(await self.build_segment('N1', n1_data, agency, version))
                
                # N3 segment (address lines) if address present
                if address and (address.street_line_1 or address.street_line_2):
                    n3_data = {
                        1: address.street_line_1,
                        2: address.street_line_2,
                    }
                    segments.append(await self.build_segment('N3', n3_data, agency, version))
                
                # N4 segment (city/state/zip) if address present
                if address and (address.city or address.state or address.postal_code):
                    n4_data = {
                        1: address.city,
                        2: address.state,
                        3: address.postal_code,
                        4: address.country_code,
                    }
                    segments.append(await self.build_segment('N4', n4_data, agency, version))
        
        return segments
    
    async def _build_LM_loops(self, data: ExtractedTransaction, agency: str, version: str) -> List[str]:
        """Build LM/LQ loops from code_lists (skip empty code lists)."""
        segments = []
        
        if not data.code_lists:
            return segments
        
        for code_list in data.code_lists:
            # Skip code lists with no codes
            if not code_list.codes:
                continue
            
            # LM segment
            lm_data = {
                1: code_list.agency_code,  # DF for DoD
                2: code_list.source_subqualifier,
            }
            segments.append(await self.build_segment('LM', lm_data, agency, version))
            
            # LQ segments for each code
            for code_pair in code_list.codes:
                lq_data = {
                    1: code_pair.qualifier,  # '0' for example
                    2: code_pair.industry_code,  # 'FS2' for example
                }
                segments.append(await self.build_segment('LQ', lq_data, agency, version))
        
        return segments
    
    async def _build_FA_loops(self, data: ExtractedTransaction, agency: str, version: str) -> List[str]:
        """Build FA1/FA2 loops from financial_accounting."""
        segments = []
        
        if not data.financial_accounting or not data.financial_accounting.breakdown_codes:
            return segments
        
        # FA1 segment - always emit if FA2 exists, default to DZ
        fa1_data = {
            1: data.financial_accounting.agency_code or 'DZ',
        }
        segments.append(await self.build_segment('FA1', fa1_data, agency, version))
        
        # FA2 segments
        for breakdown in data.financial_accounting.breakdown_codes:
            fa2_data = {
                1: breakdown.breakdown_code,  # '58', '18'
                2: breakdown.financial_code,  # '97X12345678', '2142020'
            }
            segments.append(await self.build_segment('FA2', fa2_data, agency, version))
        
        return segments
    
    async def _build_IT1_loops(self, data: ExtractedTransaction, agency: str, version: str) -> List[str]:
        """Build IT1 line item segments - data-driven based on what IDs are present."""
        segments = []
        
        for item in data.items:
            it1_data = {
                1: item.line_number,
                2: item.quantity,
                3: item.unit_of_measure,
                4: item.unit_price,
                5: 'ST' if item.nsn and not item.buyer_part_number else None,  # Basis only if NSN primary
            }
            
            # Pattern 1: NSN exists and is primary (DoD pattern) - use FS qualifier
            if item.nsn and not item.buyer_part_number:
                # Remove dashes from NSN for FS qualifier
                nsn_clean = item.nsn.replace('-', '')
                it1_data[6] = 'FS'  # Federal Supply
                it1_data[7] = nsn_clean
            
            # Pattern 2: Buyer part exists (commercial pattern) - BP primary, VP/N4 secondary
            elif item.buyer_part_number:
                it1_data[6] = 'BP'
                it1_data[7] = item.buyer_part_number
                
                # Add vendor part if present
                if item.vendor_part_number:
                    it1_data[8] = 'VP'
                    it1_data[9] = item.vendor_part_number
                
                # Add NSN/NDC if present (with dashes)
                if item.nsn:
                    it1_data[10] = 'N4'
                    it1_data[11] = item.nsn
            
            # Pattern 3: Only item_id exists
            elif item.item_id:
                it1_data[6] = 'FS'
                it1_data[7] = item.item_id
            
            segments.append(await self.build_segment('IT1', it1_data, agency, version))
        
        return segments
    
    async def _build_PO1_loops(self, data: ExtractedTransaction, agency: str, version: str) -> List[str]:
        """Build PO1 line item segments for purchase orders."""
        segments = []

        for item in data.items:
            # For CANCELLED items, set quantity to 0
            quantity = 0 if item.status == 'CANCELLED' else item.quantity

            # Use product_id_qualifier if provided, otherwise default to appropriate type
            id_qualifier = item.product_id_qualifier or 'BP'  # BP = Buyer's Part Number
            product_id = item.nsn or item.item_id

            po1_data = {
                1: item.line_number,
                2: quantity,
                3: item.unit_of_measure,
                4: item.unit_price,
                5: None,  # Basis of Unit Price Code
                6: id_qualifier,  # Product ID Qualifier
                7: product_id,  # Product ID
            }
            segments.append(await self.build_segment('PO1', po1_data, agency, version))

            # Add PID segment for description if present
            if item.item_description:
                pid_data = {
                    1: 'F',  # Item Description Type (F=Free-form)
                    2: None,  # Product/Process Characteristic Code
                    3: None,  # Agency Qualifier Code
                    4: None,  # Product Description Code
                    5: item.item_description,  # Description
                }
                segments.append(await self.build_segment('PID', pid_data, agency, version))

            # Add PO4 segment for pack size if present
            if item.pack_size:
                po4_data = {
                    1: item.pack_size,  # Pack size
                }
                segments.append(await self.build_segment('PO4', po4_data, agency, version))

            # Add AMT segment for line amount if present
            if item.extended_amount:
                amt_data = {
                    1: '1',  # 1 = Line Item Total
                    2: item.extended_amount,
                }
                segments.append(await self.build_segment('AMT', amt_data, agency, version))

        return segments
    
    async def _build_REF_loops(self, data: ExtractedTransaction, agency: str, version: str) -> List[str]:
        """Build REF reference segments for all reference types."""
        segments = []
        
        for ref in data.references:
            ref_data = {
                1: ref.qualifier,  # PO, CN, TN, etc.
                2: ref.identifier,
                # Note: position 3 (description) is omitted per X12 spec
            }
            segments.append(await self.build_segment('REF', ref_data, agency, version))
        
        return segments
    
    async def _build_REF_carrier(self, data: ExtractedTransaction, agency: str, version: str) -> Optional[str]:
        """Build REF segment for carrier tracking number from references list."""
        # Look for CN qualifier in references list
        for ref in data.references:
            if ref.qualifier == 'CN':
                ref_data = {
                    1: 'CN',  # Carrier's Reference Number (Tracking)
                    2: ref.identifier,
                    3: ref.description,
                }
                return await self.build_segment('REF', ref_data, agency, version)
        return None
    
    async def _build_ITD(self, data: ExtractedTransaction, agency: str, version: str) -> Optional[str]:
        """Build ITD (Terms of Sale/Deferred Terms of Sale) segment."""
        if not data.payment_terms:
            return None
        
        terms = data.payment_terms
        itd_data = {
            1: terms.terms_type or '01',  # 01=Basic, 05=Discount Not Applicable
            2: '3' if terms.discount_percent else None,  # 3=Invoice Date
            3: terms.discount_percent,  # Discount %
            4: terms.discount_due_days,  # Days from invoice date for discount
            5: None,  # Discount Due Date (YYYYMMDD)
            6: terms.net_due_days,  # Net Days
            7: terms.due_date,  # Net Due Date (YYYYMMDD)
        }
        return await self.build_segment('ITD', itd_data, agency, version)
    
    async def _build_TD5(self, data: ExtractedTransaction, agency: str, version: str) -> Optional[str]:
        """Build TD5 (Carrier Details - Routing Sequence) segment."""
        if not data.carrier_info:
            return None
        
        carrier = data.carrier_info
        td5_data = {
            1: carrier.routing_sequence or 'O',  # O=Origin (Shippers' Routing)
            2: carrier.id_qualifier or '2',  # 2=SCAC (Standard Carrier Alpha Code)
            3: carrier.id_code,  # FDXG for FedEx Ground
            4: carrier.transport_method or 'M',  # M=Motor (Common Carrier)
            5: carrier.routing,  # "Federal Express Ground"
        }
        return await self.build_segment('TD5', td5_data, agency, version)
    
    async def _build_DTM_loops(self, data: ExtractedTransaction, agency: str, version: str) -> List[str]:
        """Build DTM date segments for all dates."""
        segments = []
        
        for dt in data.dates:
            dtm_data = {
                1: dt.qualifier,
                2: dt.date_value,
                3: dt.time_value,
            }
            segments.append(await self.build_segment('DTM', dtm_data, agency, version))
        
        return segments
    
    async def _build_CAD(self, data: ExtractedTransaction, agency: str, version: str) -> Optional[str]:
        """Build CAD (Carrier Detail) segment - minimal carrier info (routing only)."""
        if not data.carrier_detail:
            return None
        
        cad_data = {
            # For DoD CAD, only send routing in position 5
            # Positions 1-4 left empty per spec
            5: data.carrier_detail.routing,
        }
        return await self.build_segment('CAD', cad_data, agency, version)
    
    async def _build_SAC_loops(self, data: ExtractedTransaction, agency: str, version: str) -> List[str]:
        """Build SAC service charge segments."""
        segments = []
        
        for charge in data.service_charges:
            # Convert amount to cents (remove decimal)
            amount_cents = str(int(charge.amount * 100)) if charge.amount else None
            
            sac_data = {
                1: charge.indicator,  # C or A
                2: charge.code,  # D350
                3: charge.agency_qualifier,
                4: charge.agency_code,
                5: amount_cents,
            }
            segments.append(await self.build_segment('SAC', sac_data, agency, version))
        
        return segments
    
    async def _build_LM_loops_2(self, data: ExtractedTransaction, agency: str, version: str) -> List[str]:
        """Build second LM/LQ block (appears after SAC in boss's output)."""
        segments = []
        
        if not data.code_lists_post_sac:
            return segments
        
        for code_list in data.code_lists_post_sac:            # Skip if no codes present
            if not code_list.codes:
                continue
                        # LM segment
            lm_data = {
                1: code_list.agency_code,  # DF for DoD
                2: code_list.source_subqualifier,
            }
            segments.append(await self.build_segment('LM', lm_data, agency, version))
            
            # LQ segments for each code
            for code_pair in code_list.codes:
                lq_data = {
                    1: code_pair.qualifier,  # '0', 'DE', 'DG', 'A9'
                    2: code_pair.industry_code,  # 'FA2', 'J', '7G', 'WQQQQQ'
                }
                segments.append(await self.build_segment('LQ', lq_data, agency, version))
        
        return segments
    
    async def _build_TDS(self, data: ExtractedTransaction, agency: str, version: str) -> Optional[str]:
        """Build TDS (Total Monetary Value Summary) segment for final total."""
        if not data.total_amount:
            return None
        
        # Convert to cents
        amount_cents = str(int(data.total_amount * 100))
        
        data_map = {
            1: amount_cents,
        }
        return await self.build_segment('TDS', data_map, agency, version)
    
    async def _build_TDS_subtotal(self, data: ExtractedTransaction, agency: str, version: str) -> Optional[str]:
        """Build TDS segment for subtotal (before service charges)."""
        if not data.subtotal_amount:
            return None
        
        # Convert to cents
        amount_cents = str(int(data.subtotal_amount * 100))
        
        data_map = {
            1: amount_cents,
        }
        return await self.build_segment('TDS', data_map, agency, version)
    
    async def _build_CTT(self, data: ExtractedTransaction, agency: str, version: str) -> Optional[str]:
        """Build CTT (Transaction Totals) segment."""
        if not data.number_of_line_items:
            return None

        data_map = {
            1: data.number_of_line_items,
        }
        return await self.build_segment('CTT', data_map, agency, version)

    async def _build_AMT_total(self, data: ExtractedTransaction, agency: str, version: str) -> Optional[str]:
        """Build AMT (Monetary Amount) segment for total order value."""
        if not data.total_amount:
            return None

        data_map = {
            1: 'GV',  # GV = Gross Invoice Amount
            2: data.total_amount,
        }
        return await self.build_segment('AMT', data_map, agency, version)

    async def _build_CUR(self, data: ExtractedTransaction, agency: str, version: str) -> Optional[str]:
        """Build CUR (Currency) segment."""
        # Default to USD if not specified
        currency = data.currency or 'USD'

        data_map = {
            1: 'BY',  # BY = Buying Party (Buyer's Currency)
            2: currency,
        }
        return await self.build_segment('CUR', data_map, agency, version)

    async def _build_FOB(self, data: ExtractedTransaction, agency: str, version: str) -> Optional[str]:
        """Build FOB (Free on Board) shipping terms segment."""
        if not data.fob_terms:
            return None

        fob = data.fob_terms
        data_map = {
            1: fob.shipment_method,  # CC=Collect, PP=Prepaid
            2: fob.location_qualifier,  # OR=Origin, DE=Destination
            3: fob.description,  # Description
            4: fob.transportation_terms,  # Transportation terms code
        }
        return await self.build_segment('FOB', data_map, agency, version)

    async def _build_N9_MTX_loops(self, data: ExtractedTransaction, agency: str, version: str) -> List[str]:
        """Build N9/MTX loops for special instructions and notes."""
        segments = []

        for instruction in data.special_instructions:
            # N9 segment
            n9_data = {
                1: instruction.reference_qualifier or 'L1',  # L1=Letters or Notes
                2: instruction.reference_id,
            }
            segments.append(await self.build_segment('N9', n9_data, agency, version))

            # MTX segments for each message line
            for message in instruction.messages:
                mtx_data = {
                    1: None,  # Message text type (optional)
                    2: message,  # Message text
                }
                segments.append(await self.build_segment('MTX', mtx_data, agency, version))

        return segments
