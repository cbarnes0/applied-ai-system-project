import streamlit as st
from pawpal_system import Owner, Pet, Task, DailyPlan

st.set_page_config(page_title="PawPal+", page_icon="🐾", layout="centered")

st.title("🐾 PawPal+")

st.markdown(
    """
Welcome to the PawPal+ starter app.

This file is intentionally thin. It gives you a working Streamlit app so you can start quickly,
but **it does not implement the project logic**. Your job is to design the system and build it.

Use this app as your interactive demo once your backend classes/functions exist.
"""
)

with st.expander("Scenario", expanded=True):
    st.markdown(
        """
**PawPal+** is a pet care planning assistant. It helps a pet owner plan care tasks
for their pet(s) based on constraints like time, priority, and preferences.

You will design and implement the scheduling logic and connect it to this Streamlit UI.
"""
    )

with st.expander("What you need to build", expanded=True):
    st.markdown(
        """
At minimum, your system should:
- Represent pet care tasks (what needs to happen, how long it takes, priority)
- Represent the pet and the owner (basic info and preferences)
- Build a plan/schedule for a day that chooses and orders tasks based on constraints
- Explain the plan (why each task was chosen and when it happens)
"""
    )

st.divider()

# --- Session State Initialization ---
# Guard each key with "not in" so objects are only created once per session.
# Without this guard, every button click would wipe all pets and tasks.
if "owner" not in st.session_state:
    st.session_state.owner = None

if "pets" not in st.session_state:
    st.session_state.pets = []

# --- Owner Setup ---
st.subheader("Owner")
owner_name = st.text_input("Your name", value="Jordan")
available_hours = st.number_input("Hours available per day", min_value=0.5, max_value=24.0, value=2.0, step=0.5)

if st.button("Save Owner"):
    st.session_state.owner = Owner(name=owner_name, available_hours_per_day=available_hours)
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
st.subheader("Build Schedule")

if st.button("Generate schedule"):
    if st.session_state.owner is None:
        st.warning("Save an owner first.")
    else:
        plan = DailyPlan(owner=st.session_state.owner)
        plan.generate()
        st.text(plan.display())
