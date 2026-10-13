"""
Re-export every ORM model and enum for convenient imports.
"""

from app.models.application import Application
from app.models.automation import AutomationRun
from app.models.enums import (
    ApplicationStatus,
    JobStatus,
    MatchTier,
    NotificationType,
    Proficiency,
    RemoteStatus,
    RunStatus,
    SkillCategory,
)
from app.models.job import Job, JobMatch, JobRequirement
from app.models.notification import Notification
from app.models.user import Profile, Project, Skill, User

__all__ = [
    "Application",
    "ApplicationStatus",
    "AutomationRun",
    "Job",
    "JobMatch",
    "JobRequirement",
    "JobStatus",
    "MatchTier",
    "Notification",
    "NotificationType",
    "Proficiency",
    "Profile",
    "Project",
    "RemoteStatus",
    "RunStatus",
    "Skill",
    "SkillCategory",
    "User",
]