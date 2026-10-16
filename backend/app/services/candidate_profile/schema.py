import re
from typing import Optional

from pydantic import BaseModel, Field, field_validator

DATE_RE = re.compile(r"^\d{4}-\d{2}$")
EVIDENCE_LEVELS = {"verified", "unverified"}


class Metric(BaseModel):
    value: float
    unit: str
    context: str


class Person(BaseModel):
    full_name: str
    location: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    certification_tagline: Optional[str] = None
    focus_tagline: Optional[str] = None
    photo_path: Optional[str] = None
    links: dict[str, str] = Field(default_factory=dict)


class Preferences(BaseModel):
    target_roles: list[str] = Field(default_factory=list)
    default_cv_language: str = "en"
    maximum_pages: int = 2


class SummaryFact(BaseModel):
    id: str
    statement: str
    evidence_level: str = "verified"

    @field_validator("evidence_level")
    @classmethod
    def check_evidence_level(cls, v: str) -> str:
        if v not in EVIDENCE_LEVELS:
            raise ValueError(f"invalid evidence_level: {v!r}")
        return v


class Responsibility(BaseModel):
    id: str
    statement: str
    evidence_level: str = "verified"

    @field_validator("evidence_level")
    @classmethod
    def check_evidence_level(cls, v: str) -> str:
        if v not in EVIDENCE_LEVELS:
            raise ValueError(f"invalid evidence_level: {v!r}")
        return v


class Achievement(BaseModel):
    id: str
    statement: str
    metrics: list[Metric] = Field(default_factory=list)
    technologies: list[str] = Field(default_factory=list)
    evidence_level: str = "verified"

    @field_validator("evidence_level")
    @classmethod
    def check_evidence_level(cls, v: str) -> str:
        if v not in EVIDENCE_LEVELS:
            raise ValueError(f"invalid evidence_level: {v!r}")
        return v


class Experience(BaseModel):
    id: str
    company: str
    position: str
    start_date: str
    end_date: Optional[str] = None
    location: Optional[str] = None
    technologies: list[str] = Field(default_factory=list)
    responsibilities: list[Responsibility] = Field(default_factory=list)
    achievements: list[Achievement] = Field(default_factory=list)

    @field_validator("start_date")
    @classmethod
    def check_start_date(cls, v: str) -> str:
        if not DATE_RE.match(v):
            raise ValueError(f"start_date must match YYYY-MM: {v!r}")
        return v

    @field_validator("end_date")
    @classmethod
    def check_end_date(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and not DATE_RE.match(v):
            raise ValueError(f"end_date must match YYYY-MM or be null: {v!r}")
        return v


class Skill(BaseModel):
    id: str
    name: str
    level: str
    category: Optional[str] = None
    evidence_refs: list[str] = Field(default_factory=list)


class Education(BaseModel):
    id: str
    institution: str
    degree: str
    start_date: Optional[str] = None
    end_date: Optional[str] = None


class Certification(BaseModel):
    id: str
    name: str
    issuer: Optional[str] = None
    issued_date: Optional[str] = None


class Language(BaseModel):
    name: str
    level: str


class Project(BaseModel):
    id: str
    name: str
    statement: str
    technologies: list[str] = Field(default_factory=list)
    evidence_level: str = "verified"


class CandidateProfile(BaseModel):
    schema_version: int
    person: Person
    preferences: Preferences = Field(default_factory=Preferences)
    summary_facts: list[SummaryFact] = Field(default_factory=list)
    experience: list[Experience] = Field(default_factory=list)
    skills: list[Skill] = Field(default_factory=list)
    education: list[Education] = Field(default_factory=list)
    certifications: list[Certification] = Field(default_factory=list)
    languages: list[Language] = Field(default_factory=list)
    projects: list[Project] = Field(default_factory=list)
