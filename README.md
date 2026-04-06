# resume-mcp

MCP server for maintaining a professional profile database and generating tailored, ATS-optimized resumes for specific job postings.

## Features

- **Profile database** — SQLite store for contact info, education, work experience, projects, and skills with proficiency ratings
- **Job scraping** — fetch and parse job postings from URLs; extract tech stack, experience level, requirements, and salary automatically
- **Tailored resume generation** — scores every experience and project against the job, selects the most relevant ones, and produces a clean LaTeX resume
- **Relevance scoring** — deterministic match score based on tech overlap, keyword coverage, and description similarity
- **ATS/keyword analysis** — identifies keyword gaps, naming mismatches (`React` vs `React.js`), weak action verbs, bullets lacking metrics, and unused profile items that could strengthen the resume
- **No extra API keys** — all analysis is pure Python (regex + keyword matching). The calling LLM (Claude, GPT, etc.) does the creative rewriting using its own subscription
- **Application tracker** — auto-logs every generated resume to a formatted `applications.xlsx` spreadsheet with color-coded scores and status tracking

## How tailoring works

Each experience and project is scored 0–1 against the job posting:

| Signal | Weight |
|---|---|
| Tech stack tag overlap | 40% |
| Keyword match against requirements | 35% |
| Description keyword match | 25% |

Items are ranked by score, the top 4 experiences and top 4 projects are selected, and skills matching the JD are reordered to appear first.

## Review pipeline

1. **`full_pipeline(url)`** — scrapes job → generates initial resume → runs deterministic analysis in one call
2. The analysis returns: keyword gaps, ATS issues (exact phrasing mismatches), weak verb flags, bullets missing metrics, and unused profile items from the DB
3. The calling LLM acts as a hiring manager and rewrites bullets, weaves in missing keywords, reorders sections
4. **`save_optimized_resume(...)`** — saves the LLM-rewritten LaTeX back to the DB and compiles to PDF

No API keys are consumed in step 2. The LLM you're already talking to does the creative work.

## Setup

```bash
cd ~/resume-mcp
pip install -r requirements.txt

# seed_profile.py is a template — open it and replace the placeholder data
# with your own info, then run it to populate the database:
python seed_profile.py
```

**Tip:** To keep your personal data out of git, copy the template to a private file:

```bash
cp seed_profile.py seed_yourname.py
echo "seed_yourname.py" >> .gitignore
python seed_yourname.py
```

**Optional:** Install `pdflatex` to compile resumes to PDF locally. Without it, `.tex` files are saved and can be compiled via [Overleaf](https://overleaf.com).

### Claude Desktop config

Add to `~/Library/Application Support/Claude/claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "resume-builder": {
      "command": "python3",
      "args": ["/Users/your-username/resume-mcp/server.py"]
    }
  }
}
```

## Data storage

| Path | Contents |
|---|---|
| `~/.resume-mcp/profile.db` | SQLite profile database |
| `~/.resume-mcp/generated/` | Generated `.tex` and `.pdf` files |
| `~/.resume-mcp/applications.xlsx` | Application tracker spreadsheet |

## MCP tools

### Profile

| Tool | Description |
|---|---|
| `get_profile` | Return full profile (contact, education, experience, projects, skills) |
| `set_contact_info` | Set name, email, phone, LinkedIn, GitHub, website, location |
| `add_experience` | Add a work experience entry with bullet points and tech tags |
| `update_experience` | Update fields on an existing experience by ID |
| `delete_experience` | Remove an experience by ID |
| `add_project` | Add a project with tech stack, bullets, URL, and status |
| `update_project` | Update fields on an existing project by ID |
| `delete_project` | Remove a project by ID |
| `add_education` | Add an education entry with GPA, coursework, honors |
| `add_skill` | Add or update a skill with category and proficiency (1–5) |
| `remove_skill` | Remove a skill |
| `bulk_add_skills` | Add multiple skills at once via `{"Category": ["Skill1", "Skill2"]}` |

### Job scraping

| Tool | Description |
|---|---|
| `scrape_job_posting` | Fetch a job posting URL and extract structured data |
| `analyze_job_from_text` | Parse a job from pasted text when URL scraping fails |

### Resume generation

| Tool | Description |
|---|---|
| `generate_resume` | Generate a tailored resume given job details |
| `scrape_and_generate` | One-shot: scrape URL and immediately generate resume |
| `match_score` | Check profile-to-job match without generating a resume |
| `get_resume_latex` | Retrieve full LaTeX source of a previously generated resume |
| `list_generated_resumes` | List recent resumes with job details and match scores |

### Review & optimization

| Tool | Description |
|---|---|
| `full_pipeline` | Scrape → generate → analyze in one call; returns everything the LLM needs to rewrite |
| `review_resume_against_job` | Run deterministic analysis on a resume by ID or raw LaTeX |
| `get_resume_with_context` | Get resume LaTeX + job info + full profile in one call for rewriting |
| `save_optimized_resume` | Save LLM-rewritten LaTeX back to DB and compile to PDF |

### Application tracker

| Tool | Description |
|---|---|
| `log_application` | Manually log an application to the spreadsheet |
| `update_application_status` | Update status (Generated → Applied → Interview → Offer/Rejected) |
| `get_application_stats` | Summary stats: total, by-status breakdown, average scores |

## Usage examples

These are natural language commands you'd send to Claude with the MCP server connected:

```
Generate a resume for this job posting: [paste URL]

Scrape this job and run the full pipeline so you can optimize my resume: [URL]

Add a new experience: I worked at Acme Corp as a backend engineer from Jan 2024 to present.
Bullets: [...]

What's my match score for a job that requires React, TypeScript, and AWS experience?

Update my application status for row 3 to "Interview"

Show me my application stats
```
