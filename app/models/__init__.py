"""
Re-export every ORM model and enum for convenient imports.
"""

from app.models.application import Application
from app.models.automation import AutomationRun
from app.models.enums import (
    ApplicationStatus,
    AvailabilityStatus,
    ClosingDateStatus,
    DatePostedStatus,
    EmploymentType,
    JobStatus,
    MatchTier,
    NotificationType,
    Proficiency,
    RemoteStatus,
    RunStatus,
    Seniority,
    SkillCategory,
)
from app.models.feed_source import FeedSource
from app.models.job import Job, JobMatch, JobRequirement
from app.models.job_alias import JobAlias
from app.models.notification import Notification
from app.models.user import Profile, Project, Skill, User

__all__ = [
    "Application",
    "ApplicationStatus",
    "AutomationRun",
    "AvailabilityStatus",
    "ClosingDateStatus",
    "DatePostedStatus",
    "EmploymentType",
    "FeedSource",
    "Job",
    "JobAlias",
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
    "Seniority",
    "Skill",
    "SkillCategory",
    "User",
]