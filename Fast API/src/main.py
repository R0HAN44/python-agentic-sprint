from fastapi import FastAPI,Query
from pydantic import BaseModel
from typing import Annotated,Any
from .schemas import Trial,ExtractRequest,ExtractionError
from .service import extract_trial
from fastapi.responses import JSONResponse
import logging
from .utils.chunker import chunk_section

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

sample_document_text = """
# Phase III Clinical Trial Evaluation of Combination Therapy in Advanced Oncology

## 1. Introduction and Background
Colorectal cancer remains a leading cause of cancer-related mortality worldwide. Despite advancements in standard first-line therapies, patients diagnosed with advanced stages frequently experience disease progression and treatment-resistant symptoms. This study evaluates the efficacy and safety profile of combining oxaliplatin, capecitabine, and aflibercept in a structured dose-escalation protocol. Previous trials demonstrated synergistic antineoplastic activity when vascular endothelial growth factor (VEGF) inhibitors are administered concurrently with fluoropyrimidine-based regimens. However, cumulative peripheral neuropathy and gastrointestinal toxicities remain principal dose-limiting factors requiring careful evaluation.

## 2. Methodology and Patient Recruitment
A multi-center, open-label, phase III dose-escalation clinical trial was conducted across five specialized oncology research centers between January 2024 and December 2025. A total of 150 treatment-naive adult participants aged 18 to 75 years with histologically confirmed metastatic colorectal adenocarcinoma were enrolled. 

### Inclusion Criteria
Participants were required to have measurable disease according to RECIST version 1.1 guidelines, an Eastern Cooperative Oncology Group (ECOG) performance status of 0 or 1, and adequate bone marrow, hepatic, and renal function parameters prior to initial dosing. Patients with prior platinum-based treatment histories or active central nervous system metastases were strictly excluded from the study cohort.

### Treatment Protocol
Participants received treatment cycles consisting of intravenous oxaliplatin and oral capecitabine administered twice daily, alongside intravenous aflibercept infusions. The regimen was administered in 21-day cycles for a total duration of 12 treatment cycles or until confirmed disease progression, unacceptable toxicity, or patient withdrawal.

## 3. Results and Treatment Outcomes
Primary endpoint evaluations focused on progression-free survival (PFS) rates and overall response rates (ORR) measured at the 12-week post-treatment mark. 

### Primary Efficacy Observations
Secondary endpoints included overall survival, duration of response, and the incidence of grade 3 or higher treatment-emergent adverse events. Data indicated significant improvements in tumor reduction markers among cohorts receiving optimized dosing schemas compared to historical control metrics.
"""

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

def main():
    chunks = chunk_section(
            text=sample_document_text,
            document_title="Clinical Trial A",
            section_path=["Methods"],
            chunk_size = 600,
            chunk_overlap =50
        )
    
    for chunk in chunks:
        print(chunk,"\n")   
        
main()