"""
Resume generator. Produces tailored LaTeX resumes based on profile data
and job posting requirements. Scores relevance and selects the best
experience/projects to highlight.
"""

import json
import re
import subprocess
import os
from pathlib import Path
from dataclasses import dataclass

from database import get_full_profile, get_skills
from scraper import JobPosting


RESUME_OUTPUT_DIR = Path.home() / ".resume-mcp" / "generated"


def ensure_output_dir():
    RESUME_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    return RESUME_OUTPUT_DIR


def compute_relevance_score(item_tags: list[str], item_text: str,
                            job_tech: list[str], job_requirements: list[str],
                            job_description: str) -> float:
    """
    Score how relevant a profile item is to a job posting.
    Returns 0.0-1.0.
    """
    score = 0.0
    max_score = 0.0

    # Tag overlap with job tech stack (high weight)
    if job_tech:
        max_score += 40
        item_tags_lower = {t.lower() for t in item_tags}
        job_tech_lower = {t.lower() for t in job_tech}
        overlap = item_tags_lower & job_tech_lower
        if job_tech_lower:
            score += 40 * (len(overlap) / len(job_tech_lower))

    # Keyword overlap with requirements
    if job_requirements:
        max_score += 35
        req_text = " ".join(job_requirements).lower()
        item_text_lower = item_text.lower()
        # Count matching important words
        important_words = set(re.findall(r'\b\w{4,}\b', req_text))
        item_words = set(re.findall(r'\b\w{4,}\b', item_text_lower))
        if important_words:
            word_overlap = important_words & item_words
            score += 35 * min(1.0, len(word_overlap) / (len(important_words) * 0.3))

    # Description keyword match (lower weight)
    if job_description:
        max_score += 25
        desc_lower = job_description.lower()
        item_text_lower = item_text.lower()
        desc_words = set(re.findall(r'\b\w{5,}\b', desc_lower))
        item_words = set(re.findall(r'\b\w{5,}\b', item_text_lower))
        if desc_words:
            overlap = desc_words & item_words
            score += 25 * min(1.0, len(overlap) / (len(desc_words) * 0.2))

    return (score / max_score) if max_score > 0 else 0.5


def select_items_for_job(profile: dict, job: JobPosting,
                         max_experiences: int = 4, max_projects: int = 4) -> dict:
    """Select and rank the most relevant experience and projects for a job."""

    # Score experiences
    scored_exp = []
    for exp in profile["experience"]:
        text = f"{exp['title']} {exp['company']} {' '.join(exp['bullets'])}"
        tags = exp.get("tags", [])
        score = compute_relevance_score(tags, text, job.tech_stack,
                                        job.requirements, job.description)
        scored_exp.append((score, exp))

    scored_exp.sort(key=lambda x: x[0], reverse=True)

    # Score projects
    scored_proj = []
    for proj in profile["projects"]:
        text = f"{proj['name']} {' '.join(proj['bullets'])} {' '.join(proj.get('tech_stack', []))}"
        tags = proj.get("tags", []) + proj.get("tech_stack", [])
        score = compute_relevance_score(tags, text, job.tech_stack,
                                        job.requirements, job.description)
        scored_proj.append((score, proj))

    scored_proj.sort(key=lambda x: x[0], reverse=True)

    # Select relevant skills
    all_skills = profile.get("skills", {})
    job_tech_lower = {t.lower() for t in job.tech_stack}
    req_text = " ".join(job.requirements + job.preferred).lower()

    selected_skills = {}
    for category, skill_list in all_skills.items():
        relevant = []
        other = []
        for s in skill_list:
            name_lower = s["name"].lower()
            if name_lower in job_tech_lower or name_lower in req_text:
                relevant.append(s)
            else:
                other.append(s)
        # Put relevant skills first, then fill with others
        selected_skills[category] = relevant + other

    # Compute overall match score
    all_scores = [s for s, _ in scored_exp] + [s for s, _ in scored_proj]
    match_score = sum(all_scores) / len(all_scores) if all_scores else 0.0

    return {
        "experiences": [(s, e) for s, e in scored_exp[:max_experiences]],
        "projects": [(s, p) for s, p in scored_proj[:max_projects]],
        "skills": selected_skills,
        "match_score": round(match_score, 3),
    }


def escape_latex(text: str) -> str:
    """Escape special LaTeX characters."""
    replacements = {
        '&': r'\&',
        '%': r'\%',
        '$': r'\$',
        '#': r'\#',
        '_': r'\_',
        '{': r'\{',
        '}': r'\}',
        '~': r'\textasciitilde{}',
        '^': r'\textasciicircum{}',
    }
    for char, replacement in replacements.items():
        text = text.replace(char, replacement)
    return text


def generate_latex(profile: dict, selection: dict, job: JobPosting) -> str:
    """Generate a complete LaTeX resume tailored to the job."""
    contact = profile.get("contact", {}) or {}
    education = profile.get("education", [])

    # Build header
    name = escape_latex(contact.get("name", "Your Name"))
    header_parts = []
    if contact.get("phone"):
        header_parts.append(contact["phone"])
    if contact.get("email"):
        header_parts.append(r"\href{mailto:" + contact["email"] + "}{" + escape_latex(contact["email"]) + "}")
    if contact.get("linkedin"):
        li = contact["linkedin"]
        header_parts.append(r"\href{https://linkedin.com/in/" + li + "}{linkedin.com/in/" + escape_latex(li) + "}")
    if contact.get("github"):
        gh = contact["github"]
        header_parts.append(r"\href{https://github.com/" + gh + "}{github.com/" + escape_latex(gh) + "}")
    if contact.get("website"):
        ws = contact["website"]
        header_parts.append(r"\href{https://" + ws + "}{" + escape_latex(ws) + "}")

    header_line = " $|$ ".join(header_parts)

    # Build education section
    edu_items = []
    for edu in education:
        institution = escape_latex(edu.get("institution", ""))
        location = escape_latex(edu.get("location", ""))
        degree = escape_latex(edu.get("degree", ""))
        field = escape_latex(edu.get("field", ""))
        degree_str = f"{degree} in {field}" if field else degree
        gpa_str = f", GPA: {edu['gpa']}" if edu.get("gpa") else ""
        dates = ""
        if edu.get("end_date"):
            dates = f"Expected {escape_latex(edu['end_date'])}" if "2028" in str(edu.get("end_date", "")) else escape_latex(edu["end_date"])

        coursework = ""
        if edu.get("coursework"):
            courses = ", ".join(escape_latex(c) for c in edu["coursework"])
            coursework = f"\n    \\resumeItem{{Relevant Coursework: {courses}}}"

        edu_items.append(f"""    \\resumeSubheading
      {{{institution}}}{{{location}}}
      {{{degree_str}{gpa_str}}}{{{dates}}}{coursework}""")

    edu_section = "\n".join(edu_items)

    # Build experience section
    exp_items = []
    for score, exp in selection["experiences"]:
        company = escape_latex(exp.get("company", ""))
        title = escape_latex(exp.get("title", ""))
        location = escape_latex(exp.get("location", ""))
        start = escape_latex(exp.get("start_date", ""))
        end = escape_latex(exp.get("end_date", "Present"))
        dates = f"{start} -- {end}"

        bullets = "\n".join(
            f"        \\resumeItem{{{escape_latex(b)}}}"
            for b in exp.get("bullets", [])
        )

        exp_items.append(f"""    \\resumeSubheading
      {{{title}}}{{{dates}}}
      {{{company}}}{{{location}}}
      \\resumeItemListStart
{bullets}
      \\resumeItemListEnd""")

    exp_section = "\n".join(exp_items)

    # Build projects section
    proj_items = []
    for score, proj in selection["projects"]:
        name_esc = escape_latex(proj.get("name", ""))
        tech = ", ".join(escape_latex(t) for t in proj.get("tech_stack", []))
        url = proj.get("url", "")

        if url:
            proj_header = f"\\resumeProjectHeading{{\\textbf{{{name_esc}}} $|$ \\emph{{\\small {tech}}}}}{{\\href{{{url}}}{{\\underline{{Link}}}}}}"
        else:
            proj_header = f"\\resumeProjectHeading{{\\textbf{{{name_esc}}} $|$ \\emph{{\\small {tech}}}}}{{}}"

        bullets = "\n".join(
            f"        \\resumeItem{{{escape_latex(b)}}}"
            for b in proj.get("bullets", [])
        )

        proj_items.append(f"""    {proj_header}
      \\resumeItemListStart
{bullets}
      \\resumeItemListEnd""")

    proj_section = "\n".join(proj_items)

    # Build skills section
    skill_lines = []
    for category, skills in selection["skills"].items():
        names = ", ".join(escape_latex(s["name"]) for s in skills)
        skill_lines.append(f"      \\textbf{{{escape_latex(category)}}}{{: {names}}} \\\\")

    skills_section = "\n".join(skill_lines)

    # Assemble full LaTeX document
    latex = r"""\documentclass[letterpaper,11pt]{article}

\usepackage{latexsym}
\usepackage[empty]{fullpage}
\usepackage{titlesec}
\usepackage{marvosym}
\usepackage[usenames,dvipsnames]{color}
\usepackage{verbatim}
\usepackage{enumitem}
\usepackage[hidelinks]{hyperref}
\usepackage{fancyhdr}
\usepackage[english]{babel}
\usepackage{tabularx}
\input{glyphtounicode}

\pagestyle{fancy}
\fancyhf{}
\fancyfoot{}
\renewcommand{\headrulewidth}{0pt}
\renewcommand{\footrulewidth}{0pt}

\addtolength{\oddsidemargin}{-0.5in}
\addtolength{\evensidemargin}{-0.5in}
\addtolength{\textwidth}{1in}
\addtolength{\topmargin}{-.5in}
\addtolength{\textheight}{1.0in}

\urlstyle{same}
\raggedbottom
\raggedright
\setlength{\tabcolsep}{0in}

\titleformat{\section}{
  \vspace{-4pt}\scshape\raggedright\large
}{}{0em}{}[\color{black}\titlerule \vspace{-5pt}]

\pdfgentounicode=1

% Custom commands
\newcommand{\resumeItem}[1]{\item\small{#1 \vspace{-2pt}}}
\newcommand{\resumeSubheading}[4]{
  \vspace{-2pt}\item
    \begin{tabular*}{0.97\textwidth}[t]{l@{\extracolsep{\fill}}r}
      \textbf{#1} & #2 \\
      \textit{\small#3} & \textit{\small #4} \\
    \end{tabular*}\vspace{-7pt}
}
\newcommand{\resumeProjectHeading}[2]{
    \item
    \begin{tabular*}{0.97\textwidth}{l@{\extracolsep{\fill}}r}
      \small#1 & #2 \\
    \end{tabular*}\vspace{-7pt}
}
\newcommand{\resumeItemListStart}{\begin{itemize}[leftmargin=0.15in, label={}] \setlength\itemsep{0pt}}
\newcommand{\resumeItemListEnd}{\end{itemize}}
\newcommand{\resumeSubHeadingListStart}{\begin{itemize}[leftmargin=0.15in, label={}]}
\newcommand{\resumeSubHeadingListEnd}{\end{itemize}}

\begin{document}

%----------HEADING----------
\begin{center}
    \textbf{\Huge \scshape """ + name + r"""} \\ \vspace{1pt}
    \small """ + header_line + r"""
\end{center}

%-----------EDUCATION-----------
\section{Education}
  \resumeSubHeadingListStart
""" + edu_section + r"""
  \resumeSubHeadingListEnd

%-----------EXPERIENCE-----------
\section{Experience}
  \resumeSubHeadingListStart
""" + exp_section + r"""
  \resumeSubHeadingListEnd

%-----------PROJECTS-----------
\section{Projects}
  \resumeSubHeadingListStart
""" + proj_section + r"""
  \resumeSubHeadingListEnd

%-----------TECHNICAL SKILLS-----------
\section{Technical Skills}
  \begin{itemize}[leftmargin=0.15in, label={}]
    \small{\item{
""" + skills_section + r"""
    }}
  \end{itemize}

\end{document}
"""
    return latex


def generate_resume_for_job(job: JobPosting, profile: dict = None) -> dict:
    """
    Main entry point: generate a tailored resume for a job posting.
    Returns dict with latex, match_score, selection details.
    """
    if profile is None:
        profile = get_full_profile()

    selection = select_items_for_job(profile, job)
    latex = generate_latex(profile, selection, job)

    return {
        "latex": latex,
        "match_score": selection["match_score"],
        "selected_experience_ids": [e.get("id") for _, e in selection["experiences"]],
        "selected_project_ids": [p.get("id") for _, p in selection["projects"]],
        "selected_skills": [
            s["name"] for skills in selection["skills"].values() for s in skills
        ],
    }


def _find_latex_compiler() -> tuple[str | None, str | None]:
    """Search PATH + macOS/Linux common locations for a LaTeX compiler.
    Returns (compiler_name, binary_path) or (None, None)."""
    import shutil

    extra_dirs = [
        "/Library/TeX/texbin",
        "/usr/local/texlive/2024/bin/universal-darwin",
        "/usr/local/texlive/2023/bin/universal-darwin",
        "/usr/local/texlive/2022/bin/universal-darwin",
        "/usr/local/texlive/2024/bin/x86_64-linux",
        "/usr/local/texlive/2023/bin/x86_64-linux",
        "/opt/homebrew/bin",
        "/usr/local/bin",
    ]

    for name in ["pdflatex", "xelatex", "lualatex", "tectonic", "latexmk"]:
        found = shutil.which(name)
        if found:
            return name, found
        for d in extra_dirs:
            candidate = os.path.join(d, name)
            if os.path.isfile(candidate) and os.access(candidate, os.X_OK):
                return name, candidate

    return None, None


def compile_latex_to_pdf(latex: str, output_name: str) -> str:
    """Attempt to compile LaTeX to PDF using any available compiler.
    Always saves .tex regardless of compilation result. Returns PDF path or error message."""
    out_dir = ensure_output_dir()
    tex_path = out_dir / f"{output_name}.tex"
    pdf_path = out_dir / f"{output_name}.pdf"

    tex_path.write_text(latex)

    compiler, compiler_path = _find_latex_compiler()
    if not compiler:
        return (
            f"No LaTeX compiler found. LaTeX source saved to {tex_path}. "
            "Install texlive or tectonic to compile."
        )

    if compiler == "tectonic":
        cmd = [compiler_path, "--outdir", str(out_dir), str(tex_path)]
    elif compiler == "latexmk":
        cmd = [compiler_path, "-pdf", "-interaction=nonstopmode",
               f"-output-directory={out_dir}", str(tex_path)]
    else:
        # pdflatex, xelatex, lualatex
        cmd = [compiler_path, "-interaction=nonstopmode",
               "-output-directory", str(out_dir), str(tex_path)]

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
        if pdf_path.exists():
            for ext in [".aux", ".log", ".out"]:
                aux = out_dir / f"{output_name}{ext}"
                if aux.exists():
                    aux.unlink()
            return str(pdf_path)
        else:
            return f"Compilation failed ({compiler}): {result.stderr[-500:]}"
    except subprocess.TimeoutExpired:
        return f"Compilation timed out after 60s. LaTeX source saved to {tex_path}."
