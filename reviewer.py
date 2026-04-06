"""
Resume reviewer module. Performs deterministic ATS checks on a resume,
then packages everything the calling LLM needs to act as a hiring manager.

No scoring, no keyword extraction. Regex only does what it's reliable for.
The LLM (Claude, GPT, etc.) does the judgment.
"""

import json
import re
from dataclasses import dataclass, asdict, field


# ==================== CONSTANTS ====================

WEAK_VERBS = {
    "responsible for", "worked on", "helped with", "assisted in",
    "involved in", "participated in", "contributed to", "tasked with",
    "dealt with", "handled", "managed", "was part of", "supported",
    "utilized", "leveraged",
}

QUANTIFICATION_PATTERNS = [
    r'\d+%', r'\$[\d,]+', r'\d+x\b', r'\d+\+?\s*(users|clients|customers|facilities|lockers)',
    r'reduced\s+.*\d+', r'increased\s+.*\d+', r'improved\s+.*\d+',
    r'saving\s+.*\d+', r'generating\s+.*\d+', r'scaled\s+to\s+\d+',
    r'\d+\s*(ms|seconds?|minutes?|hours?)', r'\d+\s*GB',
]

# Canonical tech name → list of accepted aliases
TECH_ALIASES = {
    "react": ["react", "react.js", "reactjs"],
    "next.js": ["next.js", "nextjs", "next"],
    "node.js": ["node.js", "nodejs", "node"],
    "express.js": ["express.js", "expressjs", "express"],
    "vue.js": ["vue.js", "vuejs", "vue"],
    "typescript": ["typescript", "ts"],
    "javascript": ["javascript", "js"],
    "postgresql": ["postgresql", "postgres", "psql"],
    "mongodb": ["mongodb", "mongo"],
    "kubernetes": ["kubernetes", "k8s"],
    "golang": ["golang", "go"],
    "ci/cd": ["ci/cd", "cicd", "ci cd", "continuous integration", "continuous deployment"],
    "aws": ["aws", "amazon web services"],
    "gcp": ["gcp", "google cloud", "google cloud platform"],
    "machine learning": ["machine learning", "ml"],
    "deep learning": ["deep learning", "dl"],
    "natural language processing": ["natural language processing", "nlp"],
    "rest api": ["rest api", "rest apis", "restful", "rest"],
}

EVALUATION_INSTRUCTIONS = """
You are acting as a senior hiring manager and ATS expert reviewing a resume against a job posting.

You have been given:
- The resume in LaTeX source and plain text
- The job posting details (title, company, description, requirements, preferred)
- A deterministic ATS check with objective issues (see ats_check)
- The candidate's full accomplishment database (full_profile_structured)

Your job is to act as THREE people simultaneously:

1. ATS SCANNER
   - Flag every place where the JD uses a specific phrasing and the resume doesn't match exactly.
   - "React.js" in the JD means the resume should say "React.js", not "React".
   - Check phrasing_mismatches in ats_check for pre-detected cases.

2. HIRING MANAGER (6-second scan)
   - You want quantified impact: %, $, users, scale, time saved.
   - Strong action verbs: "Engineered" >> "Worked on". See weak_verb_bullets in ats_check.
   - Achievement-oriented bullets, not responsibility-oriented.
   - unquantified_bullets in ats_check flags bullets that need numbers added.

3. TECHNICAL RECRUITER
   - Does the tech stack depth match the role seniority?
   - Are the most relevant technologies from the JD surfaced prominently?
   - Could any unused profile items (from full_profile_structured) strengthen the resume?

REWRITE PROCESS:
1. Fix every ATS phrasing mismatch — match the JD's exact tech names.
2. Rewrite weak-verb bullets with strong action verbs + quantified impact.
3. Add metrics to unquantified bullets where plausible (use profile context).
4. Add any missing section headers flagged in missing_sections.
5. Consider swapping in unused profile items more relevant to this specific role.
6. Reorder skills so JD-matching ones appear first in each category.
7. Return the complete improved LaTeX, then call save_optimized_resume.

Be specific. Change actual bullets. Don't just describe what to change.
""".strip()


# ==================== DATACLASSES ====================

@dataclass
class ATSCheck:
    phrasing_mismatches: list[dict]   # [{"jd_form": "React.js", "resume_form": "React"}]
    weak_verb_bullets: list[dict]     # [{"text": "...", "weak_verb": "responsible for"}]
    unquantified_bullets: list[str]   # bullet texts without any metric pattern
    quantified_bullet_count: int
    total_bullet_count: int
    missing_sections: list[str]       # e.g. ["Education", "Skills"]

    def to_dict(self):
        return asdict(self)


# ==================== HELPERS ====================

def _extract_text_from_latex(latex: str) -> str:
    """Strip LaTeX commands to get plain text content."""
    text = latex
    text = re.sub(r'\\(?:textbf|textit|emph|small|large|huge|scshape|underline)\{([^}]*)\}', r'\1', text)
    text = re.sub(r'\\href\{[^}]*\}\{([^}]*)\}', r'\1', text)
    text = re.sub(r'\\(?:resumeItem|resumeSubheading|resumeProjectHeading)\{', '', text)
    text = re.sub(r'\\[a-zA-Z]+(?:\[[^\]]*\])?\{?', '', text)
    text = re.sub(r'[{}\\$]', ' ', text)
    text = re.sub(r'\s+', ' ', text)
    return text.strip()


def _extract_bullets_from_latex(latex: str) -> list[str]:
    """Extract bullet text strings from \\resumeItem{...} entries."""
    bullets = []
    for match in re.finditer(r'\\resumeItem\{((?:[^{}]|\{[^{}]*\})*)\}', latex):
        raw = match.group(1)
        clean = re.sub(r'\\[a-zA-Z]+\{([^}]*)\}', r'\1', raw)
        clean = re.sub(r'[\\{}$]', '', clean).strip()
        if clean and len(clean) > 10:
            bullets.append(clean)
    return bullets


def _check_weak_verb(text: str) -> str | None:
    """Return the weak verb if the bullet starts with one, else None."""
    lower = text.lower().strip()
    for verb in WEAK_VERBS:
        if lower.startswith(verb):
            return verb
    return None


def _has_metric(text: str) -> bool:
    for pattern in QUANTIFICATION_PATTERNS:
        if re.search(pattern, text, re.IGNORECASE):
            return True
    return False


# ==================== PUBLIC API ====================

def run_ats_check(resume_latex: str, jd_text: str) -> ATSCheck:
    """
    Deterministic ATS check. Only does what regex is reliable for:
    - Exact tech name phrasing mismatches between JD and resume
    - Weak verb detection on bullet starts
    - Metric pattern matching on bullets
    - Section header existence
    """
    resume_plain = _extract_text_from_latex(resume_latex)
    resume_lower = resume_plain.lower()
    jd_lower = jd_text.lower()

    # --- Phrasing mismatches ---
    mismatches = []
    for canonical, aliases in TECH_ALIASES.items():
        jd_forms = [a for a in aliases if re.search(r'\b' + re.escape(a) + r'\b', jd_lower)]
        resume_forms = [a for a in aliases if re.search(r'\b' + re.escape(a) + r'\b', resume_lower)]
        if jd_forms and resume_forms:
            jd_form = jd_forms[0]
            resume_form = resume_forms[0]
            if jd_form != resume_form:
                mismatches.append({"jd_form": jd_form, "resume_form": resume_form})

    # --- Bullet analysis ---
    bullets = _extract_bullets_from_latex(resume_latex)
    weak_verb_bullets = []
    unquantified = []
    quantified_count = 0

    for text in bullets:
        verb = _check_weak_verb(text)
        if verb:
            weak_verb_bullets.append({"text": text, "weak_verb": verb})

        if _has_metric(text):
            quantified_count += 1
        else:
            unquantified.append(text)

    # --- Missing sections ---
    missing_sections = []
    for section in ["Education", "Experience", "Skills"]:
        if not re.search(r'\\section\{[^}]*' + section, resume_latex):
            missing_sections.append(section)

    return ATSCheck(
        phrasing_mismatches=mismatches,
        weak_verb_bullets=weak_verb_bullets,
        unquantified_bullets=unquantified[:15],
        quantified_bullet_count=quantified_count,
        total_bullet_count=len(bullets),
        missing_sections=missing_sections,
    )


def build_evaluation_context(
    resume_latex: str,
    job_title: str = "",
    company: str = "",
    job_description: str = "",
    requirements: list[str] = None,
    preferred: list[str] = None,
    tech_stack: list[str] = None,
    full_profile: dict = None,
) -> dict:
    """
    Package everything the calling LLM needs to evaluate and rewrite the resume.
    Returns a dict ready for JSON serialization.
    """
    from database import get_full_profile

    if full_profile is None:
        full_profile = get_full_profile()

    requirements = requirements or []
    preferred = preferred or []
    tech_stack = tech_stack or []

    jd_text = f"{job_title} {company} {job_description} {' '.join(requirements)} {' '.join(preferred)}"
    ats = run_ats_check(resume_latex, jd_text)
    resume_plain = _extract_text_from_latex(resume_latex)

    return {
        "resume_latex": resume_latex,
        "resume_plain_text": resume_plain,
        "job": {
            "title": job_title,
            "company": company,
            "description": job_description,
            "requirements": requirements,
            "preferred": preferred,
            "tech_stack": tech_stack,
        },
        "ats_check": ats.to_dict(),
        "full_profile_text": json.dumps(full_profile, indent=2, default=str),
        "full_profile_structured": full_profile,
        "evaluation_instructions": EVALUATION_INSTRUCTIONS,
    }
