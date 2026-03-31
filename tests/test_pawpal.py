import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from pawpal_system import Task, Pet, Owner, DailyPlan


# --- Helpers ---

def make_owner(hours=2.0):
    return Owner(name="Alex", available_hours_per_day=hours)

def make_pet(name="Buddy"):
    return Pet(name=name, species="Dog")

def make_task(name="Morning Walk", duration=30, priority="high", recurrence="daily",
              task_type="walk", time_of_day="morning", sort_order=0,
              due_days=None, override_today=False):
    return Task(
        name=name,
        task_type=task_type,
        duration_minutes=duration,
        priority=priority,
        recurrence=recurrence,
        time_of_day=time_of_day,
        sort_order=sort_order,
        due_days=due_days,
        override_today=override_today,
    )


# --- Original tests ---

def test_task_completion_and_clear():
    task = make_task()

    assert task.completed is False, "Task should start incomplete"

    task.mark_complete()
    assert task.completed is True, "Task should be complete after mark_complete()"

    task.clear_completion()
    assert task.completed is False, "Task should be incomplete after clear_completion()"


def test_add_task_to_pet():
    pet = make_pet()
    task = make_task()

    assert len(pet.get_tasks()) == 0, "Pet should start with no tasks"

    pet.add_task(task)

    assert len(pet.get_tasks()) == 1, "Pet should have one task after add_task()"
    assert pet.get_tasks()[0] is task, "The added task should be retrievable"
    assert task.pet_name == "Buddy", "Task should have pet_name set after being added"


# --- Core behavior: budget enforcement ---

def test_tasks_over_budget_go_to_skipped():
    owner = make_owner(hours=0.5)  # 30 min budget
    pet = make_pet()
    pet.add_task(make_task("Walk",      duration=20))
    pet.add_task(make_task("Breakfast", duration=20, task_type="feeding"))
    owner.add_pet(pet)

    plan = DailyPlan(owner=owner)
    plan.generate()

    assert len(plan.scheduled_tasks) == 1, "Only one task should fit in 30 min"
    assert len(plan.skipped_tasks) == 1,   "One task should be skipped"


def test_task_exactly_filling_budget_is_scheduled():
    owner = make_owner(hours=0.5)  # exactly 30 min
    pet = make_pet()
    pet.add_task(make_task("Walk", duration=30))
    owner.add_pet(pet)

    plan = DailyPlan(owner=owner)
    plan.generate()

    assert len(plan.scheduled_tasks) == 1, "Task that exactly fills budget should be scheduled"
    assert len(plan.skipped_tasks) == 0


# --- Core behavior: sort order within a slot ---

def test_sort_order_controls_sequence_within_slot():
    owner = make_owner()
    pet = make_pet()
    # Added in reverse sort_order on purpose
    pet.add_task(make_task("Third",  sort_order=2))
    pet.add_task(make_task("First",  sort_order=0, task_type="feeding"))
    pet.add_task(make_task("Second", sort_order=1, task_type="medication"))
    owner.add_pet(pet)

    plan = DailyPlan(owner=owner)
    plan.generate()

    names = [t.name for t in plan.scheduled_tasks]
    assert names.index("First") < names.index("Second") < names.index("Third")


# --- Core behavior: mark_complete queues next occurrence ---

def test_mark_complete_does_not_duplicate_task():
    pet = make_pet()
    task = make_task(recurrence="daily")
    pet.add_task(task)

    assert len(pet.get_tasks()) == 1
    task.mark_complete()
    assert len(pet.get_tasks()) == 1, "Completing a task should not add a duplicate to the pet's task list"


# --- Core behavior: conflict detection ---

def test_duplicate_task_type_same_pet_same_slot_is_flagged():
    owner = make_owner()
    pet = make_pet()
    pet.add_task(make_task("Breakfast 1", task_type="feeding", sort_order=0))
    pet.add_task(make_task("Breakfast 2", task_type="feeding", sort_order=1))
    owner.add_pet(pet)

    plan = DailyPlan(owner=owner)
    plan.generate()

    assert len(plan.conflicts) == 1, "One conflict should be detected"
    assert "feeding" in plan.conflicts[0]


def test_same_task_type_different_slots_is_not_a_conflict():
    owner = make_owner()
    pet = make_pet()
    pet.add_task(make_task("Morning Feed", task_type="feeding", time_of_day="morning"))
    pet.add_task(make_task("Evening Feed", task_type="feeding", time_of_day="evening"))
    owner.add_pet(pet)

    plan = DailyPlan(owner=owner)
    plan.generate()

    assert len(plan.conflicts) == 0, "Same task type in different slots should not conflict"


# --- Core behavior: is_due_today recurrence logic ---

def test_as_needed_task_not_scheduled_without_override():
    owner = make_owner()
    pet = make_pet()
    pet.add_task(make_task(recurrence="as_needed"))
    owner.add_pet(pet)

    plan = DailyPlan(owner=owner)
    plan.generate()

    assert len(plan.scheduled_tasks) == 0, "as_needed task should not appear without override"


def test_as_needed_task_scheduled_with_override():
    owner = make_owner()
    pet = make_pet()
    pet.add_task(make_task(recurrence="as_needed", override_today=True))
    owner.add_pet(pet)

    plan = DailyPlan(owner=owner)
    plan.generate()

    assert len(plan.scheduled_tasks) == 1, "as_needed task with override_today should be scheduled"


def test_weekly_task_with_empty_due_days_is_not_scheduled():
    owner = make_owner()
    pet = make_pet()
    pet.add_task(make_task(recurrence="weekly", due_days=[]))
    owner.add_pet(pet)

    plan = DailyPlan(owner=owner)
    plan.generate()

    assert len(plan.scheduled_tasks) == 0, "Weekly task with no due_days should not crash or schedule"


# --- Required: sorting correctness ---

def test_sorting_chronological_order_across_slots():
    owner = make_owner()
    pet = make_pet()
    # Added in reverse chronological order on purpose
    pet.add_task(make_task("Evening Task",   time_of_day="evening",   task_type="enrichment"))
    pet.add_task(make_task("Afternoon Task", time_of_day="afternoon", task_type="grooming"))
    pet.add_task(make_task("Morning Task",   time_of_day="morning",   task_type="walk"))
    owner.add_pet(pet)

    plan = DailyPlan(owner=owner)
    plan.generate()

    slots = [t.time_of_day for t in plan.scheduled_tasks]
    assert slots == ["morning", "afternoon", "evening"], (
        f"Tasks should be ordered morning → afternoon → evening, got: {slots}"
    )


# --- Required: recurrence logic ---

def test_recurrence_daily_task_appears_in_next_plan():
    pet = make_pet()
    task = make_task(name="Give Meds", task_type="medication", duration=5, recurrence="daily")
    pet.add_task(task)
    task.mark_complete()

    # Daily tasks always return True from is_due_today(), so the same task
    # appears in the next generated plan — no duplication needed
    owner = make_owner()
    owner.add_pet(pet)
    plan = DailyPlan(owner=owner)
    plan.generate()

    scheduled_names = [t.name for t in plan.scheduled_tasks]
    assert "Give Meds" in scheduled_names, "Daily task should still appear in next plan after being completed"


# --- Required: conflict detection ---

def test_conflict_detection_flags_duplicate_time_slot():
    owner = make_owner()
    pet = make_pet()
    # Two walk tasks both assigned to morning for the same pet
    pet.add_task(make_task("Walk 1", task_type="walk", time_of_day="morning", sort_order=0))
    pet.add_task(make_task("Walk 2", task_type="walk", time_of_day="morning", sort_order=1))
    owner.add_pet(pet)

    plan = DailyPlan(owner=owner)
    plan.generate()

    assert len(plan.conflicts) >= 1, "Scheduler should flag the duplicate time slot"
    assert "Buddy" in plan.conflicts[0],  "Conflict message should name the pet"
    assert "morning" in plan.conflicts[0], "Conflict message should name the time slot"


# --- Edge cases ---

def test_owner_with_no_pets_generates_empty_plan():
    owner = make_owner()
    plan = DailyPlan(owner=owner)
    plan.generate()

    assert plan.scheduled_tasks == []
    assert plan.skipped_tasks == []
    assert plan.conflicts == []


def test_pet_with_no_tasks_does_not_crash():
    owner = make_owner()
    pet = make_pet()
    owner.add_pet(pet)

    plan = DailyPlan(owner=owner)
    plan.generate()

    assert plan.scheduled_tasks == []
