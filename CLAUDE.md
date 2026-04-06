# Resume Builder MCP

This is a resume-builder MCP server. When the user asks about resumes, job applications, or their professional profile, use the resume-builder tools.

## First-time setup
If the user hasn't set up their profile yet (get_profile returns empty data), suggest they run setup_profile with their website URL and/or paste their resume text.

## Typical workflows
- "Generate a resume for [job URL]" → use full_pipeline or scrape_and_generate
- "How well do I match this job?" → use match_score
- "Review my resume" → use evaluate_resume
- "Add my new job at X" → use add_experience
- "Show my applications" → use get_application_stats
