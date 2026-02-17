from chroma.chromadb_service import ChromaDBService
import asyncio

async def main():

    chroma_service = ChromaDBService()
    collection_name = "mercury-collection"

    metadata_filter = {
        "$and": [
            {"interchange_sender": "6303207447"},
            {"edi_info_id": "29940316-c9da-4a27-a5a4-3a079d57ba91"}
        ]
    }

    documents = await chroma_service.get_relevant_chunks(
        collection_name=collection_name,
        query="This is a summary of a transaction set with the identifier code 810 and control number 7540",
        metadata_filter=metadata_filter,
        n_results=10,
    )

    print(documents)

if __name__ == "__main__":
    asyncio.run(main())



# PO Number: PO-2026-001
# PO Date: August 15, 2026