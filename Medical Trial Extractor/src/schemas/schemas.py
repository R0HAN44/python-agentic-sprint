from typing import Optional
from pydantic import BaseModel

class AgeRange(BaseModel):
    minimum: Optional[int]
    maximum: Optional[int]

class StudyDesign(BaseModel):
    phase: Optional[str]
    randomized: Optional[bool]
    blinding: Optional[str]
    control: Optional[str]
    allocation_ratio: Optional[str]
    duration_weeks: Optional[int]

class Population(BaseModel):
    condition: Optional[str]
    total_participants: Optional[int]
    age_range_years: Optional[AgeRange]

class Arm(BaseModel):
    name: str
    drug: Optional[str]
    dose: Optional[str]
    frequency: Optional[str]
    participants: Optional[int]

class ArmResult(BaseModel):
    arm: str
    response_rate_percent: Optional[float]

class Outcome(BaseModel):
    name: str
    type: Optional[str]          # primary / secondary
    timepoint: Optional[str]
    results: list[ArmResult]
    p_value: Optional[str]

class CommonAE(BaseModel):
    event: str
    incidence_percent: Optional[float]

class SeriousAE(BaseModel):
    arm: Optional[str]
    number_of_events: Optional[int]
    considered_treatment_related: Optional[bool]

class AdverseEvents(BaseModel):
    common: list[CommonAE]
    serious: list[SeriousAE]

class TrialExtraction(BaseModel):
    trial_id: Optional[str]
    study_design: StudyDesign
    population: Population
    arms: list[Arm]
    outcomes: list[Outcome]
    adverse_events: AdverseEvents