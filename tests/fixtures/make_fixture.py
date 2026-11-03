"""
Generate a sample CV DOCX for testing.

Run this once; the resulting .docx is checked into the repo.
"""

from __future__ import annotations

from pathlib import Path

from docx import Document

HERE = Path(__file__).resolve().parent
OUT = HERE / "sample_cv.docx"


def main() -> None:
    doc = Document()

    doc.add_heading("Katleho Mokoena", level=1)
    doc.add_paragraph("Junior Software Developer | Johannesburg, South Africa")
    doc.add_paragraph("Python | FastAPI | SQLite | Git")

    doc.add_heading("Education", level=2)
    doc.add_paragraph("BSc Computer Science")
    doc.add_paragraph("University of Example, 2022–2025")

    doc.add_heading("Skills", level=2)
    doc.add_paragraph(
        "Languages: Python, Java, JavaScript, SQL. "
        "Frameworks: FastAPI, Spring Boot, React. "
        "Databases: PostgreSQL, SQLite, MongoDB. "
        "Tools: Git, Docker, Linux, Postman."
    )

    doc.add_heading("Projects", level=2)
    doc.add_paragraph("JobFlow AI")
    doc.add_paragraph(
        "Local-first job intelligence and application-preparation automation system. "
        "Built with Python, FastAPI, SQLite, SQLAlchemy, and Streamlit."
    )
    doc.add_paragraph("Campus Timetable App")
    doc.add_paragraph(
        "Web application for students to view and manage timetables. "
        "Java, Spring Boot, PostgreSQL, Thymeleaf."
    )

    doc.add_heading("Experience", level=2)
    doc.add_paragraph("Software Engineering Intern, Acme Ltd (2024)")
    doc.add_paragraph("Worked on backend APIs using Python and FastAPI.")

    doc.save(OUT)
    print(f"Wrote: {OUT}")


if __name__ == "__main__":
    main()