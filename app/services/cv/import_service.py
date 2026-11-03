"""
CV import service.

Two-step pipeline:
    1. `propose(path)` — validate, extract, return a CVProposal (nothing saved)
    2. `apply(proposal)` — merge the proposal into the profile

The user reviews the proposal between these steps.
"""

from __future__ import annotations

import logging
import shutil
import uuid
from dataclasses import dataclass, field
from pathlib import Path

from sqlalchemy.orm import Session

from app.services.cv.errors import CVError, CVValidationError
from app.services.cv.experience import (
    ExtractedEducation,
    ExtractedProjectName,
    extract_education,
    extract_project_names,
)
from app.services.cv.extractor import extract_text
from app.services.cv.skills import ExtractedSkill, extract_skills
from app.services.cv.validation import validate_file
from app.services.profile import ProfileService, ProjectService, SkillService

logger = logging.getLogger(__name__)

UPLOAD_DIR = Path(__file__).resolve().parents[3] / "uploads"


@dataclass
class CVProposal:
    """What the extractor proposes to add to the profile."""
    source_filename: str
    stored_filename: str | None
    raw_text: str
    skills: list[ExtractedSkill] = field(default_factory=list)
    education: list[ExtractedEducation] = field(default_factory=list)
    projects: list[ExtractedProjectName] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)


def _store_upload(source_path: Path) -> Path:
    """Copy the uploaded file into `uploads/` with a UUID name. Returns the new path."""
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    stored_name = f"{uuid.uuid4().hex}{source_path.suffix.lower()}"
    dest = UPLOAD_DIR / stored_name
    shutil.copyfile(source_path, dest)
    return dest


class CVImportService:
    def __init__(self, session: Session):
        self.session = session

    def propose(self, source_path: str | Path) -> CVProposal:
        """
        Validate, extract, and return a proposal. Does NOT touch the profile.
        """
        path = Path(source_path)
        try:
            validate_file(path)
            text = extract_text(path)
        except CVError:
            raise
        except Exception as exc:
            raise CVError(f"CV processing failed: {exc}") from exc

        skills = extract_skills(text)
        education = extract_education(text)
        projects = extract_project_names(text)

        # Store the uploaded copy — safe now that we know the file is valid.
        try:
            stored_path = _store_upload(path)
            stored_filename = stored_path.name
        except OSError as exc:
            logger.warning("Could not store upload: %s", exc)
            stored_filename = None

        notes: list[str] = []
        if not skills:
            notes.append("No technical skills detected in CV text.")
        if not education:
            notes.append("No education lines detected.")
        if not projects:
            notes.append("No projects section detected.")

        return CVProposal(
            source_filename=path.name,
            stored_filename=stored_filename,
            raw_text=text,
            skills=skills,
            education=education,
            projects=projects,
            notes=notes,
        )

    def apply(
        self,
        proposal: CVProposal,
        *,
        confirm: bool = False,
    ) -> dict:
        """
        Merge a proposal into the profile. Requires confirm=True.

        - Skills: added if missing, updated if present (proficiency hint only).
        - Education: sets `profile.education` and `profile.degree` if empty.
        - Projects: created as new projects with no technologies yet.

        Returns a summary dict for CLI display.
        """
        if not confirm:
            raise CVError("apply requires confirm=True")

        profile_svc = ProfileService(self.session)
        skill_svc = SkillService(self.session)
        project_svc = ProjectService(self.session)
        profile = profile_svc.ensure_profile()

        added_skills = 0
        updated_skills = 0
        for skill in proposal.skills:
            existed = skill_svc.get_skill(skill.name) is not None
            skill_svc.add_skill(
                skill.name,
                category=skill.category,
                proficiency="intermediate",  # neutral default; user edits later
                evidence=skill.evidence,
            )
            if existed:
                updated_skills += 1
            else:
                added_skills += 1

        added_projects = 0
        for project in proposal.projects:
            if project_svc.get_project(project.name) is None:
                project_svc.add_project(
                    project.name,
                    description=project.line,
                    technologies=[],
                )
                added_projects += 1

        education_updated = False
        if proposal.education and not profile.education:
            profile.education = proposal.education[0].line
            education_updated = True
        if proposal.education and not profile.degree:
            # Try to use a degree-looking line if different from the first.
            for edu in proposal.education[1:]:
                if edu.line != profile.education:
                    profile.degree = edu.line
                    education_updated = True
                    break

        self.session.flush()

        return {
            "added_skills": added_skills,
            "updated_skills": updated_skills,
            "added_projects": added_projects,
            "education_updated": education_updated,
            "stored_filename": proposal.stored_filename,
        }