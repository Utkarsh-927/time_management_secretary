import { useEffect, useRef, useState } from "react";
import "./App.css";
import api from "./services/api";

function App() {
  const [message, setMessage] = useState("");
  const [mode, setMode] = useState("ask");

  const [messages, setMessages] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const chatEndRef = useRef(null);
  const textareaRef = useRef(null);

  useEffect(() => {
    chatEndRef.current?.scrollIntoView({
      behavior: "smooth",
    });
  }, [messages, loading]);

  const sendMessage = async (event) => {
    event?.preventDefault();

    const text = message.trim();

    if (!text || loading) {
      return;
    }

    setError("");

    const userMessage = {
      id: `${Date.now()}-user`,
      role: "user",
      text,
    };

    setMessages((previous) => [...previous, userMessage]);
    setMessage("");
    setLoading(true);

    try {
      if (mode === "ask") {
        const data = await api.askSecretary(text);

        const assistantMessage = {
          id: `${Date.now()}-assistant`,
          role: "assistant",
          type: "answer",
          text:
            data.answer ||
            "I could not find an answer to that.",
        };

        setMessages((previous) => [
          ...previous,
          assistantMessage,
        ]);
      } else {
        const data = await api.processMessage(text);

        const created = data.created || {};
        const createdItems = [];

        if (created.tasks > 0) {
          createdItems.push(
            `${created.tasks} task${
              created.tasks === 1 ? "" : "s"
            }`
          );
        }

        if (created.meetings > 0) {
          createdItems.push(
            `${created.meetings} meeting${
              created.meetings === 1 ? "" : "s"
            }`
          );
        }

        if (created.availability > 0) {
          createdItems.push(
            `${created.availability} availability window${
              created.availability === 1 ? "" : "s"
            }`
          );
        }

        if (created.reminders > 0) {
          createdItems.push(
            `${created.reminders} reminder${
              created.reminders === 1 ? "" : "s"
            }`
          );
        }

        let commandAnswer =
          data.answer ||
          data.message ||
          "Your request has been processed.";

        if (createdItems.length > 0) {
          commandAnswer += ` Created ${createdItems.join(
            ", "
          )}.`;
        }

        const assistantMessage = {
          id: `${Date.now()}-assistant`,
          role: "assistant",
          type: "command",
          text: commandAnswer,
          data,
        };

        setMessages((previous) => [
          ...previous,
          assistantMessage,
        ]);
      }
    } catch (err) {
      console.error(err);

      const errorText =
        err.message ||
        "Unable to connect to the AI Secretary.";

      setError(errorText);

      setMessages((previous) => [
        ...previous,
        {
          id: `${Date.now()}-error`,
          role: "assistant",
          type: "error",
          text: errorText,
        },
      ]);
    } finally {
      setLoading(false);

      setTimeout(() => {
        textareaRef.current?.focus();
      }, 50);
    }
  };

  const handleTextareaKeyDown = (event) => {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();

      if (!loading && message.trim()) {
        sendMessage(event);
      }
    }
  };

  const askExamples = [
    "What responsibilities did I give Arun?",
    "What tasks are part of the ABC website project?",
    "How much money is allocated to the ABC project?",
    "When should I review the ABC website project?",
    "I have 20 minutes. What should I work on?",
  ];

  const commandExamples = [
    "Add my Python assignment for tomorrow.",
    "Move my ML assignment to Friday.",
    "Make Python task critical.",
    "Remind me 30 minutes before my meeting.",
  ];

  const examples =
    mode === "ask" ? askExamples : commandExamples;

  const clearConversation = () => {
    setMessages([]);
    setError("");
    setMessage("");

    setTimeout(() => {
      textareaRef.current?.focus();
    }, 50);
  };

  const changeMode = (newMode) => {
    if (loading) {
      return;
    }

    setMode(newMode);
    setError("");
    setMessage("");

    setTimeout(() => {
      textareaRef.current?.focus();
    }, 50);
  };

  return (
    <div className="secretary-app">
      <div className="secretary-shell">

        {/* Header */}
        <header className="secretary-header">
          <div className="secretary-brand">
            <div className="secretary-logo">
              M
            </div>

            <div className="secretary-brand-text">
              <span className="secretary-kicker">
                MANAGEMENT MODEL
              </span>

              <h1>AI Secretary</h1>

              <p>
                Your personal AI assistant for tasks,
                projects, responsibilities, deadlines,
                and planning.
              </p>
            </div>
          </div>

          <button
            type="button"
            className="clear-button"
            onClick={clearConversation}
            disabled={
              loading || messages.length === 0
            }
          >
            Clear
          </button>
        </header>

        {/* Mode switch */}
        <div className="secretary-toolbar">
          <div className="secretary-mode-switch">
            <button
              type="button"
              className={
                mode === "ask"
                  ? "mode-button active"
                  : "mode-button"
              }
              onClick={() => changeMode("ask")}
              disabled={loading}
            >
              <span className="mode-icon">✦</span>
              Ask Secretary
            </button>

            <button
              type="button"
              className={
                mode === "command"
                  ? "mode-button active"
                  : "mode-button"
              }
              onClick={() => changeMode("command")}
              disabled={loading}
            >
              <span className="mode-icon">⚡</span>
              Manage
            </button>
          </div>

          <div className="secretary-status">
            <span className="status-dot" />

            <span>
              {loading
                ? "Thinking..."
                : "AI Secretary is ready"}
            </span>
          </div>
        </div>

        {/* Main chat */}
        <main className="secretary-chat">

          {messages.length === 0 ? (
            <section className="secretary-welcome">
              <div className="welcome-avatar">
                ✦
              </div>

              <h2>
                {mode === "ask"
                  ? "How can I help you?"
                  : "What would you like me to manage?"}
              </h2>

              <p>
                {mode === "ask"
                  ? "Ask questions about your projects, responsibilities, tasks, budgets, deadlines, reviews, or available time."
                  : "Use natural language to create or manage tasks, meetings, reminders, and availability."}
              </p>
            </section>
          ) : (
            <div className="message-list">
              {messages.map((item) => (
                <div
                  key={item.id}
                  className={`chat-message ${item.role} ${
                    item.type || ""
                  }`}
                >
                  <div className="message-avatar">
                    {item.role === "user"
                      ? "You"
                      : "AI"}
                  </div>

                  <div className="message-content">
                    <div className="message-top">
                      <span className="message-label">
                        {item.role === "user"
                          ? "YOU"
                          : "AI SECRETARY"}
                      </span>
                    </div>

                    <div className="message-bubble">
                      <p>{item.text}</p>
                    </div>

                    {item.type === "command" &&
                      item.data?.created && (
                        <div className="created-summary">

                          {item.data.created.tasks >
                            0 && (
                            <span>
                              Tasks{" "}
                              {item.data.created.tasks}
                            </span>
                          )}

                          {item.data.created
                            .meetings > 0 && (
                            <span>
                              Meetings{" "}
                              {
                                item.data.created
                                  .meetings
                              }
                            </span>
                          )}

                          {item.data.created
                            .availability > 0 && (
                            <span>
                              Availability{" "}
                              {
                                item.data.created
                                  .availability
                              }
                            </span>
                          )}

                          {item.data.created
                            .reminders > 0 && (
                            <span>
                              Reminders{" "}
                              {
                                item.data.created
                                  .reminders
                              }
                            </span>
                          )}

                        </div>
                      )}
                  </div>
                </div>
              ))}

              {loading && (
                <div className="chat-message assistant">
                  <div className="message-avatar">
                    AI
                  </div>

                  <div className="message-content">
                    <div className="message-top">
                      <span className="message-label">
                        AI SECRETARY
                      </span>
                    </div>

                    <div className="message-bubble typing-bubble">
                      <div className="typing-indicator">
                        <span />
                        <span />
                        <span />
                      </div>
                    </div>
                  </div>
                </div>
              )}

              <div ref={chatEndRef} />
            </div>
          )}
        </main>

        {/* Example prompts */}
        <section className="secretary-examples">
          <div className="examples-header">
            <span>
              {mode === "ask"
                ? "SUGGESTED QUESTIONS"
                : "QUICK COMMANDS"}
            </span>
          </div>

          <div className="examples-list">
            {examples.map((example) => (
              <button
                type="button"
                key={example}
                onClick={() => {
                  setMessage(example);

                  setTimeout(() => {
                    textareaRef.current?.focus();
                  }, 50);
                }}
                disabled={loading}
              >
                {example}
              </button>
            ))}
          </div>
        </section>

        {/* Error */}
        {error && (
          <div className="secretary-error">
            <span>!</span>

            <p>{error}</p>

            <button
              type="button"
              onClick={() => setError("")}
            >
              ×
            </button>
          </div>
        )}

        {/* Composer */}
        <form
          className="secretary-composer"
          onSubmit={sendMessage}
        >
          <textarea
            ref={textareaRef}
            value={message}
            onChange={(event) =>
              setMessage(event.target.value)
            }
            onKeyDown={handleTextareaKeyDown}
            placeholder={
              mode === "ask"
                ? "Ask your Secretary anything..."
                : "Tell your Secretary what to manage..."
            }
            rows="1"
            disabled={loading}
          />

          <div className="composer-footer">
            <span className="composer-hint">
              Press Enter to send · Shift + Enter for
              new line
            </span>

            <button
              type="submit"
              className="send-button"
              disabled={
                loading || !message.trim()
              }
            >
              <span>
                {loading
                  ? "Thinking"
                  : mode === "ask"
                  ? "Ask"
                  : "Send"}
              </span>

              <span className="send-icon">
                ↑
              </span>
            </button>
          </div>
        </form>

      </div>
    </div>
  );
}

export default App;