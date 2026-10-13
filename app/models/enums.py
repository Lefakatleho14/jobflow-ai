"""
String enums used across the schema.

We store them as plain strings in SQLite for readability.
"""

from __future__ import annotations

from enum import Enum


class JobStatus(str, Enum):
    DISCOVERED = "discovered"
    ANALYSED = "analysed"
    MATCHED = "matched"
    REVIEWING = "reviewing"
    APPROVED = "approved"
    REJECTED = "rejected"
    APPLIED = "applied"
    ARCHIVED = "archived"


class RemoteStatus(str, Enum):
    UNKNOWN = "unknown"
    REMOTE = "remote"
    HYBRID = "hybrid"
    ONSITE = "onsite"


class ApplicationStatus(str, Enum):
    SAVED = "saved"
    REVIEWING = "reviewing"
    APPROVED = "approved"
    APPLIED = "applied"
    INTERVIEW = "interview"
    REJECTED = "rejected"
    OFFER = "offer"


class MatchTier(str, Enum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class NotificationType(str, Enum):
    NEW_MATCH = "new_match"
    FOLLOW_UP = "follow_up"
    RUN_FAILED = "run_failed"
    SYSTEM = "system"


class RunStatus(str, Enum):
    RUNNING = "running"
    SUCCESS = "success"
    PARTIAL = "partial"
    FAILED = "failed"


class SkillCategory(str, Enum):
    LANGUAGE = "language"
    FRAMEWORK = "framework"
    DATABASE = "database"
    CLOUD = "cloud"
    DEVOPS = "devops"
    TOOL = "tool"
    SOFT = "soft"
    OTHER = "other"


class Proficiency(str, Enum):
    BEGINNER = "beginner"
    INTERMEDIATE = "intermediate"
    ADVANCED = "advanced"
    EXPERT = "expert"