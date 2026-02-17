import asyncio
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
import asyncio
import os
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text
import dotenv
dotenv.load_dotenv()
from utils.database import get_async_session
from utils.entities import SegmentNLP


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

engine = create_async_engine(DATABASE_URL, echo=False, pool_pre_ping=True, pool_recycle=3600)

async def get_entities_for_segment(segment_id: str, agency: str, version: str):
    # query custom_elementusagedefs table first, if not found, query elementusagedefs table
    async with engine.begin() as conn:
        result = await conn.execute(text(f"""SELECT * FROM mercury."custom_elementusagedefs" WHERE "segment_id"='{segment_id}' AND "agency"='{agency}' AND "version"='{version}' ORDER BY "position" ASC;"""))
        rows = result.fetchall()
        rows_dict = [dict(row._mapping) for row in rows]
        if not rows_dict:
            result = await conn.execute(text(f"""SELECT * FROM mercury."elementusagedefs" WHERE "segment_id"='{segment_id}' AND "agency"='{agency}' AND "version"='{version}' ORDER BY "position" ASC;"""))
            rows = result.fetchall()
            rows_dict = [dict(row._mapping) for row in rows]
    segment_entities = []
    for row in rows_dict:
        segment_entities.append({'entity': row['description'], 'required': row['requirement_designator'], 'type': row['type']})

    return segment_entities


async def get_segments_usage(agency: str, version: str, transaction_set_id: str):
    # query custom_segmentusage table first, if not found, query segmentusage table
    async with engine.begin() as conn:
        result = await conn.execute(text(f"""SELECT * FROM mercury."custom_segmentusage" WHERE "agency"='{agency}' AND "version"='{version}' AND "transactionsetid"='{transaction_set_id}' ORDER BY "position" ASC;"""))
        rows = result.fetchall()
        rows_dict = [dict(row._mapping) for row in rows]
        if not rows_dict:
            result = await conn.execute(text(f"""SELECT * FROM mercury."segmentusage" WHERE "agency"='{agency}' AND "version"='{version}' AND "transactionsetid"='{transaction_set_id}' ORDER BY "position" ASC;"""))
            rows = result.fetchall()
            rows_dict = [dict(row._mapping) for row in rows]
        return rows_dict

async def get_segment_description(segment_id: str, agency: str, version: str):
    # query custom_segmentdescription table first, if not found, query segmentdescription table
    async with engine.begin() as conn:
        result = await conn.execute(text(f"""SELECT * FROM mercury."custom_segmentdescription" WHERE "segment_id"='{segment_id}' AND "agency"='{agency}' AND "version"='{version}';"""))
        rows = result.fetchall()  # Changed from fetchone() to fetchall()
        rows_dict = [dict(row._mapping) for row in rows]
        if not rows_dict:
            result = await conn.execute(text(f"""SELECT * FROM mercury."segmentdescription" WHERE "segment_id"='{segment_id}' AND "agency"='{agency}' AND "version"='{version}';"""))
            rows = result.fetchall()
            rows_dict = [dict(row._mapping) for row in rows]
    return rows_dict
