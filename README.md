# PawPal+ (Module 2 Project)

You are building **PawPal+**, a Streamlit app that helps a pet owner plan care tasks for their pet.

## Scenario

A busy pet owner needs help staying consistent with pet care. They want an assistant that can:

- Track pet care tasks (walks, feeding, meds, enrichment, grooming, etc.)
- Consider constraints (time available, priority, owner preferences)
- Produce a daily plan and explain why it chose that plan

Your job is to design the system first (UML), then implement the logic in Python, then connect it to the Streamlit UI.

## What you will build

Your final app should:

- Let a user enter basic owner + pet info
- Let a user add/edit tasks (duration + priority at minimum)
- Generate a daily schedule/plan based on constraints and priorities
- Display the plan clearly (and ideally explain the reasoning)
- Include tests for the most important scheduling behaviors

## Getting started

### Setup

```bash
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

### Suggested workflow

1. Read the scenario carefully and identify requirements and edge cases.
2. Draft a UML diagram (classes, attributes, methods, relationships).
3. Convert UML into Python class stubs (no logic yet).
4. Implement scheduling logic in small increments.
5. Add tests to verify key behaviors.
6. Connect your logic to the Streamlit UI in `app.py`.
7. Refine UML so it matches what you actually built.

### Smarter Scheduling

The scheduler goes beyond a basic to-do list with a few key upgrades:

- **Sort order** — tasks have a `sort_order` field so you can control exactly what happens first within a time slot (e.g. give meds before breakfast, not just "both are high priority morning tasks")
- **Filtering** — you can pull tasks for a specific pet or see only what's still incomplete, useful for checking off the day as you go
- **Recurring task auto-scheduling** — when you mark a daily or weekly task complete, a fresh copy is automatically queued so it shows up again next time without you having to re-add it
- **Skipped tasks** — if your time budget runs out, the plan tells you what got dropped instead of silently leaving it out
- **Conflict detection** — if the same type of task is scheduled twice for the same pet in the same time slot, the plan flags it as a conflict
- **Override** — any task can be forced into today's plan with `override_today=True`, even if it's weekly or as-needed
