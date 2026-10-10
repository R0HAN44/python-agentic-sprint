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