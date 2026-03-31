import streamlit as st
from pawpal_system import Owner, Pet, Task, DailyPlan

st.set_page_config(page_title="PawPal+", page_icon="🐾", layout="centered")

st.title("🐾 PawPal+")
st.caption("Your daily pet care planner.")

st.divider()

# --- Session State Initialization ---
if "owner" not in st.session_state:
    st.session_state.owner = None

if "pets" not in st.session_state:
    st.session_state.pets = []

if "plan" not in st.session_state:
    st.session_state.plan = None

# --- Owner Setup ---
st.subheader("Owner")
owner_name = st.text_input("Your name", value="Jordan")
available_hours = st.number_input("Hours available per day", min_value=0.5, max_value=24.0, value=2.0, step=0.5)

if st.button("Save Owner"):
    st.session_state.owner = Owner(name=owner_name, available_hours_per_day=available_hours)
    st.session_state.plan = None
    st.success(f"Owner '{owner_name}' saved!")

st.divider()

# --- Pet Setup ---
st.subheader("Pets")
col1, col2 = st.columns(2)
with col1:
    pet_name = st.text_input("Pet name", value="Mochi")
with col2:
    species = st.selectbox("Species", ["dog", "cat", "other"])

if st.button("Add Pet"):
    if st.session_state.owner is None:
        st.warning("Save an owner first.")
    else:
        new_pet = Pet(name=pet_name, species=species)
        st.session_state.owner.add_pet(new_pet)
        st.session_state.pets.append(pet_name)
        st.success(f"Added pet '{pet_name}'!")

if st.session_state.pets:
    st.write("Pets added:", ", ".join(st.session_state.pets))

st.divider()

# --- Task Setup ---
st.subheader("Add a Task")

if not st.session_state.owner or not st.session_state.owner.get_pets():
    st.info("Save an owner and add at least one pet before adding tasks.")
else:
    pet_names = [p.name for p in st.session_state.owner.get_pets()]
    selected_pet_name = st.selectbox("Assign to pet", pet_names)

    col1, col2 = st.columns(2)
    with col1:
        task_name = st.text_input("Task name", value="Morning Walk")
        task_type = st.selectbox("Type", ["walk", "feeding", "medication", "grooming", "enrichment"])
        duration = st.number_input("Duration (minutes)", min_value=1, max_value=240, value=20)
    with col2:
        priority = st.selectbox("Priority", ["high", "medium", "low"])
        recurrence = st.selectbox("Recurrence", ["daily", "weekly", "as_needed"])
        time_of_day = st.selectbox("Time of day", ["morning", "afternoon", "evening"])

    due_days = []
    if recurrence == "weekly":
        due_days = st.multiselect(
            "Due on",
            ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
        )

    if st.button("Add Task"):
        selected_pet = next(p for p in st.session_state.owner.get_pets() if p.name == selected_pet_name)
        selected_pet.add_task(Task(
            name=task_name,
            task_type=task_type,
            duration_minutes=int(duration),
            priority=priority,
            recurrence=recurrence,
            time_of_day=time_of_day,
            due_days=due_days
        ))
        st.success(f"Added '{task_name}' to {selected_pet_name}!")

    all_tasks = [
        {
            "Pet": t.pet_name,
            "Task": t.name,
            "Type": t.task_type,
            "Duration (min)": t.duration_minutes,
            "Priority": t.priority,
            "Recurrence": t.recurrence,
            "Time of Day": t.time_of_day,
        }
        for p in st.session_state.owner.get_pets()
        for t in p.get_tasks()
    ]
    if all_tasks:
        st.write("Current tasks:")
        st.table(all_tasks)

st.divider()

# --- Build Schedule ---
st.subheader("Daily Schedule")

if st.button("Generate Schedule"):
    if st.session_state.owner is None:
        st.warning("Save an owner first.")
    else:
        plan = DailyPlan(owner=st.session_state.owner)
        plan.generate()
        st.session_state.plan = plan

if st.session_state.plan:
    plan = st.session_state.plan
    budget_minutes = int(plan.owner.available_hours_per_day * 60)

    # --- Summary metrics ---
    col1, col2, col3 = st.columns(3)
    col1.metric("Scheduled", f"{len(plan.scheduled_tasks)} tasks")
    col2.metric("Time Used", f"{plan.total_duration_minutes} min")
    col3.metric("Budget", f"{budget_minutes} min")

    # --- Conflicts ---
    for conflict in plan.conflicts:
        st.warning(f"Conflict detected: {conflict}")

    # --- Skipped tasks ---
    skipped = plan.get_skipped_tasks()
    if skipped:
        with st.expander(f"Skipped ({len(skipped)} tasks — budget exceeded)"):
            st.table([
                {"Pet": t.pet_name, "Task": t.name, "Duration (min)": t.duration_minutes, "Priority": t.priority}
                for t in skipped
            ])

    # --- Filter by pet ---
    pet_names = ["All pets"] + [p.name for p in plan.owner.get_pets()]
    selected_filter = st.selectbox("Filter by pet", pet_names)

    # --- Tasks by time slot with checkboxes ---
    for slot in ["morning", "afternoon", "evening"]:
        if selected_filter == "All pets":
            slot_tasks = [t for t in plan.scheduled_tasks if t.time_of_day == slot]
        else:
            slot_tasks = [t for t in plan.get_tasks_for_pet(selected_filter) if t.time_of_day == slot]

        if not slot_tasks:
            continue

        st.markdown(f"**{slot.capitalize()}**")

        # Column headers
        h1, h2, h3, h4, h5, h6 = st.columns([1, 2, 3, 2, 2, 2])
        h1.caption("Done")
        h2.caption("Pet")
        h3.caption("Task")
        h4.caption("Type")
        h5.caption("Duration")
        h6.caption("Priority")

        for task in slot_tasks:
            c1, c2, c3, c4, c5, c6 = st.columns([1, 2, 3, 2, 2, 2])
            checked = c1.checkbox("", value=task.completed, key=f"task_{id(task)}", label_visibility="collapsed")
            if checked and not task.completed:
                task.mark_complete()
                st.rerun()
            elif not checked and task.completed:
                task.clear_completion()
                st.rerun()
            c2.write(task.pet_name)
            c3.write(task.name)
            c4.write(task.task_type)
            c5.write(f"{task.duration_minutes} min")
            c6.write(task.priority)

    # --- Incomplete summary ---
    incomplete = plan.get_incomplete_tasks()
    if not incomplete:
        st.success("All tasks complete for today!")
    else:
        st.info(f"{len(incomplete)} task(s) still pending.")
