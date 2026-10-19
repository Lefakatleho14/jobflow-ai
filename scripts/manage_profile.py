"""
CLI: manage the local profile.

Commands:
    show                                 Print the current profile
    load <path>                          Load from a JSON file (upsert by name)
    set <field> <value>                  Update a scalar field
    set-list <field> <value> [<value>..] Replace a JSON-list field
    pref --remote <val> --min-score <n>  Update preferences
    skill-add <name> [--category C] [--proficiency P] [--years Y] [--evidence E]
    skill-rm <name>                      Remove a skill
    skill-list                           List skills
    project-add <name> [--description D] [--tech T1,T2] [--role R] [--url U]
    project-rm <name>                    Remove a project
    project-list                         List projects
    reset --yes                          Delete the profile (destructive)
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.database.connection import session_scope  # noqa: E402
from app.services.profile import (                 # noqa: E402
    ProfileError,
    ProfileService,
    ProjectService,
    SkillService,
)


def _print_profile(profile_dict: dict) -> None:
    print("=" * 60)
    print(" JOBFLOW — PROFILE")
    print("=" * 60)
    if not profile_dict.get("exists"):
        print("  (no profile yet — run `load` or `set` to create one)")
        print("=" * 60)
        return

    for key in (
        "name", "education", "degree", "experience_summary",
        "remote_preference", "minimum_match_score",
    ):
        value = profile_dict.get(key)
        print(f"  {key:22}: {value if value is not None else '-'}")

    for key in (
        "languages", "frameworks", "databases", "cloud", "devops",
        "tools", "certifications", "preferred_titles", "preferred_locations",
    ):
        values = profile_dict.get(key) or []
        joined = ", ".join(values) if values else "-"
        print(f"  {key:22}: {joined}")

    print(f"  {'skills_count':22}: {profile_dict.get('skills_count', 0)}")
    print(f"  {'projects_count':22}: {profile_dict.get('projects_count', 0)}")
    print("=" * 60)


def _cmd_show(args) -> int:
    with session_scope() as session:
        _print_profile(ProfileService(session).to_dict())
    return 0


def _cmd_load(args) -> int:
    path = Path(args.path)
    if not path.is_file():
        print(f"[FAIL] No such file: {path}")
        return 1
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        print(f"[FAIL] Invalid JSON: {exc}")
        return 1

    try:
        with session_scope() as session:
            svc = ProfileService(session)
            svc.ensure_profile()

            for scalar in ("name", "education", "degree", "experience_summary"):
                if scalar in data:
                    svc.update_scalar(scalar, data[scalar])

            for lst in (
                "languages", "frameworks", "databases", "cloud", "devops",
                "tools", "certifications", "preferred_titles", "preferred_locations",
            ):
                if lst in data:
                    svc.update_list(lst, data[lst])

            svc.update_preferences(
                remote_preference=data.get("remote_preference"),
                minimum_match_score=data.get("minimum_match_score"),
            )

            skill_svc = SkillService(session)
            for s in data.get("skills", []):
                skill_svc.add_skill(
                    s["name"],
                    category=s.get("category", "other"),
                    proficiency=s.get("proficiency", "intermediate"),
                    years=s.get("years"),
                    evidence=s.get("evidence"),
                )

            proj_svc = ProjectService(session)
            for p in data.get("projects", []):
                proj_svc.add_project(
                    p["name"],
                    description=p.get("description"),
                    technologies=p.get("technologies", []),
                    role=p.get("role"),
                    url=p.get("url"),
                    start_date=p.get("start_date"),
                    end_date=p.get("end_date"),
                )
        print(f"[OK] Loaded profile from {path}")
    except ProfileError as exc:
        print(f"[FAIL] {exc}")
        return 1
    return 0


def _cmd_set(args) -> int:
    with session_scope() as session:
        try:
            ProfileService(session).update_scalar(args.field, args.value)
        except ProfileError as exc:
            print(f"[FAIL] {exc}")
            return 1
    print(f"[OK] {args.field} = {args.value!r}")
    return 0


def _cmd_set_list(args) -> int:
    with session_scope() as session:
        try:
            ProfileService(session).update_list(args.field, args.values)
        except ProfileError as exc:
            print(f"[FAIL] {exc}")
            return 1
    print(f"[OK] {args.field} = {args.values}")
    return 0


def _cmd_pref(args) -> int:
    with session_scope() as session:
        try:
            ProfileService(session).update_preferences(
                remote_preference=args.remote,
                minimum_match_score=args.min_score,
            )
        except ProfileError as exc:
            print(f"[FAIL] {exc}")
            return 1
    print("[OK] preferences updated")
    return 0


def _cmd_skill_add(args) -> int:
    with session_scope() as session:
        try:
            skill = SkillService(session).add_skill(
                args.name,
                category=args.category,
                proficiency=args.proficiency,
                years=args.years,
                evidence=args.evidence,
            )
        except ProfileError as exc:
            print(f"[FAIL] {exc}")
            return 1
    print(f"[OK] skill: {skill.name} ({skill.category}, {skill.proficiency})")
    return 0


def _cmd_skill_rm(args) -> int:
    with session_scope() as session:
        removed = SkillService(session).remove_skill(args.name)
    print("[OK] removed" if removed else "[=] not found")
    return 0


def _cmd_skill_list(args) -> int:
    with session_scope() as session:
        skills = SkillService(session).list_skills()
    if not skills:
        print("(no skills)")
        return 0
    print(f"{'name':<25} {'category':<12} {'proficiency':<14} {'years':>6}")
    print("-" * 60)
    for s in skills:
        years = f"{s.years:g}" if s.years is not None else "-"
        print(f"{s.name:<25} {s.category:<12} {s.proficiency:<14} {years:>6}")
    return 0


def _cmd_project_add(args) -> int:
    techs = [t.strip() for t in (args.tech.split(",") if args.tech else []) if t.strip()]
    with session_scope() as session:
        try:
            p = ProjectService(session).add_project(
                args.name,
                description=args.description,
                technologies=techs,
                role=args.role,
                url=args.url,
                start_date=args.start,
                end_date=args.end,
            )
        except ProfileError as exc:
            print(f"[FAIL] {exc}")
            return 1
    print(f"[OK] project: {p.name}")
    return 0


def _cmd_project_rm(args) -> int:
    with session_scope() as session:
        removed = ProjectService(session).remove_project(args.name)
    print("[OK] removed" if removed else "[=] not found")
    return 0


def _cmd_project_list(args) -> int:
    with session_scope() as session:
        projects = ProjectService(session).list_projects()
    if not projects:
        print("(no projects)")
        return 0
    for p in projects:
        print(f"- {p.name}")
        if p.role:
            print(f"    role: {p.role}")
        if p.technologies:
            print(f"    tech: {', '.join(p.technologies)}")
        if p.description:
            print(f"    desc: {p.description[:100]}")
        if p.start_date or p.end_date:
            print(f"    dates: {p.start_date or '?'} → {p.end_date or 'present'}")
    return 0


def _cmd_reset(args) -> int:
    if not args.yes:
        print("[FAIL] reset requires --yes")
        return 1
    with session_scope() as session:
        ProfileService(session).reset(confirm=True)
    print("[OK] profile reset")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Manage the JobFlow AI profile")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("show", help="Print the current profile")
    p.set_defaults(func=_cmd_show)

    p = sub.add_parser("load", help="Load profile from a JSON file")
    p.add_argument("path")
    p.set_defaults(func=_cmd_load)

    p = sub.add_parser("set", help="Update a scalar field")
    p.add_argument("field")
    p.add_argument("value")
    p.set_defaults(func=_cmd_set)

    p = sub.add_parser("set-list", help="Replace a JSON-list field")
    p.add_argument("field")
    p.add_argument("values", nargs="+")
    p.set_defaults(func=_cmd_set_list)

    p = sub.add_parser("pref", help="Update preferences")
    p.add_argument("--remote", choices=["any", "remote", "hybrid", "onsite"])
    p.add_argument("--min-score", type=int)
    p.set_defaults(func=_cmd_pref)

    p = sub.add_parser("skill-add", help="Add or update a skill")
    p.add_argument("name")
    p.add_argument("--category", default="other")
    p.add_argument("--proficiency", default="intermediate")
    p.add_argument("--years", type=float)
    p.add_argument("--evidence")
    p.set_defaults(func=_cmd_skill_add)

    p = sub.add_parser("skill-rm", help="Remove a skill")
    p.add_argument("name")
    p.set_defaults(func=_cmd_skill_rm)

    p = sub.add_parser("skill-list", help="List skills")
    p.set_defaults(func=_cmd_skill_list)

    p = sub.add_parser("project-add", help="Add or update a project")
    p.add_argument("name")
    p.add_argument("--description")
    p.add_argument("--tech", help="Comma-separated list of technologies")
    p.add_argument("--role")
    p.add_argument("--url")
    p.add_argument("--start")
    p.add_argument("--end")
    p.set_defaults(func=_cmd_project_add)

    p = sub.add_parser("project-rm", help="Remove a project")
    p.add_argument("name")
    p.set_defaults(func=_cmd_project_rm)

    p = sub.add_parser("project-list", help="List projects")
    p.set_defaults(func=_cmd_project_list)

    p = sub.add_parser("reset", help="Delete the profile (destructive)")
    p.add_argument("--yes", action="store_true")
    p.set_defaults(func=_cmd_reset)

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())