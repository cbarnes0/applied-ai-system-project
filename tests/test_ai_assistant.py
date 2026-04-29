import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch, mock_open

sys.path.insert(0, str(Path(__file__).parent.parent))

import anthropic
from ai_assistant import (
    _tokenize,
    retrieve_relevant_entries,
    sanitize_query,
    is_off_topic,
    validate_api_key,
    build_schedule_snapshot,
    ask_care_advisor,
    analyze_schedule,
    _parse_analyzer_response,
    _log_interaction,
    LOG_FILE,
)
from pawpal_system import Owner, Pet, Task, DailyPlan


# ── Retrieval Tests ────────────────────────────────────────────────────────────

class TestTokenize(unittest.TestCase):
    def test_lowercases_and_splits(self):
        result = _tokenize("Dog Walking Frequency")
        self.assertIn("dog", result)
        self.assertIn("walking", result)
        self.assertIn("frequency", result)

    def test_drops_short_tokens(self):
        result = _tokenize("a an is my")
        self.assertEqual(result, set())

    def test_handles_punctuation(self):
        result = _tokenize("cat's ear, nail!")
        self.assertIn("cat", result)
        self.assertIn("ear", result)
        self.assertIn("nail", result)


class TestRetrieveRelevantEntries(unittest.TestCase):
    def test_dog_species_filter_returns_dog_compatible_entries(self):
        entries = retrieve_relevant_entries(query="", species_filter=["dog"], top_k=10)
        for entry in entries:
            self.assertTrue(
                "dog" in entry["species"],
                f"Entry '{entry['id']}' species {entry['species']} does not include 'dog'"
            )

    def test_cat_species_filter_excludes_dog_only_entries(self):
        entries = retrieve_relevant_entries(query="", species_filter=["cat"], top_k=10)
        for entry in entries:
            self.assertNotIn(
                entry["id"],
                ["dog-walk-frequency", "dog-feeding-schedule", "dog-medication-admin", "dog-grooming", "dog-enrichment"],
                f"Dog-only entry '{entry['id']}' should not appear for cat filter"
            )

    def test_keyword_match_returns_grooming_entry_first(self):
        entries = retrieve_relevant_entries(
            query="brushing nails grooming coat",
            species_filter=["dog"],
            top_k=3,
        )
        ids = [e["id"] for e in entries]
        self.assertIn("dog-grooming", ids)
        self.assertEqual(ids[0], "dog-grooming", "Grooming entry should be ranked first for grooming query")

    def test_top_k_respected(self):
        entries = retrieve_relevant_entries(query="", species_filter=["dog", "cat", "other"], top_k=2)
        self.assertLessEqual(len(entries), 2)

    def test_empty_query_with_species_filter_returns_entries(self):
        entries = retrieve_relevant_entries(query="", species_filter=["cat"], top_k=5)
        self.assertGreater(len(entries), 0)
        for entry in entries:
            self.assertIn("cat", entry["species"])

    def test_task_type_filter_narrows_results(self):
        entries = retrieve_relevant_entries(
            query="",
            species_filter=["dog"],
            task_type_filter=["medication"],
            top_k=5,
        )
        for entry in entries:
            self.assertTrue(
                "medication" in entry["task_types"],
                f"Entry '{entry['id']}' task_types {entry['task_types']} does not include 'medication'"
            )

    def test_exact_species_match_scores_higher_than_universal(self):
        entries = retrieve_relevant_entries(
            query="feeding food meal",
            species_filter=["dog"],
            top_k=5,
        )
        ids = [e["id"] for e in entries]
        if "dog-feeding-schedule" in ids and "general-feeding-water" in ids:
            dog_rank = ids.index("dog-feeding-schedule")
            general_rank = ids.index("general-feeding-water")
            self.assertLess(dog_rank, general_rank, "Dog-specific entry should rank higher than universal for dog filter")

    def test_unknown_species_falls_back_to_universal_entries(self):
        entries = retrieve_relevant_entries(query="", species_filter=["hamster"], top_k=5)
        self.assertGreater(len(entries), 0)


# ── Guardrail Tests ────────────────────────────────────────────────────────────

class TestSanitizeQuery(unittest.TestCase):
    def test_strips_whitespace(self):
        self.assertEqual(sanitize_query("  hello  "), "hello")

    def test_truncates_long_query(self):
        long = "a" * 600
        result = sanitize_query(long)
        self.assertEqual(len(result), 503)
        self.assertTrue(result.endswith("..."))

    def test_short_query_unchanged(self):
        self.assertEqual(sanitize_query("walk my dog"), "walk my dog")


class TestIsOffTopic(unittest.TestCase):
    def test_returns_true_for_non_pet_query(self):
        self.assertTrue(is_off_topic("what is the capital of France"))

    def test_returns_false_for_pet_query(self):
        self.assertFalse(is_off_topic("how often should I walk my dog"))

    def test_returns_false_for_schedule_query(self):
        self.assertFalse(is_off_topic("morning schedule for feeding"))

    def test_returns_false_for_medication_query(self):
        self.assertFalse(is_off_topic("how do I give my cat a pill"))

    def test_returns_true_for_clearly_unrelated(self):
        self.assertTrue(is_off_topic("write me a poem about mountains"))


class TestValidateApiKey(unittest.TestCase):
    def test_returns_false_when_key_missing(self):
        with patch.dict(os.environ, {}, clear=True):
            os.environ.pop("ANTHROPIC_API_KEY", None)
            self.assertFalse(validate_api_key())

    def test_returns_false_when_key_empty(self):
        with patch.dict(os.environ, {"ANTHROPIC_API_KEY": ""}):
            self.assertFalse(validate_api_key())

    def test_returns_true_when_key_set(self):
        with patch.dict(os.environ, {"ANTHROPIC_API_KEY": "sk-ant-test123"}):
            self.assertTrue(validate_api_key())


# ── Snapshot Builder Tests ─────────────────────────────────────────────────────

class TestBuildScheduleSnapshot(unittest.TestCase):
    def _make_owner(self):
        owner = Owner(name="Alex", available_hours_per_day=2.0)
        pet = Pet(name="Buddy", species="dog")
        pet.add_task(Task(
            name="Morning Walk",
            task_type="walk",
            duration_minutes=30,
            priority="high",
            recurrence="daily",
            time_of_day="morning",
        ))
        owner.add_pet(pet)
        return owner

    def test_none_owner_returns_empty_snapshot(self):
        snap = build_schedule_snapshot(owner=None, plan=None)
        self.assertEqual(snap["scheduled_tasks"], [])
        self.assertEqual(snap["skipped_tasks"], [])
        self.assertEqual(snap["pets"], [])

    def test_no_plan_returns_empty_tasks(self):
        owner = self._make_owner()
        snap = build_schedule_snapshot(owner=owner, plan=None)
        self.assertEqual(snap["scheduled_tasks"], [])
        self.assertEqual(snap["skipped_tasks"], [])
        self.assertEqual(snap["conflicts"], [])

    def test_budget_minutes_computed_correctly(self):
        owner = self._make_owner()
        snap = build_schedule_snapshot(owner=owner, plan=None)
        self.assertEqual(snap["budget_minutes"], 120)

    def test_after_generate_snapshot_reflects_tasks(self):
        owner = self._make_owner()
        plan = DailyPlan(owner=owner)
        plan.generate()
        snap = build_schedule_snapshot(owner=owner, plan=plan)
        self.assertEqual(len(snap["scheduled_tasks"]), len(plan.scheduled_tasks))

    def test_snapshot_includes_conflicts(self):
        owner = Owner(name="Test", available_hours_per_day=3.0)
        pet = Pet(name="Cat", species="cat")
        pet.add_task(Task("Feed 1", "feeding", 10, "high", "daily", "morning"))
        pet.add_task(Task("Feed 2", "feeding", 10, "high", "daily", "morning"))
        owner.add_pet(pet)
        plan = DailyPlan(owner=owner)
        plan.generate()
        snap = build_schedule_snapshot(owner=owner, plan=plan)
        self.assertGreater(len(snap["conflicts"]), 0)

    def test_pets_list_includes_species(self):
        owner = self._make_owner()
        snap = build_schedule_snapshot(owner=owner, plan=None)
        self.assertEqual(snap["pets"], [{"name": "Buddy", "species": "dog"}])


# ── Parse Analyzer Response Tests ─────────────────────────────────────────────

class TestParseAnalyzerResponse(unittest.TestCase):
    VALID = json.dumps({
        "overall_assessment": "Good schedule.",
        "issues": [],
        "suggestions": [],
        "missing_task_types": [],
        "positive_observations": ["Feeding is consistent."],
    })

    def test_parses_valid_json(self):
        result = _parse_analyzer_response(self.VALID)
        self.assertIsNotNone(result)
        self.assertEqual(result["overall_assessment"], "Good schedule.")

    def test_strips_markdown_fences(self):
        wrapped = f"```json\n{self.VALID}\n```"
        result = _parse_analyzer_response(wrapped)
        self.assertIsNotNone(result)

    def test_returns_none_for_invalid_json(self):
        result = _parse_analyzer_response("not json at all")
        self.assertIsNone(result)

    def test_returns_none_for_missing_keys(self):
        partial = json.dumps({"overall_assessment": "ok", "issues": []})
        result = _parse_analyzer_response(partial)
        self.assertIsNone(result)


# ── API Call Tests (mocked) ────────────────────────────────────────────────────

def _make_mock_response(text: str, input_tokens: int = 100, output_tokens: int = 50):
    mock = MagicMock()
    mock.content = [MagicMock(text=text)]
    mock.usage = MagicMock(input_tokens=input_tokens, output_tokens=output_tokens)
    return mock


class TestAskCareAdvisor(unittest.TestCase):
    def _call(self, side_effect=None, return_value=None):
        with patch("ai_assistant.get_client") as mock_get:
            client = MagicMock()
            mock_get.return_value = client
            if side_effect:
                client.messages.create.side_effect = side_effect
            elif return_value:
                client.messages.create.return_value = return_value
            with patch("ai_assistant._log_interaction"):
                return ask_care_advisor("How often walk?", {}, [])

    def test_returns_success_on_valid_response(self):
        result = self._call(return_value=_make_mock_response("Walk your dog daily."))
        self.assertTrue(result["success"])
        self.assertIn("Walk", result["response"])
        self.assertEqual(result["usage"]["input_tokens"], 100)

    def test_returns_false_on_auth_error(self):
        error = anthropic.AuthenticationError.__new__(anthropic.AuthenticationError)
        result = self._call(side_effect=error)
        self.assertFalse(result["success"])
        self.assertIn("API key", result["response"])

    def test_returns_false_on_rate_limit(self):
        error = anthropic.RateLimitError.__new__(anthropic.RateLimitError)
        result = self._call(side_effect=error)
        self.assertFalse(result["success"])
        self.assertIn("Rate limit", result["response"])

    def test_returns_false_on_connection_error(self):
        error = anthropic.APIConnectionError.__new__(anthropic.APIConnectionError)
        result = self._call(side_effect=error)
        self.assertFalse(result["success"])
        self.assertIn("connect", result["response"])

    def test_returns_false_on_unexpected_error(self):
        result = self._call(side_effect=RuntimeError("boom"))
        self.assertFalse(result["success"])
        self.assertIn("unexpected", result["response"])


VALID_ANALYSIS_JSON = json.dumps({
    "overall_assessment": "Schedule looks good.",
    "issues": [],
    "suggestions": [{"pet": "Buddy", "action": "Add enrichment", "reason": "Mental stimulation needed"}],
    "missing_task_types": [],
    "positive_observations": ["Daily walk is scheduled."],
})


class TestAnalyzeSchedule(unittest.TestCase):
    def _make_owner(self):
        owner = Owner(name="Alex", available_hours_per_day=2.0)
        pet = Pet(name="Buddy", species="dog")
        pet.add_task(Task("Walk", "walk", 30, "high", "daily", "morning"))
        owner.add_pet(pet)
        return owner

    def test_returns_success_with_valid_json(self):
        owner = self._make_owner()
        plan = DailyPlan(owner=owner)
        plan.generate()
        snap = build_schedule_snapshot(owner=owner, plan=plan)

        with patch("ai_assistant.get_client") as mock_get:
            client = MagicMock()
            mock_get.return_value = client
            client.messages.create.return_value = _make_mock_response(VALID_ANALYSIS_JSON)
            with patch("ai_assistant._log_interaction"):
                result = analyze_schedule(snap, owner)

        self.assertTrue(result["success"])
        self.assertIsNotNone(result["analysis"])
        self.assertEqual(result["analysis"]["overall_assessment"], "Schedule looks good.")

    def test_retries_on_bad_json_first_call(self):
        owner = self._make_owner()
        plan = DailyPlan(owner=owner)
        plan.generate()
        snap = build_schedule_snapshot(owner=owner, plan=plan)

        with patch("ai_assistant.get_client") as mock_get:
            client = MagicMock()
            mock_get.return_value = client
            client.messages.create.side_effect = [
                _make_mock_response("not json at all"),
                _make_mock_response(VALID_ANALYSIS_JSON),
            ]
            with patch("ai_assistant._log_interaction"):
                result = analyze_schedule(snap, owner)

        self.assertTrue(result["success"])
        self.assertEqual(client.messages.create.call_count, 2)

    def test_returns_failure_after_two_bad_json_responses(self):
        owner = self._make_owner()
        snap = build_schedule_snapshot(owner=owner, plan=None)

        with patch("ai_assistant.get_client") as mock_get:
            client = MagicMock()
            mock_get.return_value = client
            client.messages.create.return_value = _make_mock_response("bad json")
            with patch("ai_assistant._log_interaction"):
                result = analyze_schedule(snap, owner)

        self.assertFalse(result["success"])
        self.assertIsNone(result["analysis"])
        self.assertIsNotNone(result["error"])


# ── Logging Tests ──────────────────────────────────────────────────────────────

class TestLogInteraction(unittest.TestCase):
    def test_creates_jsonl_file_and_appends_record(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            log_path = Path(tmpdir) / "test_log.jsonl"
            with patch("ai_assistant.LOG_FILE", log_path), \
                 patch("ai_assistant.LOG_DIR", Path(tmpdir)):
                _log_interaction(
                    query_type="qa",
                    query="how often walk?",
                    retrieved_entries=[{"id": "dog-walk-frequency", "title": "Dog Walking"}],
                    response_text="Walk daily.",
                    usage={"input_tokens": 100, "output_tokens": 50},
                )
            self.assertTrue(log_path.exists())
            with open(log_path, "r") as f:
                record = json.loads(f.readline())
            self.assertEqual(record["query_type"], "qa")
            self.assertIn("timestamp", record)
            self.assertIn("usage", record)
            self.assertTrue(record["success"])

    def test_log_record_has_all_required_keys(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            log_path = Path(tmpdir) / "test_log.jsonl"
            with patch("ai_assistant.LOG_FILE", log_path), \
                 patch("ai_assistant.LOG_DIR", Path(tmpdir)):
                _log_interaction("analyzer", "[schedule analysis]", [], "result", {}, error=None)
            with open(log_path, "r") as f:
                record = json.loads(f.readline())
            required = {"timestamp", "query_type", "query_preview", "retrieved_entry_ids",
                        "response_preview", "usage", "success", "error"}
            self.assertTrue(required.issubset(record.keys()))


if __name__ == "__main__":
    unittest.main()
