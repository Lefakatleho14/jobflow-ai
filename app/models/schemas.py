"""
Pydantic schemas for API request/response and internal DTOs.

Naming convention:
    *Create   — input when creating
    *Read     — output from API/DB
    *Update   — partial update payload
"""

from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field


# ---------------- User / Profile ----------------

class UserCreate(BaseModel):
    display_name: str = Field(min_length=1, max_length=120)
    email: Optional[str] = None


class UserRead(UserCreate):
    model_config = ConfigDict(from_attributes=True)
    id: str
    created_at: datetime
    updated_at: datetime


class ProfileCreate(BaseModel):
    name: Optional[str] = None
    education: Optional[str] = None
    degree: Optional[str] = None
    languages: List[str] = []
    frameworks: List[str] = []
    databases: List[str] = []
    cloud: List[str] = []
    devops: List[str] = []
    tools: List[str] = []
    certifications: List[str] = []
    preferred_titles: List[str] = []
    preferred_locations: List[str] = []
    remote_preference: str = "any"
    minimum_match_score: int = Field(default=70, ge=0, le=100)
    experience_summary: Optional[str] = None


class ProfileRead(ProfileCreate):
    model_config = ConfigDict(from_attributes=True)
    id: str
    user_id: str
    created_at: datetime
    updated_at: datetime


class SkillCreate(BaseModel):
    name: str
    category: str = "other"
    proficiency: str = "intermediate"
    years: Optional[float] = None
    evidence: Optional[str] = None


class SkillRead(SkillCreate):
    model_config = ConfigDict(from_attributes=True)
    id: str
    profile_id: str


class ProjectCreate(BaseModel):
    name: str
    description: Optional[str] = None
    technologies: List[str] = []
    role: Optional[str] = None
    url: Optional[str] = None
    start_date: Optional[str] = None
    end_date: Optional[str] = None


class ProjectRead(ProjectCreate):
    model_config = ConfigDict(from_attributes=True)
    id: str
    profile_id: str


# ---------------- Job ----------------

class JobCreate(BaseModel):
    title: str
    company: str
    location: Optional[str] = None
    remote_status: str = "unknown"
    description: str = ""
    url: Optional[str] = None
    source: str = "manual"
    external_id: Optional[str] = None
    date_posted: Optional[datetime] = None
    salary_min: Optional[int] = None
    salary_max: Optional[int] = None
    salary_currency: Optional[str] = None


class JobRead(JobCreate):
    model_config = ConfigDict(from_attributes=True)
    id: str
    status: str
    date_found: Optional[datetime] = None
    content_hash: Optional[str] = None
    created_at: datetime
    updated_at: datetime


class JobRequirementCreate(BaseModel):
    seniority: Optional[str] = None
    languages: List[str] = []
    frameworks: List[str] = []
    databases: List[str] = []
    cloud: List[str] = []
    devops: List[str] = []
    soft_skills: List[str] = []
    education: List[str] = []
    experience_years: Optional[int] = None
    salary: Optional[str] = None
    raw_json: Optional[str] = None


class JobRequirementRead(JobRequirementCreate):
    model_config = ConfigDict(from_attributes=True)
    id: str
    job_id: str
    extracted_at: Optional[datetime] = None


class JobMatchCreate(BaseModel):
    score: float
    tier: str
    technical_score: float
    education_score: float
    experience_score: float
    projects_score: float
    location_score: float
    other_score: float
    strong_matches: List[str] = []
    partial_matches: List[str] = []
    missing_skills: List[str] = []
    explanation: Optional[str] = None


class JobMatchRead(JobMatchCreate):
    model_config = ConfigDict(from_attributes=True)
    id: str
    job_id: str
    profile_id: str
    matched_at: Optional[datetime] = None


# ---------------- Application / Notification / Automation ----------------

class ApplicationCreate(BaseModel):
    job_id: str
    status: str = "saved"
    notes: Optional[str] = None


class ApplicationUpdate(BaseModel):
    status: Optional[str] = None
    notes: Optional[str] = None
    interview_info: Optional[str] = None
    follow_up_at: Optional[datetime] = None
    applied_at: Optional[datetime] = None


class ApplicationRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    job_id: str
    status: str
    applied_at: Optional[datetime] = None
    follow_up_at: Optional[datetime] = None
    notes: Optional[str] = None
    interview_info: Optional[str] = None
    created_at: datetime
    updated_at: datetime


class NotificationRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    type: str
    title: str
    body: Optional[str] = None
    job_id: Optional[str] = None
    application_id: Optional[str] = None
    is_read: bool
    created_at: datetime


class AutomationRunRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None
    status: str
    jobs_discovered: int
    jobs_added: int
    duplicates: int
    jobs_analysed: int
    errors: int
    notifications: int
    message: Optional[str] = None
    created_at: datetime