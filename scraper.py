"""
Job posting scraper. Extracts structured job data from URLs.
Uses trafilatura for content extraction and basic NLP for parsing.
"""

import re
import json
from dataclasses import dataclass, asdict
from typing import Optional

try:
    import trafilatura
except ImportError:
    trafilatura = None

try:
    import requests
except ImportError:
    requests = None


@dataclass
class JobPosting:
    title: str
    company: str
    location: str
    url: str
    description: str
    requirements: list[str]
    preferred: list[str]
    responsibilities: list[str]
    tech_stack: list[str]
    experience_level: str  # entry, mid, senior, staff
    salary_range: Optional[str] = None
    remote: Optional[bool] = None

    def to_dict(self):
        return asdict(self)

    def to_json(self):
        return json.dumps(self.to_dict(), indent=2)


# Common tech keywords for extraction
TECH_KEYWORDS = {
    # Languages
    "python", "java", "javascript", "typescript", "go", "golang", "rust", "c++", "c#",
    "ruby", "php", "swift", "kotlin", "scala", "r", "sql", "html", "css", "bash",
    # Frameworks
    "react", "react.js", "reactjs", "next.js", "nextjs", "angular", "vue", "vue.js",
    "django", "flask", "fastapi", "spring", "express", "express.js", "node.js", "nodejs",
    "pytorch", "tensorflow", "keras", "langchain", "langgraph",
    # Cloud/Infra
    "aws", "gcp", "azure", "docker", "kubernetes", "k8s", "terraform", "jenkins",
    "github actions", "ci/cd", "cloudflare", "vercel", "heroku", "netlify",
    # Databases
    "postgresql", "postgres", "mysql", "mongodb", "redis", "dynamodb", "supabase",
    "firebase", "sqlite", "elasticsearch", "cassandra",
    # Tools/Concepts
    "git", "graphql", "rest", "grpc", "microservices", "distributed systems",
    "machine learning", "deep learning", "computer vision", "nlp", "llm",
    "agile", "scrum", "prisma", "trpc", "oauth", "stripe", "websockets",
}

EXPERIENCE_PATTERNS = {
    "entry": [r"entry.?level", r"junior", r"0.?[–-].?2\s*years?", r"new\s*grad", r"intern"],
    "mid": [r"mid.?level", r"2.?[–-].?5\s*years?", r"3.?\+?\s*years?"],
    "senior": [r"senior", r"sr\.?", r"5.?\+?\s*years?", r"6.?[–-].?10\s*years?"],
    "staff": [r"staff", r"principal", r"lead", r"10.?\+?\s*years?", r"architect"],
}


def fetch_page_text(url: str) -> str:
    """Fetch and extract main text content from a URL."""
    if requests is None:
        raise ImportError("requests library required: pip install requests")

    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
    }
    resp = requests.get(url, headers=headers, timeout=15)
    resp.raise_for_status()

    if trafilatura:
        text = trafilatura.extract(resp.text, include_links=False, include_tables=True)
        if text:
            return text

    # Fallback: basic HTML stripping
    from html.parser import HTMLParser

    class TextExtractor(HTMLParser):
        def __init__(self):
            super().__init__()
            self.parts = []
            self.skip = False

        def handle_starttag(self, tag, attrs):
            if tag in ("script", "style", "nav", "footer", "header"):
                self.skip = True

        def handle_endtag(self, tag):
            if tag in ("script", "style", "nav", "footer", "header"):
                self.skip = False

        def handle_data(self, data):
            if not self.skip:
                self.parts.append(data.strip())

    extractor = TextExtractor()
    extractor.feed(resp.text)
    return "\n".join(p for p in extractor.parts if p)


def extract_tech_stack(text: str) -> list[str]:
    """Extract technology keywords from text."""
    text_lower = text.lower()
    found = []
    for tech in TECH_KEYWORDS:
        # Word boundary matching
        pattern = r'\b' + re.escape(tech) + r'\b'
        if re.search(pattern, text_lower):
            found.append(tech)
    return sorted(set(found))


def extract_experience_level(text: str) -> str:
    """Determine experience level from posting text."""
    text_lower = text.lower()
    for level, patterns in reversed(list(EXPERIENCE_PATTERNS.items())):
        for pattern in patterns:
            if re.search(pattern, text_lower):
                return level
    return "mid"  # default assumption


def extract_bullet_sections(text: str) -> dict[str, list[str]]:
    """Extract bulleted/listed sections from job posting."""
    sections = {
        "requirements": [],
        "preferred": [],
        "responsibilities": [],
    }

    requirement_headers = [
        r"requirements?", r"qualifications?", r"must.?have", r"minimum",
        r"what you.?ll need", r"what we.?re looking for", r"required skills",
    ]
    preferred_headers = [
        r"preferred", r"nice.?to.?have", r"bonus", r"plus", r"ideal",
    ]
    responsibility_headers = [
        r"responsibilities", r"what you.?ll do", r"role", r"duties",
        r"day.?to.?day", r"about the role",
    ]

    lines = text.split("\n")
    current_section = None

    for line in lines:
        line_stripped = line.strip()
        line_lower = line_stripped.lower()

        # Check if this is a section header
        for pattern in requirement_headers:
            if re.search(pattern, line_lower) and len(line_stripped) < 80:
                current_section = "requirements"
                break
        for pattern in preferred_headers:
            if re.search(pattern, line_lower) and len(line_stripped) < 80:
                current_section = "preferred"
                break
        for pattern in responsibility_headers:
            if re.search(pattern, line_lower) and len(line_stripped) < 80:
                current_section = "responsibilities"
                break

        # Check if this is a bullet point
        if current_section and re.match(r'^[\s]*[•\-\*\+⁃▪▸►]|\d+[\.\)]\s', line_stripped):
            bullet = re.sub(r'^[\s]*[•\-\*\+⁃▪▸►]\s*|\d+[\.\)]\s*', '', line_stripped).strip()
            if bullet and len(bullet) > 10:
                sections[current_section].append(bullet)
        elif current_section and line_stripped and not any(
            re.search(p, line_lower) for patterns in
            [requirement_headers, preferred_headers, responsibility_headers]
            for p in patterns
        ):
            # Could be a continuation or a non-bulleted requirement
            if len(line_stripped) > 15 and len(line_stripped) < 300:
                sections[current_section].append(line_stripped)

    return sections


def parse_job_posting(url: str, text: str = None) -> JobPosting:
    """Parse a job posting from URL or provided text."""
    if text is None:
        text = fetch_page_text(url)

    sections = extract_bullet_sections(text)
    tech_stack = extract_tech_stack(text)
    exp_level = extract_experience_level(text)

    # Try to extract title and company from first lines
    lines = [l.strip() for l in text.split("\n") if l.strip()]
    title = lines[0] if lines else "Unknown Position"
    company = "Unknown Company"

    # Look for company name patterns
    for line in lines[:10]:
        if re.search(r'(at|@)\s+\w+', line, re.IGNORECASE):
            match = re.search(r'(?:at|@)\s+(.+?)(?:\s*[–\-|]|$)', line, re.IGNORECASE)
            if match:
                company = match.group(1).strip()
                break

    # Look for location
    location = "Unknown"
    location_patterns = [
        r'(remote)', r'(hybrid)', r'(on.?site)',
        r'([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?,\s*[A-Z]{2})',  # City, ST
    ]
    for line in lines[:15]:
        for pattern in location_patterns:
            match = re.search(pattern, line, re.IGNORECASE)
            if match:
                location = match.group(1).strip()
                break

    remote = None
    text_lower = text.lower()
    if "remote" in text_lower:
        remote = True
    elif "on-site" in text_lower or "onsite" in text_lower:
        remote = False

    # Salary extraction
    salary = None
    salary_match = re.search(
        r'\$[\d,]+(?:k)?\s*[-–]\s*\$?[\d,]+(?:k)?(?:\s*(?:per\s+)?(?:year|annually|yr))?',
        text, re.IGNORECASE
    )
    if salary_match:
        salary = salary_match.group(0)

    return JobPosting(
        title=title[:200],
        company=company[:200],
        location=location,
        url=url,
        description=text[:5000],
        requirements=sections["requirements"],
        preferred=sections["preferred"],
        responsibilities=sections["responsibilities"],
        tech_stack=tech_stack,
        experience_level=exp_level,
        salary_range=salary,
        remote=remote,
    )
