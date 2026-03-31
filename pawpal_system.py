from datetime import date


class Task:
    def __init__(self, name: str, task_type: str, duration_minutes: int, priority: str, recurrence: str):
        self.name = name
        self.task_type = task_type          # "walk", "feeding", "medication", "grooming", "enrichment"
        self.duration_minutes = duration_minutes
        self.priority = priority            # "high", "medium", "low"
        self.recurrence = recurrence        # "daily", "weekly", "as_needed"

    def is_due_today(self) -> bool:
        pass


class Pet:
    def __init__(self, name: str, species: str):
        self.name = name
        self.species = species
        self.tasks: list[Task] = []

    def add_task(self, task: Task) -> None:
        pass

    def get_tasks(self) -> list[Task]:
        pass


class Owner:
    def __init__(self, name: str, available_hours_per_day: float):
        self.name = name
        self.available_hours_per_day = available_hours_per_day
        self.pets: list[Pet] = []

    def add_pet(self, pet: Pet) -> None:
        pass

    def get_pets(self) -> list[Pet]:
        pass


class DailyPlan:
    def __init__(self, owner: Owner, plan_date: date = None):
        self.date = plan_date or date.today()
        self.owner = owner
        self.scheduled_tasks: list[Task] = []
        self.total_duration_minutes: int = 0

    def generate(self) -> None:
        pass

    def get_tasks_by_priority(self) -> list[Task]:
        pass

    def display(self) -> str:
        pass
