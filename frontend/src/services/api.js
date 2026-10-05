const API_BASE_URL =
  import.meta.env.VITE_API_BASE_URL ||
  "http://127.0.0.1:8000";

const handleResponse = async (response) => {
  const data = await response.json().catch(() => ({}));

  if (!response.ok) {
    throw new Error(
      data.detail ||
        data.message ||
        "Request failed."
    );
  }

  return data;
};

export const api = {
  // =========================================================
  // AI SECRETARY — QUESTIONS
  // =========================================================

  askSecretary: async (question) => {
    const response = await fetch(
      `${API_BASE_URL}/ai/secretary/ask`,
      {
        method: "POST",

        headers: {
          "Content-Type": "application/json",
        },

        body: JSON.stringify({
          user_id: "default",
          question,
        }),
      }
    );

    return handleResponse(response);
  },

  // =========================================================
  // AI SECRETARY — COMMANDS
  // =========================================================

  processMessage: async (message) => {
    const response = await fetch(
      `${API_BASE_URL}/ai/process`,
      {
        method: "POST",

        headers: {
          "Content-Type": "application/json",
        },

        body: JSON.stringify({
          message,
        }),
      }
    );

    return handleResponse(response);
  },
};

export default api;