import chromadb
import httpx
from typing import List, Dict, Optional, Any, Tuple
from sqlalchemy.ext.asyncio import AsyncSession
import logging
import uuid

logger = logging.getLogger(__name__)
from typing import List, Optional

import requests
from langchain.embeddings.base import Embeddings


class MercuryEmbeddings(Embeddings):
    """
    LangChain wrapper for a self-hosted embedding model with an HTTP API.
    """

    def __init__(self, api_url: str, api_key: Optional[str] = None):
        self.api_url = api_url
        self.api_key = api_key

    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        """
        Embed a list of documents.
        """
        headers = {"Authorization": f"Bearer {self.api_key}"} if self.api_key else {}
        response = requests.post(
            f"{self.api_url}/embed_batch",
            json={"texts": texts},
            headers=headers,
            timeout=60,
        )
        response.raise_for_status()
        return response.json()["embeddings"]

    def embed_query(self, text: str) -> List[float]:
        """
        Embed a single query.
        """
        return self.embed_documents([text])[0]
# DTOs
class ComplianceResult:
    def __init__(self, compliance_result: str, individual_rule_checks: Optional[List[str]] = None):
        self.compliance_result = compliance_result
        self.individual_rule_checks = individual_rule_checks

class CollectionInformation:
    def __init__(self, collection_id: str = '', collection_name: str = '', status: bool = False):
        self.collection_id = collection_id
        self.collection_name = collection_name
        self.status = status

class CollectionExistenceResult:
    def __init__(self, existed_before: bool, was_created: bool):
        self.existed_before = existed_before
        self.was_created = was_created

class AddDocumentResult:
    def __init__(self, status: bool = False, error_message: str = '', total_processed: int = 0, total_failed: int = 0, failed_ids: Optional[List[str]] = None):
        self.status = status
        self.error_message = error_message
        self.total_processed = total_processed
        self.total_failed = total_failed
        self.failed_ids = failed_ids or []

# Main service class
class ChromaDBService:
    def __init__(self):
        self.chroma_url = "http://3.217.236.185:8050"
        self.embeddings = MercuryEmbeddings("http://ai.kontratar.com:5000")

    async def add_documents(self, collection_name: str, documents: List[str], embeddings: List[List[float]], metadatas: List[Dict]) -> AddDocumentResult:
        try:
            chroma_url = self.chroma_url
            logger.info(f"Attempting to get collection ID for collection: {collection_name} at {chroma_url}")
            collection_id = await self.get_collection_id(chroma_url, collection_name)
            if collection_id is None:
                logger.error(f"Collection '{collection_name}' not found in ChromaDB at {chroma_url}")
                
                logger.info(f"Collection '{collection_name}' not found. Attempting to create new collection at {chroma_url}.")
                new_collection_id = await self.create_collection(collection_name, chroma_url)
                logger.info(f"Created new collection '{collection_name}' with ID: {new_collection_id}")
                
                if new_collection_id is None:
                    return AddDocumentResult(
                        status = False, 
                        error_message = f"Could not create new collection {new_collection_id}", 
                        total_processed=0
                    )
                
                collection_id = new_collection_id

            logger.info(f"Collection ID for '{collection_name}' is '{collection_id}'. Adding documents...")

            result = await self.add_documents_to_collection(chroma_url, collection_id, documents, embeddings, metadatas)
            
            if result is None:
                logger.error(f"Failed to add documents to collection '{collection_name}' (ID: {collection_id})")
                return AddDocumentResult(status=False, total_processed=0)

            documents, embeddings = result

            logger.info(f"Successfully added {len(documents)} documents to collection '{collection_name}' (ID: {collection_id})")
            return AddDocumentResult(status=True, total_processed=len(documents))
        except Exception as e:
            logger.error(f"Exception occurred while adding documents to collection '{collection_name}': {e}", exc_info=True)
            return AddDocumentResult(status=False, error_message=str(e), total_failed=len(documents), failed_ids=[f"doc_{i}" for i in range(len(documents))])


    def delete_collection(self, collection_name: str) -> None:
        pass

    # Additional methods for update, query, etc. can be added here 
    async def get_collection_id(self, chroma_url: str, collection_name: str) -> Optional[str]:
        async with httpx.AsyncClient() as client:
            collections_url = f"{chroma_url}/api/v1/collections/{collection_name}"
            resp = await client.get(collections_url)
            if resp.status_code >= 400:
                return None
            collection_id = resp.json()["id"]
            return collection_id

    # async def get_relevant_chunks(
    #     self,
    #     collection_name: str,
    #     query: str,
    #     metadata_filter: Optional[Dict[str, str]] = None,
    #     n_results: int = 5
    # ) -> List[str]:
    #     """
    #     Retrieve relevant chunks from ChromaDB using the REST API.
    #     """

    #     chroma_url = self.chroma_url
    #     latest_collection_name = collection_name
    #     # 1. Get collection ID by name
    #     async with httpx.AsyncClient() as client:
    #         collections_url = f"{chroma_url}/api/v1/collections/{latest_collection_name}"
    #         resp = await client.get(collections_url)
    #         resp.raise_for_status()
    #         collection_id = resp.json()["id"]
            
    #         if not collection_id:
    #             logger.warning(f"Collection {latest_collection_name} not found in ChromaDB")
    #             return []

    #         # 2. Query the collection for relevant chunks
    #         query_url = f"{chroma_url}/api/v1/collections/{collection_id}/query"
    #         query_embedding = self.embeddings.embed_query(query)
    #         payload = {
    #             "query_embeddings": [query_embedding],
    #             "n_results": n_results,
    #             "include": ["documents", "metadatas", "distances"],
    #             "where": {
    #                     "$and": [{key:{ "$eq": metadata_filter[key]}} for key in metadata_filter.keys()]
    #                     }
    #         }
    #         query_resp = await client.post(query_url, json=payload)
    #         query_resp.raise_for_status()
    #         results = query_resp.json()
            
    #         #logger.debug(f"results: {results}")
    #         # The relevant chunks are in results["documents"][0]
    #         if "documents" in results and results["documents"]:
    #             return results["documents"], results["metadatas"], results["distances"]
    #         else:
    #             logger.warning(f"No relevant documents found for query in collection {collection_name}")
    #             return []

    async def get_relevant_chunks(
        self,
        collection_name: str,
        query: str,
        metadata_filter: Optional[Dict[str, Any]] = None,
        n_results: int = 5
    ) -> List[str]:
        """
        Retrieve relevant chunks from ChromaDB using the REST API.
        """

        chroma_url = self.chroma_url
        latest_collection_name = collection_name
        # 1. Get collection ID by name
        async with httpx.AsyncClient() as client:
            collections_url = f"{chroma_url}/api/v1/collections/{latest_collection_name}"
            resp = await client.get(collections_url)
            resp.raise_for_status()
            collection_id = resp.json()["id"]
            
            if not collection_id:
                logger.warning(f"Collection {latest_collection_name} not found in ChromaDB")
                return []

            # 2. Query the collection for relevant chunks
            query_url = f"{chroma_url}/api/v1/collections/{collection_id}/query"
            query_embedding = self.embeddings.embed_query(query)
            payload = {
                "query_embeddings": [query_embedding],
                "n_results": n_results,
                "include": ["documents", "metadatas", "distances"],
                # "where": {
                #         "$and": [{key:{ "$eq": metadata_filter[key]}} for key in metadata_filter.keys()]
                #         },
                "where": metadata_filter if metadata_filter is not None else {},
            }
            query_resp = await client.post(query_url, json=payload)
            query_resp.raise_for_status()
            results = query_resp.json()
            
            #logger.debug(f"results: {results}")
            # The relevant chunks are in results["documents"][0]
            if "documents" in results and results["documents"]:
                return results["documents"][0]
            else:
                logger.warning(f"No relevant documents found for query in collection {collection_name}")
                return []

    async def create_collection(self, collection_name: str, chroma_url: str) -> Optional[str]:
        """
        Creates a collection and returns the collection id if successful, otherwise returns None
        """
        async with httpx.AsyncClient() as client:
            collections_url = f"{chroma_url}/api/v1/collections"
            payload = {
                "name": collection_name,
                "get_or_create": True,
                "metadata": {
                    "collection_name": collection_name
                }
            }
            resp = await client.post(collections_url, json=payload)
            resp.raise_for_status()
            collection_id = resp.json()["id"]
            return collection_id

    async def get_sample_documents(self, collection_name: str, n_results: int = 5) -> List[Dict[str, Any]]:
        """
        Fetch a few sample documents from a collection using a simple query embedding.
        """
        try:
            chroma_url = self.chroma_url

            async with httpx.AsyncClient() as client:
                # Step 1: Get collection ID
                collections_url = f"{chroma_url}/api/v1/collections/{collection_name}"
                resp = await client.get(collections_url)
                resp.raise_for_status()
                collection_id = resp.json()["id"]

                if not collection_id:
                    logger.warning(f"Collection '{collection_name}' not found.")
                    return []

                # Step 2: Generate valid embedding using your Mercury model
                dummy_embedding = self.embeddings.embed_query("test")

                # Step 3: Query
                query_url = f"{chroma_url}/api/v1/collections/{collection_id}/query"
                payload = {
                    "query_embeddings": [dummy_embedding],
                    "n_results": n_results,
                    "include": ["documents", "metadatas", "distances"]
                }

                query_resp = await client.post(query_url, json=payload)
                query_resp.raise_for_status()
                results = query_resp.json()

                if "documents" in results and results["documents"]:
                    docs = results["documents"][0]
                    metas = results["metadatas"][0] if "metadatas" in results else [{}] * len(docs)
                    return [{"document": doc, "metadata": meta} for doc, meta in zip(docs, metas)]
                else:
                    logger.info(f"No documents returned from collection '{collection_name}'.")
                    return []

        except Exception as e:
            logger.error(f"Error fetching sample documents from collection '{collection_name}': {e}", exc_info=True)
            return []

    async def add_documents_to_collection(self, chroma_url: str, collection_id: str, documents: List[str], embeddings: List[List[float]], metadatas: List[Dict[str, Any]]) -> Optional[Tuple[List[str], List[List[float]]]]:
        try:
            logger.info(f"Preparing to add {len(documents)} documents to collection {collection_id}")
            # Generate random string ids for each document
            ids = [str(uuid.uuid4()) for _ in documents]
            logger.debug(f"Generated document IDs: {ids}")

            async with httpx.AsyncClient() as client:
                collections_url = f"{chroma_url}/api/v1/collections/{collection_id}/add"
                payload = {
                    "ids": ids,
                    "documents": documents,
                    "embeddings": embeddings,
                    "metadatas": metadatas
                }
                logger.debug(f"POST {collections_url} with payload")
                resp = await client.post(collections_url, json=payload)
                resp.raise_for_status()
                logger.info(f"Successfully added {len(documents)} documents to collection {collection_id}")
            return documents, embeddings
        except Exception as e:
            logger.error(f"Error adding documents to collection {collection_id}: {e}")
            return None