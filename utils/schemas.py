from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from datetime import date


# Line item for transactions (IT1, PO1, etc.)
class LineItem(BaseModel):
    line_number: Optional[int] = Field(None, description="Sequential line number")
    quantity: Optional[float] = Field(None, description="Quantity ordered/invoiced")
    unit_of_measure: Optional[str] = Field(None, description="Unit code (EA, PK, etc.)")
    unit_price: Optional[float] = Field(None, description="Price per unit")
    item_id: Optional[str] = Field(None, description="Product/item identifier")
    item_description: Optional[str] = Field(None, description="Human-readable product description")
    status: Optional[str] = Field("ACTIVE", description="ACTIVE, CANCELLED, BACKORDERED, etc.")
    product_id_qualifier: Optional[str] = Field(None, description="Type of product ID (BP, FS, etc.)")
    nsn: Optional[str] = Field(None, description="National Stock Number if applicable")
    vendor_part_number: Optional[str] = Field(None, description="Vendor's part number")
    buyer_part_number: Optional[str] = Field(None, description="Buyer's part number")
    extended_amount: Optional[float] = Field(None, description="Line total (qty * price)")
    pack_size: Optional[int] = Field(None, description="Pack size/inner pack quantity (PO4 segment)")


# Party/entity information (N1 loops)
class Party(BaseModel):
    entity_code: Optional[str] = Field(None, description="N1 code: BT, ST, BY, SE, RE, etc.")
    name: Optional[str] = Field(None, description="Organization name")
    id_qualifier: Optional[str] = Field(None, description="ID type: 92 (DUNS), 10 (DODAAC), 1 (DUNS+4), etc.")
    identifier: Optional[str] = Field(None, description="Actual ID value")


# Contact information (PER segment)
class Contact(BaseModel):
    function_code: str = Field(..., description="AP=Accounts Payable, BD=Buyer, SR=Receiving, etc.")
    name: Optional[str] = Field(None, description="Contact person name")
    phone: Optional[str] = Field(None, description="Phone number")
    email: Optional[str] = Field(None, description="Email address")
    fax: Optional[str] = Field(None, description="Fax number")


# Address information (N3/N4)
class Address(BaseModel):
    street_line_1: Optional[str] = Field(None, description="Street address line 1")
    street_line_2: Optional[str] = Field(None, description="Street address line 2")
    city: Optional[str] = Field(None, description="City name")
    state: Optional[str] = Field(None, description="State/province code")
    postal_code: Optional[str] = Field(None, description="ZIP/postal code")
    country_code: Optional[str] = Field(None, description="Country code")


# Date/Time reference (DTM)
class DateReference(BaseModel):
    qualifier: str = Field(..., description="DTM qualifier code (011, 063, 064, 168, etc.)")
    date_value: Optional[str] = Field(None, description="Date in YYMMDD or CCYYMMDD format")
    time_value: Optional[str] = Field(None, description="Time if applicable")


# Reference information (REF, N9)
class Reference(BaseModel):
    qualifier: str = Field(..., description="Reference type qualifier")
    identifier: Optional[str] = Field(None, description="Reference number/value")
    description: Optional[str] = Field(None, description="Free-form description")


# Code information for LQ segments
class CodePair(BaseModel):
    qualifier: Optional[str] = Field(None, description="Code list qualifier (0, DE, DG, A9, etc.)")
    industry_code: Optional[str] = Field(None, description="Industry code value (FS2, FA2, J, 7G, etc.)")


# Code list information (LM/LQ loops)
class CodeList(BaseModel):
    agency_code: str = Field(..., description="Agency qualifier (DF=DoD, etc.)")
    source_subqualifier: Optional[str] = Field(None, description="Source subqualifier")
    codes: List[CodePair] = Field(default_factory=list, description="List of qualifier:code pairs")


# Financial breakdown for FA2 segments
class FinancialBreakdown(BaseModel):
    breakdown_code: str = Field(..., description="Breakdown structure detail code (58, 18, etc.)")
    financial_code: str = Field(..., description="Financial information code")


# Financial accounting data (FA1/FA2 loops)
class FinancialAccounting(BaseModel):
    agency_code: Optional[str] = Field(None, description="FA1 agency qualifier")
    breakdown_codes: List[FinancialBreakdown] = Field(default_factory=list, description="FA2 breakdown codes")


# Carrier detail (CAD segment)
class CarrierDetail(BaseModel):
    transport_method: Optional[str] = Field(None, description="Transportation method code")
    equipment_initial: Optional[str] = Field(None, description="Equipment initial")
    equipment_number: Optional[str] = Field(None, description="Equipment number")
    scac: Optional[str] = Field(None, description="Standard Carrier Alpha Code")
    routing: Optional[str] = Field(None, description="Routing sequence code")


# Service/Allowance/Charge (SAC segment)
class ServiceCharge(BaseModel):
    indicator: str = Field(..., description="C=Charge, A=Allowance")
    code: Optional[str] = Field(None, description="Service/charge code (D350, etc.)")
    agency_qualifier: Optional[str] = Field(None, description="Agency qualifier")
    agency_code: Optional[str] = Field(None, description="Agency service code")
    amount: Optional[float] = Field(None, description="Charge/allowance amount")


# Payment terms (ITD segment)
class PaymentTerms(BaseModel):
    terms_type: Optional[str] = Field(None, description="01=Basic, 03=Fixed date, etc.")
    terms_basis_date: Optional[str] = Field(None, description="3=Invoice date, etc.")
    discount_percent: Optional[float] = Field(None, description="Discount percentage (e.g., 2.0 for 2%)")
    discount_due_days: Optional[int] = Field(None, description="Days to take discount (e.g., 10)")
    net_due_days: Optional[int] = Field(None, description="Net days due (e.g., 30)")
    due_date: Optional[str] = Field(None, description="Payment due date YYYYMMDD")


# Carrier/transportation (TD5 segment)
class CarrierInfo(BaseModel):
    routing_sequence: Optional[str] = Field(None, description="Routing sequence code")
    id_qualifier: Optional[str] = Field(None, description="2=SCAC, etc.")
    id_code: Optional[str] = Field(None, description="Carrier ID (FDXG, etc.)")
    transport_method: Optional[str] = Field(None, description="Transport method code")
    routing: Optional[str] = Field(None, description="Routing description")
    shipment_method: Optional[str] = Field(None, description="Shipment method description")


# FOB shipping terms (FOB segment)
class FOBTerms(BaseModel):
    shipment_method: Optional[str] = Field(None, description="CC=Collect, PP=Prepaid, etc.")
    location_qualifier: Optional[str] = Field(None, description="OR=Origin, DE=Destination, etc.")
    description: Optional[str] = Field(None, description="FOB description")
    transportation_terms: Optional[str] = Field(None, description="Transportation terms code")


# Special instructions/notes (N9/MTX segments)
class SpecialInstruction(BaseModel):
    reference_qualifier: Optional[str] = Field(None, description="L1=Letters or Notes, etc.")
    reference_id: Optional[str] = Field(None, description="Reference identifier")
    messages: List[str] = Field(default_factory=list, description="List of message text lines (MTX segments)")


# Main extracted transaction structure
class ExtractedTransaction(BaseModel):
    # Transaction header
    transaction_type: Optional[str] = Field(None, description="810, 850, 855, etc.")
    transaction_purpose: Optional[str] = Field("00", description="00=Original, 01=Cancellation, etc.")
    transaction_type_code: Optional[str] = Field(None, description="PP=Prepaid, etc. (BIG07)")
    po_number: Optional[str] = Field(None, description="Purchase order number")
    po_date: Optional[str] = Field(None, description="Purchase order date YYYYMMDD")
    invoice_number: Optional[str] = Field(None, description="Invoice number")
    invoice_date: Optional[str] = Field(None, description="Invoice date YYYYMMDD")
    currency: Optional[str] = Field(None, description="Currency code (USD, EUR, etc.)")
    # Parties
    buyer: Optional[Party] = Field(None, description="Buying party (BY)")
    seller: Optional[Party] = Field(None, description="Seller/remit-to party (SE)")
    remit_to: Optional[Party] = Field(None, description="Remit-to party (RE) for payment")
    issuer: Optional[Party] = Field(None, description="Issuer of invoice (II) - may have M4 qualifier")
    bill_to: Optional[Party] = Field(None, description="Bill-to party (BT)")
    ship_to: Optional[Party] = Field(None, description="Ship-to location (ST)")
    ship_from: Optional[Party] = Field(None, description="Ship-from location (SF)")
    
    # Addresses (linked to parties)
    buyer_address: Optional[Address] = Field(None, description="Buyer address details")
    seller_address: Optional[Address] = Field(None, description="Seller address details")
    remit_to_address: Optional[Address] = Field(None, description="Remit-to address")
    bill_to_address: Optional[Address] = Field(None, description="Bill-to address")
    ship_to_address: Optional[Address] = Field(None, description="Ship-to address")
    
    # Contacts (linked to parties)
    contacts: List[Contact] = Field(default_factory=list, description="Contact persons for various functions")
    
    # Line items
    items: List[LineItem] = Field(default_factory=list, description="Line items")
    
    # References (REF segments)
    references: List[Reference] = Field(default_factory=list, description="Reference identifications")
    
    # Dates
    dates: List[DateReference] = Field(default_factory=list, description="Date references (ship, delivery, etc.)")
    
    # Code lists (LM/LQ loops)
    code_lists: List[CodeList] = Field(default_factory=list, description="Code source information")
    code_lists_post_sac: List[CodeList] = Field(default_factory=list, description="Second code block (LM/LQ) after SAC segment")
    
    # Financial accounting (FA1/FA2 loops)
    financial_accounting: Optional[FinancialAccounting] = Field(None, description="Financial accounting data")
    
    # Payment terms (ITD)
    payment_terms: Optional[PaymentTerms] = Field(None, description="Payment terms and discount info")
    
    # Carrier/transportation (TD5 and CAD)
    carrier_info: Optional[CarrierInfo] = Field(None, description="Carrier identification and routing")
    carrier_detail: Optional[CarrierDetail] = Field(None, description="Carrier and routing information")

    # FOB shipping terms
    fob_terms: Optional[FOBTerms] = Field(None, description="FOB shipping terms and payment")

    # Special instructions/notes
    special_instructions: List[SpecialInstruction] = Field(default_factory=list, description="Special instructions and notes (N9/MTX)")

    # Service charges (SAC)
    service_charges: List[ServiceCharge] = Field(default_factory=list, description="Allowances and charges")
    
    # Subtotal before charges
    subtotal_amount: Optional[float] = Field(None, description="Subtotal before charges/allowances")
    
    # Totals
    total_amount: Optional[float] = Field(None, description="Invoice/PO total")
    number_of_line_items: Optional[int] = Field(None, description="Count of line items")
    
    # Extraction metadata
    confidence_score: Optional[float] = Field(None, description="Overall extraction confidence (0-1)")
    notes: Optional[str] = Field(None, description="Any extraction warnings or notes")


# Response wrapper for the API
class ExtractionResponse(BaseModel):
    extracted_data: ExtractedTransaction
    raw_edi_segments: Optional[List[str]] = Field(None, description="Generated EDI segments")
    validation_errors: List[str] = Field(default_factory=list, description="Validation issues found")
    status: str = Field("success", description="success, needs_review, failed")
