from datetime import date

PRIORITY_ORDER = {"high": 0, "medium": 1, "low": 2}
TIME_OF_DAY_ORDER = {"morning": 0, "afternoon": 1, "evening": 2}


class Task:
    def __init__(self, name: str, task_type: str, duration_minutes: int, priority: str, recurrence: str, time_of_day: str = "morning", due_days: list[str] = None, sort_order: int = 0, override_today: bool = False):
        self.name = name
        self.task_type = task_type          # "walk", "feeding", "medication", "grooming", "enrichment"
        self.duration_minutes = duration_minutes
        self.priority = priority            # "high", "medium", "low"
        self.recurrence = recurrence        # "daily", "weekly", "as_needed"
        self.time_of_day = time_of_day      # "morning", "afternoon", "evening"
        self.due_days = due_days or []      # e.g. ["Monday", "Wednesday"] — used when recurrence is "weekly"
        self.sort_order = sort_order        # lower number runs first within a time slot
        self.override_today = override_today  # force this task into today's plan regardless of recurrence
        self.pet_name: str = ""             # set automatically when added to a Pet
        self.completed: bool = False
        self._pet = None                    # back-reference to Pet, set in Pet.add_task()

    def mark_complete(self) -> None:
        """Mark this task as completed."""
        self.completed = True

    def clear_completion(self) -> None:
        """Reset this task to incomplete."""
        self.completed = False

    def is_due_today(self) -> bool:
        """Return True if this task should be scheduled today based on its recurrence."""
        if self.override_today:
            return True
        if self.recurrence == "daily":
            return True
        if self.recurrence == "weekly":
            if not self.due_days:
                return False  # no days configured, skip silently
            return date.today().strftime("%A") in self.due_days
        # "as_needed" tasks are not automatically scheduled
        return False


class Pet:
    def __init__(self, name: str, species: str):
        self.name = name
        self.species = species
        self.tasks: list[Task] = []

    def add_task(self, task: Task) -> None:
        """Add a task to this pet and assign the pet's name to the task."""
        task.pet_name = self.name
        task._pet = self
        self.tasks.append(task)

    def get_tasks(self) -> list[Task]:
        """Return all tasks assigned to this pet."""
        return self.tasks


class Owner:
    def __init__(self, name: str, available_hours_per_day: float):
        self.name = name
        self.available_hours_per_day = available_hours_per_day
        self.pets: list[Pet] = []

    def add_pet(self, pet: Pet) -> None:
        """Add a pet to this owner's list of pets."""
        self.pets.append(pet)

    def get_pets(self) -> list[Pet]:
        """Return all pets belonging to this owner."""
        return self.pets


class DailyPlan:
    def __init__(self, owner: Owner, plan_date: date = None):
        self.date = plan_date or date.today()
        self.owner = owner
        self.scheduled_tasks: list[Task] = []
        self.skipped_tasks: list[Task] = []
        self.conflicts: list[str] = []

    @property
    def total_duration_minutes(self) -> int:
        """Return the sum of all scheduled task durations in minutes."""
        return sum(t.duration_minutes for t in self.scheduled_tasks)

    def generate(self) -> None:
        """Populate scheduled_tasks with due tasks that fit within the owner's daily time budget."""
        # Sort by time of day, then intra-slot order, then priority, then shortest duration (tie-break)
        budget_minutes = self.owner.available_hours_per_day * 60

        due_tasks = [
            task
            for pet in self.owner.get_pets()
            for task in pet.get_tasks()
            if task.is_due_today()
        ]

        sorted_tasks = sorted(
            due_tasks,
            key=lambda t: (
                TIME_OF_DAY_ORDER.get(t.time_of_day, 99),
                t.sort_order,
                PRIORITY_ORDER.get(t.priority, 99),
                t.duration_minutes
            )
        )

        self.scheduled_tasks = []
        self.skipped_tasks = []
        running_total = 0
        for task in sorted_tasks:
            if running_total + task.duration_minutes <= budget_minutes:
                self.scheduled_tasks.append(task)
                running_total += task.duration_minutes
            else:
                self.skipped_tasks.append(task)

        # Detect duplicate task_type per pet per time slot
        self.conflicts = []
        seen = set()
        for task in self.scheduled_tasks:
            key = (task.pet_name, task.task_type, task.time_of_day)
            if key in seen:
                self.conflicts.append(
                    f"{task.pet_name} has duplicate '{task.task_type}' tasks in the {task.time_of_day}"
                )
            seen.add(key)

    def get_tasks_for_pet(self, pet_name: str) -> list[Task]:
        """Return scheduled tasks for a specific pet."""
        return [t for t in self.scheduled_tasks if t.pet_name == pet_name]

    def get_incomplete_tasks(self) -> list[Task]:
        """Return scheduled tasks that have not been marked complete."""
        return [t for t in self.scheduled_tasks if not t.completed]

    def get_skipped_tasks(self) -> list[Task]:
        """Return tasks that were due today but excluded due to budget overflow."""
        return self.skipped_tasks

    def get_tasks_by_priority(self) -> list[Task]:
        """Return scheduled tasks sorted by priority then shortest duration."""
        return sorted(
            self.scheduled_tasks,
            key=lambda t: (PRIORITY_ORDER.get(t.priority, 99), t.duration_minutes)
        )

    def display(self) -> str:
        """Return a formatted string of the daily plan grouped by time of day."""
        if not self.scheduled_tasks:
            return f"No tasks scheduled for {self.date}."

        lines = [f"Daily Plan for {self.owner.name} - {self.date}"]

        for slot in ["morning", "afternoon", "evening"]:
            slot_tasks = [t for t in self.scheduled_tasks if t.time_of_day == slot]
            if not slot_tasks:
                continue

            lines.append(f"\n  {slot.capitalize()}")
            lines.append("  " + "-" * 36)
            for task in sorted(slot_tasks, key=lambda t: (t.sort_order, PRIORITY_ORDER.get(t.priority, 99), t.duration_minutes)):
                status = "✓" if task.completed else " "
                lines.append(f"  [{status}] [{task.priority.upper()}] {task.pet_name}: {task.name} ({task.duration_minutes} min)")

        lines.append("\n" + "-" * 40)
        budget_minutes = int(self.owner.available_hours_per_day * 60)
        lines.append(f"Total: {self.total_duration_minutes} / {budget_minutes} min used")

        if self.skipped_tasks:
            lines.append("\n  Skipped (budget exceeded):")
            for task in self.skipped_tasks:
                lines.append(f"  - {task.pet_name}: {task.name} ({task.duration_minutes} min)")

        if self.conflicts:
            lines.append("\n  Conflicts detected:")
            for conflict in self.conflicts:
                lines.append(f"  ! {conflict}")

        return "\n".join(lines)
