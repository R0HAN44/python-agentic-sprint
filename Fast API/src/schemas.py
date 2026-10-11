from pydantic import field_validator
from pydantic import Field
from pydantic import ConfigDict
from pydantic import BaseModel


class TrialMetadata(BaseModel):
    title: str
    study_type: str
    phase: str | None
    registration_id: str | None
    sponsor: str | None


class Population(BaseModel):
    condition: str
    sample_size: int
    min_age: int | None
    max_age: int | None
    sex: str | None


class Intervention(BaseModel):
    name: str
    type: str
    dosage: str | None
    route: str | None
    frequency: str | None
    duration: str | None


class Outcome(BaseModel):
    name: str
    type: str
    measurement: str
    timepoint: str | None


class AdverseEvent(BaseModel):
    name: str
    frequency: str | None
    severity: str | None
    related_to_intervention: bool | None


class Trial(BaseModel):
    metadata: TrialMetadata
    population: Population
    inclusion_criteria: list[str]
    exclusion_criteria: list[str]
    interventions: list[Intervention]
    outcomes: list[Outcome]
    adverse_events: list[AdverseEvent]
    
    
class ExtractionError(Exception):
    
    def __init__(self, message : str = "Trial Extraction Failed"):
        self.message = message
        super().__init__(message)
    

class ExtractRequest(BaseModel):
    text : str

class DocumentChunk(BaseModel):
    model_config = ConfigDict(extra="forbid")

    chunk_id:str = Field(
        min_length=64,
        max_length=64,
        description="SHA-256 hexadecimal digest",
    )

    doc_id:str = Field(min_length=1)
    page_number:int = Field(ge=1)
    section_path:list[str] = Field(min_length=1)
    content:str = Field(min_length=1)
    token_count:int = Field(gt=0)

    @field_validator("content")
    @classmethod
    def content_shld_not_be_blank(cls, value: str) -> str:
        if not value or not value.strip():
            raise ValueError("content cannot be blank")
        return value
        
    @field_validator("section_path")
    @classmethod
    def sections_must_not_be_blank(cls, value: list[str]) -> list[str]:
        if any(not section.strip() for section in value):
            raise ValueError("sections cannot be empty")
        return value

    @field_validator("token_count")
    @classmethod
    def token_count_shld_be_positive(cls, value: int) -> int:
        if value <= 0:
            raise ValueError("token count must be positive")
        return value    
        
    @field_validator("chunk_id")
    @classmethod
    def id_must_be_sha256_hex(cls, value: str) -> str:
        if any(n not in "0123456789abcdef" for n in value):
            raise ValueError("chunk_id must be lowercase SHA-256 hex")
        return value