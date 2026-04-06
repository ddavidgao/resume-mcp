"""
Resume MCP Server
An MCP server that maintains a professional profile database and generates
tailored resumes for specific job postings.
"""

import json
import sys
import os

# Add the server directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from mcp.server.fastmcp import FastMCP

import database as db
from scraper import parse_job_posting, fetch_page_text, JobPosting
from generator import generate_resume_for_job, compile_latex_to_pdf, ensure_output_dir
from reviewer import run_ats_check, build_evaluation_context
from tracker import add_application, update_status, get_stats, TRACKER_PATH

mcp = FastMCP("resume-builder")


# ==================== ONBOARDING TOOLS ====================

@mcp.tool()
def setup_profile(
    website_url: str = None,
    resume_text: str = None,
    linkedin_url: str = None,
) -> str:
    """
    First-run onboarding tool. Collects raw profile data from multiple sources
    and returns everything to the calling LLM with instructions to populate the
    profile database using the appropriate tools.

    Args:
        website_url: Personal website or portfolio URL to scrape
        resume_text: Paste the full contents of your resume here
        linkedin_url: LinkedIn profile URL to scrape
    """
    result = {}

    if website_url:
        try:
            result["website_content"] = fetch_page_text(website_url)
        except Exception as e:
            result["website_content"] = f"[Error scraping {website_url}: {e}]"

    if resume_text:
        result["resume_content"] = resume_text

    if linkedin_url:
        try:
            result["linkedin_content"] = fetch_page_text(linkedin_url)
        except Exception as e:
            result["linkedin_content"] = f"[Error scraping {linkedin_url}: {e}]"

    result["existing_profile"] = db.get_full_profile()

    result["instructions"] = (
        "You have the candidate's raw website and/or resume text above. "
        "Extract all professional information and populate the profile using these tools: "
        "set_contact_info, add_experience, add_project, add_education, bulk_add_skills. "
        "For each experience and project, include relevant technology tags for job matching. "
        "After populating, show the user a summary of what you added and ask if anything needs correcting."
    )

    return json.dumps(result, indent=2, default=str)


@mcp.tool()
def reset_profile() -> str:
    """
    Clear all profile data and start fresh. Drops and recreates all profile tables
    (contact, education, experience, project, skill). Does NOT delete generated resumes.
    """
    conn = db.get_db()
    conn.executescript("""
        DROP TABLE IF EXISTS contact;
        DROP TABLE IF EXISTS education;
        DROP TABLE IF EXISTS experience;
        DROP TABLE IF EXISTS project;
        DROP TABLE IF EXISTS skill;
    """)
    conn.close()
    db.init_db()
    return "Profile reset. All contact, education, experience, project, and skill data cleared."


# ==================== PROFILE TOOLS ====================

@mcp.tool()
def get_profile() -> str:
    """Get the full professional profile (contact, education, experience, projects, skills)."""
    profile = db.get_full_profile()
    return json.dumps(profile, indent=2, default=str)


@mcp.tool()
def set_contact_info(
    name: str,
    email: str = None,
    phone: str = None,
    website: str = None,
    linkedin: str = None,
    github: str = None,
    location: str = None
) -> str:
    """Set or update contact information."""
    db.set_contact(name, email, phone, website, linkedin, github, location)
    return f"Contact info updated for {name}"


@mcp.tool()
def add_experience(
    company: str,
    title: str,
    bullets: list[str],
    location: str = None,
    start_date: str = None,
    end_date: str = None,
    is_current: bool = False,
    tags: list[str] = None
) -> str:
    """
    Add a work experience entry.

    Args:
        company: Company name
        title: Job title
        bullets: List of accomplishment bullet points (use action verbs, quantify impact)
        location: City, State or Remote
        start_date: Start date (e.g., "March 2025")
        end_date: End date or None if current
        is_current: Whether this is a current position
        tags: Relevant technology/skill tags for matching
    """
    exp_id = db.add_experience(company, title, bullets, location, start_date, end_date, is_current, tags)
    return f"Added experience: {title} at {company} (ID: {exp_id})"


@mcp.tool()
def update_experience(
    experience_id: int,
    company: str = None,
    title: str = None,
    bullets: list[str] = None,
    location: str = None,
    start_date: str = None,
    end_date: str = None,
    tags: list[str] = None
) -> str:
    """Update an existing experience entry by ID. Only provide fields you want to change."""
    kwargs = {}
    if company is not None: kwargs["company"] = company
    if title is not None: kwargs["title"] = title
    if bullets is not None: kwargs["bullets"] = bullets
    if location is not None: kwargs["location"] = location
    if start_date is not None: kwargs["start_date"] = start_date
    if end_date is not None: kwargs["end_date"] = end_date
    if tags is not None: kwargs["tags"] = tags
    db.update_experience(experience_id, **kwargs)
    return f"Updated experience ID {experience_id}"


@mcp.tool()
def delete_experience(experience_id: int) -> str:
    """Delete an experience entry by ID."""
    db.delete_experience(experience_id)
    return f"Deleted experience ID {experience_id}"


@mcp.tool()
def add_project(
    name: str,
    bullets: list[str],
    tech_stack: list[str] = None,
    url: str = None,
    tags: list[str] = None,
    status: str = "completed",
    revenue: str = None
) -> str:
    """
    Add a project to the profile.

    Args:
        name: Project name
        bullets: List of description bullet points
        tech_stack: Technologies used (e.g., ["Next.js", "TypeScript", "Prisma"])
        url: Project URL if live
        tags: Additional tags for job matching
        status: One of: completed, live, in_progress
        revenue: Revenue info if applicable (e.g., "$100k+")
    """
    proj_id = db.add_project(name, bullets, tech_stack, url, tags, status, revenue)
    return f"Added project: {name} (ID: {proj_id})"


@mcp.tool()
def update_project(
    project_id: int,
    name: str = None,
    bullets: list[str] = None,
    tech_stack: list[str] = None,
    url: str = None,
    tags: list[str] = None,
    status: str = None,
    revenue: str = None
) -> str:
    """Update an existing project by ID. Only provide fields you want to change."""
    kwargs = {}
    if name is not None: kwargs["name"] = name
    if bullets is not None: kwargs["bullets"] = bullets
    if tech_stack is not None: kwargs["tech_stack"] = tech_stack
    if url is not None: kwargs["url"] = url
    if tags is not None: kwargs["tags"] = tags
    if status is not None: kwargs["status"] = status
    if revenue is not None: kwargs["revenue"] = revenue
    db.update_project(project_id, **kwargs)
    return f"Updated project ID {project_id}"


@mcp.tool()
def delete_project(project_id: int) -> str:
    """Delete a project by ID."""
    db.delete_project(project_id)
    return f"Deleted project ID {project_id}"


@mcp.tool()
def add_education(
    institution: str,
    degree: str,
    field: str = None,
    location: str = None,
    gpa: float = None,
    start_date: str = None,
    end_date: str = None,
    coursework: list[str] = None,
    honors: str = None
) -> str:
    """Add an education entry."""
    edu_id = db.add_education(institution, degree, field, location, gpa, start_date, end_date, coursework, honors)
    return f"Added education: {degree} at {institution} (ID: {edu_id})"


@mcp.tool()
def add_skill(category: str, name: str, proficiency: int = 3) -> str:
    """
    Add or update a skill.

    Args:
        category: Category (e.g., "Languages", "Frameworks", "Developer Tools", "Technologies")
        name: Skill name (e.g., "Python", "React.js")
        proficiency: 1-5 scale (used for prioritization in tailored resumes)
    """
    db.add_skill(category, name, proficiency)
    return f"Added/updated skill: {name} in {category}"


@mcp.tool()
def remove_skill(category: str, name: str) -> str:
    """Remove a skill."""
    db.remove_skill(category, name)
    return f"Removed skill: {name} from {category}"


@mcp.tool()
def bulk_add_skills(skills: dict[str, list[str]]) -> str:
    """
    Add multiple skills at once.

    Args:
        skills: Dict mapping category to list of skill names.
                Example: {"Languages": ["Python", "Java"], "Frameworks": ["React", "Flask"]}
    """
    count = 0
    for category, names in skills.items():
        for name in names:
            db.add_skill(category, name)
            count += 1
    return f"Added {count} skills across {len(skills)} categories"


# ==================== JOB SCRAPING TOOLS ====================

@mcp.tool()
def scrape_job_posting(url: str) -> str:
    """
    Scrape a job posting URL and extract structured data.
    Returns title, company, requirements, tech stack, experience level, etc.
    """
    try:
        job = parse_job_posting(url)
        return job.to_json()
    except Exception as e:
        return json.dumps({"error": str(e)})


@mcp.tool()
def analyze_job_from_text(
    title: str,
    company: str,
    description: str,
    url: str = ""
) -> str:
    """
    Analyze a job posting from pasted text (when URL scraping doesn't work).
    Paste the full job description text.
    """
    from scraper import extract_tech_stack, extract_experience_level, extract_bullet_sections

    tech = extract_tech_stack(description)
    level = extract_experience_level(description)
    sections = extract_bullet_sections(description)

    job = JobPosting(
        title=title,
        company=company,
        location="Unknown",
        url=url,
        description=description[:5000],
        requirements=sections["requirements"],
        preferred=sections["preferred"],
        responsibilities=sections["responsibilities"],
        tech_stack=tech,
        experience_level=level,
    )
    return job.to_json()


# ==================== RESUME GENERATION TOOLS ====================

@mcp.tool()
def generate_resume(
    job_title: str,
    company: str,
    job_url: str = "",
    job_description: str = "",
    requirements: list[str] = None,
    preferred: list[str] = None,
    tech_stack: list[str] = None,
    experience_level: str = "mid",
    compile_pdf: bool = True
) -> str:
    """
    Generate a tailored resume for a specific job posting.
    Uses the profile database to select and prioritize the most relevant
    experience, projects, and skills.

    Args:
        job_title: The position title
        company: The company name
        job_url: URL of the job posting (optional)
        job_description: Full text of the job description
        requirements: List of job requirements
        preferred: List of preferred qualifications
        tech_stack: Technologies mentioned in the posting
        experience_level: entry, mid, senior, or staff
        compile_pdf: Whether to try compiling to PDF (requires pdflatex)
    """
    job = JobPosting(
        title=job_title,
        company=company,
        location="",
        url=job_url,
        description=job_description,
        requirements=requirements or [],
        preferred=preferred or [],
        responsibilities=[],
        tech_stack=tech_stack or [],
        experience_level=experience_level,
    )

    result = generate_resume_for_job(job)

    # Save to database
    pdf_path = None
    if compile_pdf:
        safe_name = f"{company.lower().replace(' ', '_')}_{job_title.lower().replace(' ', '_')}"
        safe_name = "".join(c for c in safe_name if c.isalnum() or c == '_')[:60]
        pdf_result = compile_latex_to_pdf(result["latex"], safe_name)
        if pdf_result.endswith(".pdf"):
            pdf_path = pdf_result

    resume_id = db.save_generated_resume(
        job_title=job_title,
        company=company,
        resume_latex=result["latex"],
        job_url=job_url,
        job_description=job_description[:3000],
        experience_ids=result["selected_experience_ids"],
        project_ids=result["selected_project_ids"],
        skills_used=result["selected_skills"],
        match_score=result["match_score"],
        resume_pdf_path=pdf_path,
    )

    output = {
        "resume_id": resume_id,
        "match_score": result["match_score"],
        "latex_preview": result["latex"][:500] + "...",
        "selected_experience_ids": result["selected_experience_ids"],
        "selected_project_ids": result["selected_project_ids"],
        "skills_highlighted": result["selected_skills"][:20],
    }

    if pdf_path:
        output["pdf_path"] = pdf_path
    else:
        # Save .tex file regardless
        out_dir = ensure_output_dir()
        safe_name = f"{company.lower().replace(' ', '_')}_{job_title.lower().replace(' ', '_')}"
        safe_name = "".join(c for c in safe_name if c.isalnum() or c == '_')[:60]
        tex_path = out_dir / f"{safe_name}.tex"
        tex_path.write_text(result["latex"])
        output["tex_path"] = str(tex_path)
        output["note"] = "PDF compilation not available. LaTeX source saved. Compile with: pdflatex <file>.tex"

    return json.dumps(output, indent=2)


@mcp.tool()
def get_resume_latex(resume_id: int) -> str:
    """Get the full LaTeX source of a previously generated resume."""
    resume = db.get_generated_resume(resume_id)
    if resume:
        return resume["resume_latex"]
    return "Resume not found"


@mcp.tool()
def list_generated_resumes(limit: int = 20) -> str:
    """List previously generated resumes with their job details and match scores."""
    resumes = db.get_generated_resumes(limit)
    return json.dumps(resumes, indent=2, default=str)


# ==================== WORKFLOW TOOLS ====================

@mcp.tool()
def scrape_and_generate(url: str, compile_pdf: bool = True) -> str:
    """
    One-shot: scrape a job posting URL and immediately generate a tailored resume.
    Combines scrape_job_posting and generate_resume into a single call.
    """
    try:
        job = parse_job_posting(url)
    except Exception as e:
        return json.dumps({"error": f"Failed to scrape job: {e}"})

    result = generate_resume_for_job(job)

    pdf_path = None
    if compile_pdf:
        safe_name = f"{job.company.lower().replace(' ', '_')}_{job.title.lower().replace(' ', '_')}"
        safe_name = "".join(c for c in safe_name if c.isalnum() or c == '_')[:60]
        pdf_result = compile_latex_to_pdf(result["latex"], safe_name)
        if pdf_result.endswith(".pdf"):
            pdf_path = pdf_result

    resume_id = db.save_generated_resume(
        job_title=job.title,
        company=job.company,
        resume_latex=result["latex"],
        job_url=url,
        job_description=job.description[:3000],
        experience_ids=result["selected_experience_ids"],
        project_ids=result["selected_project_ids"],
        skills_used=result["selected_skills"],
        match_score=result["match_score"],
        resume_pdf_path=pdf_path,
    )

    output = {
        "resume_id": resume_id,
        "job_title": job.title,
        "company": job.company,
        "tech_stack_detected": job.tech_stack,
        "experience_level": job.experience_level,
        "match_score": result["match_score"],
        "selected_experience_ids": result["selected_experience_ids"],
        "selected_project_ids": result["selected_project_ids"],
    }

    if pdf_path:
        output["pdf_path"] = pdf_path
    else:
        out_dir = ensure_output_dir()
        safe_name = f"{job.company.lower().replace(' ', '_')}_{job.title.lower().replace(' ', '_')}"
        safe_name = "".join(c for c in safe_name if c.isalnum() or c == '_')[:60]
        tex_path = out_dir / f"{safe_name}.tex"
        tex_path.write_text(result["latex"])
        output["tex_path"] = str(tex_path)

    return json.dumps(output, indent=2)


@mcp.tool()
def match_score(
    job_description: str,
    tech_stack: list[str] = None,
    requirements: list[str] = None
) -> str:
    """
    Check how well your profile matches a job without generating a full resume.
    Returns a match score and breakdown of which items are most relevant.
    """
    from generator import select_items_for_job

    job = JobPosting(
        title="", company="", location="", url="",
        description=job_description,
        requirements=requirements or [],
        preferred=[],
        responsibilities=[],
        tech_stack=tech_stack or [],
        experience_level="mid",
    )

    profile = db.get_full_profile()
    selection = select_items_for_job(profile, job)

    result = {
        "match_score": selection["match_score"],
        "top_experiences": [
            {"title": e.get("title"), "company": e.get("company"), "relevance": round(s, 2)}
            for s, e in selection["experiences"]
        ],
        "top_projects": [
            {"name": p.get("name"), "relevance": round(s, 2)}
            for s, p in selection["projects"]
        ],
        "matching_skills": [
            s["name"] for cat_skills in selection["skills"].values()
            for s in cat_skills
        ][:15],
    }
    return json.dumps(result, indent=2)


# ==================== REVIEW & ANALYSIS TOOLS ====================
# These tools do deterministic analysis (keyword gaps, weak verbs, ATS issues)
# and return structured feedback. The calling LLM (you, Claude/GPT) uses its
# own intelligence to rewrite bullets and optimize — no extra API calls needed.

@mcp.tool()
def evaluate_resume(
    resume_id: int = None,
    resume_latex: str = None,
    job_title: str = "",
    company: str = "",
    job_description: str = "",
    requirements: list[str] = None,
    preferred: list[str] = None,
    tech_stack: list[str] = None,
) -> str:
    """
    Build a complete evaluation context for resume optimization.
    Returns the resume LaTeX, plain text, job details, ATS check results,
    the full candidate profile, and detailed hiring-manager instructions.

    YOU (the calling LLM) use this context to act as a senior hiring manager
    and rewrite the resume. No scoring — you do the judgment.

    Args:
        resume_id: ID of a previously generated resume (auto-loads job details)
        resume_latex: Raw LaTeX source (alternative to resume_id)
        job_title: Position title
        company: Company name
        job_description: Full job description text
        requirements: List of requirements from posting
        preferred: List of nice-to-haves from posting
        tech_stack: Technologies mentioned in posting
    """
    if resume_id is not None:
        stored = db.get_generated_resume(resume_id)
        if not stored:
            return json.dumps({"error": f"Resume ID {resume_id} not found"})
        resume_latex = stored["resume_latex"]
        job_title = job_title or stored.get("job_title", "")
        company = company or stored.get("company", "")
        job_description = job_description or stored.get("job_description", "")

    if not resume_latex:
        return json.dumps({"error": "Provide either resume_id or resume_latex"})

    try:
        ctx = build_evaluation_context(
            resume_latex=resume_latex,
            job_title=job_title,
            company=company,
            job_description=job_description,
            requirements=requirements,
            preferred=preferred,
            tech_stack=tech_stack,
        )
        return json.dumps(ctx, indent=2, default=str)
    except Exception as e:
        return json.dumps({"error": str(e)})


@mcp.tool()
def get_resume_with_context(
    resume_id: int,
) -> str:
    """
    Get a generated resume's full LaTeX source along with the job details
    and the candidate's complete profile. Use this when you want to rewrite
    or improve a resume — it gives you everything in one call.

    Returns: resume LaTeX, job info, and the full profile database.
    """
    stored = db.get_generated_resume(resume_id)
    if not stored:
        return json.dumps({"error": f"Resume ID {resume_id} not found"})

    profile = db.get_full_profile()

    return json.dumps({
        "resume_latex": stored["resume_latex"],
        "job": {
            "title": stored.get("job_title", ""),
            "company": stored.get("company", ""),
            "url": stored.get("job_url", ""),
            "description": stored.get("job_description", ""),
        },
        "match_score": stored.get("match_score"),
        "full_profile": profile,
    }, indent=2, default=str)


@mcp.tool()
def save_optimized_resume(
    resume_latex: str,
    job_title: str,
    company: str,
    job_url: str = "",
    job_description: str = "",
    compile_pdf: bool = True,
) -> str:
    """
    Save a rewritten/optimized resume back to the database.
    Call this after YOU (the LLM) have rewritten the resume using
    review feedback. Pass in your improved LaTeX.

    Args:
        resume_latex: The improved LaTeX resume source
        job_title: Position title
        company: Company name
        job_url: Job posting URL
        job_description: Job description for records
        compile_pdf: Try to compile to PDF
    """
    pdf_path = None
    safe_name = f"{company.lower().replace(' ', '_')}_{job_title.lower().replace(' ', '_')}_optimized"
    safe_name = "".join(c for c in safe_name if c.isalnum() or c == '_')[:60]

    if compile_pdf:
        pdf_result = compile_latex_to_pdf(resume_latex, safe_name)
        if pdf_result.endswith(".pdf"):
            pdf_path = pdf_result

    resume_id = db.save_generated_resume(
        job_title=f"{job_title} (optimized)",
        company=company,
        resume_latex=resume_latex,
        job_url=job_url,
        job_description=job_description[:3000],
        resume_pdf_path=pdf_path,
    )

    output = {
        "resume_id": resume_id,
        "saved": True,
    }

    if pdf_path:
        output["pdf_path"] = pdf_path
    else:
        out_dir = ensure_output_dir()
        tex_path = out_dir / f"{safe_name}.tex"
        tex_path.write_text(resume_latex)
        output["tex_path"] = str(tex_path)
        output["note"] = "PDF compilation not available. LaTeX saved. Compile with pdflatex or paste into Overleaf."

    return json.dumps(output, indent=2)


@mcp.tool()
def full_pipeline(url: str, compile_pdf: bool = True) -> str:
    """
    Scrape a job URL → generate a tailored resume → run deterministic analysis.
    Returns the resume LaTeX, the analysis, AND the full profile so YOU (the LLM)
    can immediately rewrite it with improvements.

    No API keys needed. You do the creative optimization.

    Recommended workflow after calling this:
    1. Read the analysis (keyword gaps, weak verbs, ATS issues)
    2. Act as a hiring manager — rewrite bullets, weave in keywords, reorder sections
    3. Call save_optimized_resume with your improved LaTeX

    Args:
        url: Job posting URL
        compile_pdf: Try to compile initial version to PDF
    """
    try:
        # Step 1: Scrape
        job = parse_job_posting(url)

        # Step 2: Generate initial resume
        result = generate_resume_for_job(job)
        initial_latex = result["latex"]

        # Step 3: Build evaluation context
        jd_text = f"{job.title} {job.company} {job.description} {' '.join(job.requirements)} {' '.join(job.preferred)}"
        ats = run_ats_check(initial_latex, jd_text)
        eval_ctx = build_evaluation_context(
            resume_latex=initial_latex,
            job_title=job.title,
            company=job.company,
            job_description=job.description,
            requirements=job.requirements,
            preferred=job.preferred,
            tech_stack=job.tech_stack,
        )

        # Save initial version
        pdf_path = None
        safe_name = f"{job.company.lower().replace(' ', '_')}_{job.title.lower().replace(' ', '_')}"
        safe_name = "".join(c for c in safe_name if c.isalnum() or c == '_')[:50]

        if compile_pdf:
            pdf_result = compile_latex_to_pdf(initial_latex, safe_name)
            if pdf_result.endswith(".pdf"):
                pdf_path = pdf_result

        resume_id = db.save_generated_resume(
            job_title=job.title,
            company=job.company,
            resume_latex=initial_latex,
            job_url=url,
            job_description=job.description[:3000],
            experience_ids=result["selected_experience_ids"],
            project_ids=result["selected_project_ids"],
            skills_used=result["selected_skills"],
            match_score=result["match_score"],
            resume_pdf_path=pdf_path,
        )

        profile = db.get_full_profile()

        output = {
            "resume_id": resume_id,
            "job": {
                "title": job.title,
                "company": job.company,
                "location": job.location,
                "tech_stack": job.tech_stack,
                "experience_level": job.experience_level,
                "salary": job.salary_range,
                "requirements": job.requirements[:15],
                "preferred": job.preferred[:10],
            },
            "initial_resume_latex": initial_latex,
            "evaluation_context": eval_ctx,
        }

        if pdf_path:
            output["initial_pdf_path"] = pdf_path

        # Auto-log to tracker spreadsheet
        try:
            tracker_row = add_application(
                company=job.company,
                job_title=job.title,
                job_url=url,
                status="Generated",
                resume_id=resume_id,
                pdf_path=str(pdf_path) if pdf_path else None,
            )
            output["tracker_row"] = tracker_row
            output["tracker_path"] = str(TRACKER_PATH)
        except Exception:
            pass  # Don't fail the pipeline if tracker has issues

        return json.dumps(output, indent=2, default=str)

    except Exception as e:
        return json.dumps({"error": str(e)})


# ==================== TRACKER TOOLS ====================

@mcp.tool()
def log_application(
    company: str,
    job_title: str,
    job_url: str = "",
    status: str = "Generated",
    overall_score: int = None,
    keyword_score: int = None,
    tech_score: int = None,
    impact_score: int = None,
    tech_matches: list[str] = None,
    tech_gaps: list[str] = None,
    keyword_gaps: list[str] = None,
    resume_id: int = None,
    pdf_path: str = None,
    notes: str = "",
) -> str:
    """
    Log an application to the tracking spreadsheet (~/.resume-mcp/applications.xlsx).
    Automatically called by full_pipeline, but you can also call manually.

    Status options: Generated, Optimized, Applied, Interview, Rejected, Offer

    Args:
        company: Company name
        job_title: Position title
        job_url: Job posting URL
        status: Current status (Generated/Optimized/Applied/Interview/Rejected/Offer)
        overall_score: Analysis overall score (0-100)
        keyword_score: Keyword match score
        tech_score: Tech stack match score
        impact_score: Bullet impact score
        tech_matches: Technologies that matched
        tech_gaps: Technologies missing from resume
        keyword_gaps: Keywords missing from resume
        resume_id: ID of generated resume in database
        pdf_path: Path to generated PDF
        notes: Any notes about this application
    """
    row = add_application(
        company=company, job_title=job_title, job_url=job_url, status=status,
        overall_score=overall_score, keyword_score=keyword_score,
        tech_score=tech_score, impact_score=impact_score,
        tech_matches=tech_matches, tech_gaps=tech_gaps,
        keyword_gaps=keyword_gaps, resume_id=resume_id,
        pdf_path=pdf_path, notes=notes,
    )
    return json.dumps({
        "logged": True,
        "row": row,
        "tracker_path": str(TRACKER_PATH),
    })


@mcp.tool()
def update_application_status(
    row: int,
    status: str,
    notes: str = None,
) -> str:
    """
    Update the status of a tracked application.

    Args:
        row: Row number in the spreadsheet (returned by log_application)
        status: New status (Generated/Optimized/Applied/Interview/Rejected/Offer)
        notes: Optional notes to add
    """
    update_status(row, status, notes)
    return json.dumps({"updated": True, "row": row, "new_status": status})


@mcp.tool()
def get_application_stats() -> str:
    """
    Get summary stats from the application tracker.
    Returns total applications, breakdown by status, average scores, etc.
    """
    stats = get_stats()
    return json.dumps(stats, indent=2)


# ==================== MCP PROMPTS ====================
# These give the calling LLM (Claude/GPT) a hiring manager persona
# when working with resume tools.

@mcp.prompt()
def hiring_manager_review():
    """Adopt the persona of a senior hiring manager to review and optimize a resume."""
    return (
        "You are now acting as a senior hiring manager and ATS expert with 15+ years "
        "in tech recruiting. When reviewing resumes, you think as three people simultaneously:\n\n"
        "1. ATS SCANNER — Match job description phrases to resume text verbatim. "
        "If the JD says 'React.js', the resume must say 'React.js', not 'React'. "
        "Flag every keyword gap.\n\n"
        "2. HIRING MANAGER — You scan resumes in 6 seconds. You want: quantified impact "
        "(%, $, users, scale), strong action verbs (Engineered > Worked on), "
        "and clear relevance to the role. Achievement-oriented, not responsibility-oriented.\n\n"
        "3. TECHNICAL RECRUITER — Match tech stack depth, seniority signals, and "
        "trajectory. 'Used Python' is weaker than 'Architected distributed Python services'.\n\n"
        "Use the resume-builder tools to: get the profile, generate a resume, analyze it, "
        "then rewrite it incorporating all improvements. Save the optimized version when done."
    )


if __name__ == "__main__":
    mcp.run()
