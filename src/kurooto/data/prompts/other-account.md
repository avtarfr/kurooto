# Personal knowledge extraction: one more AI account

## Objective

I'm setting up Kurooto, a personal assistant that runs on my own computer, and I'm auditing what each of my AI accounts knows about me and how I use AI, so it can help me well from day one.

This is one account of a multi-account audit: {{SOURCE}}. Your report will be compared and merged with reports from my other accounts and other AI providers, into one profile stored on my own computer.

Reconstruct what THIS account knows about me and how I use AI, using only information genuinely accessible in this account.

## Scope and priorities

Inspect available saved memory, personalization instructions, conversation history, project instructions and files, artifacts, and other account-specific context. Do not assume you can search every past conversation or open every project or file; say what you could actually inspect.

Prioritize:
- Long-term goals and consequential decisions.
- Study, work, research, and personal projects.
- Recurring workflows, routines, and repeated problems.
- Stable preferences and constraints.
- Substantive conversations that show how I work.
- Existing AI usage and opportunities for automation.
- Important information that my other accounts are unlikely to know.

Ignore low-information exchanges such as greetings, jokes, one-off trivial questions, and casual banter unless they reveal a recurring pattern or a meaningful preference.

Leave out passwords, API keys, card or account numbers, ID numbers and any other credentials, even if you can see them.

## What to extract

### 1. Personal profile
Education, work, responsibilities, skills, expertise, interests, resources, constraints, and goals I disclosed in this account.

### 2. Goals and projects
For each significant project: its objective, status where known, decisions made, tools used, dependencies, unresolved problems, and next steps discussed.

### 3. AI usage inventory
The distinct ways I use this AI (and other AI tools I mentioned): research, learning, coding, writing, analysis, planning, admin, creative work, and anything else evidenced. For each:
- The task and the outcome I wanted.
- Whether it is occasional, recurring, or automated.
- How I currently do it: inputs, outputs, tools, and my review.
- What works and what fails.
- Whether it could be standardized, automated, or handed to an assistant, and what would be needed for that.

### 4. Routines and schedule
Recurring commitments, daily or weekly patterns, deadlines, and timing I mentioned.

### 5. Working and learning preferences
Explicit preferences about response length, depth, explanations, formatting, interaction, reliability, and efficiency. Distinguish stable preferences from instructions for one task.

### 6. Devices and tools
Devices, operating systems, apps, subscriptions, services, and technical skills I mentioned. Do not infer specifications, entitlements, or abilities without evidence.

### 7. Bottlenecks and unmet needs
Repetitive tasks, scattered knowledge, context lost between accounts, manual processes, recurring errors, and other problems an assistant could address.

### 8. Privacy and control
What I said about sensitive data, keeping things private or local, outside services, credentials, permissions, and when I want to approve things first. Do not infer sensitive personal attributes (health, religion, sexuality, politics and similar); include them only if I stated them and they matter for how an assistant should help me.

### 9. Changes over time and contradictions
Keep dated changes in goals, tools, preferences, project status, and circumstances. Distinguish current from historical information. Flag contradictions rather than silently reconciling them.

### 10. Automation opportunities
Plausible opportunities based on the evidence. For each: the problem, a proposed workflow, the likely benefit, uncertainties, and privacy considerations. Do not recommend something just because it is popular.

## Evidence standards

Label each finding:
- EXPLICIT: directly stated.
- REPEATED: supported by several independent instances.
- INFERRED: a reasonable but uncertain interpretation.
- UNKNOWN: not established.

Attach a source wherever possible: conversation title and date, project, file, or artifact. Use short paraphrases rather than long quotations. Keep separate: facts about me; my stated preferences and intentions; evidence of my actual behavior; your hypotheses and recommendations. Do not turn a one-time request into a permanent preference, treat a plan as an implemented system, fabricate citations, or claim to have searched history you couldn't access.

## Required report

Produce these sections:

A. Executive profile
B. Goals and life areas
C. Skills, interests, and learning preferences
D. Work style and decision-making
E. Routines and schedule
F. AI usage inventory
G. Existing workflow reconstructions
H. Projects and commitments
I. Devices, tools and services
J. Privacy and control requirements
K. Repeated bottlenecks and context fragmentation
L. Automation opportunities
M. Changes over time and contradictions
N. Missing information and access limitations
O. High-value questions for me

Use tables for workflows and use cases. Give important facts, projects, workflows, and opportunities stable IDs with the prefix {{PREFIX}}. Do not assume that IDs from different accounts refer to the same thing.

Append a machine-readable YAML section: every record has an id, category, description, confidence, temporal status where known, and source reference where available.

## Questions

Produce the report before asking anything. Then ask up to 10 targeted questions that would materially improve it. Do not ask me to repeat information this account already has.

## Final instruction

Be thorough about consequential information and selective about conversational noise. The goal is a reliable account-specific audit that can be merged with reports from my other accounts and providers.

Begin now.
