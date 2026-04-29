# PawPal+

**PawPal+** is a pet care planning app that helps busy pet owners stay on top of their animals' daily needs. Set your time budget, add your pets and tasks, and let PawPal+ build a smart daily schedule — automatically sorted, conflict-checked, and ready to go.

The app now includes an **AI Care Advisor** powered by Claude (Anthropic) that uses Retrieval-Augmented Generation (RAG) to answer pet care questions grounded in a curated knowledge base, and an **Agentic Schedule Analyzer** that examines your plan and delivers structured, actionable feedback.

---

## Screenshot

![Demo Screenshot](PawPal_Screenshot.png)

---

## System Design

![UML Class Diagram](uml_final.png)

### Architecture Diagram

```mermaid
flowchart TD
    User([User]) -->|enters question\nor clicks Analyze| UI[Streamlit UI\napp.py]

    subgraph core["Core Scheduler  •  pawpal_system.py"]
        UI -->|owner + pets + tasks| Sched[DailyPlan Scheduler]
        Sched -->|scheduled tasks\nskipped tasks\nconflicts| Plan[Daily Schedule]
        Plan --> UI
    end

    subgraph ai["AI Layer  •  ai_assistant.py"]
        UI -->|user query| Guard[Guardrails\nsanitize · off-topic filter]
        Guard -->|blocked| UI
        Guard -->|approved| Ret[RAG Retriever]
        KB[(pet_care_kb.json\n14 entries)] --> Ret
        Ret -->|top-3 relevant facts| PB[Prompt Builder]
        Plan -->|schedule snapshot| PB
        PB --> Claude[Claude API\nclaude-sonnet-4-6]
        Claude -->|Q&A answer| UI
        Claude -->|JSON analysis| Val[JSON Validator]
        Val -->|valid| UI
        Val -->|retry once| Claude
    end

    subgraph observe["Observability"]
        Claude --> Log[(logs/\nai_interactions.jsonl)]
    end

    subgraph testing["Reliability  •  pytest  •  58 tests"]
        T1[Scheduler tests\n17 tests] -->|unit| Sched
        T2[AI layer tests\n41 tests] -->|unit + mocked API| Ret
        T2 -->|unit + mocked API| Guard
        T2 -->|unit + mocked API| Claude
    end

    User -->|reviews output\nmarks tasks done| UI
```

---

## Features

### AI Care Advisor (RAG-powered Q&A)
- Ask questions about your pets in natural language from the sidebar chat
- Answers are grounded in a curated pet care knowledge base (14 entries covering dog/cat/other × all task types)
- The AI retrieves the most relevant facts before answering — not generic advice
- All interactions are logged to `logs/ai_interactions.jsonl` for transparency

### Agentic Schedule Analyzer
- Click "Analyze My Schedule" in the sidebar after generating a plan
- The AI automatically examines your schedule, retrieves species-specific care guidelines, and produces structured feedback:
  - Issues (high/medium/low severity)
  - Actionable suggestions per pet
  - Possibly missing task types
  - What's working well
- Retries automatically if the AI response is malformed

### Owner & Pet Management
- Create an owner profile with a configurable daily time budget
- Add multiple pets, each with their own independent task lists
- All data persists across interactions within a session

### Task Management
- Add tasks to any pet with a name, type, duration, priority, time of day, and recurrence
- Task types: `walk`, `feeding`, `medication`, `grooming`, `enrichment`
- Priority levels: `high`, `medium`, `low`
- Time slots: `morning`, `afternoon`, `evening`

### Sorting by Time
- The scheduler organizes tasks chronologically — morning before afternoon before evening
- Within a time slot, a `sort_order` field controls exact sequencing (e.g. give meds before breakfast)
- Priority and duration serve as automatic tie-breakers when sort order is equal

### Daily & Weekly Recurrence
- Tasks marked `daily` are automatically included in every plan
- Tasks marked `weekly` are scheduled only on their configured days (e.g. Monday, Thursday)
- When a daily or weekly task is marked complete, a fresh copy is automatically queued for the next occurrence
- Tasks marked `as_needed` are excluded from automatic scheduling but can be forced in with an override flag

### Budget Enforcement
- The scheduler respects the owner's daily time budget and will not overschedule
- Tasks that don't fit are collected in a skipped list — nothing is silently dropped
- The UI shows how many minutes are used versus the total budget

### Conflict Warnings
- If the same type of task is scheduled twice for the same pet in the same time slot, the plan flags it as a conflict
- Conflicts surface as visible warnings in the UI so the owner can resolve them

### Filtering & Status Tracking
- Filter the daily plan by pet to focus on one animal at a time
- Incomplete tasks are tracked separately so you can see what still needs to be done
- Tasks can be individually marked complete or reset

---

## Getting Started

### Setup

```bash
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

### API Key (required for AI features)

The AI Care Advisor requires an [Anthropic API key](https://console.anthropic.com/). Add it to a `.env` file in the project root:

```
ANTHROPIC_API_KEY=sk-ant-...
```

The app loads `.env` automatically on startup. The app runs without a key — the sidebar shows a warning and AI features are hidden until one is set.

### Run the app

```bash
streamlit run app.py
```

---

## Testing

```bash
# Original scheduling tests (17 tests)
python -m pytest tests/test_pawpal.py -v

# AI layer tests (retrieval, guardrails, mocked API calls)
python -m pytest tests/test_ai_assistant.py -v

# All tests
python -m pytest tests/ -v
```

The AI tests use `unittest.mock` to avoid real API calls — no key is needed to run the test suite.

---

## AI Feature Details

### How RAG Works

1. A local knowledge base (`pet_care_kb.json`) contains 14 entries covering pet care facts organized by species and task type.
2. When a question is submitted, a retrieval algorithm scores each KB entry using keyword overlap, title match, and species/task-type bonuses.
3. The top 3 relevant entries are passed to Claude alongside the question and the current schedule state.
4. Claude's response is grounded in the retrieved facts — not generic advice.

### Logging

Every AI interaction is appended to `logs/ai_interactions.jsonl`:
- Timestamp, query type (qa/analyzer)
- Which KB entries were retrieved
- Token usage
- Error details if something went wrong

### Guardrails

| Guardrail | Behavior |
|---|---|
| Missing API key | AI panel hidden; warning shown |
| Long input | Truncated to 500 characters |
| Off-topic question | Redirect message returned; no API call made |
| API errors | User-friendly message; details logged |
| Malformed AI output | Analyzer retries once automatically |
