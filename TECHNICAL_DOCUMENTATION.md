# EDI AI Engine - Technical Documentation

## System Overview

The EDI AI Engine is a FastAPI-based service that converts natural language descriptions of business transactions into X12 EDI format. The system uses OpenAI GPT-4.1 for extraction and a database-driven approach for EDI segment construction.

---

## Architecture Components

### 1. **FastAPI Application** (`app.py`)
- **Role**: HTTP interface exposing conversion endpoints
- **Endpoints**:
  - `POST /convert_text_to_edi_v2` - Main conversion endpoint with structured extraction
  - `POST /convert_text_to_edi` - Legacy endpoint (segment-by-segment extraction)
- **Singleton**: `EDIConverter` instance initialized at startup
- **Environment**: Loads `.env` for database and API credentials

### 2. **EDI Converter** (`engine/edi_converter.py`)
- **Role**: Orchestrates the entire conversion workflow
- **Key Methods**:
  - `convert_text_to_edi_v2()` - New structured extraction pipeline
  - `convert_text_to_edi()` - Legacy segment-based pipeline
- **Process Flow**:
  1. Query EDI metadata from database
  2. Fetch natural language text
  3. Extract structured data using LLM
  4. Validate extracted data
  5. Build EDI segments from database schema
  6. Return JSON response with segments and validation errors

### 3. **DB-Driven EDI Builder** (`engine/edi_builder_v2.py`)
- **Role**: Dynamically constructs EDI segments based on database schema
- **Key Features**:
  - Queries `mercury.elementusagedefs` for segment structure
  - Data-driven logic adapts to available data
  - Supports multiple transaction patterns (DoD vs commercial)
- **Main Methods**:
  - `get_segment_structure()` - Fetches element definitions from DB
  - `build_segment()` - Constructs segment string with proper formatting
  - `build_transaction()` - Routes to transaction-specific builder (810/850)
  - `_build_810_transaction()` - Invoice segment ordering
  - `_build_850_transaction()` - Purchase order segment ordering

### 4. **LangChain Integration** (`engine/chains.py`)
- **Role**: LLM prompts and structured output parsing
- **Key Chains**:
  - `chain_structured_extraction` - Full transaction extraction with schema
  - `chain_entities_extraction` - Legacy entity extraction
  - `chain_relevant_text` - Segment relevance checking
  - `chain_edi_expression` - EDI string generation
- **LLM Configuration**:
  - Model: `gpt-4.1`
  - Temperature: `0.1` (deterministic)
  - Uses `with_structured_output(ExtractedTransaction)` for validation

### 5. **Pydantic Schemas** (`utils/schemas.py`)
- **Role**: Data validation and type safety
- **Key Models**:
  - `ExtractedTransaction` - Root transaction container
  - `Party`, `Address`, `Contact` - Entity models
  - `LineItem` - Product/service details
  - `PaymentTerms`, `CarrierInfo`, `CarrierDetail` - Business rules
  - `Reference`, `DateReference` - Metadata
  - `CodeList`, `FinancialAccounting` - DoD-specific
  - `ServiceCharge` - Allowances/charges

### 6. **ChromaDB Service** (`chroma/chromadb_service.py`)
- **Role**: Vector similarity search for context retrieval
- **Endpoint**: `http://3.217.236.185:8050`
- **Embedding Model**: MercuryEmbeddings at `http://ai.kontratar.com:5000`
- **Usage**: Retrieves relevant historical EDI examples for context

---

## Database Schema (PostgreSQL - mercury)

### Core Tables

#### 1. **mercury.edi_info**
- **Purpose**: Stores EDI interchange metadata
- **Key Columns**:
  - `edi_info_id` (UUID) - Primary key, links to raw_processed_data
  - `interchange_sender` - Sender identification
  - `interchange_receiver` - Receiver identification
  - `transaction_set_id` - Transaction type (810, 850, etc.)
  - `sender_id` - Sender qualifier
  - `receiver_id` - Receiver qualifier
  - `version` - EDI version (004010, etc.)
  - `agency` - Agency code (X for ASC X12)
- **Role**: Entry point for conversion, provides transaction context

#### 2. **mercury.raw_processed_data**
- **Purpose**: Stores natural language and EDI text pairs
- **Key Columns**:
  - `doc_id` - Foreign key to edi_info (suffixed with `_NL` or `_EDI`)
  - `text` - Natural language or EDI content
  - `type` - Content type indicator
- **Query Pattern**:
  ```sql
  SELECT text FROM mercury.raw_processed_data 
  WHERE doc_id = :edi_info_id || '_NL'
  ```

#### 3. **mercury.elementusagedefs** ⭐ CRITICAL
- **Purpose**: Defines structure of every EDI segment
- **Key Columns**:
  - `segmentid` - Segment identifier (BIG, N1, IT1, etc.)
  - `position` - Element position within segment (1, 2, 3...)
  - `elementid` - Element identifier (DTM01, N101, etc.)
  - `requirementdesignator` - M=Mandatory, O=Optional
  - `type` - Data type (AN, N0, N2, R, DT, ID)
  - `minimum_length` - Min characters
  - `maximum_length` - Max characters
  - `agency` - Agency code (default 'X')
  - `version` - EDI version (default '004010')
- **Query Pattern**:
  ```sql
  SELECT position, elementid, requirementdesignator, type, 
         minimum_length, maximum_length
  FROM mercury.elementusagedefs
  WHERE LOWER(segmentid) = LOWER(:segment_id)
    AND agency = :agency
    AND version = :version
  ORDER BY position
  ```
- **Critical Role**: This table IS the EDI specification - it defines what elements exist, their order, types, and requirements for every segment

#### 4. **mercury.segmentusage**
- **Purpose**: Defines which segments appear in which transactions
- **Key Columns**:
  - `transactionsetid` - Transaction type (810, 850)
  - `segmentid` - Segment identifier
  - `position` - Order within transaction
  - `requirementdesignator` - M=Mandatory, O=Optional
  - `maximum_use` - How many times segment can repeat
  - `loopidentifier` - Loop grouping (N1, IT1, etc.)
  - `agency`, `version` - Standard qualifiers
- **Query Pattern**:
  ```sql
  SELECT segmentid, position, requirementdesignator, loopidentifier
  FROM mercury.segmentusage
  WHERE transactionsetid = :transaction_id
    AND agency = :agency
    AND version = :version
  ORDER BY position
  ```
- **Role**: Provides transaction-level segment ordering and requirements

#### 5. **mercury.custom_* tables** (Optional Overrides)
- **custom_elementusagedefs**: Project-specific element overrides
- **custom_segmentusage**: Project-specific segment ordering
- **Priority**: System checks custom tables first, falls back to base tables
- **Use Case**: Client-specific EDI variations without modifying core schema

### Segment-Specific Tables

#### 6. **mercury.segmentdefs**
- **Purpose**: Segment descriptions and metadata
- **Columns**: `segmentid`, `description`, `functional_area`

#### 7. **mercury.elementdefs**
- **Purpose**: Element descriptions and valid values
- **Columns**: `elementid`, `description`, `data_type`, `valid_codes`

---

## Data Flow

### V2 Pipeline (Structured Extraction)

```
1. HTTP Request
   ↓
   POST /convert_text_to_edi_v2
   Body: {
     "edi_info_id": "uuid",
     "build_edi": true/false
   }

2. Query EDI Metadata
   ↓
   EDIConverter.query_edi_info_data()
   ↓
   SELECT * FROM mercury.edi_info WHERE edi_info_id = :id
   ↓
   Returns: {transaction_set_id, version, agency, sender, receiver}

3. Fetch Natural Language
   ↓
   EDIConverter.query_raw_data()
   ↓
   SELECT text FROM mercury.raw_processed_data 
   WHERE doc_id = :id || '_NL'
   ↓
   Returns: Full natural language description

4. Optional: Retrieve Context (if under token limit)
   ↓
   ChromaDBService.get_relevant_chunks()
   ↓
   Embeddings → Vector Search → Similar transactions
   ↓
   Returns: List of relevant EDI examples

5. LLM Extraction
   ↓
   chain_structured_extraction.invoke({
     "transaction_type": "810",
     "text": nl_text,
     "metadata_summary": segment_list
   })
   ↓
   OpenAI GPT-4.1 with structured output
   ↓
   Returns: ExtractedTransaction (Pydantic model)
   {
     transaction_type: "810",
     invoice_number: "...",
     invoice_date: "...",
     parties: [...],
     items: [...],
     dates: [...],
     references: [...],
     financial_accounting: {...},
     ...
   }

6. Validation
   ↓
   Check mandatory fields
   Validate totals
   Check line item counts
   ↓
   Append warnings to validation_errors list

7. EDI Building (if build_edi=true)
   ↓
   DBDrivenEDIBuilder.build_transaction()
   ↓
   
   For each segment in transaction:
   
   7a. Query Segment Structure
       ↓
       get_segment_structure(segment_id, agency, version)
       ↓
       SELECT * FROM mercury.elementusagedefs
       WHERE segmentid = :id AND agency = :agency AND version = :version
       ORDER BY position
       ↓
       Returns: [
         {position: 1, elementid: 'BIG01', type: 'DT', max_length: 8, required: 'M'},
         {position: 2, elementid: 'BIG02', type: 'AN', max_length: 22, required: 'M'},
         ...
       ]
   
   7b. Map Data to Positions
       ↓
       data_map = {
         1: extracted_data.invoice_date,
         2: extracted_data.invoice_number,
         3: extracted_data.po_date,
         4: extracted_data.po_number,
         ...
       }
   
   7c. Format Elements
       ↓
       For each position:
         - Apply type-specific formatting (DT→YYYYMMDD, N0→remove decimals, R→2 decimals)
         - Truncate to max_length
         - Validate required fields
       ↓
       formatted_elements = ['20240827', 'INV123', ...]
   
   7d. Build Segment String
       ↓
       segment = "BIG*20240827*INV123*...*~"
       ↓
       Append to segments list

8. Response
   ↓
   {
     "extracted_data": ExtractedTransaction,
     "raw_edi_segments": ["BIG*...", "N1*...", ...],
     "validation_errors": ["WARNING: ..."],
     "status": "success"
   }
```

### Transaction-Specific Flows

#### 810 Invoice Flow
```
_build_810_transaction():
  ↓
  1. BIG - Beginning segment (date, invoice#, PO#)
  2. REF - Reference IDs (PO, tracking numbers)
  3. N1 Loops - Parties
     ├─ IF issuer exists (DoD pattern):
     │  ├─ BT (bill-to) with TO indicator
     │  ├─ II (issuer) with FR indicator  
     │  └─ II (second, DODAAC)
     └─ ELSE (commercial pattern):
        ├─ RE (remit-to) + PER (AP contact)
        ├─ BT (bill-to) + N3/N4 (address) + PER (BD contact)
        └─ ST (ship-to) + N3/N4 (address) + PER (SR contact)
  4. LM/LQ - Code lists (if present)
  5. FA1/FA2 - Financial accounting (if present)
  6. IT1 - Line items
     ├─ IF nsn && !buyer_part: IT1*...*ST*FS*6515015616204
     └─ ELSE: IT1*...**BP*buyer*VP*vendor*N4*nsn
  7. DTM - Dates (all qualifiers from dates list)
  8. ITD - Payment terms (if present)
  9. CAD/TD5 - Carrier (CAD if carrier_detail, TD5 if carrier_info)
  10. TDS - Subtotal (if subtotal_amount present)
  11. SAC - Service charges/allowances
  12. LM/LQ - Second code block (if present)
  13. TDS - Final total
  14. CTT - Transaction count
```

#### 850 Purchase Order Flow
```
_build_850_transaction():
  ↓
  1. BEG - Beginning segment (purpose, type, PO#, date)
  2. N1 Loops - Parties (standard hierarchy)
     ├─ BY (buyer) + N3/N4 (address)
     ├─ SE (seller) + N3/N4 (address)
     ├─ BT (bill-to) + N3/N4 (address)
     ├─ ST (ship-to) + N3/N4 (address)
     └─ SF (ship-from)
  3. PO1 - Line items
     ├─ quantity = 0 if CANCELLED
     └─ PID (description) after each PO1
  4. DTM - Dates
  5. CTT - Transaction count
```

---

## Key Business Logic

### Data-Driven Segment Building

The builder adapts to available data:

```python
# Example: N1 party detection
if data.issuer:
    # DoD pattern: BT + II + II
    emit_BT_with_TO_indicator()
    emit_II_with_FR_indicator()
    emit_second_II_DODAAC()
elif data.remit_to:
    # Commercial pattern: RE + BT + ST
    emit_RE_with_addresses()
    emit_BT_with_addresses()
    emit_ST_with_addresses()
```

### IT1 Product ID Logic

```python
# Pattern 1: NSN primary (DoD)
if item.nsn and not item.buyer_part_number:
    IT1*1*5*PK*362.34*ST*FS*6515015616204~

# Pattern 2: Buyer part primary (commercial)
elif item.buyer_part_number:
    IT1*1*25*BX*18.5**BP*MED-GLV*VP*TSI-8847*N4*12345-678-90~

# Pattern 3: Generic item ID
else:
    IT1*1*10*EA*5.00**FS*ITEM123~
```

### Element Type Formatting

```python
# DT (Date): YYYYMMDD format, 8 digits
"20240827"

# N0 (Numeric no decimal): Remove decimal point
362.34 → "36234"

# N2 (Numeric 2 decimals): Multiply by 100
18.50 → "1850"

# R (Decimal): Keep as string
"362.34"

# AN (Alphanumeric): Truncate to max_length
"VERYLONGINVOICENUMBER" (max 22) → "VERYLONGINVOICENUM"
```

### FA1/FA2 Financial Accounting

```python
# Always emit FA1 if FA2 exists
if financial_accounting.breakdown_codes:
    FA1*DZ~  # Default agency to DZ
    for breakdown in breakdown_codes:
        FA2*58*97X12345678~
        FA2*18*2142020~
```

---

## Configuration

### Environment Variables (.env)
```bash
# Database
POSTGRES_HOST=your-host
POSTGRES_PORT=5432
POSTGRES_DB=mercury
POSTGRES_USER=your-user
POSTGRES_PASSWORD=your-password

# OpenAI
OPENAI_API_KEY=sk-...

# ChromaDB (optional)
CHROMA_HOST=3.217.236.185
CHROMA_PORT=8050
EMBEDDING_URL=http://ai.kontratar.com:5000
```

### Constants (`utils/constants.py`)
```python
TOKENS_LIMIT = 120000  # Max tokens before skipping Chroma retrieval
DATABASE_URL = f"postgresql+asyncpg://{user}:{pwd}@{host}:{port}/{db}"
```

---

## Error Handling

### Validation Levels
1. **ERROR**: Blocks EDI generation
   - Missing mandatory transaction fields
   - Database query failures
   - Segment build errors

2. **WARNING**: Generates EDI with cautions
   - Missing optional fields
   - Total amount mismatches
   - No party information found

### Status Codes
- `"success"` - Full EDI generated
- `"extraction_only"` - Data extracted but EDI not built
- `"needs_review"` - Generated with warnings
- `"failed"` - Critical error, no output

---

## Performance Considerations

### Database Queries
- Segment structure queries are NOT cached (queries on every build)
- Consider implementing query result caching for `elementusagedefs`
- Connection pooling via async SQLAlchemy

### Token Management
- `tiktoken` library with `cl100k_base` encoding
- Context limited to `TOKENS_LIMIT` to prevent OpenAI timeout
- Chroma retrieval skipped if base prompt exceeds limit

### Async Operations
- All database calls use `async/await`
- Engine disposal after each request: `await engine.dispose()`
- Proper connection cleanup prevents pool exhaustion

---

## Testing

### Test Scripts
- `test_v2.sh` - cURL wrapper for v2 endpoint
- `seed_test.py` - Inserts test data into database
- `test_full_transaction.py` - Unit test for complete transactions
- `test_db_builder.py` - Tests segment structure queries
- `compare_output.py` - Compares generated vs expected EDI

### Test Data Patterns
1. **DoD Invoice** (boss's test): BT/II/II, FA1/FA2, single NSN item, LM blocks
2. **Commercial Invoice**: RE/BT/ST, multiple items with BP/VP/N4, contacts, payment terms
3. **Purchase Order**: BY/SE/BT/ST/SF, PO1 with descriptions

---

## Extension Points

### Adding New Transaction Types
1. Query `mercury.segmentusage` for segment order
2. Add `_build_XXX_transaction()` method in edi_builder_v2.py
3. Add routing in `build_transaction()` method
4. Update schema if new entities needed

### Adding New Segments
1. Ensure segment exists in `mercury.elementusagedefs`
2. Add `_build_SEGMENT()` method returning segment string
3. Call method in appropriate transaction builder
4. Add extraction logic if new data fields needed

### Custom EDI Variations
1. Insert overrides into `mercury.custom_elementusagedefs`
2. Insert custom ordering into `mercury.custom_segmentusage`
3. System automatically prefers custom tables over base

---

## Troubleshooting

### Common Issues

**"No structure found for segment XXX"**
- Check `mercury.elementusagedefs` has entries for segment
- Verify agency='X' and version='004010' match
- Check case sensitivity (system uses LOWER())

**"Total amount mismatch"**
- LLM extraction issue - check prompt clarity
- Verify service charges are correctly signed (C vs A indicator)
- Check line item extended amounts sum correctly

**"Missing mandatory element"**
- Check Pydantic schema has field as Optional vs required
- Verify extraction prompt mentions the field
- Check if data exists in natural language input

**Duplicate segments appearing**
- Check for double append in builder loop
- Verify loop conditions don't overlap
- Look for copy-paste errors in builder code

---

## API Reference

### POST /convert_text_to_edi_v2

**Request:**
```json
{
  "edi_info_id": "uuid-string",
  "build_edi": true
}
```

**Response:**
```json
{
  "extracted_data": {
    "transaction_type": "810",
    "invoice_number": "INV123",
    "invoice_date": "20240827",
    "bill_to": {...},
    "items": [...],
    "dates": [...],
    "references": [...],
    "total_amount": 1811.70,
    "confidence_score": 0.95,
    "notes": "..."
  },
  "raw_edi_segments": [
    "BIG*20240827*INV123*...",
    "N1*BT*...",
    "..."
  ],
  "validation_errors": [
    "WARNING: ..."
  ],
  "status": "success"
}
```

---

## Dependencies

### Python Packages
- `fastapi==0.115.8` - Web framework
- `sqlalchemy==2.0.27` - Database ORM
- `asyncpg` - PostgreSQL async driver
- `langchain==0.3.26` - LLM orchestration
- `langchain-openai` - OpenAI integration
- `pydantic` - Data validation
- `tiktoken` - Token counting
- `python-dotenv` - Environment config

### External Services
- PostgreSQL (mercury database)
- OpenAI API (GPT-4.1)
- ChromaDB (optional, for context retrieval)
- MercuryEmbeddings API (optional, for vector search)

---

## Security Considerations

- API keys stored in `.env`, never committed
- Database credentials in environment variables
- No user authentication implemented (add if needed)
- SQL injection prevented via parameterized queries
- Input validation via Pydantic schemas

---

## Deployment

### Local Development
```bash
uvicorn app:app --host 0.0.0.0 --port 8000 --reload
```

### Production
```bash
uvicorn app:app --host 0.0.0.0 --port 8000 --workers 4
```

### Docker
```dockerfile
FROM python:3.12-slim
COPY . /app
WORKDIR /app
RUN pip install -r requirements.txt
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000"]
```

---

## Maintenance

### Database Migrations
- Use Alembic or raw SQL for schema changes
- Test with multiple transaction types before deployment
- Backup `elementusagedefs` and `segmentusage` before modifications

### Monitoring
- Log all conversions to `logs/app.log`
- Monitor OpenAI API usage and costs
- Track validation_errors for extraction quality
- Monitor database connection pool health

### Updates
- LangChain and OpenAI SDK updates may change API
- Test thoroughly after dependency updates
- Keep test cases updated with new transaction patterns
