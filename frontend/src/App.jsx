import { useEffect, useState } from "react";
import "./App.css";

const API_BASE_URL =
  import.meta.env.VITE_API_URL || "http://localhost:8000";

function App() {
  const [dashboard, setDashboard] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  // =========================================================
  // AI ASSISTANT
  // =========================================================

  const [aiMessage, setAiMessage] = useState("");
  const [aiResult, setAiResult] = useState(null);
  const [loadingAI, setLoadingAI] = useState(false);
  const [assistantOpen, setAssistantOpen] = useState(true);
  const [activeView, setActiveView] = useState("overview");

  // =========================================================
  // SMART PLAN
  // =========================================================

  const [plan, setPlan] = useState(null);
  const [loadingPlan, setLoadingPlan] = useState(false);

  // =========================================================
  // MODALS
  // =========================================================

  const [showTaskModal, setShowTaskModal] = useState(false);
  const [showMeetingModal, setShowMeetingModal] = useState(false);
  const [showAvailabilityModal, setShowAvailabilityModal] =
    useState(false);

  // =========================================================
  // EDITING STATE
  // =========================================================

  const [editingTask, setEditingTask] = useState(null);
  const [editingMeeting, setEditingMeeting] = useState(null);
  const [editingAvailability, setEditingAvailability] =
    useState(null);

  // =========================================================
  // SAVING STATE
  // =========================================================

  const [saving, setSaving] = useState(false);

  // =========================================================
  // TASK FORM
  // =========================================================

  const emptyTask = {
    title: "",
    description: "",
    deadline: "",
    estimated_duration: "",
    importance: 3,
  };

  const [taskForm, setTaskForm] = useState(emptyTask);

  // =========================================================
  // MEETING FORM
  // =========================================================

  const emptyMeeting = {
    title: "",
    description: "",
    start_time: "",
    end_time: "",
    location: "",
    participants: "",
  };

  const [meetingForm, setMeetingForm] = useState(emptyMeeting);

  // =========================================================
  // AVAILABILITY FORM
  // =========================================================

  const emptyAvailability = {
    start_date: "",
    end_date: "",
    start_time: "",
    end_time: "",
    recurrence: "none",
    weekdays: "",
  };

  const [availabilityForm, setAvailabilityForm] =
    useState(emptyAvailability);

  // =========================================================
  // LOAD DASHBOARD
  // =========================================================

  const loadDashboard = async () => {
    try {
      setLoading(true);
      setError("");

      const response = await fetch(`${API_BASE_URL}/dashboard`);

      if (!response.ok) {
        throw new Error("Failed to load dashboard");
      }

      const data = await response.json();

      setDashboard(data);
    } catch (err) {
      console.error(err);

      setError(
        err.message || "Unable to connect to the backend."
      );
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadDashboard();
  }, []);

  // =========================================================
  // PROCESS AI MESSAGE
  // =========================================================

  const processAIMessage = async (event) => {
    event.preventDefault();

    if (!aiMessage.trim()) {
      setError("Please enter a message for the AI assistant.");
      return;
    }

    try {
      setLoadingAI(true);
      setError("");
      setAiResult(null);

      const response = await fetch(`${API_BASE_URL}/ai/process`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          message: aiMessage.trim(),
        }),
      });

      const data = await response.json();

      if (!response.ok) {
        throw new Error(
          data.detail || "Failed to process your message."
        );
      }

      setAiResult(data);
      setAiMessage("");

      await loadDashboard();
      setPlan(null);
    } catch (err) {
      console.error(err);

      setError(
        err.message || "Unable to process the AI request."
      );
    } finally {
      setLoadingAI(false);
    }
  };

  // =========================================================
  // CLEAR AI RESULT
  // =========================================================

  const clearAIResult = () => {
    setAiResult(null);
  };

  // =========================================================
  // GENERATE SMART PLAN
  // =========================================================

  const generatePlan = async () => {
    try {
      setLoadingPlan(true);
      setError("");

      const response = await fetch(`${API_BASE_URL}/planner/`);
      const data = await response.json();

      if (!response.ok) {
        throw new Error(
          data.detail || "Failed to generate smart plan"
        );
      }

      setPlan(data);
    } catch (err) {
      console.error(err);

      setError(
        err.message || "Unable to generate smart plan."
      );
    } finally {
      setLoadingPlan(false);
    }
  };

  // =========================================================
  // HELPERS
  // =========================================================

  const formatDate = (value) => {
    if (!value) return "Not set";

    return new Date(value).toLocaleDateString("en-US", {
      month: "short",
      day: "numeric",
      year: "numeric",
    });
  };

  const formatDateTime = (value) => {
    if (!value) return "Not set";

    return new Date(value).toLocaleString("en-US", {
      month: "short",
      day: "numeric",
      year: "numeric",
      hour: "numeric",
      minute: "2-digit",
    });
  };

  const formatTime = (value) => {
    if (!value) return "--";

    return new Date(value).toLocaleTimeString("en-US", {
      hour: "numeric",
      minute: "2-digit",
    });
  };

  const formatMinutes = (minutes) => {
    const value = Number(minutes || 0);

    if (value < 60) {
      return `${value} min`;
    }

    const hours = Math.floor(value / 60);
    const remainingMinutes = value % 60;

    if (remainingMinutes === 0) {
      return `${hours} hr${hours !== 1 ? "s" : ""}`;
    }

    return `${hours}h ${remainingMinutes}m`;
  };

  const getCreatedCount = (type) => {
    return aiResult?.created?.[type] || 0;
  };

  // =========================================================
  // CLOSE MODALS
  // =========================================================

  const closeAllModals = () => {
    setShowTaskModal(false);
    setShowMeetingModal(false);
    setShowAvailabilityModal(false);

    setEditingTask(null);
    setEditingMeeting(null);
    setEditingAvailability(null);

    setTaskForm(emptyTask);
    setMeetingForm(emptyMeeting);
    setAvailabilityForm(emptyAvailability);
  };

  // =========================================================
  // TASK FORM CHANGE
  // =========================================================

  const handleTaskChange = (event) => {
    const { name, value } = event.target;

    setTaskForm((previous) => ({
      ...previous,
      [name]: value,
    }));
  };

  // =========================================================
  // CREATE TASK
  // =========================================================

  const openCreateTask = () => {
    setError("");
    setEditingTask(null);
    setTaskForm(emptyTask);
    setShowTaskModal(true);
  };

  // =========================================================
  // EDIT TASK
  // =========================================================

  const openEditTask = (task) => {
    setError("");
    setEditingTask(task);

    setTaskForm({
      title: task.title || "",
      description: task.description || "",
      deadline: task.deadline
        ? new Date(task.deadline).toISOString().slice(0, 16)
        : "",
      estimated_duration: task.estimated_duration || "",
      importance: task.importance || 3,
    });

    setShowTaskModal(true);
  };

  // =========================================================
  // SAVE TASK
  // =========================================================

  const saveTask = async (event) => {
    event.preventDefault();

    if (!taskForm.title.trim()) {
      setError("Task title is required.");
      return;
    }

    try {
      setSaving(true);
      setError("");

      const payload = {
        title: taskForm.title.trim(),
        description: taskForm.description.trim() || null,
        deadline: taskForm.deadline
          ? new Date(taskForm.deadline).toISOString()
          : null,
        estimated_duration: taskForm.estimated_duration
          ? Number(taskForm.estimated_duration)
          : null,
        importance: Number(taskForm.importance),
      };

      const url = editingTask
        ? `${API_BASE_URL}/tasks/${editingTask.id}`
        : `${API_BASE_URL}/tasks/`;

      const method = editingTask ? "PUT" : "POST";

      const response = await fetch(url, {
        method,
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify(payload),
      });

      const data = await response.json();

      if (!response.ok) {
        throw new Error(
          data.detail || "Failed to save task"
        );
      }

      closeAllModals();
      await loadDashboard();
      setPlan(null);
    } catch (err) {
      console.error(err);

      setError(
        err.message || "Failed to save task."
      );
    } finally {
      setSaving(false);
    }
  };

  // =========================================================
  // COMPLETE TASK
  // =========================================================

  const completeTask = async (taskId) => {
    try {
      setError("");

      const response = await fetch(
        `${API_BASE_URL}/tasks/${taskId}/complete`,
        {
          method: "PATCH",
        }
      );

      const data = await response.json();

      if (!response.ok) {
        throw new Error(
          data.detail || "Failed to complete task"
        );
      }

      await loadDashboard();
      setPlan(null);
    } catch (err) {
      console.error(err);

      setError(
        err.message || "Failed to complete task."
      );
    }
  };

  // =========================================================
  // DELETE TASK
  // =========================================================

  const deleteTask = async (taskId) => {
    const confirmed = window.confirm(
      "Are you sure you want to delete this task?"
    );

    if (!confirmed) return;

    try {
      setError("");

      const response = await fetch(
        `${API_BASE_URL}/tasks/${taskId}`,
        {
          method: "DELETE",
        }
      );

      const data = await response.json();

      if (!response.ok) {
        throw new Error(
          data.detail || "Failed to delete task"
        );
      }

      await loadDashboard();
      setPlan(null);
    } catch (err) {
      console.error(err);

      setError(
        err.message || "Failed to delete task."
      );
    }
  };

  // =========================================================
  // MEETING FORM CHANGE
  // =========================================================

  const handleMeetingChange = (event) => {
    const { name, value } = event.target;

    setMeetingForm((previous) => ({
      ...previous,
      [name]: value,
    }));
  };

  // =========================================================
  // CREATE MEETING
  // =========================================================

  const openCreateMeeting = () => {
    setError("");
    setEditingMeeting(null);
    setMeetingForm(emptyMeeting);
    setShowMeetingModal(true);
  };

  // =========================================================
  // EDIT MEETING
  // =========================================================

  const openEditMeeting = (meeting) => {
    setError("");
    setEditingMeeting(meeting);

    setMeetingForm({
      title: meeting.title || "",
      description: meeting.description || "",
      start_time: meeting.start_time
        ? new Date(meeting.start_time).toISOString().slice(0, 16)
        : "",
      end_time: meeting.end_time
        ? new Date(meeting.end_time).toISOString().slice(0, 16)
        : "",
      location: meeting.location || "",
      participants: Array.isArray(meeting.participants)
        ? meeting.participants.join(", ")
        : meeting.participants || "",
    });

    setShowMeetingModal(true);
  };

  // =========================================================
  // SAVE MEETING
  // =========================================================

  const saveMeeting = async (event) => {
    event.preventDefault();

    if (!meetingForm.title.trim()) {
      setError("Meeting title is required.");
      return;
    }

    if (
      !meetingForm.start_time ||
      !meetingForm.end_time
    ) {
      setError(
        "Meeting start and end time are required."
      );
      return;
    }

    if (
      new Date(meetingForm.end_time) <=
      new Date(meetingForm.start_time)
    ) {
      setError(
        "Meeting end time must be after start time."
      );
      return;
    }

    try {
      setSaving(true);
      setError("");

      const participants = meetingForm.participants
        .split(",")
        .map((item) => item.trim())
        .filter(Boolean);

      const payload = {
        title: meetingForm.title.trim(),
        description:
          meetingForm.description.trim() || null,
        start_time: new Date(
          meetingForm.start_time
        ).toISOString(),
        end_time: new Date(
          meetingForm.end_time
        ).toISOString(),
        location:
          meetingForm.location.trim() || null,
        participants,
      };

      const url = editingMeeting
        ? `${API_BASE_URL}/meetings/${editingMeeting.id}`
        : `${API_BASE_URL}/meetings/`;

      const method = editingMeeting ? "PUT" : "POST";

      const response = await fetch(url, {
        method,
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify(payload),
      });

      const data = await response.json();

      if (!response.ok) {
        throw new Error(
          data.detail || "Failed to save meeting"
        );
      }

      closeAllModals();
      await loadDashboard();
      setPlan(null);
    } catch (err) {
      console.error(err);

      setError(
        err.message || "Failed to save meeting."
      );
    } finally {
      setSaving(false);
    }
  };

  // =========================================================
  // DELETE MEETING
  // =========================================================

  const deleteMeeting = async (meetingId) => {
    const confirmed = window.confirm(
      "Are you sure you want to delete this meeting?"
    );

    if (!confirmed) return;

    try {
      setError("");

      const response = await fetch(
        `${API_BASE_URL}/meetings/${meetingId}`,
        {
          method: "DELETE",
        }
      );

      const data = await response.json();

      if (!response.ok) {
        throw new Error(
          data.detail || "Failed to delete meeting"
        );
      }

      await loadDashboard();
      setPlan(null);
    } catch (err) {
      console.error(err);

      setError(
        err.message || "Failed to delete meeting."
      );
    }
  };

  // =========================================================
  // AVAILABILITY FORM CHANGE
  // =========================================================

  const handleAvailabilityChange = (event) => {
    const { name, value } = event.target;

    setAvailabilityForm((previous) => ({
      ...previous,
      [name]: value,
    }));
  };

  // =========================================================
  // CREATE AVAILABILITY
  // =========================================================

  const openCreateAvailability = () => {
    setError("");
    setEditingAvailability(null);
    setAvailabilityForm(emptyAvailability);
    setShowAvailabilityModal(true);
  };

  // =========================================================
  // EDIT AVAILABILITY
  // =========================================================

  const openEditAvailability = (item) => {
    setError("");
    setEditingAvailability(item);

    setAvailabilityForm({
      start_date: item.start_date || "",
      end_date: item.end_date || "",
      start_time: item.start_time
        ? item.start_time.slice(0, 5)
        : "",
      end_time: item.end_time
        ? item.end_time.slice(0, 5)
        : "",
      recurrence: item.recurrence || "none",
      weekdays: Array.isArray(item.weekdays)
        ? item.weekdays.join(", ")
        : item.weekdays || "",
    });

    setShowAvailabilityModal(true);
  };

  // =========================================================
  // SAVE AVAILABILITY
  // =========================================================

  const saveAvailability = async (event) => {
    event.preventDefault();

    if (
      !availabilityForm.start_date ||
      !availabilityForm.end_date
    ) {
      setError(
        "Start date and end date are required."
      );
      return;
    }

    if (
      new Date(availabilityForm.end_date) <
      new Date(availabilityForm.start_date)
    ) {
      setError(
        "End date must be after or equal to start date."
      );
      return;
    }

    if (
      availabilityForm.start_time &&
      availabilityForm.end_time &&
      availabilityForm.end_time <=
        availabilityForm.start_time
    ) {
      setError(
        "End time must be after start time."
      );
      return;
    }

    if (
      availabilityForm.recurrence === "weekly" &&
      !availabilityForm.weekdays.trim()
    ) {
      setError(
        "Weekdays are required for weekly recurrence."
      );
      return;
    }

    try {
      setSaving(true);
      setError("");

      const weekdays = availabilityForm.weekdays
        .split(",")
        .map((item) => item.trim())
        .filter(Boolean);

      const payload = {
        start_date: availabilityForm.start_date,
        end_date: availabilityForm.end_date,
        start_time:
          availabilityForm.start_time || null,
        end_time:
          availabilityForm.end_time || null,
        recurrence:
          availabilityForm.recurrence,
        weekdays:
          availabilityForm.recurrence === "weekly"
            ? weekdays
            : [],
      };

      const url = editingAvailability
        ? `${API_BASE_URL}/availability/${editingAvailability.id}`
        : `${API_BASE_URL}/availability/`;

      const method = editingAvailability
        ? "PUT"
        : "POST";

      const response = await fetch(url, {
        method,
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify(payload),
      });

      const data = await response.json();

      if (!response.ok) {
        throw new Error(
          data.detail ||
            "Failed to save availability"
        );
      }

      closeAllModals();
      await loadDashboard();
      setPlan(null);
    } catch (err) {
      console.error(err);

      setError(
        err.message ||
          "Failed to save availability."
      );
    } finally {
      setSaving(false);
    }
  };

  // =========================================================
  // DELETE AVAILABILITY
  // =========================================================

  const deleteAvailability = async (
    availabilityId
  ) => {
    const confirmed = window.confirm(
      "Are you sure you want to delete this availability?"
    );

    if (!confirmed) return;

    try {
      setError("");

      const response = await fetch(
        `${API_BASE_URL}/availability/${availabilityId}`,
        {
          method: "DELETE",
        }
      );

      const data = await response.json();

      if (!response.ok) {
        throw new Error(
          data.detail ||
            "Failed to delete availability"
        );
      }

      await loadDashboard();
      setPlan(null);
    } catch (err) {
      console.error(err);

      setError(
        err.message ||
          "Failed to delete availability."
      );
    }
  };


  // =========================================================
  // DERIVED DASHBOARD ANALYTICS
  // =========================================================

  const analytics = {
    pending_tasks: (dashboard?.tasks || []).filter(
      (task) => task.status !== "completed"
    ).length,

    overdue_tasks: (dashboard?.tasks || []).filter((task) => {
      if (!task.deadline || task.status === "completed") {
        return false;
      }

      const deadline = new Date(task.deadline);
      return !Number.isNaN(deadline.getTime()) && deadline < new Date();
    }).length,

    upcoming_meetings: (dashboard?.meetings || []).filter((meeting) => {
      if (!meeting.start_time) return false;

      const start = new Date(meeting.start_time);
      return !Number.isNaN(start.getTime()) && start >= new Date();
    }).length,

    scheduled_minutes: (plan?.schedule || []).reduce(
      (total, item) => total + Number(item.duration_minutes || 0),
      0
    ),

    available_minutes: (dashboard?.availability || []).reduce(
      (total, item) => {
        if (!item.start_time || !item.end_time) {
          return total;
        }

        const [startHour, startMinute] = String(item.start_time)
          .slice(0, 5)
          .split(":")
          .map(Number);

        const [endHour, endMinute] = String(item.end_time)
          .slice(0, 5)
          .split(":")
          .map(Number);

        if (
          Number.isNaN(startHour) ||
          Number.isNaN(startMinute) ||
          Number.isNaN(endHour) ||
          Number.isNaN(endMinute)
        ) {
          return total;
        }

        const minutes =
          endHour * 60 +
          endMinute -
          (startHour * 60 + startMinute);

        return total + Math.max(0, minutes);
      },
      0
    ),
  };

  // =========================================================
  // LOADING
  // =========================================================


  // =========================================================
  // DASHBOARD TIMELINE
  // =========================================================

  const timelineItems = [
    ...(dashboard?.meetings || []).map((meeting) => ({
      id: `meeting-${meeting.id}`,
      type: "meeting",
      title: meeting.title || "Meeting",
      start: meeting.start_time,
      end: meeting.end_time,
      meta: meeting.location || "Meeting",
    })),
    ...(plan?.schedule || []).map((item, index) => ({
      id: `plan-${item.task_id}-${index}`,
      type: "task",
      title: item.task_title || `Task #${item.task_id}`,
      start: item.start_time,
      end: item.end_time,
      meta: `${item.duration_minutes || 0} min · ${item.priority || "Planned"}`,
    })),
  ].sort(
    (a, b) =>
      new Date(a.start).getTime() -
      new Date(b.start).getTime()
  );

  return (
    <>
      <div className="app-shell">
        <header className="topbar">
          <div className="topbar-brand">
            <div className="brand-mark">M</div>
            <div>
              <span className="brand-kicker">PERSONAL COMMAND CENTER</span>
              <strong>Management Model</strong>
              <span>AI-powered time management</span>
            </div>
          </div>

          <nav className="main-nav" aria-label="Primary navigation">
            {[
              ["overview", "Overview"],
              ["tasks", "Tasks"],
              ["meetings", "Meetings"],
              ["availability", "Availability"],
              ["reminders", "Reminders"],
            ].map(([key, label]) => (
              <button
                type="button"
                key={key}
                className={`nav-item ${activeView === key ? "active" : ""}`}
                onClick={() => setActiveView(key)}
              >
                {label}
              </button>
            ))}
          </nav>

          <div className="topbar-actions">
            <button
              type="button"
              className="topbar-primary"
              onClick={generatePlan}
              disabled={loadingPlan}
            >
              {loadingPlan ? "Planning..." : "Generate plan"}
            </button>
          </div>
        </header>

        <div className={`dashboard-layout ${assistantOpen ? "assistant-visible" : "assistant-hidden"}`} data-assistant={assistantOpen ? "open" : "closed"}>
          <main className="dashboard-main">
            <section className="page-heading">
              <div>
                <span className="page-kicker">
                  {activeView === "overview" ? "TODAY" : activeView.toUpperCase()}
                </span>
                <h1>
                  {activeView === "overview" && "Your day, organized."}
                  {activeView === "tasks" && "Tasks"}
                  {activeView === "meetings" && "Meetings"}
                  {activeView === "availability" && "Availability"}
                  {activeView === "reminders" && "Reminders"}
                </h1>
                <p>
                  {activeView === "overview" &&
                    (dashboard?.date
                      ? new Date(dashboard.date).toLocaleDateString("en-US", {
                          weekday: "long",
                          month: "long",
                          day: "numeric",
                          year: "numeric",
                        })
                      : "Today")}
                  {activeView === "tasks" &&
                    "Manage your workload, priorities, deadlines, and progress."}
                  {activeView === "meetings" &&
                    "Keep your meetings visible, organized, and easy to edit."}
                  {activeView === "availability" &&
                    "Define the windows your planner can use for scheduling."}
                  {activeView === "reminders" &&
                    "Review the reminders connected to your plan."}
                </p>
              </div>

              <div className="page-actions">
                {activeView === "tasks" && (
                  <button type="button" className="topbar-primary" onClick={openCreateTask}>
                    + New task
                  </button>
                )}
                {activeView === "meetings" && (
                  <button type="button" className="topbar-primary" onClick={openCreateMeeting}>
                    + New meeting
                  </button>
                )}
                {activeView === "availability" && (
                  <button
                    type="button"
                    className="topbar-primary"
                    onClick={openCreateAvailability}
                  >
                    + New window
                  </button>
                )}
              </div>
            </section>

            {error && (
              <div className="dashboard-error">
                <span>!</span>
                <p>{error}</p>
              </div>
            )}

            {activeView === "overview" && (
              <>
                <section className="stats-row">
                  <div className="stat-card stat-focus">
                    <span>ACTIVE TASKS</span>
                    <strong>{analytics.pending_tasks || 0}</strong>
                    <small>Need your attention</small>
                  </div>
                  <div className="stat-card">
                    <span>OVERDUE</span>
                    <strong>{analytics.overdue_tasks || 0}</strong>
                    <small>Tasks to catch up</small>
                  </div>
                  <div className="stat-card">
                    <span>MEETINGS</span>
                    <strong>{analytics.upcoming_meetings || 0}</strong>
                    <small>Upcoming</small>
                  </div>
                  <div className="stat-card">
                    <span>FOCUS TIME</span>
                    <strong>{formatMinutes(analytics.scheduled_minutes)}</strong>
                    <small>Planned</small>
                  </div>
                  <div className="stat-card">
                    <span>FREE TIME</span>
                    <strong>{formatMinutes(analytics.available_minutes)}</strong>
                    <small>Open today</small>
                  </div>
                </section>

                <div className="dashboard-grid">
                  <section className="panel timeline-panel">
                    <div className="panel-header">
                      <div>
                        <span className="panel-kicker">SCHEDULE</span>
                        <h2>Today’s timeline</h2>
                      </div>
                      <span className="panel-badge">{timelineItems.length} items</span>
                    </div>

                    <div className="panel-body timeline-body">
                      {timelineItems.length === 0 ? (
                        <div className="empty-panel">
                          <div className="empty-icon">◷</div>
                          <strong>No schedule blocks yet</strong>
                          <span>Generate a plan to organize your day.</span>
                        </div>
                      ) : (
                        timelineItems.slice(0, 8).map((item) => (
                          <div className="timeline-item" key={item.id}>
                            <div className="timeline-time">
                              <strong>{formatTime(item.start)}</strong>
                              <span>{formatTime(item.end)}</span>
                            </div>
                            <div className={`timeline-line ${item.type}`}>
                              <span className="timeline-node" />
                            </div>
                            <div className={`timeline-card ${item.type}`}>
                              <div>
                                <span className="timeline-label">
                                  {item.type === "meeting" ? "MEETING" : "PLANNED TASK"}
                                </span>
                                <strong>{item.title}</strong>
                                <span>{item.meta}</span>
                              </div>
                            </div>
                          </div>
                        ))
                      )}
                    </div>
                  </section>

                  <section className="panel focus-panel">
                    <div className="panel-header">
                      <div>
                        <span className="panel-kicker">PRIORITY</span>
                        <h2>Focus tasks</h2>
                      </div>
                      <button
                        type="button"
                        className="panel-link"
                        onClick={openCreateTask}
                      >
                        + New task
                      </button>
                    </div>

                    <div className="panel-body focus-body">
                      {!dashboard?.tasks?.length ? (
                        <div className="empty-panel">
                          <div className="empty-icon success">✓</div>
                          <strong>No active tasks</strong>
                          <span>Your workload is clear.</span>
                        </div>
                      ) : (
                        dashboard.tasks.slice(0, 8).map((task) => (
                          <div className="focus-row" key={task.id}>
                            <button
                              type="button"
                              className="focus-check"
                              onClick={() => completeTask(task.id)}
                            >
                              ✓
                            </button>
                            <div className="focus-content">
                              <strong>{task.title}</strong>
                              <span>
                                {task.deadline
                                  ? `Due ${formatDateTime(task.deadline)}`
                                  : "No deadline"}{" "}
                                · {task.estimated_duration || 0} min
                              </span>
                            </div>
                            <span className={`priority priority-${task.importance || 3}`}>
                              P{task.importance || 3}
                            </span>
                            <button
                              type="button"
                              className="row-menu"
                              onClick={() => openEditTask(task)}
                            >
                              …
                            </button>
                          </div>
                        ))
                      )}
                    </div>
                  </section>

                  <section className="panel compact-card">
                    <div className="panel-header">
                      <div>
                        <span className="panel-kicker">REMINDERS</span>
                        <h2>Next reminders</h2>
                      </div>
                      <button
                        type="button"
                        className="panel-link"
                        onClick={() => setActiveView("reminders")}
                      >
                        View all
                      </button>
                    </div>
                    <div className="panel-body compact-body">
                      {!dashboard?.reminders?.length ? (
                        <div className="empty-inline">
                          <span className="compact-symbol">◌</span>
                          <strong>Nothing pending</strong>
                        </div>
                      ) : (
                        dashboard.reminders.slice(0, 4).map((reminder) => (
                          <div className="compact-row" key={reminder.id}>
                            <span className="compact-symbol">◌</span>
                            <div>
                              <strong>{reminder.title || "Reminder"}</strong>
                              <span>
                                {reminder.reminder_time
                                  ? formatDateTime(reminder.reminder_time)
                                  : "Scheduled"}
                              </span>
                            </div>
                          </div>
                        ))
                      )}
                    </div>
                  </section>

                  <section className="panel compact-card">
                    <div className="panel-header">
                      <div>
                        <span className="panel-kicker">AVAILABILITY</span>
                        <h2>Open windows</h2>
                      </div>
                      <button
                        type="button"
                        className="panel-link"
                        onClick={() => setActiveView("availability")}
                      >
                        View all
                      </button>
                    </div>
                    <div className="panel-body compact-body">
                      {!dashboard?.availability?.length ? (
                        <div className="empty-inline">
                          <span className="compact-symbol green">◷</span>
                          <strong>No availability set</strong>
                        </div>
                      ) : (
                        dashboard.availability.slice(0, 4).map((item) => (
                          <div className="compact-row" key={item.id}>
                            <span className="compact-symbol green">◷</span>
                            <div>
                              <strong>
                                {item.start_time?.slice(0, 5) || "--"} —{" "}
                                {item.end_time?.slice(0, 5) || "--"}
                              </strong>
                              <span>
                                {item.recurrence === "weekly"
                                  ? item.weekdays || "Weekly"
                                  : item.recurrence || "Today"}
                              </span>
                            </div>
                          </div>
                        ))
                      )}
                    </div>
                  </section>
                </div>

                <section className="plan-footer">
                  <div>
                    <span className="panel-kicker">SMART PLANNING</span>
                    <h2>
                      {plan
                        ? `${plan.schedule?.length || 0} focused blocks generated`
                        : "Build a smarter day"}
                    </h2>
                    <p>
                      {plan
                        ? `${plan.unscheduled_tasks?.length || 0} task(s) still need attention.`
                        : "Fit work around your meetings, deadlines, and available time."}
                    </p>
                  </div>
                  <button
                    type="button"
                    className="plan-button"
                    onClick={generatePlan}
                    disabled={loadingPlan}
                  >
                    {loadingPlan
                      ? "Generating..."
                      : plan
                      ? "Regenerate plan"
                      : "Generate smart plan"}
                  </button>
                </section>
              </>
            )}

            {activeView === "tasks" && (
              <section className="full-page-panel">
                {!dashboard?.tasks?.length ? (
                  <div className="page-empty">
                    <div className="empty-icon">✓</div>
                    <h2>No active tasks</h2>
                    <p>Create a task to start planning your workload.</p>
                    <button className="topbar-primary" onClick={openCreateTask}>
                      + Create task
                    </button>
                  </div>
                ) : (
                  <div className="entity-list">
                    {dashboard.tasks.map((task) => (
                      <article className="entity-card" key={task.id}>
                        <button type="button" className="entity-check" onClick={() => completeTask(task.id)}>
                          ✓
                        </button>
                        <div className="entity-main">
                          <div className="entity-title-row">
                            <h3>{task.title}</h3>
                            <span className={`priority priority-${task.importance || 3}`}>
                              Priority {task.importance || 3}
                            </span>
                          </div>
                          {task.description && <p>{task.description}</p>}
                          <div className="entity-meta">
                            <span>{task.deadline ? `Due ${formatDateTime(task.deadline)}` : "No deadline"}</span>
                            <span>{task.estimated_duration || 0} min</span>
                            <span>{task.status || "pending"}</span>
                          </div>
                        </div>
                        <div className="entity-actions">
                          <button className="edit-button" onClick={() => openEditTask(task)}>Edit</button>
                          <button className="delete-button" onClick={() => deleteTask(task.id)}>Delete</button>
                        </div>
                      </article>
                    ))}
                  </div>
                )}
              </section>
            )}

            {activeView === "meetings" && (
              <section className="full-page-panel">
                {!dashboard?.meetings?.length ? (
                  <div className="page-empty">
                    <div className="empty-icon blue">◷</div>
                    <h2>No meetings scheduled</h2>
                    <p>Add meetings here so the planner knows when you are busy.</p>
                    <button className="topbar-primary" onClick={openCreateMeeting}>+ Add meeting</button>
                  </div>
                ) : (
                  <div className="entity-list">
                    {dashboard.meetings
                      .slice()
                      .sort((a, b) => new Date(a.start_time) - new Date(b.start_time))
                      .map((meeting) => (
                        <article className="meeting-card" key={meeting.id}>
                          <div className="meeting-time-block">
                            <strong>{formatTime(meeting.start_time)}</strong>
                            <span>{formatTime(meeting.end_time)}</span>
                          </div>
                          <div className="meeting-line" />
                          <div className="entity-main">
                            <span className="meeting-label">MEETING</span>
                            <h3>{meeting.title}</h3>
                            {meeting.description && <p>{meeting.description}</p>}
                            <div className="entity-meta">
                              <span>{formatDateTime(meeting.start_time)}</span>
                              {meeting.location && <span>📍 {meeting.location}</span>}
                              {Array.isArray(meeting.participants) && meeting.participants.length > 0 && (
                                <span>👥 {meeting.participants.length} participants</span>
                              )}
                            </div>
                          </div>
                          <div className="entity-actions">
                            <button className="edit-button" onClick={() => openEditMeeting(meeting)}>Edit</button>
                            <button className="delete-button" onClick={() => deleteMeeting(meeting.id)}>Delete</button>
                          </div>
                        </article>
                      ))}
                  </div>
                )}
              </section>
            )}

            {activeView === "availability" && (
              <section className="full-page-panel">
                {!dashboard?.availability?.length ? (
                  <div className="page-empty">
                    <div className="empty-icon success">◷</div>
                    <h2>No availability windows</h2>
                    <p>Add the time you want the scheduler to use.</p>
                    <button className="topbar-primary" onClick={openCreateAvailability}>+ Add availability</button>
                  </div>
                ) : (
                  <div className="entity-list">
                    {dashboard.availability.map((item) => (
                      <article className="entity-card" key={item.id}>
                        <div className="entity-icon green">◷</div>
                        <div className="entity-main">
                          <div className="entity-title-row">
                            <h3>{item.recurrence === "weekly" ? "Weekly availability" : "Available time"}</h3>
                            <span className="soft-badge">{item.recurrence || "none"}</span>
                          </div>
                          <p>{formatDate(item.start_date)} — {formatDate(item.end_date)}</p>
                          <div className="entity-meta">
                            <span>{item.start_time?.slice(0,5) || "--"} — {item.end_time?.slice(0,5) || "--"}</span>
                            {item.weekdays?.length > 0 && (
                              <span>{Array.isArray(item.weekdays) ? item.weekdays.join(", ") : item.weekdays}</span>
                            )}
                          </div>
                        </div>
                        <div className="entity-actions">
                          <button className="edit-button" onClick={() => openEditAvailability(item)}>Edit</button>
                          <button className="delete-button" onClick={() => deleteAvailability(item.id)}>Delete</button>
                        </div>
                      </article>
                    ))}
                  </div>
                )}
              </section>
            )}

            {activeView === "reminders" && (
              <section className="full-page-panel">
                {!dashboard?.reminders?.length ? (
                  <div className="page-empty">
                    <div className="empty-icon amber">◌</div>
                    <h2>No reminders</h2>
                    <p>Reminders created through the app or AI assistant will appear here.</p>
                  </div>
                ) : (
                  <div className="entity-list">
                    {dashboard.reminders.map((reminder) => (
                      <article className="entity-card" key={reminder.id}>
                        <div className="entity-icon amber">◌</div>
                        <div className="entity-main">
                          <div className="entity-title-row">
                            <h3>{reminder.title || "Reminder"}</h3>
                            <span className="soft-badge">{reminder.reminder_type || "scheduled"}</span>
                          </div>
                          {reminder.message && <p>{reminder.message}</p>}
                          <div className="entity-meta">
                            <span>
                              {reminder.reminder_time
                                ? formatDateTime(reminder.reminder_time)
                                : "No reminder time set"}
                            </span>
                          </div>
                        </div>
                      </article>
                    ))}
                  </div>
                )}
              </section>
            )}
          </main>

          <aside className={`assistant-panel ${assistantOpen ? "open" : "closed"}`}>
            <div className="assistant-header">
              <div>
                <span className="assistant-kicker">AI ASSISTANT</span>
                <h2>Plan your day</h2>
                <p>Manage tasks, meetings, reminders, and availability.</p>
              </div>
              <button
                type="button"
                className="assistant-close"
                onClick={() => setAssistantOpen(false)}
                aria-label="Close AI assistant"
              >
                ×
              </button>
            </div>

            <div className="assistant-body">
              <div className="assistant-status">
                <span className="assistant-pulse" />
                AI ready
              </div>

              <div className="assistant-welcome">
                <div className="assistant-avatar">🤖</div>
                <div>
                  <strong>Tell me what to change</strong>
                  <p>Use plain language to create, move, update, or cancel records.</p>
                </div>
              </div>

              <div className="assistant-examples">
                {[
                  "Add my Python assignment for tomorrow.",
                  "Move my ML assignment to Friday.",
                  "Make Python task critical.",
                  "Remind me 30 minutes before my meeting.",
                ].map((example) => (
                  <button
                    type="button"
                    key={example}
                    onClick={() => setAiMessage(example)}
                    disabled={loadingAI}
                  >
                    {example}
                  </button>
                ))}
              </div>

              {aiResult && (
                <div className="assistant-result">
                  <div className="assistant-result-top">
                    <div>
                      <span className="result-check">✓</span>
                      <div>
                        <strong>Done</strong>
                        <span>Message processed.</span>
                      </div>
                    </div>
                    <button type="button" className="clear-result" onClick={clearAIResult}>
                      Clear
                    </button>
                  </div>

                  <div className="result-grid">
                    {[
                      ["Tasks", "tasks"],
                      ["Meetings", "meetings"],
                      ["Availability", "availability"],
                      ["Reminders", "reminders"],
                    ].map(([label, key]) => (
                      <div className="result-metric" key={key}>
                        <span>{label}</span>
                        <strong>{getCreatedCount(key)}</strong>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>

            <form className="assistant-composer" onSubmit={processAIMessage}>
              <textarea
                value={aiMessage}
                onChange={(event) => setAiMessage(event.target.value)}
                placeholder="Try: Move my Python task to Friday..."
                rows="4"
                disabled={loadingAI}
              />
              <button type="submit" disabled={loadingAI || !aiMessage.trim()}>
                {loadingAI ? "Processing..." : "Run assistant"}
                <span>→</span>
              </button>
            </form>
          </aside>

          {!assistantOpen && (
            <button
              type="button"
              className="assistant-fab"
              onClick={() => setAssistantOpen(true)}
              aria-label="Open AI assistant"
            >
              🤖
            </button>
          )}
        </div>
      </div>

      {/* ===================================================
          TASK MODAL
      =================================================== */}

      {showTaskModal && (
        <div
          className="modal-overlay"
          onMouseDown={(event) => {
            if (
              event.target ===
                event.currentTarget &&
              !saving
            ) {
              closeAllModals();
            }
          }}
        >
          <div className="task-modal">
            <div className="modal-header">
              <div>
                <span className="eyebrow">
                  {editingTask
                    ? "EDIT TASK"
                    : "NEW TASK"}
                </span>

                <h2>
                  {editingTask
                    ? "Edit Task"
                    : "Create Task"}
                </h2>

                <p>
                  Manage your task details.
                </p>
              </div>

              <button
                className="modal-close"
                onClick={closeAllModals}
                disabled={saving}
              >
                ×
              </button>
            </div>

            <form
              className="task-form"
              onSubmit={saveTask}
            >
              <label>
                Task title

                <input
                  type="text"
                  name="title"
                  placeholder="e.g. Complete ML assignment"
                  value={taskForm.title}
                  onChange={handleTaskChange}
                  autoFocus
                  required
                />
              </label>

              <label>
                Description

                <textarea
                  name="description"
                  placeholder="Add some details..."
                  value={taskForm.description}
                  onChange={handleTaskChange}
                  rows="3"
                />
              </label>

              <div className="form-row">
                <label>
                  Deadline

                  <input
                    type="datetime-local"
                    name="deadline"
                    value={taskForm.deadline}
                    onChange={handleTaskChange}
                  />
                </label>

                <label>
                  Duration (minutes)

                  <input
                    type="number"
                    name="estimated_duration"
                    min="1"
                    placeholder="120"
                    value={
                      taskForm.estimated_duration
                    }
                    onChange={handleTaskChange}
                  />
                </label>
              </div>

              <label>
                Importance

                <select
                  name="importance"
                  value={taskForm.importance}
                  onChange={handleTaskChange}
                >
                  <option value="1">
                    1 — Low
                  </option>

                  <option value="2">
                    2 — Below average
                  </option>

                  <option value="3">
                    3 — Normal
                  </option>

                  <option value="4">
                    4 — High
                  </option>

                  <option value="5">
                    5 — Critical
                  </option>
                </select>
              </label>

              <div className="modal-actions">
                <button
                  type="button"
                  className="secondary-button"
                  onClick={closeAllModals}
                  disabled={saving}
                >
                  Cancel
                </button>

                <button
                  type="submit"
                  className="primary-button"
                  disabled={saving}
                >
                  {saving
                    ? "Saving..."
                    : editingTask
                    ? "Save Changes"
                    : "Create Task"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* ===================================================
          MEETING MODAL
      =================================================== */}

      {showMeetingModal && (
        <div
          className="modal-overlay"
          onMouseDown={(event) => {
            if (
              event.target ===
                event.currentTarget &&
              !saving
            ) {
              closeAllModals();
            }
          }}
        >
          <div className="task-modal">
            <div className="modal-header">
              <div>
                <span className="eyebrow">
                  {editingMeeting
                    ? "EDIT MEETING"
                    : "NEW MEETING"}
                </span>

                <h2>
                  {editingMeeting
                    ? "Edit Meeting"
                    : "Create Meeting"}
                </h2>

                <p>
                  Add a meeting to your schedule.
                </p>
              </div>

              <button
                className="modal-close"
                onClick={closeAllModals}
                disabled={saving}
              >
                ×
              </button>
            </div>

            <form
              className="task-form"
              onSubmit={saveMeeting}
            >
              <label>
                Meeting title

                <input
                  type="text"
                  name="title"
                  placeholder="e.g. Team meeting"
                  value={meetingForm.title}
                  onChange={handleMeetingChange}
                  autoFocus
                  required
                />
              </label>

              <label>
                Description

                <textarea
                  name="description"
                  placeholder="Meeting details..."
                  value={
                    meetingForm.description
                  }
                  onChange={
                    handleMeetingChange
                  }
                  rows="3"
                />
              </label>

              <div className="form-row">
                <label>
                  Start time

                  <input
                    type="datetime-local"
                    name="start_time"
                    value={
                      meetingForm.start_time
                    }
                    onChange={
                      handleMeetingChange
                    }
                    required
                  />
                </label>

                <label>
                  End time

                  <input
                    type="datetime-local"
                    name="end_time"
                    value={
                      meetingForm.end_time
                    }
                    onChange={
                      handleMeetingChange
                    }
                    required
                  />
                </label>
              </div>

              <label>
                Location

                <input
                  type="text"
                  name="location"
                  placeholder="e.g. Conference Room A"
                  value={
                    meetingForm.location
                  }
                  onChange={
                    handleMeetingChange
                  }
                />
              </label>

              <label>
                Participants

                <input
                  type="text"
                  name="participants"
                  placeholder="John, Sarah, Mike"
                  value={
                    meetingForm.participants
                  }
                  onChange={
                    handleMeetingChange
                  }
                />

                <small>
                  Separate participants with commas.
                </small>
              </label>

              <div className="modal-actions">
                <button
                  type="button"
                  className="secondary-button"
                  onClick={closeAllModals}
                  disabled={saving}
                >
                  Cancel
                </button>

                <button
                  type="submit"
                  className="primary-button"
                  disabled={saving}
                >
                  {saving
                    ? "Saving..."
                    : editingMeeting
                    ? "Save Changes"
                    : "Create Meeting"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* ===================================================
          AVAILABILITY MODAL
      =================================================== */}

      {showAvailabilityModal && (
        <div
          className="modal-overlay"
          onMouseDown={(event) => {
            if (
              event.target ===
                event.currentTarget &&
              !saving
            ) {
              closeAllModals();
            }
          }}
        >
          <div className="task-modal">
            <div className="modal-header">
              <div>
                <span className="eyebrow">
                  {editingAvailability
                    ? "EDIT AVAILABILITY"
                    : "NEW AVAILABILITY"}
                </span>

                <h2>
                  {editingAvailability
                    ? "Edit Availability"
                    : "Add Availability"}
                </h2>

                <p>
                  Define when you are available.
                </p>
              </div>

              <button
                className="modal-close"
                onClick={closeAllModals}
                disabled={saving}
              >
                ×
              </button>
            </div>

            <form
              className="task-form"
              onSubmit={saveAvailability}
            >
              <div className="form-row">
                <label>
                  Start date

                  <input
                    type="date"
                    name="start_date"
                    value={
                      availabilityForm.start_date
                    }
                    onChange={
                      handleAvailabilityChange
                    }
                    required
                  />
                </label>

                <label>
                  End date

                  <input
                    type="date"
                    name="end_date"
                    value={
                      availabilityForm.end_date
                    }
                    onChange={
                      handleAvailabilityChange
                    }
                    required
                  />
                </label>
              </div>

              <div className="form-row">
                <label>
                  Start time

                  <input
                    type="time"
                    name="start_time"
                    value={
                      availabilityForm.start_time
                    }
                    onChange={
                      handleAvailabilityChange
                    }
                  />
                </label>

                <label>
                  End time

                  <input
                    type="time"
                    name="end_time"
                    value={
                      availabilityForm.end_time
                    }
                    onChange={
                      handleAvailabilityChange
                    }
                  />
                </label>
              </div>

              <label>
                Recurrence

                <select
                  name="recurrence"
                  value={
                    availabilityForm.recurrence
                  }
                  onChange={
                    handleAvailabilityChange
                  }
                >
                  <option value="none">
                    None
                  </option>

                  <option value="daily">
                    Daily
                  </option>

                  <option value="weekly">
                    Weekly
                  </option>
                </select>
              </label>

              {availabilityForm.recurrence ===
                "weekly" && (
                <label>
                  Weekdays

                  <input
                    type="text"
                    name="weekdays"
                    placeholder="Monday, Wednesday, Friday"
                    value={
                      availabilityForm.weekdays
                    }
                    onChange={
                      handleAvailabilityChange
                    }
                  />

                  <small>
                    Separate weekdays with commas.
                  </small>
                </label>
              )}

              <div className="modal-actions">
                <button
                  type="button"
                  className="secondary-button"
                  onClick={closeAllModals}
                  disabled={saving}
                >
                  Cancel
                </button>

                <button
                  type="submit"
                  className="primary-button"
                  disabled={saving}
                >
                  {saving
                    ? "Saving..."
                    : editingAvailability
                    ? "Save Changes"
                    : "Add Availability"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}    </>
  );
}

export default App;