# PawPal+ Project Reflection

## 1. System Design

**a. Initial design**

- Briefly describe your initial UML design.
- What classes did you include, and what responsibilities did you assign to each?

We want to start with the most important things. The main things is making sure your pet is getting walked, fed, and taking any medicine they need. They need to be able to schedule all of these. Obviously they will also need to be able to add their pets and ad these tasks per pet. They need to be able to see the tasks for the day in a simple format. 

We ended up making classes for Task, Owner, Pet, and DailyPlan. This will allow for all of the basic things I identified as necessary for an MVP.
Task is simply a class for the things associated for the task you must do with your pet. Owner is a profile of sorts that we created to assign pets to and then assign tasks via the pet. DailyPlan allows for a view of all of the tasks, kind of like a dashboard. 

**b. Design changes**

- Did your design change during implementation?

Summary of suggested additions:

Where:	     What to add:
Task	    pet: Pet back-reference (or pet_name: str)
Task	    due_days: list[str] for weekly recurrence
DailyPlan	tie-breaking rule doc/comment on generate()
DailyPlan	consider total_duration_minutes as @property

- If yes, describe at least one change and why you made it.

Yes. In the initial UML, `Task` had no reference to the pet it belonged to. During review we realized that when `DailyPlan.generate()` collects tasks from all pets and flattens them into a single list, the pet context is lost — you could no longer display something like "Walk Buddy." We added a `pet_name` attribute to `Task` that gets set automatically when a task is added to a `Pet`, so the plan can display each task with its pet's name without needing to trace back through the object graph.

---

## 2. Scheduling Logic and Tradeoffs

**a. Constraints and priorities**

- What constraints does your scheduler consider (for example: time, priority, preferences)?
- How did you decide which constraints mattered most?

The scheduler considers three constraints: the owner's available hours per day (a hard budget cap), task priority (high / medium / low), and time of day (morning / afternoon / evening). Recurrence also acts as a soft constraint — only tasks that are due today enter the plan at all.

Time budget was treated as the most important constraint because it's the one that forces real decisions. Without it, the scheduler is just a to-do list. Priority determines which tasks survive when the time budget of the owner runs out. high-priority tasks (medication, feeding, walks) are protected while low-priority ones (enrichment, grooming) are the first to be dropped. Time of day was added not as a hard limit but as an organizational layer, ensuring the plan reflects how a real day is structured rather than dumping everything into one flat list. Within a time slot, a `sort_order` field gives the owner fine-grained control over sequencing when priority alone isn't enough (e.g., give meds before breakfast).

**b. Tradeoffs**

- Describe one tradeoff your scheduler makes.
- Why is that tradeoff reasonable for this scenario?

The scheduler uses time of day buckets (morning, afternoon, evening) rather than checking for actual clock-time overlaps. Two 30-minute tasks both assigned to "morning" are treated as compatible as long as they fit within the owner's total daily budget — the scheduler never asks whether there are literally enough morning minutes to fit both. This means two tasks could theoretically both be labeled "morning" even if a real morning only has 45 minutes and the tasks together take 60.

This tradeoff is reasonable for this scenario because the app is aimed at a casual pet owner planning their day, not a calendar tool with hard time blocks. Coarse slots are easy to fill out in the UI and easy to read at a glance. Adding exact clock-time scheduling would require start/end times on every task, per-slot time budgets, and overlap arithmetic — complexity that would make the app harder to use without meaningfully improving pet care outcomes.

---

## 3. AI Collaboration

**a. How you used AI**

- How did you use AI tools during this project (for example: design brainstorming, debugging, refactoring)?
- What kinds of prompts or questions were most helpful?

**b. Judgment and verification**

- Describe one moment where you did not accept an AI suggestion as-is.
- How did you evaluate or verify what the AI suggested?

---

## 4. Testing and Verification

**a. What you tested**

- What behaviors did you test?
- Why were these tests important?

**b. Confidence**

- How confident are you that your scheduler works correctly?
- What edge cases would you test next if you had more time?

---

## 5. Reflection

**a. What went well**

- What part of this project are you most satisfied with?

**b. What you would improve**

- If you had another iteration, what would you improve or redesign?

**c. Key takeaway**

- What is one important thing you learned about designing systems or working with AI on this project?
