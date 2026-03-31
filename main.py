from pawpal_system import Owner, Pet, Task, DailyPlan

alex = Owner(name="Alex", available_hours_per_day=2.0)

buddy = Pet(name="Buddy", species="Dog")
whiskers = Pet(name="Whiskers", species="Cat")

alex.add_pet(buddy)
alex.add_pet(whiskers)

buddy.add_task(Task("Give Meds",    task_type="medication", duration_minutes=5,  priority="high",   recurrence="daily", time_of_day="morning",   sort_order=0))
buddy.add_task(Task("Breakfast",    task_type="feeding",    duration_minutes=10, priority="high",   recurrence="daily", time_of_day="morning",   sort_order=1))
buddy.add_task(Task("Morning Walk", task_type="walk",       duration_minutes=30, priority="high",   recurrence="daily", time_of_day="morning",   sort_order=2))
buddy.add_task(Task("Fetch / Play", task_type="enrichment", duration_minutes=20, priority="low",    recurrence="daily", time_of_day="afternoon"))

whiskers.add_task(Task("Breakfast", task_type="feeding",    duration_minutes=5,  priority="high",   recurrence="daily", time_of_day="morning",   sort_order=0))
whiskers.add_task(Task("Laser Toy", task_type="enrichment", duration_minutes=10, priority="low",    recurrence="daily", time_of_day="evening"))

# --- CONFLICT: two feeding tasks for Whiskers in the same morning slot ---
whiskers.add_task(Task("Second Feeding", task_type="feeding", duration_minutes=5, priority="medium", recurrence="daily", time_of_day="morning",  sort_order=1))

# =========================================================
# PART 1: Conflict detection
# =========================================================
print("=" * 50)
print(" PART 1: Conflict Detection")
print("=" * 50)

plan = DailyPlan(owner=alex)
plan.generate()
print(plan.display())

# =========================================================
# PART 2: Auto-schedule next occurrence on mark_complete
# =========================================================
print("\n" + "=" * 50)
print(" PART 2: Auto-schedule next occurrence")
print("=" * 50)

morning_tasks = plan.get_tasks_for_pet("Buddy")
walk_task = next(t for t in morning_tasks if t.name == "Morning Walk")

print(f"\nBuddy's tasks before completing '{walk_task.name}': {len(buddy.get_tasks())}")

walk_task.mark_complete()

print(f"Buddy's tasks after  completing '{walk_task.name}': {len(buddy.get_tasks())}")
print(f"New task added: '{buddy.get_tasks()[-1].name}' | completed={buddy.get_tasks()[-1].completed}")

# Generate a fresh plan — completed task is excluded, new occurrence appears
print("\n--- Fresh plan after mark_complete ---")
plan2 = DailyPlan(owner=alex)
plan2.generate()

print(f"\nBuddy's scheduled tasks in new plan:")
for t in plan2.get_tasks_for_pet("Buddy"):
    status = "done" if t.completed else "pending"
    print(f"  [{status}] {t.name} ({t.time_of_day})")
