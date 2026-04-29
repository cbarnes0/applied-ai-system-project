import json
import os
import re
import logging
from datetime import datetime, timezone
from pathlib import Path

import anthropic

# ── Constants ──────────────────────────────────────────────────────────────────

KB_PATH = Path(__file__).parent / "pet_care_kb.json"
LOG_DIR = Path(__file__).parent / "logs"
LOG_FILE = LOG_DIR / "ai_interactions.jsonl"

MODEL = "claude-sonnet-4-6"
MAX_TOKENS_QA = 512
MAX_TOKENS_ANALYZER = 1024
MAX_QUERY_CHARS = 500
MAX_SCHEDULE_TASKS = 50

PET_KEYWORDS = {
    "dog", "cat", "pet", "animal", "feed", "food", "walk", "groom",
    "medicine", "medication", "pill", "vet", "veterinarian", "exercise",
    "play", "brush", "bath", "nail", "ear", "water", "hydrat", "health",
    "schedule", "task", "morning", "evening", "afternoon", "daily",
    "weekly", "puppy", "kitten", "senior", "rabbit", "bird", "enrichment",
    "grooming", "feeding", "treat", "fur", "coat", "paw", "teeth", "flea",
    "tick", "dose", "antibiotic", "tablet", "training", "toy", "leash"
}

# ── Prompts ────────────────────────────────────────────────────────────────────

SYSTEM_PROMPT_QA = """You are PawPal+ Care Advisor, an expert in pet care integrated into a daily pet scheduling app.

The user has provided a question about their pets. You have been given:
1. The user's current schedule state (owner name, pets, scheduled tasks, skipped tasks, conflicts)
2. Relevant pet care facts retrieved from a curated knowledge base

Your job is to answer the user's question in a friendly, specific, and actionable way. Ground your answer in the retrieved facts whenever relevant. If the retrieved facts do not directly answer the question, use your general knowledge but be transparent about it.

Rules:
- Keep your response under 250 words
- Focus on the user's specific pets and schedule, not generic advice
- If the user's schedule has conflicts or skipped tasks relevant to the question, mention them
- Never recommend specific medications or diagnose medical conditions; always direct serious health concerns to a vet
- If the question is off-topic (not about pets or pet care), politely decline and redirect"""

SYSTEM_PROMPT_ANALYZER = """You are PawPal+ Schedule Analyzer, an expert in pet care scheduling.

You will be given a complete daily schedule snapshot and relevant care guidelines from a knowledge base. Your task is to analyze the schedule and produce structured, actionable feedback.

You MUST respond in exactly this JSON format (no markdown fences, no extra text — raw JSON only):
{
  "overall_assessment": "<one sentence summary of the schedule quality>",
  "issues": [
    {"severity": "high|medium|low", "description": "<specific issue found in the schedule>"}
  ],
  "suggestions": [
    {"pet": "<pet name or 'All pets'>", "action": "<specific actionable suggestion>", "reason": "<brief why>"}
  ],
  "missing_task_types": [
    {"pet": "<pet name>", "task_type": "<type>", "note": "<why it might be needed>"}
  ],
  "positive_observations": ["<thing the schedule does well>"]
}

Rules:
- Base your analysis on the actual schedule data provided — do not invent facts
- Reference specific task names, pet names, and time slots from the data
- If the schedule has no issues, say so clearly in overall_assessment and provide an empty issues list
- missing_task_types should only flag task types genuinely important for that species
- Limit to 3 issues, 4 suggestions, 3 missing_task_types, and 2 positive_observations maximum
- Severity "high" = health or safety risk; "medium" = notable gap; "low" = nice-to-have"""

# ── Knowledge Base ─────────────────────────────────────────────────────────────

_kb_cache: list[dict] | None = None


def load_knowledge_base() -> list[dict]:
    global _kb_cache
    if _kb_cache is None:
        with open(KB_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        _kb_cache = data["entries"]
    return _kb_cache


def _tokenize(text: str) -> set[str]:
    tokens = re.split(r"[^a-z]+", text.lower())
    return {t for t in tokens if len(t) >= 3}


def _score_entry(
    entry: dict,
    query_tokens: set[str],
    species_filter: list[str] | None,
    task_type_filter: list[str] | None,
) -> float:
    score = 0.0
    entry_keywords = set(entry.get("keywords", []))
    title_tokens = _tokenize(entry.get("title", ""))
    facts_text = " ".join(entry.get("facts", []))
    fact_tokens = _tokenize(facts_text)

    if query_tokens:
        kw_matches = len(query_tokens & entry_keywords)
        kw_norm = kw_matches / max(len(entry_keywords), 1)
        score += kw_norm * 3.0

        title_matches = len(query_tokens & title_tokens)
        title_norm = title_matches / max(len(title_tokens), 1)
        score += title_norm * 2.0

        fact_matches = len(query_tokens & fact_tokens)
        fact_norm = fact_matches / max(len(fact_tokens), 1)
        score += fact_norm * 1.0

    if species_filter:
        entry_species = set(entry.get("species", []))
        filter_species = set(species_filter)
        if entry_species and entry_species.issubset(filter_species):
            score += 2.0

    if task_type_filter:
        entry_types = set(entry.get("task_types", []))
        filter_types = set(task_type_filter)
        if entry_types & filter_types:
            score += 1.5

    return score


def retrieve_relevant_entries(
    query: str,
    species_filter: list[str] | None = None,
    task_type_filter: list[str] | None = None,
    top_k: int = 3,
) -> list[dict]:
    entries = load_knowledge_base()
    query_tokens = _tokenize(query) if query else set()

    candidates = []
    for entry in entries:
        entry_species = set(entry.get("species", []))
        entry_types = set(entry.get("task_types", []))

        if species_filter and not (entry_species & set(species_filter)):
            continue
        if task_type_filter and not (entry_types & set(task_type_filter)):
            continue

        candidates.append(entry)

    if not candidates:
        candidates = entries[:]

    scored = [(e, _score_entry(e, query_tokens, species_filter, task_type_filter)) for e in candidates]
    scored.sort(key=lambda x: (-x[1], len(x[0].get("species", []))))

    top = scored[:top_k]

    if query_tokens and top and top[0][1] == 0:
        return [e for e, _ in scored[:top_k]]

    return [e for e, _ in top]


# ── Schedule Snapshot ──────────────────────────────────────────────────────────

def build_schedule_snapshot(owner, plan=None) -> dict:
    if owner is None:
        return {
            "owner_name": "Unknown",
            "budget_minutes": 0,
            "total_minutes_used": 0,
            "pets": [],
            "scheduled_tasks": [],
            "skipped_tasks": [],
            "conflicts": [],
        }

    pets_info = [{"name": p.name, "species": p.species} for p in owner.get_pets()]
    budget_minutes = int(owner.available_hours_per_day * 60)

    scheduled_tasks = []
    skipped_tasks = []
    conflicts = []
    total_minutes_used = 0

    if plan is not None:
        raw_scheduled = plan.scheduled_tasks[:]
        raw_skipped = plan.skipped_tasks[:]

        if len(raw_scheduled) + len(raw_skipped) > MAX_SCHEDULE_TASKS:
            raw_scheduled = raw_scheduled[:MAX_SCHEDULE_TASKS]

        for t in raw_scheduled:
            scheduled_tasks.append({
                "pet": t.pet_name,
                "name": t.name,
                "task_type": t.task_type,
                "duration_minutes": t.duration_minutes,
                "priority": t.priority,
                "time_of_day": t.time_of_day,
                "recurrence": t.recurrence,
                "completed": t.completed,
            })
        for t in raw_skipped:
            skipped_tasks.append({
                "pet": t.pet_name,
                "name": t.name,
                "task_type": t.task_type,
                "duration_minutes": t.duration_minutes,
                "priority": t.priority,
            })
        conflicts = list(plan.conflicts)
        total_minutes_used = plan.total_duration_minutes

    return {
        "owner_name": owner.name,
        "budget_minutes": budget_minutes,
        "total_minutes_used": total_minutes_used,
        "pets": pets_info,
        "scheduled_tasks": scheduled_tasks,
        "skipped_tasks": skipped_tasks,
        "conflicts": conflicts,
    }


def _format_schedule_snapshot(snapshot: dict) -> str:
    lines = [
        f"Owner: {snapshot.get('owner_name', 'Unknown')}, daily budget: {snapshot.get('budget_minutes', 0)} min",
        f"Time used: {snapshot.get('total_minutes_used', 0)} min",
    ]

    pets = snapshot.get("pets", [])
    if pets:
        lines.append("Pets: " + ", ".join(f"{p['name']} ({p['species']})" for p in pets))
    else:
        lines.append("Pets: none added yet")

    scheduled = snapshot.get("scheduled_tasks", [])
    lines.append(f"\nSCHEDULED TASKS ({len(scheduled)}):")
    if scheduled:
        for slot in ["morning", "afternoon", "evening"]:
            slot_tasks = [t for t in scheduled if t.get("time_of_day") == slot]
            if slot_tasks:
                lines.append(f"  [{slot}]")
                for t in slot_tasks:
                    done = " [DONE]" if t.get("completed") else ""
                    lines.append(
                        f"    - {t['pet']}: {t['name']} ({t['task_type']}, {t['duration_minutes']}min, {t['priority']} priority){done}"
                    )
    else:
        lines.append("  (no tasks scheduled — schedule not yet generated)")

    skipped = snapshot.get("skipped_tasks", [])
    if skipped:
        lines.append(f"\nSKIPPED TASKS ({len(skipped)}, budget exceeded):")
        for t in skipped:
            lines.append(f"  - {t['pet']}: {t['name']} ({t['duration_minutes']}min, {t['priority']} priority)")

    conflicts = snapshot.get("conflicts", [])
    if conflicts:
        lines.append(f"\nCONFLICTS ({len(conflicts)}):")
        for c in conflicts:
            lines.append(f"  - {c}")

    return "\n".join(lines)


def _format_kb_context(entries: list[dict]) -> str:
    if not entries:
        return "(No specific guidelines retrieved)"
    parts = []
    for entry in entries:
        facts = "\n".join(f"  - {f}" for f in entry.get("facts", []))
        parts.append(f"[Source: {entry['title']} — {entry['category']}]\n{facts}")
    return "\n\n".join(parts)


def _format_per_pet_kb_context(entries_per_pet: dict) -> str:
    parts = []
    for pet_name, entries in entries_per_pet.items():
        header = f"=== {pet_name} ==="
        body = _format_kb_context(entries)
        parts.append(f"{header}\n{body}")
    return "\n\n".join(parts)


# ── Prompt Builders ────────────────────────────────────────────────────────────

def build_qa_messages(
    user_question: str,
    schedule_snapshot: dict,
    retrieved_entries: list[dict],
) -> list[dict]:
    context_block = _format_kb_context(retrieved_entries)
    schedule_block = _format_schedule_snapshot(schedule_snapshot)

    user_content = f"""## My Question
{user_question}

## My Current Schedule
{schedule_block}

## Relevant Care Facts (from knowledge base)
{context_block}"""

    return [{"role": "user", "content": user_content}]


def build_analyzer_messages(
    schedule_snapshot: dict,
    retrieved_entries_per_pet: dict,
) -> list[dict]:
    schedule_block = _format_schedule_snapshot(schedule_snapshot)
    kb_block = _format_per_pet_kb_context(retrieved_entries_per_pet)

    user_content = f"""## Schedule to Analyze
{schedule_block}

## Care Guidelines by Pet
{kb_block}

Analyze this schedule and respond with valid JSON only."""

    return [{"role": "user", "content": user_content}]


# ── Guardrails ─────────────────────────────────────────────────────────────────

def sanitize_query(query: str) -> str:
    query = query.strip()
    if len(query) > MAX_QUERY_CHARS:
        query = query[:MAX_QUERY_CHARS] + "..."
    return query


def is_off_topic(query: str) -> bool:
    tokens = _tokenize(query)
    return len(tokens & PET_KEYWORDS) == 0


def validate_api_key() -> bool:
    return bool(os.environ.get("ANTHROPIC_API_KEY", "").strip())


# ── Logging ────────────────────────────────────────────────────────────────────

def _ensure_log_dir() -> None:
    LOG_DIR.mkdir(parents=True, exist_ok=True)


def _log_interaction(
    query_type: str,
    query: str,
    retrieved_entries: list[dict],
    response_text: str,
    usage: dict,
    error: str | None = None,
) -> None:
    try:
        _ensure_log_dir()
        record = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "query_type": query_type,
            "query_preview": query[:200],
            "retrieved_entry_ids": [e.get("id", "") for e in retrieved_entries],
            "retrieved_entry_titles": [e.get("title", "") for e in retrieved_entries],
            "response_preview": response_text[:300] if response_text else "",
            "usage": usage,
            "success": error is None,
            "error": error,
        }
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(json.dumps(record) + "\n")
    except Exception as log_err:
        logging.warning(f"PawPal+ logging failed: {log_err}")


# ── Claude API ─────────────────────────────────────────────────────────────────

def get_client() -> anthropic.Anthropic:
    key = os.environ.get("ANTHROPIC_API_KEY", "").strip()
    if not key:
        raise EnvironmentError("ANTHROPIC_API_KEY is not set.")
    return anthropic.Anthropic(api_key=key)


def ask_care_advisor(
    user_question: str,
    schedule_snapshot: dict,
    retrieved_entries: list[dict],
) -> dict:
    messages = build_qa_messages(user_question, schedule_snapshot, retrieved_entries)
    try:
        client = get_client()
        response = client.messages.create(
            model=MODEL,
            max_tokens=MAX_TOKENS_QA,
            system=SYSTEM_PROMPT_QA,
            messages=messages,
        )
        text = response.content[0].text
        usage = {
            "input_tokens": response.usage.input_tokens,
            "output_tokens": response.usage.output_tokens,
        }
        _log_interaction("qa", user_question, retrieved_entries, text, usage)
        return {
            "success": True,
            "response": text,
            "usage": usage,
            "retrieved_count": len(retrieved_entries),
        }
    except anthropic.AuthenticationError:
        msg = "API key is invalid. Please check your ANTHROPIC_API_KEY environment variable."
        _log_interaction("qa", user_question, retrieved_entries, "", {}, error=msg)
        return {"success": False, "response": msg, "usage": {}, "retrieved_count": 0}
    except anthropic.RateLimitError:
        msg = "Rate limit reached. Please wait a moment and try again."
        _log_interaction("qa", user_question, retrieved_entries, "", {}, error=msg)
        return {"success": False, "response": msg, "usage": {}, "retrieved_count": 0}
    except anthropic.APIConnectionError:
        msg = "Could not connect to the AI service. Check your internet connection."
        _log_interaction("qa", user_question, retrieved_entries, "", {}, error=msg)
        return {"success": False, "response": msg, "usage": {}, "retrieved_count": 0}
    except Exception as e:
        msg = "An unexpected error occurred. Please try again."
        _log_interaction("qa", user_question, retrieved_entries, "", {}, error=str(e))
        return {"success": False, "response": msg, "usage": {}, "retrieved_count": 0}


def _parse_analyzer_response(raw: str) -> dict | None:
    text = raw.strip()
    fence_match = re.search(r"```(?:json)?\s*([\s\S]+?)\s*```", text)
    if fence_match:
        text = fence_match.group(1).strip()
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        return None
    required_keys = {"overall_assessment", "issues", "suggestions", "missing_task_types", "positive_observations"}
    if not required_keys.issubset(parsed.keys()):
        return None
    return parsed


def analyze_schedule(snapshot: dict, owner) -> dict:
    entries_per_pet: dict = {}
    if owner is not None:
        for pet in owner.get_pets():
            task_types = [t.task_type for t in pet.get_tasks()]
            entries_per_pet[pet.name] = retrieve_relevant_entries(
                query="",
                species_filter=[pet.species],
                task_type_filter=task_types if task_types else None,
                top_k=4,
            )

    all_retrieved = [e for entries in entries_per_pet.values() for e in entries]
    messages = build_analyzer_messages(snapshot, entries_per_pet)

    def _call_claude(extra_system: str = "") -> tuple[str, dict]:
        system = SYSTEM_PROMPT_ANALYZER + extra_system
        client = get_client()
        response = client.messages.create(
            model=MODEL,
            max_tokens=MAX_TOKENS_ANALYZER,
            system=system,
            messages=messages,
        )
        text = response.content[0].text
        usage = {
            "input_tokens": response.usage.input_tokens,
            "output_tokens": response.usage.output_tokens,
        }
        return text, usage

    try:
        raw, usage = _call_claude()
        parsed = _parse_analyzer_response(raw)

        if parsed is None:
            raw, usage = _call_claude(
                extra_system="\n\nIMPORTANT: Your previous response was not valid JSON. Respond with raw JSON only — no markdown, no explanation."
            )
            parsed = _parse_analyzer_response(raw)

        if parsed is None:
            error_msg = "AI returned an unparseable response after retry."
            _log_interaction("analyzer", "[schedule analysis]", all_retrieved, raw, usage, error=error_msg)
            return {"success": False, "analysis": None, "response_raw": raw, "usage": usage, "error": error_msg}

        _log_interaction("analyzer", "[schedule analysis]", all_retrieved, raw, usage)
        return {"success": True, "analysis": parsed, "response_raw": raw, "usage": usage, "error": None}

    except anthropic.AuthenticationError:
        msg = "API key is invalid. Please check your ANTHROPIC_API_KEY environment variable."
        _log_interaction("analyzer", "[schedule analysis]", all_retrieved, "", {}, error=msg)
        return {"success": False, "analysis": None, "response_raw": "", "usage": {}, "error": msg}
    except anthropic.RateLimitError:
        msg = "Rate limit reached. Please wait a moment and try again."
        _log_interaction("analyzer", "[schedule analysis]", all_retrieved, "", {}, error=msg)
        return {"success": False, "analysis": None, "response_raw": "", "usage": {}, "error": msg}
    except anthropic.APIConnectionError:
        msg = "Could not connect to the AI service. Check your internet connection."
        _log_interaction("analyzer", "[schedule analysis]", all_retrieved, "", {}, error=msg)
        return {"success": False, "analysis": None, "response_raw": "", "usage": {}, "error": msg}
    except Exception as e:
        msg = "An unexpected error occurred. Please try again."
        _log_interaction("analyzer", "[schedule analysis]", all_retrieved, "", {}, error=str(e))
        return {"success": False, "analysis": None, "response_raw": "", "usage": {}, "error": msg}
