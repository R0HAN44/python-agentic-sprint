from typing import Literal

from pydantic import BaseModel, Field


class Population(BaseModel):
    min_age: int = Field(ge=0)
    max_age: int = Field(gt=0)
    condition: str = Field(min_length=1)


class Intervention(BaseModel):
    name: str = Field(min_length=1)
    dosage: str | None = None


class Outcome(BaseModel):
    name: str = Field(min_length=1)
    type: Literal["primary", "secondary"]


class Trial(BaseModel):
    title: str = Field(min_length=1)
    phase: Literal[
        "Phase 1",
        "Phase 2",
        "Phase 3",
        "Phase 4"
    ]
    participants: int = Field(gt=0)

    population: Population

    interventions: list[Intervention]

    outcomes: list[Outcome]