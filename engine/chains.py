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
    # Set timeout to 10 minutes for large extractions
    http_client = httpx.Client(verify=False, timeout=600.0)

    llm = ChatOpenAI(
        model=LLM_MODEL,
        temperature=0.1,
        openai_api_key=LLM_API_KEY,
        openai_api_base=LLM_API_URL,
        http_client=http_client,
        request_timeout=600,  # 10 minute timeout for complex extractions
        max_tokens=None,  # No limit - let the LLM server decide (128k available)
        streaming=False  # Disable streaming for stability
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
Extract EDI transaction data from the text below into structured JSON.

**Extract:**
1. Header: transaction type, PO/invoice number & date, currency (default USD)
2. Parties: buyer, seller, ship_to, bill_to (name, identifier, address)
3. Payment terms: discount %, days, net days
4. Carrier: routing, SCAC code, transport method
5. Line items: line#, quantity, UOM, price, amount, item ID, description, pack_size
6. References: PO, DP, MR, PD, IA, AN, CN, TN with qualifiers
7. Dates: ship, delivery dates (YYYYMMDD format)
8. Service charges: indicator (C/A), amount, code
9. Totals: subtotal, total, line count

**Transaction Type:** {transaction_type}

**Natural Language Text:**
{text}

**Expected Fields Reference (from metadata):**
{metadata_summary}

**Output the extracted data as JSON matching the ExtractedTransaction schema.**

IMPORTANT:
- Return ONLY the JSON structure, no explanations or commentary
- Use null for missing values
- Keep notes field brief (max 50 words)
- Extract only what's explicitly in the text
- Be concise and precise
""")

chain_structured_extraction = prompt_template_structured_extraction | llm.with_structured_output(ExtractedTransaction)
chain_structured_extraction.name = "ChainStructuredExtraction"