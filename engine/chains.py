import json
import os
from typing import List, Dict, Any, Optional
from langchain_openai import ChatOpenAI
from langchain.prompts import ChatPromptTemplate
from langchain.schema import BaseOutputParser
from langchain_core.runnables import RunnableSequence
from pydantic import BaseModel, Field
import httpx


# Define the output structure
class ExtractedEntity(BaseModel):
    entity: str = Field(description="The entity name")
    value: Optional[str] = Field(description="The extracted value, null if not found")
    required: str = Field(description="Whether the entity is mandatory (M) or optional (O)")
    found: bool = Field(description="Whether the entity was found in the text")

class EntityExtractionResult(BaseModel):
    extracted_entities: List[ExtractedEntity] = Field(description="List of extracted entities")
    confidence_score: float = Field(description="Overall confidence score (0-1)")

# Custom output parser
class EntityOutputParser(BaseOutputParser[EntityExtractionResult]):
    def parse(self, text: str) -> EntityExtractionResult:
        try:
            # Clean the text to extract JSON
            if "```json" in text:
                json_start = text.find("```json") + 7
                json_end = text.find("```", json_start)
                json_text = text[json_start:json_end].strip()
            else:
                json_text = text.strip()
            
            data = json.loads(json_text)
            return EntityExtractionResult(**data)
        except Exception as e:
            # Fallback parsing
            return EntityExtractionResult(
                extracted_entities=[],
                confidence_score=0.0
            )

# Initialize the LLM - Use custom LLM if configured, otherwise fallback to OpenAI
LLM_API_URL = os.getenv("LLM_API_URL")
LLM_API_KEY = os.getenv("LLM_API_KEY")
LLM_MODEL = os.getenv("LLM_MODEL")

if LLM_API_URL and LLM_API_KEY and LLM_MODEL:
    # Use custom LLM (OpenAI-compatible API)
    print(f"🔧 Using custom LLM: {LLM_MODEL} at {LLM_API_URL}")

    # Create HTTP client that ignores SSL verification (for self-signed certs)
    http_client = httpx.Client(verify=False)

    llm = ChatOpenAI(
        model=LLM_MODEL,
        temperature=0.1,
        openai_api_key=LLM_API_KEY,
        openai_api_base=LLM_API_URL,
        http_client=http_client
    )
else:
    # Fallback to OpenAI
    print("🔧 Using OpenAI GPT-4.1")
    llm = ChatOpenAI(
        model="gpt-4.1",
        temperature=0.1
    )

# Create the prompt template
prompt_template_entities_extraction = ChatPromptTemplate.from_template("""
You are an expert EDI (Electronic Data Interchange) data extraction specialist. Your task is to extract specific entities from the given text.

**Instructions:**
1. Carefully analyze the provided text
2. Extract values for each specified entity if present
3. Mark entities as found (true) or not found (false)
4. Maintain the required status (M=Mandatory, O=Optional) as provided
5. Provide a confidence score between 0 and 1 for the overall extraction

**Text to analyze:**
{text}

**Entities to extract:**
{entities}

**Output format (JSON):**
```json
{{
    "extracted_entities": [
        {{
            "entity": "ENTITY_NAME",
            "value": "extracted_value_or_null",
            "required": "M_or_O",
            "found": true_or_false
        }}
    ],
    "confidence_score": 0.95
}}
```

Extract the entities now:
""")
    
# Create the output parser
# output_parser = EntityOutputParser()

# Create the chain
chain_entities_extraction = prompt_template_entities_extraction | llm.with_structured_output(EntityExtractionResult)
chain_entities_extraction.name = "ChainEntitiesExtraction"


## Chain to return whether the text is relevant to the segment
class RelevantTextResult(BaseModel):
    relevant: bool = Field(description="Whether the text is relevant to the segment")

prompt_template_relevant_text = ChatPromptTemplate.from_template("""You are an expert EDI (Electronic Data Interchange) data extraction specialist. Your task is to determine whether the text is relevant to the segment.

**Text to analyze:**
{text}

**Segment to analyze:**
{segment}

Is expected to contain the following entities:
{entities}

**Output format (JSON):**
```json
{{
    "relevant": true_or_false
}}
```
""")

chain_relevant_text = prompt_template_relevant_text | llm.with_structured_output(RelevantTextResult)
chain_relevant_text.name = "ChainRelevantText"

# Chain to generate EDI expression given the segment and entities extracted
class EDIExpressionOutputParser(BaseModel):
    edi_expression: str = Field(description="The EDI expression for the segment and entities extracted")


prompt_template_edi_expression = ChatPromptTemplate.from_template("""
You are an expert EDI (Electronic Data Interchange) data extraction specialist. Your task is to generate an EDI expression for the segment and the entities extracted below.
Version: {version}

Segment: {segment}
Entities: {entities}

Output format:
```
{{
    "edi_expression": "EDI_EXPRESSION"
}}
```
""")

chain_edi_expression = prompt_template_edi_expression | llm.with_structured_output(EDIExpressionOutputParser)
chain_edi_expression.name = "ChainEDIExpression"


# ============================================================================
# NEW: Structured extraction chain that returns full transaction JSON
# ============================================================================

from utils.schemas import ExtractedTransaction

prompt_template_structured_extraction = ChatPromptTemplate.from_template("""
You are an expert EDI data extraction specialist focusing on DoD/DFAS invoice and purchase order transactions. Extract ALL relevant information from the natural language text into a structured JSON format.

**CRITICAL INSTRUCTIONS:**

1. **Transaction Header:**
   - Extract transaction type (810=Invoice, 850=Purchase Order)
   - Extract transaction_purpose (00=Original, 01=Cancellation)
   - Extract transaction_type_code (PP=Prepaid, CC=Collect, etc.)
   - Extract invoice_number, invoice_date, po_number, po_date

2. **Parties - Pay attention to DoD entity codes:**
   - **buyer** (BY): The ordering/purchasing organization
   - **seller** (SE): The vendor/supplier organization  
   - **issuer** (II): The party issuing the invoice - may use M4 qualifier
   - **bill_to** (BT): Payment recipient
   - **remit_to** (RE): Remittance address (where to send payment)
   - **ship_to** (ST): Delivery location
   - **ship_from** (SF): Shipping origin
   - For each party extract: entity_code, name, id_qualifier (10=DODAAC, M4=logistics, 92=DUNS, 1=DUNS+4), identifier
   - Extract addresses: street_line_1, street_line_2, city, state, postal_code, country_code

3. **Contacts (PER segments):**
   - Extract function_code:
     - AP = Accounts Payable Department
     - BD = Buyer Name/Department
     - SR = Ship Receiving Contact
   - Extract name, phone, email, fax for each contact
   - Multiple contacts may be present

4. **Payment Terms (ITD segment):**
   - Extract discount_percent (e.g., 2.0 for 2%)
   - Extract discount_due_days (days from invoice date, e.g., 10)
   - Extract net_due_days (e.g., 30 for Net 30)
   - Extract due_date if specific date mentioned (YYYYMMDD format)
   - Extract terms_type (01=Basic, 05=Discount Not Applicable)

5. **Carrier Information:**
   - **For TD5 (detailed carrier with SCAC):** routing name + SCAC code (extract to carrier_info)
     - Extract routing (e.g., "Federal Express Ground")
     - Extract id_code (SCAC like "FDXG")
     - Extract id_qualifier (2 for SCAC)
     - Extract transport_method (M=Motor, A=Air)
     - Extract routing_sequence (O=Origin)
   - **For CAD (minimal, code only):** If just routing code like "Z" (extract to carrier_detail)
     - Extract routing (just the code/letter)
     - Extract transport_method (M=Motor)
     - Leave other fields null

6. **Line Items:**
   - Extract line_number, quantity, unit_of_measure (PK=package, EA=each)
   - Extract unit_price, extended_amount
   - Extract item_id, nsn (National Stock Number with dashes like 6515-01-234-5678)
   - Extract buyer_part_number, vendor_part_number if mentioned
   - Extract item_description
   - Extract status (ACTIVE, CANCELLED, BACKORDERED)
   - product_id_qualifier: FS=Federal Supply, BP=Buyer Part, VP=Vendor Part, N4=NDC/NSN

7. **References (REF segments):**
   - Extract ALL references with qualifiers:
     - PO = Purchase Order Number
     - CN = Carrier Reference (tracking number)
     - TN = Transaction Reference Number
     - DF = Department of Defense references
   - Format as: qualifier, identifier, description

8. **Dates (DTM segments):**
   - Extract with proper qualifiers:
     - 011 = Invoice date
     - 003 = Ship date
     - 004 = Delivery date
     - 035 = Delivery requested
     - 063 = Do not deliver before
     - 064 = Do not deliver after
     - 168 = Service period
   - Format dates as YYYYMMDD (8 digits)

9. **Code Lists (LM/LQ loops):**
   - **First block (before IT1):**
     - Extract agency codes (DF=Department of Defense)
     - Extract source_subqualifier if present
     - Extract ALL industry code pairs: MUST have BOTH qualifier ("0", "DE", "DG") AND industry_code ("FS2", "J", "7G", "FA2", "WQQQQQ")
     - Do NOT include pairs missing industry_code
     - Store in: code_lists
   - **Second block (after SAC charges):**
     - Extract additional agency codes for financial classification
     - Extract ALL code pairs with qualifiers 0/DE/DG/A9 paired with codes FA2/J/7G/WQQQQQ
     - Do NOT include pairs with null industry_code
     - Store in: code_lists_post_sac
     - Example qualifiers: "0", "DE" (signal), "DG" (fund group), "A9" (organization)

10. **Financial Accounting (FA1/FA2):**
    - Extract agency_code for FA1 (DZ, etc.)
    - Extract breakdown_codes for FA2: breakdown_code "58", financial_code "97X12345678"
    - Look for fund codes, authorization codes, appropriation numbers

11. **Service Charges (SAC):**
    - Extract indicator: C=Charge (money added to invoice), A=Allowance (money deducted)
    - For DoD invoices: typically C (Charge) with code D350 (Goods and Services)
    - Extract agency_code (e.g., "85"), agency_qualifier (e.g., "ZZ")
    - Extract amount (numeric only, like 125.50)
    - Look for words: charge, freight, shipping, allowance, credit, discount, fee

12. **Carrier Detail (CAD):**
    - Only if TD5 not used
    - Extract routing, transport_method, scac, tracking_number

13. **Totals:**
    - Extract subtotal_amount (before charges)
    - Extract total_amount (final total including charges)
    - Count number_of_line_items

**Transaction Type:** {transaction_type}

**Natural Language Text:**
{text}

**Expected Fields Reference (from metadata):**
{metadata_summary}

**Output the extracted data as JSON matching the ExtractedTransaction schema.**
Return ONLY valid JSON with all fields populated from the text. Use null for missing optional values.
Provide confidence_score (0-1) and notes about extraction quality or missing data.
For contacts, payment_terms, and carrier_info - extract complete details from text.
""")

chain_structured_extraction = prompt_template_structured_extraction | llm.with_structured_output(ExtractedTransaction)
chain_structured_extraction.name = "ChainStructuredExtraction"