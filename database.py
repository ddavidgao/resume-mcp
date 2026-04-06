"""
SQLite database for storing professional profile data.
Stores experience, projects, education, skills, and generated resumes.
"""

import sqlite3
import json
import os
from datetime import datetime
from pathlib import Path

DB_DIR = Path.home() / ".resume-mcp"
DB_PATH = DB_DIR / "profile.db"


def get_db() -> sqlite3.Connection:
    DB_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db():
    conn = get_db()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS contact (
            id INTEGER PRIMARY KEY CHECK (id = 1),
            name TEXT NOT NULL,
            email TEXT,
            phone TEXT,
            website TEXT,
            linkedin TEXT,
            github TEXT,
            location TEXT,
            updated_at TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS education (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            institution TEXT NOT NULL,
            location TEXT,
            degree TEXT NOT NULL,
            field TEXT,
            gpa REAL,
            start_date TEXT,
            end_date TEXT,
            coursework TEXT,  -- JSON array
            honors TEXT,
            updated_at TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS experience (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            company TEXT NOT NULL,
            title TEXT NOT NULL,
            location TEXT,
            start_date TEXT NOT NULL,
            end_date TEXT,
            is_current INTEGER DEFAULT 0,
            bullets TEXT NOT NULL,  -- JSON array of bullet points
            tags TEXT,  -- JSON array of relevant tags/keywords
            updated_at TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS project (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            url TEXT,
            tech_stack TEXT,  -- JSON array
            bullets TEXT NOT NULL,  -- JSON array of bullet points
            tags TEXT,  -- JSON array
            status TEXT DEFAULT 'completed',  -- completed, live, in_progress
            revenue TEXT,
            updated_at TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS skill (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            category TEXT NOT NULL,  -- Languages, Frameworks, Tools, Technologies
            name TEXT NOT NULL,
            proficiency INTEGER DEFAULT 3,  -- 1-5 scale
            UNIQUE(category, name)
        );

        CREATE TABLE IF NOT EXISTS generated_resume (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            job_title TEXT NOT NULL,
            company TEXT NOT NULL,
            job_url TEXT,
            job_description TEXT,
            resume_latex TEXT NOT NULL,
            resume_pdf_path TEXT,
            selected_experience_ids TEXT,  -- JSON array of IDs used
            selected_project_ids TEXT,  -- JSON array of IDs used
            selected_skills TEXT,  -- JSON array of skills used
            match_score REAL,
            created_at TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS custom_section (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            section_name TEXT NOT NULL,
            content TEXT NOT NULL,  -- JSON: flexible content
            updated_at TEXT DEFAULT (datetime('now'))
        );
    """)
    conn.commit()
    conn.close()


# --- Contact ---

def set_contact(name, email=None, phone=None, website=None, linkedin=None, github=None, location=None):
    conn = get_db()
    conn.execute("""
        INSERT INTO contact (id, name, email, phone, website, linkedin, github, location, updated_at)
        VALUES (1, ?, ?, ?, ?, ?, ?, ?, datetime('now'))
        ON CONFLICT(id) DO UPDATE SET
            name=excluded.name, email=excluded.email, phone=excluded.phone,
            website=excluded.website, linkedin=excluded.linkedin, github=excluded.github,
            location=excluded.location, updated_at=datetime('now')
    """, (name, email, phone, website, linkedin, github, location))
    conn.commit()
    conn.close()


def get_contact():
    conn = get_db()
    row = conn.execute("SELECT * FROM contact WHERE id=1").fetchone()
    conn.close()
    return dict(row) if row else None


# --- Education ---

def add_education(institution, degree, field=None, location=None, gpa=None,
                  start_date=None, end_date=None, coursework=None, honors=None):
    conn = get_db()
    cur = conn.execute("""
        INSERT INTO education (institution, degree, field, location, gpa, start_date, end_date, coursework, honors)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (institution, degree, field, location, gpa, start_date, end_date,
          json.dumps(coursework or []), honors))
    conn.commit()
    edu_id = cur.lastrowid
    conn.close()
    return edu_id


def get_education():
    conn = get_db()
    rows = conn.execute("SELECT * FROM education ORDER BY end_date DESC").fetchall()
    conn.close()
    result = []
    for r in rows:
        d = dict(r)
        d["coursework"] = json.loads(d["coursework"]) if d["coursework"] else []
        result.append(d)
    return result


# --- Experience ---

def add_experience(company, title, bullets, location=None, start_date=None,
                   end_date=None, is_current=False, tags=None):
    conn = get_db()
    cur = conn.execute("""
        INSERT INTO experience (company, title, location, start_date, end_date, is_current, bullets, tags)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (company, title, location, start_date, end_date, int(is_current),
          json.dumps(bullets), json.dumps(tags or [])))
    conn.commit()
    exp_id = cur.lastrowid
    conn.close()
    return exp_id


def get_experiences():
    conn = get_db()
    rows = conn.execute("SELECT * FROM experience ORDER BY start_date DESC").fetchall()
    conn.close()
    result = []
    for r in rows:
        d = dict(r)
        d["bullets"] = json.loads(d["bullets"]) if d["bullets"] else []
        d["tags"] = json.loads(d["tags"]) if d["tags"] else []
        result.append(d)
    return result


def update_experience(exp_id, **kwargs):
    conn = get_db()
    for key in ["bullets", "tags"]:
        if key in kwargs and isinstance(kwargs[key], list):
            kwargs[key] = json.dumps(kwargs[key])
    sets = ", ".join(f"{k}=?" for k in kwargs)
    vals = list(kwargs.values()) + [exp_id]
    conn.execute(f"UPDATE experience SET {sets}, updated_at=datetime('now') WHERE id=?", vals)
    conn.commit()
    conn.close()


def delete_experience(exp_id):
    conn = get_db()
    conn.execute("DELETE FROM experience WHERE id=?", (exp_id,))
    conn.commit()
    conn.close()


# --- Projects ---

def add_project(name, bullets, tech_stack=None, url=None, tags=None, status="completed", revenue=None):
    conn = get_db()
    cur = conn.execute("""
        INSERT INTO project (name, url, tech_stack, bullets, tags, status, revenue)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (name, url, json.dumps(tech_stack or []), json.dumps(bullets),
          json.dumps(tags or []), status, revenue))
    conn.commit()
    proj_id = cur.lastrowid
    conn.close()
    return proj_id


def get_projects():
    conn = get_db()
    rows = conn.execute("SELECT * FROM project ORDER BY updated_at DESC").fetchall()
    conn.close()
    result = []
    for r in rows:
        d = dict(r)
        d["tech_stack"] = json.loads(d["tech_stack"]) if d["tech_stack"] else []
        d["bullets"] = json.loads(d["bullets"]) if d["bullets"] else []
        d["tags"] = json.loads(d["tags"]) if d["tags"] else []
        result.append(d)
    return result


def update_project(proj_id, **kwargs):
    conn = get_db()
    for key in ["bullets", "tags", "tech_stack"]:
        if key in kwargs and isinstance(kwargs[key], list):
            kwargs[key] = json.dumps(kwargs[key])
    sets = ", ".join(f"{k}=?" for k in kwargs)
    vals = list(kwargs.values()) + [proj_id]
    conn.execute(f"UPDATE project SET {sets}, updated_at=datetime('now') WHERE id=?", vals)
    conn.commit()
    conn.close()


def delete_project(proj_id):
    conn = get_db()
    conn.execute("DELETE FROM project WHERE id=?", (proj_id,))
    conn.commit()
    conn.close()


# --- Skills ---

def add_skill(category, name, proficiency=3):
    conn = get_db()
    conn.execute("""
        INSERT INTO skill (category, name, proficiency) VALUES (?, ?, ?)
        ON CONFLICT(category, name) DO UPDATE SET proficiency=excluded.proficiency
    """, (category, name, proficiency))
    conn.commit()
    conn.close()


def get_skills():
    conn = get_db()
    rows = conn.execute("SELECT * FROM skill ORDER BY category, proficiency DESC").fetchall()
    conn.close()
    skills = {}
    for r in rows:
        cat = r["category"]
        if cat not in skills:
            skills[cat] = []
        skills[cat].append({"name": r["name"], "proficiency": r["proficiency"]})
    return skills


def remove_skill(category, name):
    conn = get_db()
    conn.execute("DELETE FROM skill WHERE category=? AND name=?", (category, name))
    conn.commit()
    conn.close()


# --- Generated Resumes ---

def save_generated_resume(job_title, company, resume_latex, job_url=None,
                          job_description=None, experience_ids=None,
                          project_ids=None, skills_used=None, match_score=None,
                          resume_pdf_path=None):
    conn = get_db()
    cur = conn.execute("""
        INSERT INTO generated_resume
        (job_title, company, job_url, job_description, resume_latex, resume_pdf_path,
         selected_experience_ids, selected_project_ids, selected_skills, match_score)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (job_title, company, job_url, job_description, resume_latex, resume_pdf_path,
          json.dumps(experience_ids or []), json.dumps(project_ids or []),
          json.dumps(skills_used or []), match_score))
    conn.commit()
    resume_id = cur.lastrowid
    conn.close()
    return resume_id


def get_generated_resumes(limit=20):
    conn = get_db()
    rows = conn.execute(
        "SELECT id, job_title, company, job_url, match_score, created_at FROM generated_resume ORDER BY created_at DESC LIMIT ?",
        (limit,)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_generated_resume(resume_id):
    conn = get_db()
    row = conn.execute("SELECT * FROM generated_resume WHERE id=?", (resume_id,)).fetchone()
    conn.close()
    if row:
        d = dict(row)
        for key in ["selected_experience_ids", "selected_project_ids", "selected_skills"]:
            d[key] = json.loads(d[key]) if d[key] else []
        return d
    return None


# --- Full Profile Export ---

def get_full_profile():
    """Return the entire profile as a dictionary."""
    return {
        "contact": get_contact(),
        "education": get_education(),
        "experience": get_experiences(),
        "projects": get_projects(),
        "skills": get_skills(),
    }


# Initialize on import
init_db()
