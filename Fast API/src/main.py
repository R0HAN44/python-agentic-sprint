from fastapi import FastAPI,Query
from pydantic import BaseModel
from typing import Annotated,Any
from .schemas import Trial,ExtractRequest,ExtractionError
from .service import extract_trial
from fastapi.responses import JSONResponse
import logging

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

if not logger.handlers:
    handler = logging.StreamHandler()
    formatter = logging.Formatter(
        "%(asctime)s | %(levelname)-8s | %(name)s:%(funcName)s:%(lineno)d - %(message)s"
    )
    handler.setFormatter(formatter)
    logger.addHandler(handler)

# class Item(BaseModel):
#     name: str
#     description: str | None = None
#     price: float
#     tax: float | None = None


app = FastAPI()


# @app.post("/items/")
# async def create_item(item: Item):
#     item_dict = item.model_dump()
#     if item.tax is not None:
#         price_with_tax = item.price + item.tax
#         item_dict.update({"price_with_tax": price_with_tax})
#     return item_dict
  
# @app.get("/items/")
# async def read_items(q: Annotated[str | None, Query(title="Query String", max_length=50)] = None):
#     results : dict[str, Any] = {"items": [{"item_id": "Foo"}, {"item_id": "Bar"}]}
#     if q:
#         results.update({"q": q})
#     return results

@app.exception_handler(ExtractionError)
async def extraction_error_handler(request: ExtractRequest, exc: ExtractionError):
    return JSONResponse(
        status_code=500,
        content={
            "detail" : exc.message
        }
    )
    

    
@app.post("/extract", response_model=Trial)
async def extract(request : ExtractRequest) -> Trial:
    if not request.text.strip():
        logger.error("Provided String is not Valid")
        raise ExtractionError("Provided String is not Valid")
    extracted_trial_data = extract_trial(request.text)
    if not extracted_trial_data:
        logger.error("Failed to extract trial data")
        raise ExtractionError("Failed to extract trial data")
    logger.info("Successfully returned extracted data")
    return extracted_trial_data