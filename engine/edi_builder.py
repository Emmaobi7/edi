"""
Deterministic EDI segment builder.
Takes structured JSON (ExtractedTransaction) and builds properly formatted EDI segments.
"""
from typing import List, Dict, Optional
from utils.schemas import ExtractedTransaction, LineItem, Party, Address, DateReference, Reference


class EDIBuilder:
    """Builds EDI segments from structured JSON data using deterministic rules."""
    
    def __init__(self, version: str = "004010"):
        self.version = version
        self.segment_terminator = "~"
        self.element_separator = "*"
        
    def build_transaction(self, data: ExtractedTransaction, transaction_type: str) -> List[str]:
        """
        Build complete transaction segments based on type.
        
        Args:
            data: Extracted transaction data
            transaction_type: "810", "850", etc.
            
        Returns:
            List of formatted EDI segment strings
        """
        segments = []
        
        if transaction_type == "810":
            segments.extend(self._build_810_invoice(data))
        elif transaction_type == "850":
            segments.extend(self._build_850_po(data))
        else:
            raise ValueError(f"Unsupported transaction type: {transaction_type}")
        
        return segments
    
    def _build_810_invoice(self, data: ExtractedTransaction) -> List[str]:
        """Build 810 invoice segments."""
        segments = []
        
        # BIG - Beginning Segment for Invoice
        if data.invoice_number:
            big = self._build_BIG(data)
            if big:
                segments.append(big)
        
        # REF - Reference Identification
        for ref in data.references:
            ref_seg = self._build_REF(ref)
            if ref_seg:
                segments.append(ref_seg)
        
        # N1 loops - Standard 810 hierarchy: BT → SE → ST → SF
        n1_hierarchy = [
            ('BT', data.bill_to, data.bill_to_address), # Bill-to party (who pays)
            ('SE', data.seller, data.seller_address),   # Selling party
            ('ST', data.ship_to, data.ship_to_address), # Ship-to location
            ('SF', data.ship_from, None)                # Ship-from location
        ]
        
        for entity_code, party, address in n1_hierarchy:
            if party:
                # Override entity_code to enforce correct qualifier
                party_copy = Party(
                    entity_code=entity_code,
                    name=party.name,
                    id_qualifier=party.id_qualifier,
                    identifier=party.identifier
                )
                segments.extend(self._build_N1_loop(party_copy, address))
        
        # DTM - Date/Time Reference
        for date_ref in data.dates:
            dtm = self._build_DTM(date_ref)
            if dtm:
                segments.append(dtm)
        
        # IT1 - Baseline Item Data (Invoice)
        for idx, item in enumerate(data.items, start=1):
            it1 = self._build_IT1(item, idx)
            if it1:
                segments.append(it1)
        
        # TDS - Total Monetary Value Summary
        if data.total_amount is not None:
            tds = self._build_TDS(data)
            if tds:
                segments.append(tds)
        
        # CTT - Transaction Totals
        if data.number_of_line_items:
            ctt = self._build_CTT(data)
            if ctt:
                segments.append(ctt)
        
        return segments
    
    def _build_850_po(self, data: ExtractedTransaction) -> List[str]:
        """Build 850 purchase order segments."""
        segments = []
        
        # BEG - Beginning Segment for Purchase Order
        if data.po_number:
            beg = self._build_BEG(data)
            if beg:
                segments.append(beg)
        
        # REF - Reference Identification
        for ref in data.references:
            ref_seg = self._build_REF(ref)
            if ref_seg:
                segments.append(ref_seg)
        
        # DTM - Date/Time Reference
        for date_ref in data.dates:
            dtm = self._build_DTM(date_ref)
            if dtm:
                segments.append(dtm)
        
        # N1 loops - Standard 850 hierarchy: BY → SE → BT → ST → SF
        n1_hierarchy = [
            ('BY', data.buyer, data.buyer_address),
            ('SE', data.seller, data.seller_address),
            ('BT', data.bill_to, data.bill_to_address),
            ('ST', data.ship_to, data.ship_to_address),
            ('SF', data.ship_from, None)
        ]
        
        for entity_code, party, address in n1_hierarchy:
            if party:
                # Override entity_code to enforce correct qualifier
                party_copy = Party(
                    entity_code=entity_code,
                    name=party.name,
                    id_qualifier=party.id_qualifier,
                    identifier=party.identifier
                )
                segments.extend(self._build_N1_loop(party_copy, address))
        
        # PO1 - Baseline Item Data (Purchase Order)
        for idx, item in enumerate(data.items, start=1):
            po1 = self._build_PO1(item, idx)
            if po1:
                segments.append(po1)
        
        # CTT - Transaction Totals
        if data.number_of_line_items:
            ctt = self._build_CTT(data)
            if ctt:
                segments.append(ctt)
        
        return segments
    
    # ========================================================================
    # Individual segment builders
    # ========================================================================
    
    def _build_BIG(self, data: ExtractedTransaction) -> Optional[str]:
        """BIG - Beginning Segment for Invoice"""
        parts = ["BIG"]
        parts.append(data.invoice_date or "")
        parts.append(data.invoice_number or "")
        parts.append(data.po_date or "")
        parts.append(data.po_number or "")
        parts.append("")  # Release number
        parts.append("")  # Change order sequence
        parts.append(data.transaction_purpose or "")
        parts.append("")  # Transaction type code
        
        return self.element_separator.join(parts) + self.segment_terminator
    
    def _build_BEG(self, data: ExtractedTransaction) -> Optional[str]:
        """BEG - Beginning Segment for Purchase Order"""
        parts = ["BEG"]
        parts.append(data.transaction_purpose or "00")  # Purpose code
        parts.append("SA")  # PO type code (SA = Stand Alone)
        parts.append(data.po_number or "")
        parts.append("")  # Release number
        parts.append(data.po_date or "")
        
        return self.element_separator.join(parts) + self.segment_terminator
    
    def _build_REF(self, ref: Reference) -> Optional[str]:
        """REF - Reference Identification"""
        if not ref.qualifier:
            return None
        
        parts = ["REF"]
        parts.append(ref.qualifier)
        parts.append(ref.identifier or "")
        parts.append(ref.description or "")
        
        return self.element_separator.join(parts) + self.segment_terminator
    
    def _build_N1_loop(self, party: Party, address: Optional[Address] = None) -> List[str]:
        """Build N1/N3/N4 loop for a party"""
        segments = []
        
        # N1 - Name
        if party.entity_code:
            parts = ["N1"]
            parts.append(party.entity_code)
            parts.append(party.name or "")
            parts.append(party.id_qualifier or "")
            parts.append(party.identifier or "")
            segments.append(self.element_separator.join(parts) + self.segment_terminator)
        
        # N3 - Address Information
        if address and (address.street_line_1 or address.street_line_2):
            parts = ["N3"]
            parts.append(address.street_line_1 or "")
            if address.street_line_2:
                parts.append(address.street_line_2)
            segments.append(self.element_separator.join(parts) + self.segment_terminator)
        
        # N4 - Geographic Location
        if address and (address.city or address.state or address.postal_code):
            parts = ["N4"]
            parts.append(address.city or "")
            parts.append(address.state or "")
            parts.append(address.postal_code or "")
            if address.country_code:
                parts.append(address.country_code)
            segments.append(self.element_separator.join(parts) + self.segment_terminator)
        
        return segments
    
    def _build_DTM(self, date_ref: DateReference) -> Optional[str]:
        """DTM - Date/Time Reference"""
        if not date_ref.qualifier or not date_ref.date_value:
            return None
        
        parts = ["DTM"]
        parts.append(date_ref.qualifier)
        parts.append(date_ref.date_value)
        if date_ref.time_value:
            parts.append(date_ref.time_value)
        
        return self.element_separator.join(parts) + self.segment_terminator
    
    def _build_IT1(self, item: LineItem, line_num: int) -> Optional[str]:
        """IT1 - Baseline Item Data (Invoice)"""
        parts = ["IT1"]
        parts.append(str(line_num))
        parts.append(str(item.quantity) if item.quantity else "")
        parts.append(item.unit_of_measure or "")
        parts.append(str(item.unit_price) if item.unit_price else "")
        parts.append("")  # Basis of unit price
        parts.append(item.product_id_qualifier or "")
        parts.append(item.item_id or "")
        
        return self.element_separator.join(parts) + self.segment_terminator
    
    def _build_PO1(self, item: LineItem, line_num: int) -> Optional[str]:
        """PO1 - Baseline Item Data (Purchase Order)"""
        # Handle cancelled items
        qty = 0 if item.status == "CANCELLED" else (item.quantity or 0)
        
        parts = ["PO1"]
        parts.append(str(line_num))
        parts.append(str(qty))
        parts.append(item.unit_of_measure or "EA")
        parts.append(str(item.unit_price) if item.unit_price else "")
        parts.append("")  # Basis of unit price
        parts.append(item.product_id_qualifier or "BP")
        parts.append(item.item_id or "")
        
        return self.element_separator.join(parts) + self.segment_terminator
    
    def _build_TDS(self, data: ExtractedTransaction) -> Optional[str]:
        """TDS - Total Monetary Value Summary"""
        if data.total_amount is None:
            return None
        
        # Convert to cents/smallest unit (multiply by 100, no decimal)
        amount_str = str(int(data.total_amount * 100))
        
        parts = ["TDS"]
        parts.append(amount_str)
        
        return self.element_separator.join(parts) + self.segment_terminator
    
    def _build_CTT(self, data: ExtractedTransaction) -> Optional[str]:
        """CTT - Transaction Totals"""
        if not data.number_of_line_items:
            return None
        
        parts = ["CTT"]
        parts.append(str(data.number_of_line_items))
        
        return self.element_separator.join(parts) + self.segment_terminator
