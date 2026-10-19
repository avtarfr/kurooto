# Personal knowledge extraction: my main AI account

## Mission

I'm setting up Kurooto, a personal assistant that runs on my own computer. It reminds me of things, keeps track of my deadlines and calendar, asks how my days go, keeps my notes, helps me study and research, and does tasks for me with AI. To help me well from day one, it needs an accurate picture of who I am, how I work, what I care about, and how I already use AI.

This is my main AI account (the one I use most): {{SOURCE}}. I'm running a version of this audit in every AI account I have, and the reports will be merged into one profile, stored on my own computer, and given to my assistant.

Your task is to extract everything materially useful that you know about me from the information genuinely accessible to you.

## 1. Inspect your available information

Use whatever personal context you can actually access, including, where available:

- Saved memories and personalization information.
- Past conversations and conversation summaries.
- Projects, uploaded files, documents, and other accessible artifacts.
- My stated preferences, instructions, goals, plans, and recurring workflows.
- Evidence of how I use AI, including tasks I repeatedly delegate or struggle with.
- Tools, apps and workflows I have explicitly mentioned.

Do not claim to have inspected conversation histories, files, or account data that you cannot access. Clearly distinguish accessible information from unavailable information.

Prioritize substantive conversations, ongoing projects, recurring patterns, consequential decisions, and long-term goals. Ignore greetings, banter, isolated jokes, trivial questions, disposable image requests, and other low-information exchanges unless they reveal a meaningful recurring preference or pattern. Do not let many trivial conversations outweigh a few important ones.

Leave out passwords, API keys, card or account numbers, ID numbers and any other credentials, even if you can see them.

## 2. Build my personal knowledge profile

Extract and organize these categories:

1. **Identity and context:** education, work, responsibilities, where and how I live and work, skills, and other relevant context I have disclosed.
2. **Goals and ambitions:** long-term objectives, active projects, the life I want, future plans.
3. **Interests and expertise:** subjects I study, research, practice or explore; distinguish real expertise from beginner-level familiarity.
4. **Working style:** how I learn, reason, decide, manage projects, and like to receive information.
5. **Preferences and constraints:** communication preferences, time and budget limits, privacy expectations, devices and software, tool preferences.
6. **Routines and schedule:** recurring commitments, daily or weekly patterns, deadlines, and timing I have mentioned.
7. **Recurring problems:** bottlenecks, repetitive work, organizational difficulties, things I forget, tasks that take disproportionate time.
8. **Commitments and ongoing projects:** important active efforts, their goals, status where known, dependencies, and next steps I mentioned.
9. **Existing AI usage:** every materially distinct use of AI you can establish: the task, purpose, frequency if known, tools or models used, workflow, limitations, and what I wish were better.
10. **Work done without AI:** important activities I do by hand or with ordinary software that an assistant could help with.
11. **Resources and infrastructure:** devices, operating systems, apps, subscriptions, accounts, services, and technical skills explicitly established.
12. **Privacy and boundaries:** information or tasks I want kept private, local, or handled with special care. Do not infer sensitive personal attributes (health, religion, sexuality, politics and similar); include them only if I stated them and they matter for how an assistant should help me.
13. **Unmet opportunities:** plausible ways an assistant could help, clearly labeled as hypotheses rather than facts.

Do not invent information to fill empty categories. Mark them as unknown or insufficiently evidenced.

## 3. Reconstruct my existing AI workflows

For each significant workflow, document:

- Its name and intended outcome.
- What starts it.
- Inputs and where they come from.
- The current steps.
- AI models and other tools involved, if known.
- Human decisions, review or intervention required.
- Outputs and where they go.
- Frequency and time cost, if known.
- Current failures, friction, limitations, and duplication.
- Whether it could be fully automated, partly automated, or not at all.
- Your confidence in the reconstruction, and what's missing.

Do not treat asking an AI a question as an established workflow. Distinguish one-off help, repeatable procedures, and genuinely automated systems.

## 4. Identify patterns across conversations

Identify:

- Goals and interests that recur over time.
- Projects that seem to have stalled, changed direction, or been dropped, without assuming why.
- Repeated questions that may point to an unmet need.
- Tasks I repeatedly explain to different AIs or tools.
- Preferences that stay consistent and preferences that have changed.
- Contradictions between stated intentions and observed behavior, where the evidence is sufficient.
- Important knowledge scattered across conversations, documents, or services.

Separate direct evidence, reasonable inference, and speculation. Never present a psychological interpretation as fact.

## 5. Evidence and provenance

For every important finding, include its source where possible: conversation date, project, document, or a short paraphrase of what I said.

Use these confidence labels:

- **Explicit:** directly stated by me.
- **Repeated:** supported by several independent instances.
- **Inferred:** reasonably derived from the evidence.
- **Unknown:** not established by the accessible information.

Do not reproduce large amounts of private conversation verbatim; summarize only what is useful. Where information conflicts, keep both versions with dates and explain the uncertainty. Do not silently treat older information as current.

## 6. Output format

Produce a comprehensive, structured Markdown report with these sections:

A. Executive profile
B. Goals and life areas
C. Skills, knowledge, and learning preferences
D. Working style and decision preferences
E. Routines, schedule and recurring commitments
F. Existing AI usage inventory
G. Reconstructed workflows
H. Tasks done without AI, and automation opportunities
I. Projects and commitments
J. Tools, subscriptions, and devices
K. Privacy and boundaries
L. Repeated bottlenecks and unmet needs
M. Contradictions, outdated information, and uncertainties
N. Questions that would materially improve the profile
O. What you could and couldn't access

Use tables where useful. Keep important detail; do not reduce the report to a generic personality summary.

At the end, add a machine-readable YAML appendix with stable IDs (prefix {{PREFIX}}) for major facts, projects, workflows, and opportunities. Each record: id, category, description, confidence, temporal status where known, and source reference where available. Quote and escape strings correctly. Do not invent source references.

## 7. Questions

First produce the best evidence-based report you can from your existing context; do not wait for answers. Then ask at most 10 high-value, specific questions, prioritizing uncertainties that would change how an assistant should help me. Do not ask me to repeat information you can already access. Say which questions are about missing evidence and which are decisions only I can make.

## Final instruction

This is a personal knowledge audit, not a flattering biography and not product recommendations. Optimize for accuracy, completeness, usefulness, and traceability. Include inconvenient findings and unresolved gaps. The report will be merged with reports from my other AI accounts, so use these categories, explicit confidence labels, and sources consistently.

Begin the audit now.
