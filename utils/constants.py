import pandas as pd
import os
import dotenv
dotenv.load_dotenv()


# DF_ELEMENTUSAGEDEFS = pd.read_csv('./mappings/elementusagedefs_006010.csv')
EDI_VERSION = "006010"
SEGMENTS_SUPPORTED = ["BIG", "DTM", "N1", "N3", "IT1"]

AGENCY_MAP = {
    "EDI/X12": "X",
    "EDIFACT": "E",
}

# Use DATABASE_URL from .env directly
DATABASE_URL = os.getenv('DATABASE_URL')
if not DATABASE_URL:
    # Fallback to building from components
    DB_USER = os.getenv('POSTGRES_USER', 'postgres')
    DB_PASSWORD = os.getenv('POSTGRES_PASSWORD', 'postgres')
    DB_HOST = os.getenv('POSTGRES_HOST', 'localhost')
    DB_PORT = os.getenv('POSTGRES_PORT', '5432')
    DB_NAME = os.getenv('POSTGRES_DB', 'govcon')
    DATABASE_URL = f"postgresql+asyncpg://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
CHROMA_QUERY = """Return the most relevant text for the following segment: {segment_id}, {segment_description},
Is expected to contain the following entities:
{entities}"""

TOKENS_LIMIT = 2000
