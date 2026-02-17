from typing import List, Dict, Tuple, Any
import json
import asyncio
import requests
import os
from tqdm import tqdm
from engine.chains import EntityExtractionResult, ExtractedEntity, chain_entities_extraction,\
    chain_edi_expression, chain_relevant_text, RelevantTextResult, EDIExpressionOutputParser,\
    chain_structured_extraction
from engine.edi_builder import EDIBuilder
from engine.edi_builder_v2 import DBDrivenEDIBuilder
from utils.utils import get_entities_for_segment, get_segments_usage, get_segment_description
from utils.constants import DATABASE_URL, CHROMA_QUERY, AGENCY_MAP, TOKENS_LIMIT
from utils.schemas import ExtractedTransaction, ExtractionResponse
from chroma.chromadb_service import ChromaDBService
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text
import tiktoken


class EDIConverter:

    def __init__(self):
        self.chroma_service = ChromaDBService()
        self.collection_name = "mercury-collection"
        # Create a shared engine with connection pooling
        self.engine = create_async_engine(
            DATABASE_URL,
            echo=False,
            pool_pre_ping=True,
            pool_recycle=3600,
            pool_size=5,
            max_overflow=10
        )

    def tokens_count(self, text: str):
        encoding = tiktoken.get_encoding("cl100k_base")
        tokens = encoding.encode(text)
        return len(tokens)

    async def query_edi_info_data(self, interchange_sender: str, edi_info_id: str):
            async with self.engine.begin() as conn:
                # Example: Select from mercury.your_table_name
                result = await conn.execute(
                    text('SELECT * FROM mercury."edi_info" where interchange_sender = :interchange_sender and edi_info_id = :edi_info_id'),
                    {"interchange_sender": interchange_sender, "edi_info_id": edi_info_id}
                )
                row = result.fetchone()
                data = {}
                if row:
                    for col, val in row._mapping.items():
                        data[col] = val
            return data

    async def query_raw_data(self, edi_info_id: str):
        async with self.engine.begin() as conn:
            result = await conn.execute(text(f'SELECT * FROM mercury."raw_processed_data" where doc_id = :edi_info_id'),{"edi_info_id": edi_info_id+"_NL"})
            row = result.fetchone()
            data = {}
            if row:
                for col, val in row._mapping.items():
                    data[col] = val
        return data

    async def query_raw_edi_data(self, edi_info_id: str):
        async with self.engine.begin() as conn:
            result = await conn.execute(text(f'SELECT * FROM mercury."raw_processed_data" where doc_id = :edi_info_id'),{"edi_info_id": edi_info_id+"_EDI"})
            row = result.fetchone()
            data = {}
            if row:
                for col, val in row._mapping.items():
                    data[col] = val
        return data
    
    async def convert_text_to_edi(self, interchange_sender: str, edi_info_id: str) -> Tuple[List[str], List[List[Dict[str, str]]]]:
        """
        Convert text to EDI format.
        """
        # get edi info id data from database
        edi_info_data = await self.query_edi_info_data(interchange_sender, edi_info_id)
        if not edi_info_data:
            raise ValueError(f"EDI info data not found for interchange sender {interchange_sender} and edi info id {edi_info_id}")
        edi_info_agency = edi_info_data['type']
        version = edi_info_data['standard_version']
        transactionid = edi_info_data['transaction_name']
        agency = 'X'
        if edi_info_agency in AGENCY_MAP:
            agency = AGENCY_MAP[edi_info_agency]
        raw_text = await self.query_raw_data(edi_info_id)
        raw_text = raw_text['raw_data']
        edi_segments = await get_segments_usage(agency, version, transactionid)
        try:
            edi_segments = self.deduplicate_segments(edi_segments)
        except Exception as e:
            print(f"Error deduplicating segments: {e}")
        
        edi_expressions = []
        edi_entities_per_segment = []
        for edi_segment in tqdm(edi_segments):
            segment_id = edi_segment['segmentid']
            segment_description = await get_segment_description(segment_id, agency, version)
            segment_entities = await get_entities_for_segment(segment_id, agency, version)
            segment_entities_str = '\n'.join([f"{entity['entity']}: {entity['required'].replace('M', 'Mandatory').replace('O', 'Optional')}" for entity in segment_entities])

            # check if any entity has type 'ID'
            if any(entity['type'] == 'ID' for entity in segment_entities):
                print(f"Segment {segment_id} has ID type entities")
            
            chroma_query = CHROMA_QUERY.format(
                segment_id=segment_id,
                segment_description=segment_description[0]['description'],
                entities=segment_entities_str
            )
            metadata_filter = {
                "$and": [
                    {"interchange_sender": interchange_sender},
                    {"edi_info_id": edi_info_id}
                ]
            }

            relevant_text = raw_text
            if self.tokens_count(raw_text) > TOKENS_LIMIT:
                print("Raw text is too long, using chroma to get relevant text...")
                relevant_text = raw_text
                relevant_chunks = await self.chroma_service.get_relevant_chunks(
                    collection_name=self.collection_name,
                    query=chroma_query,
                    metadata_filter=metadata_filter,
                    n_results=5,
                )
                relevant_text = '\n'.join(relevant_chunks)

            is_segment_relevant = await self.is_segment_relevant(segment_id, segment_description[0]['description'], relevant_text, segment_entities_str)
            if not is_segment_relevant.relevant:
                print(f"Segment {segment_id} is not relevant, skipping...")
                continue

            extracted_entities = self.extract_entities(relevant_text, segment_entities)
            # Check if all mandatory entities are extracted
            if not all(entity.found for entity in extracted_entities.extracted_entities if entity.required == 'M'):
                print(f"Segment {segment_id} has missing mandatory entities, skipping...")
                continue

            extracted_entities = [item.model_dump() for item in extracted_entities.extracted_entities]
            edi_expression = self.generate_edi_expression(segment_id, extracted_entities, version)
            edi_expressions.append(edi_expression)
            edi_entities_per_segment.append({segment_id: extracted_entities})

        return edi_expressions, edi_entities_per_segment

    def deduplicate_segments(self, segments: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Deduplicate segments while maintaining the order.
        """
        # order by position
        segments.sort(key=lambda x: int(x['position']))
        seen = set()
        deduplicated_segments = []
        for segment in segments:
            if segment['segmentid'] not in seen:
                seen.add(segment['segmentid'])
                deduplicated_segments.append(segment)
        return deduplicated_segments

    def extract_entities(self, text: str, entities: List[Dict[str, str]]) -> EntityExtractionResult:
        """
        Extract entities from text using the LLM chain.
        
        Args:
            text: The text to analyze
            entities: List of entities to extract with their required status
        
        Returns:
            EntityExtractionResult with extracted entities and confidence score
        """
        
        # Format entities for the prompt
        entities_str = json.dumps(entities, indent=2)
        # Run the chain
        try:
            result = chain_entities_extraction.invoke({'text': text, 'entities': entities_str})
            return result
        except Exception as e:
            print(f"Error during extraction: {e}")
            # Return empty result on error
            return EntityExtractionResult(
                extracted_entities=[
                    ExtractedEntity(
                        entity=entity['entity'],
                        value=None,
                        required=entity['required'],
                        found=False
                    ) for entity in entities
                ],
                confidence_score=0.0
            )
        
    def generate_edi_expression(self, segment_id: str, entities: List[Dict[str, str]], version: str) -> EDIExpressionOutputParser:
        """
        Generate an EDI expression for a segment from the entities extracted.
        """
        entities_str = json.dumps(entities, indent=2)
        result = chain_edi_expression.invoke({'segment': segment_id, 'entities': entities_str, 'version': version})
        return result

    async def is_segment_relevant(self, segment_id: str, segment_description: str, relevant_text: str, entities: str) -> RelevantTextResult:
        """
        Check if the segment is relevant to the text.
        """
        is_segment_relevant = chain_relevant_text.invoke({'text': relevant_text, 'segment': f"{segment_id} - {segment_description}", 'entities': entities})
        return is_segment_relevant
    
    # ========================================================================
    # NEW: Structured extraction and deterministic building
    # ========================================================================
    
    async def convert_text_to_edi_v2(self, interchange_sender: str, edi_info_id: str, build_edi: bool = True) -> ExtractionResponse:
        """
        New pipeline: Extract structured JSON → Validate → Build EDI deterministically.
        
        Args:
            build_edi: If False, skip EDI building and only return extracted JSON
        
        Returns:
            ExtractionResponse with extracted JSON, EDI segments, and validation errors
        """
        # Step 1: Get metadata
        edi_info_data = await self.query_edi_info_data(interchange_sender, edi_info_id)
        if not edi_info_data:
            raise ValueError(f"EDI info data not found for interchange sender {interchange_sender} and edi info id {edi_info_id}")
        
        edi_info_agency = edi_info_data['type']
        version = edi_info_data['standard_version']
        transaction_type = edi_info_data['transaction_name']
        agency = 'X'
        if edi_info_agency in AGENCY_MAP:
            agency = AGENCY_MAP[edi_info_agency]
        
        # Step 2: Get raw text
        raw_data = await self.query_raw_data(edi_info_id)
        raw_text = raw_data['raw_data']
        
        # Step 3: Get segment metadata for context
        edi_segments = await get_segments_usage(agency, version, transaction_type)
        metadata_summary = f"Transaction {transaction_type} version {version} with {len(edi_segments)} segments"
        
        # Step 4: Extract structured JSON using LLM
        print(f"Extracting structured data from text (transaction type: {transaction_type})...")
        extracted_data: ExtractedTransaction = chain_structured_extraction.invoke({
            'text': raw_text,
            'transaction_type': transaction_type,
            'metadata_summary': metadata_summary
        })
        
        # Step 5: Validate extracted data
        validation_errors = self._validate_extraction(extracted_data, transaction_type)
        
        # Step 6: Build EDI segments deterministically (only if build_edi=True and validation passes)
        edi_segments_output = []
        status = "success"
        
        if not build_edi:
            # Skip building, just return extracted JSON
            print(f"⚠ Skipping EDI building (build_edi=False)")
            status = "extraction_only"
        elif not validation_errors or all("WARNING" in err for err in validation_errors):
            try:
                # Use DB-driven builder for accurate segment construction
                builder = DBDrivenEDIBuilder()
                await builder.initialize()
                edi_segments_output = await builder.build_transaction(extracted_data, agency, version)
                await builder.dispose()
                print(f"✓ Built {len(edi_segments_output)} EDI segments using DB rules")
            except Exception as e:
                validation_errors.append(f"ERROR: Failed to build EDI segments: {str(e)}")
                status = "failed"
        else:
            status = "needs_review"
            print(f"⚠ Validation failed with {len(validation_errors)} errors. Review required.")
        
        return ExtractionResponse(
            extracted_data=extracted_data,
            raw_edi_segments=edi_segments_output,
            validation_errors=validation_errors,
            status=status
        )
    
    def _validate_extraction(self, data: ExtractedTransaction, transaction_type: str) -> List[str]:
        """
        Validate extracted data for completeness and logical consistency.
        
        Returns:
            List of validation error messages (empty if valid)
        """
        errors = []
        
        # Check mandatory fields based on transaction type
        if transaction_type == "810":
            if not data.invoice_number:
                errors.append("ERROR: Missing mandatory invoice number")
            if not data.invoice_date:
                errors.append("ERROR: Missing mandatory invoice date")
        elif transaction_type == "850":
            if not data.po_number:
                errors.append("ERROR: Missing mandatory PO number")
            if not data.po_date:
                errors.append("WARNING: Missing PO date (recommended)")
        
        # Check for parties
        if not data.buyer and not data.seller:
            errors.append("WARNING: No buyer or seller information found")
        
        if transaction_type == "850" and not data.buyer:
            errors.append("WARNING: Missing buyer information (BY party)")
        
        if transaction_type == "810" and not data.bill_to:
            errors.append("WARNING: Missing bill-to information (BT party)")
        
        # Check line items
        if not data.items:
            errors.append("ERROR: No line items found")
        else:
            for idx, item in enumerate(data.items, start=1):
                if item.quantity is None and item.status != "CANCELLED":
                    errors.append(f"ERROR: Line {idx} missing quantity")
                if item.unit_price is None:
                    errors.append(f"WARNING: Line {idx} missing unit price")
                if not item.item_id:
                    errors.append(f"WARNING: Line {idx} missing item ID")
        
        # Check totals consistency
        if data.total_amount and data.items:
            calculated_total = sum(
                (item.quantity or 0) * (item.unit_price or 0)
                for item in data.items
                if item.status != "CANCELLED"
            )
            if abs(calculated_total - data.total_amount) > 0.01:
                errors.append(f"WARNING: Total amount mismatch (stated: {data.total_amount}, calculated: {calculated_total})")
        
        # Check confidence score
        if data.confidence_score and data.confidence_score < 0.7:
            errors.append(f"WARNING: Low extraction confidence ({data.confidence_score:.2f})")
        
        return errors
