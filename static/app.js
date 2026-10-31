/**
 * Customer Support Assistant Client Application
 * Safe, accessible, and responsive chat logic
 */

(function () {
  "use strict";

  // Elements
  const chatMessages = document.getElementById("chatMessages");
  const chatForm = document.getElementById("chatForm");
  const messageInput = document.getElementById("messageInput");
  const sendBtn = document.getElementById("sendBtn");
  const typingIndicator = document.getElementById("typingIndicator");
  const clearChatBtn = document.getElementById("clearChatBtn");
  const toggleDevMode = document.getElementById("toggleDevMode");
  const statusDot = document.getElementById("statusDot");
  const statusText = document.getElementById("statusText");
  const chatErrorBanner = document.getElementById("chatErrorBanner");
  const errorMsgText = document.getElementById("errorMsgText");
  const retryBtn = document.getElementById("retryBtn");
  const welcomeTimestamp = document.getElementById("welcomeTimestamp");

  // State
  let isSubmitting = false;
  let devModeActive = false;
  let lastFailedMessage = "";
  const apiBase = (window.APP_CONFIG && window.APP_CONFIG.API_BASE_URL) || "";

  // Set initial welcome timestamp
  if (welcomeTimestamp) {
    welcomeTimestamp.textContent = formatTimestamp(new Date());
  }

  // Check backend health on load
  checkBackendHealth();

  // Setup prompt pills click handlers
  initPromptPills();

  // Handle textarea auto-resize
  messageInput.addEventListener("input", function () {
    this.style.height = "auto";
    this.style.height = Math.min(this.scrollHeight, 140) + "px";
  });

  // Handle Enter to send, Shift+Enter for newline
  messageInput.addEventListener("keydown", function (e) {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      if (!isSubmitting) {
        chatForm.requestSubmit();
      }
    }
  });

  // Handle Form Submission
  chatForm.addEventListener("submit", async function (e) {
    e.preventDefault();
    const text = messageInput.value.trim();
    if (!text || isSubmitting) return;

    await sendMessage(text);
  });

  // Retry failed message
  retryBtn.addEventListener("click", async function () {
    if (lastFailedMessage && !isSubmitting) {
      hideError();
      await sendMessage(lastFailedMessage);
    }
  });

  // Clear chat
  clearChatBtn.addEventListener("click", function () {
    if (confirm("Clear this conversation and start fresh?")) {
      resetChat();
    }
  });

  // Toggle Dev Diagnostics
  toggleDevMode.addEventListener("click", function () {
    devModeActive = !devModeActive;
    this.setAttribute("aria-pressed", devModeActive ? "true" : "false");
    this.classList.toggle("active", devModeActive);

    // Toggle visibility of existing dev diagnostic sections in DOM
    const devPanels = document.querySelectorAll(".dev-diagnostics");
    devPanels.forEach(panel => {
      panel.style.display = devModeActive ? "block" : "none";
    });
  });

  /**
   * Send a message to the backend
   */
  async function sendMessage(text) {
    // Hide previous error banner
    hideError();

    // Append user message bubble
    appendMessage("user", text);

    // Clear input & reset height
    messageInput.value = "";
    messageInput.style.height = "auto";
    setLoadingState(true);
    lastFailedMessage = text;

    try {
      const response = await fetch(`${apiBase}/chat`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({ message: text }),
      });

      if (!response.ok) {
        let errorDetail = `Server returned status ${response.status}`;
        try {
          const errData = await response.json();
          if (errData && errData.detail) {
            errorDetail = errData.detail;
          }
        } catch (_) {
          // ignore json parse error on non-json error responses
        }
        throw new Error(errorDetail);
      }

      const data = await response.json();
      lastFailedMessage = "";

      // Append bot response
      appendBotResponse(data);
    } catch (err) {
      console.error("Chat error:", err);
      showError(err.message || "Failed to contact support assistant. Please check connection.");
    } finally {
      setLoadingState(false);
      messageInput.focus();
    }
  }

  /**
   * Append a simple message to the chat
   */
  function appendMessage(sender, text) {
    const group = document.createElement("div");
    group.className = `message-group ${sender}-group`;

    const avatar = document.createElement("div");
    avatar.className = `avatar ${sender}-avatar`;
    avatar.setAttribute("aria-hidden", "true");
    avatar.textContent = sender === "user" ? "You" : "Bot";

    const content = document.createElement("div");
    content.className = "message-content";

    const label = document.createElement("div");
    label.className = "sender-label";
    label.textContent = sender === "user" ? "You" : "Support Assistant";

    const bubble = document.createElement("div");
    bubble.className = `bubble ${sender}-bubble`;
    // User messages are rendered strictly as plain text (no HTML or Markdown parsing)
    bubble.textContent = text;

    const time = document.createElement("span");
    time.className = "timestamp";
    time.textContent = formatTimestamp(new Date());

    content.appendChild(label);
    content.appendChild(bubble);
    content.appendChild(time);

    group.appendChild(avatar);
    group.appendChild(content);

    chatMessages.appendChild(group);
    scrollToBottom();
  }

  /**
   * Escape HTML entities to prevent script execution in fallback parser
   */
  function escapeHtml(str) {
    if (!str || typeof str !== "string") return "";
    return str
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#039;");
  }

  /**
   * Format inline markdown patterns on already-escaped text
   */
  function formatInlineMarkdown(str) {
    return str
      // Bold: **text** or __text__
      .replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>")
      .replace(/__(.+?)__/g, "<strong>$1</strong>")
      // Italic: *text* or _text_
      .replace(/(?<!\*)\*(?!\*)(.+?)(?<!\*)\*(?!\*)/g, "<em>$1</em>")
      // Inline code: `code`
      .replace(/`([^`]+)`/g, "<code>$1</code>");
  }

  /**
   * Safe fallback Markdown renderer (escapes all HTML first, then formats lists and bold text)
   */
  function renderFallbackMarkdown(text) {
    if (!text || typeof text !== "string") return "";

    const escaped = escapeHtml(text);
    const lines = escaped.split(/\r?\n/);
    let html = "";
    let inOl = false;
    let inUl = false;

    function closeLists() {
      if (inOl) {
        html += "</ol>";
        inOl = false;
      }
      if (inUl) {
        html += "</ul>";
        inUl = false;
      }
    }

    for (let i = 0; i < lines.length; i++) {
      const line = lines[i].trim();

      if (!line) {
        closeLists();
        continue;
      }

      // Check for numbered list item: "1. ", "2. ", etc.
      const olMatch = line.match(/^(\d+)\.\s+(.*)$/);
      if (olMatch) {
        if (inUl) {
          html += "</ul>";
          inUl = false;
        }
        if (!inOl) {
          html += "<ol>";
          inOl = true;
        }
        const itemContent = formatInlineMarkdown(olMatch[2]);
        html += `<li>${itemContent}</li>`;
        continue;
      }

      // Check for unordered list item: "- " or "* "
      const ulMatch = line.match(/^[-*]\s+(.*)$/);
      if (ulMatch) {
        if (inOl) {
          html += "</ol>";
          inOl = false;
        }
        if (!inUl) {
          html += "<ul>";
          inUl = true;
        }
        const itemContent = formatInlineMarkdown(ulMatch[1]);
        html += `<li>${itemContent}</li>`;
        continue;
      }

      // Normal paragraph line
      closeLists();
      const pContent = formatInlineMarkdown(line);
      html += `<p>${pContent}</p>`;
    }

    closeLists();
    return html;
  }

  /**
   * Resolve DOMPurify instance across browser globals and window contexts
   */
  function getDOMPurify() {
    const p = (typeof window !== "undefined" && window.DOMPurify) || (typeof DOMPurify !== "undefined" ? DOMPurify : null);
    if (!p) return null;
    if (typeof p.sanitize === "function") return p;
    if (typeof p === "function") {
      try {
        const targetWindow = (typeof window !== "undefined" && window.document) ? window : null;
        if (targetWindow) {
          const inst = p(targetWindow);
          if (inst && typeof inst.sanitize === "function") return inst;
        }
      } catch (_) {}
    }
    return null;
  }

  /**
   * Resolve marked library instance across browser globals and window contexts
   */
  function getMarked() {
    return (typeof window !== "undefined" && window.marked) || (typeof marked !== "undefined" ? marked : null);
  }

  /**
   * Safely render bot response Markdown to sanitized HTML
   * Uses marked.js + DOMPurify if available, with a safe fallback parser.
   */
  function renderMarkdownSafe(text) {
    if (!text || typeof text !== "string") {
      return "";
    }

    const markedObj = getMarked();
    const purifyObj = getDOMPurify();

    // 1. Primary path: marked.js + DOMPurify
    if (markedObj && typeof markedObj.parse === "function" && purifyObj && typeof purifyObj.sanitize === "function") {
      try {
        const rawHtml = markedObj.parse(text, {
          gfm: true,
          breaks: true,
        });

        // Strictly sanitize: allow safe formatting tags, forbid scripts, iframes, and handlers
        return purifyObj.sanitize(rawHtml, {
          ALLOWED_TAGS: [
            "p", "br", "strong", "b", "em", "i", "u", "s", "del",
            "ol", "ul", "li", "code", "pre", "blockquote", "h1", "h2", "h3", "h4", "h5", "h6",
            "span", "hr", "a"
          ],
          ALLOWED_ATTR: ["href", "title", "target", "rel", "class"],
        });
      } catch (err) {
        console.warn("Markdown parsing error, using fallback:", err);
      }
    }

    // 2. Safe fallback parser (HTML-escaped first)
    return renderFallbackMarkdown(text);
  }

  // Expose on window for testing and diagnostics
  window.renderMarkdownSafe = renderMarkdownSafe;
  window.renderFallbackMarkdown = renderFallbackMarkdown;
  window.escapeHtml = escapeHtml;

  /**
   * Append a structured bot response with escalation & dev diagnostics
   */
  function appendBotResponse(data) {
    const group = document.createElement("div");
    group.className = "message-group bot-group";

    const avatar = document.createElement("div");
    avatar.className = "avatar bot-avatar";
    avatar.setAttribute("aria-hidden", "true");
    avatar.innerHTML = `
      <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
        <rect x="4" y="8" width="16" height="12" rx="2"></rect>
      </svg>
    `;

    const content = document.createElement("div");
    content.className = "message-content";

    const label = document.createElement("div");
    label.className = "sender-label";
    label.textContent = "Support Assistant";

    // Main answer bubble with sanitized Markdown formatting
    const bubble = document.createElement("div");
    bubble.className = "bubble bot-bubble";
    const rawReply = data.reply || "No response provided.";
    bubble.innerHTML = renderMarkdownSafe(rawReply);

    content.appendChild(label);
    content.appendChild(bubble);

    // If should_escalate is true, show calm, distinct support notice
    if (data.should_escalate) {
      const escCard = document.createElement("div");
      escCard.className = "escalation-notice";
      escCard.setAttribute("role", "note");

      const escHeader = document.createElement("div");
      escHeader.className = "escalation-header";
      escHeader.innerHTML = `
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <circle cx="12" cy="12" r="10"></circle>
          <line x1="12" y1="8" x2="12" y2="12"></line>
          <line x1="12" y1="16" x2="12.01" y2="16"></line>
        </svg>
        <span>Human Follow-Up May Be Needed</span>
      `;

      const escText = document.createElement("p");
      escText.textContent = "This may need help from the support team. I can't connect you to an agent or create a ticket here.";

      escCard.appendChild(escHeader);
      escCard.appendChild(escText);

      // If an escalation reason is provided, display it calmly
      if (data.escalation_reason) {
        const reasonBadge = document.createElement("span");
        reasonBadge.className = "escalation-reason-tag";
        reasonBadge.textContent = `Reason: ${data.escalation_reason.replace(/_/g, " ")}`;
        escCard.appendChild(reasonBadge);
      }

      content.appendChild(escCard);
    }

    // Developer Diagnostics Panel (Hidden from normal users)
    const devPanel = createDevPanel(data);
    devPanel.style.display = devModeActive ? "block" : "none";
    content.appendChild(devPanel);

    // Timestamp
    const time = document.createElement("span");
    time.className = "timestamp";
    time.textContent = formatTimestamp(new Date());
    content.appendChild(time);

    group.appendChild(avatar);
    group.appendChild(content);

    chatMessages.appendChild(group);
    scrollToBottom();
  }

  /**
   * Build the Developer-only diagnostics accordion
   */
  function createDevPanel(data) {
    const panel = document.createElement("div");
    panel.className = "dev-diagnostics";

    const details = document.createElement("details");
    const summary = document.createElement("summary");
    summary.className = "dev-summary";

    const titleSpan = document.createElement("span");
    titleSpan.textContent = "Debug Diagnostics";

    const intentBadge = document.createElement("span");
    intentBadge.className = "intent-badge";
    intentBadge.textContent = data.intent || "other";

    summary.appendChild(titleSpan);
    summary.appendChild(intentBadge);
    details.appendChild(summary);

    const devContent = document.createElement("div");
    devContent.className = "dev-details";

    // Escalation status
    const escLine = document.createElement("div");
    escLine.innerHTML = `<strong>Escalation:</strong> ${data.should_escalate ? "True" : "False"} ${data.escalation_reason ? `(${data.escalation_reason})` : ""}`;
    devContent.appendChild(escLine);

    // Retrieved historical cases
    if (data.retrieved_cases && data.retrieved_cases.length > 0) {
      const casesTitle = document.createElement("div");
      casesTitle.innerHTML = `<strong>Retrieved Historical Cases (${data.retrieved_cases.length}):</strong>`;
      devContent.appendChild(casesTitle);

      const casesList = document.createElement("div");
      casesList.className = "retrieved-cases-list";

      data.retrieved_cases.forEach((c, idx) => {
        const item = document.createElement("div");
        item.className = "case-item";

        const meta = document.createElement("div");
        meta.className = "case-meta";
        meta.textContent = `Case #${idx + 1} • Similarity: ${(c.similarity || 0).toFixed(3)}`;

        const pastCust = document.createElement("div");
        pastCust.textContent = `Customer: ${c.customer_text || "N/A"}`;

        const pastReply = document.createElement("div");
        pastReply.style.color = "#475569";
        pastReply.textContent = `Amazon Reply: ${c.amazon_text || "N/A"}`;

        item.appendChild(meta);
        item.appendChild(pastCust);
        item.appendChild(pastReply);
        casesList.appendChild(item);
      });

      devContent.appendChild(casesList);
    } else {
      const noCases = document.createElement("div");
      noCases.textContent = "No historical cases retrieved.";
      devContent.appendChild(noCases);
    }

    details.appendChild(devContent);
    panel.appendChild(details);
    return panel;
  }

  /**
   * Reset conversation to welcome message
   */
  function resetChat() {
    chatMessages.innerHTML = `
      <div class="message-group bot-group" id="welcomeMessageGroup">
        <div class="avatar bot-avatar" aria-hidden="true">
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <rect x="4" y="8" width="16" height="12" rx="2"></rect>
          </svg>
        </div>
        <div class="message-content">
          <div class="sender-label">Support Assistant</div>
          <div class="bubble bot-bubble">
            <p>Hello! I can help guide you through Amazon customer service steps, return processes, delivery inquiries, and payment questions.</p>
            <div class="suggestions-section">
              <span class="suggestions-label">Try asking:</span>
              <div class="suggestion-pills">
                <button type="button" class="prompt-pill" data-prompt="How can I check my order status?">
                  How can I check my order status?
                </button>
                <button type="button" class="prompt-pill" data-prompt="Where can I find my tracking information?">
                  Where can I find my tracking information?
                </button>
                <button type="button" class="prompt-pill" data-prompt="What should I do if my order is delayed?">
                  What should I do if my order is delayed?
                </button>
              </div>
            </div>
          </div>
          <span class="timestamp">${formatTimestamp(new Date())}</span>
        </div>
      </div>
    `;
    hideError();
    initPromptPills();
    messageInput.focus();
  }

  /**
   * Initialize clickable prompt pills
   */
  function initPromptPills() {
    const pills = document.querySelectorAll(".prompt-pill");
    pills.forEach(pill => {
      pill.onclick = function () {
        const prompt = this.getAttribute("data-prompt");
        if (prompt && !isSubmitting) {
          sendMessage(prompt);
        }
      };
    });
  }

  /**
   * Toggle loading UI state
   */
  function setLoadingState(loading) {
    isSubmitting = loading;
    sendBtn.disabled = loading;
    messageInput.disabled = loading;
    typingIndicator.style.display = loading ? "flex" : "none";
    if (loading) {
      scrollToBottom();
    }
  }

  /**
   * Show error banner
   */
  function showError(msg) {
    errorMsgText.textContent = msg;
    chatErrorBanner.style.display = "flex";
    scrollToBottom();
  }

  /**
   * Hide error banner
   */
  function hideError() {
    chatErrorBanner.style.display = "none";
  }

  /**
   * Check backend health and update status dot
   */
  async function checkBackendHealth() {
    try {
      const res = await fetch(`${apiBase}/health`);
      if (res.ok) {
        const data = await res.json();
        if (data.status === "ok") {
          statusDot.className = "status-dot online";
          statusText.textContent = `Online (${data.provider})`;
        } else {
          statusDot.className = "status-dot";
          statusText.textContent = `Degraded: ${data.message || "Needs API Key"}`;
        }
      } else {
        throw new Error();
      }
    } catch (_) {
      statusDot.className = "status-dot offline";
      statusText.textContent = "Backend offline";
    }
  }

  /**
   * Format timestamp HH:MM AM/PM
   */
  function formatTimestamp(date) {
    return date.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
  }

  /**
   * Scroll chat area smoothly to bottom
   */
  function scrollToBottom() {
    const container = document.querySelector(".chat-container");
    if (container) {
      setTimeout(() => {
        container.scrollTop = container.scrollHeight;
      }, 50);
    }
  }
})();

