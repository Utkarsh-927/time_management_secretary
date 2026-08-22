const API_BASE_URL = "http://127.0.0.1:8000";

export const api = {
  // Dashboard
  getDashboard: async () => {
    const response = await fetch(`${API_BASE_URL}/dashboard`);
    return response.json();
  },

  // Tasks
  getTasks: async () => {
    const response = await fetch(`${API_BASE_URL}/tasks`);
    return response.json();
  },

  createTask: async (taskData) => {
    const response = await fetch(`${API_BASE_URL}/tasks`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify(taskData),
    });

    return response.json();
  },

  updateTask: async (taskId, taskData) => {
    const response = await fetch(`${API_BASE_URL}/tasks/${taskId}`, {
      method: "PUT",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify(taskData),
    });

    return response.json();
  },

  deleteTask: async (taskId) => {
    const response = await fetch(`${API_BASE_URL}/tasks/${taskId}`, {
      method: "DELETE",
    });

    return response.json();
  },

  // Meetings
  getMeetings: async () => {
    const response = await fetch(`${API_BASE_URL}/meetings`);
    return response.json();
  },

  // Availability
  getAvailability: async () => {
    const response = await fetch(`${API_BASE_URL}/availability`);
    return response.json();
  },

  // Reminders
  getReminders: async () => {
    const response = await fetch(`${API_BASE_URL}/reminders`);
    return response.json();
  },

  // AI
  processMessage: async (message) => {
    const response = await fetch(`${API_BASE_URL}/ai/process`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        message: message,
      }),
    });

    return response.json();
  },
};