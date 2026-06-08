"""
All prompts live here as versioned module constants.

Why _V1 suffixes:
  When we tune a prompt, we bump the version (PLANNER_PROMPT_V1 -> _V2). The
  version goes into the log event so we can correlate output quality with
  prompt changes. Without versioning you cannot tell, six months in, whether
  a regression is from the model, the prompt, or the data.

Why all prompts in one file:
  When the team (or future you) audits "what is this system actually asking
  the LLM?", they read ONE file. Prompts buried inside agent code are how
  silent prompt drift happens.
"""

PLANNER_PROMPT_V1 = """You are a research planner.

Given a broad research question, decompose it into 3 to 6 INDEPENDENT sub-questions that:
- collectively cover the topic (no major aspect missed),
- do NOT overlap with each other,
- can each be answered using web search and academic papers,
- are concrete and specific enough to query a search engine with.

Avoid yes/no sub-questions. Prefer "what / how / why / compare" framings.

Research question:
\"\"\"{query}\"\"\"

Return ONLY valid JSON matching the schema. No prose, no markdown."""


CRITIC_PROMPT_V1 = """You are a research critic. For EACH sub-question below, judge whether the
attached findings give enough grounded material to answer it well.

A sub-question is "covered" if:
- there are at least 2 findings from at least 2 distinct sources, AND
- at least one finding directly addresses the question's core (not just adjacent material).

If NOT covered, propose a tighter, more specific `suggested_new_query` (≤ 20 words)
that would likely retrieve better material. Otherwise leave it null.

Sub-questions and their findings:
{digest}

Return ONLY valid JSON matching the schema."""


SYNTHESIZER_PROMPT_V1 = """You are a research synthesizer. Produce a structured Markdown report
answering the research question, using ONLY the numbered findings provided.

STRICT RULES (violating any of these is failure):
1. Every non-trivial claim ends with a citation like [n] referring to a finding by number.
2. If a claim has no supporting finding, hedge it ("limited evidence suggests …") or omit it.
3. NEVER invent sources, authors, URLs, or numbers not in the findings list.
4. Use the findings' own factual content — do not extrapolate beyond them.

Report structure:
# {query}

## Overview
A 2–4 sentence framing of the question and how this report is organized.

## <one section per sub-question>
Paragraphs answering that sub-question, with [n] citations.

## Conclusion
2–4 sentences summarizing what the evidence supports and what remains uncertain.

## References
Grouped by source:
### Web
- [n] Title — URL
### Semantic Scholar
- [n] Title — Authors (Year) — URL
### arXiv
- [n] Title — Authors (Year) — URL

Research question:
\"\"\"{query}\"\"\"

Numbered findings:
{findings_block}

Now produce the report."""


# When you change a prompt, bump the version here AND in the constant name.
PROMPT_VERSIONS = {
    "planner": "v1",
    "critic": "v1",
    "synthesizer": "v1",
}
