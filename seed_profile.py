"""
Template seed script — populate the database with YOUR profile data.

Instructions:
  1. Fill in every section below with your own information
  2. Run once after setup: python seed_profile.py
  3. Optional: copy this file to seed_yourname.py and add it to .gitignore
     so your personal data never gets committed to the repo.
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import database as db

def seed():
    print("Seeding profile database...")

    # -----------------------------------------------------------------------
    # CONTACT INFO — replace with your own
    # -----------------------------------------------------------------------
    db.set_contact(
        name="Jane Doe",
        email="jane.doe@example.com",
        website="janedoe.dev",          # optional, or remove the kwarg
        linkedin="jane-doe-123456",     # the slug after linkedin.com/in/
        github="janedoe",
        location="San Francisco, CA",
    )
    print("  Contact info set")

    # -----------------------------------------------------------------------
    # EDUCATION — add one entry per degree; call db.add_education() again
    # for additional degrees
    # -----------------------------------------------------------------------
    db.add_education(
        institution="State University",
        degree="B.S.",
        field="Computer Science",
        location="Anytown, USA",
        gpa=3.80,                       # optional
        start_date="August 2022",
        end_date="May 2026",
        coursework=[                    # optional list of relevant courses
            "Data Structures and Algorithms",
            "Operating Systems",
            "Database Systems",
            "Machine Learning",
        ],
    )
    print("  Education added")

    # -----------------------------------------------------------------------
    # EXPERIENCE — add one block per job; duplicate the db.add_experience()
    # call for additional roles
    # -----------------------------------------------------------------------
    db.add_experience(
        company="Acme Corp",
        title="Software Engineering Intern",
        location="Remote",
        start_date="June 2024",
        end_date="August 2024",
        bullets=[
            # Write strong action-verb bullets with measurable impact
            "Built a REST API for the internal dashboard, reducing report generation time by 40%.",
            "Migrated legacy data pipeline from Bash scripts to Apache Airflow, improving reliability and observability.",
        ],
        # Tags are used for relevance scoring against job postings — be thorough
        tags=["python", "rest api", "airflow", "sql", "docker"],
    )

    db.add_experience(
        company="Example Startup",
        title="Full-Stack Developer",
        location="New York, NY",
        start_date="January 2024",
        end_date="May 2024",
        bullets=[
            "Implemented real-time notifications with WebSockets, improving user engagement by 20%.",
            "Refactored authentication flow to use JWT tokens, eliminating a class of session-fixation bugs.",
        ],
        tags=["typescript", "react", "node.js", "websockets", "jwt", "postgresql"],
    )
    print("  Experience added")

    # -----------------------------------------------------------------------
    # PROJECTS — add one block per project
    # -----------------------------------------------------------------------
    db.add_project(
        name="Open Source CLI Tool",
        url="https://github.com/janedoe/example-tool",   # optional
        bullets=[
            "Built a CLI tool in Go for batch-renaming files using regex patterns, with undo support.",
            "Published to Homebrew; 500+ installs in first month.",
        ],
        tech_stack=["Go", "Cobra", "GitHub Actions"],
        tags=["cli", "go", "open source", "automation"],
        status="live",                  # "live" | "completed" | "in-progress"
    )

    db.add_project(
        name="Personal Finance Tracker",
        bullets=[
            "Scraped bank statement PDFs and categorized transactions using rule-based NLP.",
            "Visualized spending trends with a Next.js dashboard backed by a SQLite database.",
        ],
        tech_stack=["Python", "Next.js", "SQLite", "Pandas", "Matplotlib"],
        tags=["python", "data", "next.js", "sqlite", "visualization"],
        status="completed",
    )
    print("  Projects added")

    # -----------------------------------------------------------------------
    # SKILLS — organize by category; proficiency is 1 (beginner) to 5 (expert)
    # Add or remove categories and skills as needed
    # -----------------------------------------------------------------------
    skills = {
        "Languages": [
            ("Python", 5), ("TypeScript", 4), ("Go", 3),
            ("SQL", 4), ("HTML/CSS", 4),
        ],
        "Frameworks": [
            ("React.js", 4), ("Next.js", 4), ("Node.js", 4),
            ("FastAPI", 3), ("Tailwind CSS", 4),
        ],
        "Developer Tools": [
            ("Git", 5), ("Docker", 4), ("AWS (EC2, S3, RDS)", 3),
            ("Vercel", 4), ("VS Code", 5),
        ],
        "Technologies": [
            ("REST APIs", 5), ("PostgreSQL", 4), ("Redis", 3),
            ("Machine Learning", 3), ("WebSockets", 3),
        ],
    }

    for category, skill_list in skills.items():
        for name, proficiency in skill_list:
            db.add_skill(category, name, proficiency)
    print("  Skills added")

    print("\nDone! Profile seeded successfully.")
    print(f"Database location: {db.DB_PATH}")


if __name__ == "__main__":
    seed()
