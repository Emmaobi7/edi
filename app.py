from dotenv import load_dotenv
load_dotenv()
from fastapi import FastAPI, HTTPException
import uvicorn
from pydantic import BaseModel
import logging
import traceback

from engine.edi_converter import EDIConverter


logging.basicConfig(filename="logs/app.log",
                    level=logging.INFO,
                    format='%(asctime)s %(levelname)s %(message)s',
                    datefmt='%m-%d %H:%M:%S')
LOGGER = logging.getLogger(__name__)


app = FastAPI(
    title="EDI AI Engine",
    description="EDI AI Engine is a tool that converts text to EDI format.",
    version="0.1.0"
)

edi_converter = EDIConverter()

class EDIConverterQuery(BaseModel):
    interchange_sender: str
    edi_info_id: str
    build_edi: bool = True  # Flag to control EDI building

@app.post("/convert_text_to_edi")
async def convert_text_to_edi(query: EDIConverterQuery):
    """Legacy endpoint - uses old segment-by-segment extraction"""
    try:
        LOGGER.info(f"Converting text to EDI (legacy): {query.interchange_sender} for segment {query.edi_info_id}")
        return await edi_converter.convert_text_to_edi(query.interchange_sender, query.edi_info_id)
    except Exception as e:
        LOGGER.error(f"Error converting text to EDI: {str(e)}\nTraceback: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/convert_text_to_edi_v2")
async def convert_text_to_edi_v2(query: EDIConverterQuery):
    """
    New endpoint - uses structured JSON extraction + deterministic EDI building.
    
    Parameters:
        - build_edi: If False, only returns extracted JSON without building EDI segments
    
    Returns:
        - extracted_data: The structured JSON the AI extracted
        - raw_edi_segments: The formatted EDI segments (if build_edi=True and validation passed)
        - validation_errors: Any issues found
        - status: "success", "needs_review", or "failed"
    """
    try:
        LOGGER.info(f"Converting text to EDI (v2): {query.interchange_sender} for segment {query.edi_info_id}, build_edi={query.build_edi}")
        result = await edi_converter.convert_text_to_edi_v2(query.interchange_sender, query.edi_info_id, build_edi=query.build_edi)
        return result
    except Exception as e:
        LOGGER.error(f"Error converting text to EDI (v2): {str(e)}\nTraceback: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/")
def read_root():
    return {"message": "EDI AI Engine is running!"}


if __name__ == "__main__":
    uvicorn.run("app:app", host="0.0.0.0", port=8000, reload=False)