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

I used AI throughout the whole project — starting with UML design, then implementing the logic, writing tests, and reviewing the code for issues. The most useful prompts were the ones that asked it to review what we already had and identify problems, like "what are the missing relationships or logic bottlenecks?" That kind of question surfaced real issues I hadn't thought about, like the `Task` not knowing which `Pet` it belonged to. Just asking it to "write the code" was less useful than asking it to think critically first.

**b. Judgment and verification**

- Describe one moment where you did not accept an AI suggestion as-is.
- How did you evaluate or verify what the AI suggested?

When reviewing the `generate()` method, AI suggested replacing the nested list comprehension with `itertools.chain.from_iterable`. It was technically more Pythonic but harder to read — especially for someone who hasn't seen `chain` before. I kept the nested comprehension because it reads like plain English ("for each pet, for each task") and there was no real performance reason to change it. I did accept the running total fix in the same review because that one had a clear reason behind it.

---

## 4. Testing and Verification

**a. What you tested**

- What behaviors did you test?
- Why were these tests important?

We ended up with 16 tests covering budget enforcement, sort order across and within time slots, recurrence logic, conflict detection, and edge cases like an owner with no pets or a weekly task with no days set. These were the most important to test because they're the behaviors the whole app depends on — if sorting is wrong or a task sneaks past the budget, the plan is useless. The edge cases mattered because they're the kind of thing a user could accidentally trigger from the UI.

**b. Confidence**

- How confident are you that your scheduler works correctly?
- What edge cases would you test next if you had more time?

4/5. The core logic is solid and all 16 tests pass. I'd knock it down a star because the Streamlit UI has zero automated tests, and the weekly recurrence tests rely on today's actual date — run them on the wrong day and you could get unexpected results. If I had more time I'd test what happens when an owner's budget is set to 0, and add some basic UI tests to make sure the generate button actually produces visible output.

---

## 5. Reflection

**a. What went well**

- What part of this project are you most satisfied with?

The scheduling logic came out cleaner than I expected. The combination of time slots, priority, sort order, and budget enforcement all working together in `generate()` without it getting messy felt good. I was also happy with how the conflict detection ended up — it's a simple set-based check but it actually catches a real problem a user could run into.

**b. What you would improve**

- If you had another iteration, what would you improve or redesign?

The task list showing up while the schedule is already on screen feels redundant — I'd probably move tasks into a collapsible section or a separate tab so the schedule is the main focus once it's generated. I'd also think about giving the owner a way to see what tasks are coming up tomorrow, not just today.

**c. Key takeaway**

- What is one important thing you learned about designing systems or working with AI on this project?

Designing with UML first actually saved time. I would have run into the missing `pet_name` back-reference bug mid-implementation if we hadn't caught it during the diagram review. The lesson is that spending time on design upfront — even a rough one — is worth it because the cost of fixing a structural issue in a diagram is way lower than fixing it in code.
