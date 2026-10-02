/**
 * Prayash — Career Chat Widget
 * ================================
 * AI-powered career advisor for the workspace page.
 * Sends messages to the /api/career-chat endpoint with per-session memory.
 * 
 * Initialization:
 *   CareerChat.init({ resumeText: 'optional resume text for context' });
 */
(() => {
  'use strict';

  // ─── CONFIGURATION ───
  const API_ENDPOINT = '/api/career-chat';
  const SESSION_STORAGE_KEY = 'prayash-career-session';
  const TYPING_DELAY = 800;
  const GREETING_DELAY = 600;

  // ─── STATE ───
  let toggleBtn, panel, messagesContainer, inputField, sendBtn, minimizeBtn, statusText;
  let typingIndicator = null;
  let isOpen = false;
  let isProcessing = false;
  let sessionId = '';
  let resumeContext = '';
  let hasGreeted = false;

  // ─── DOM HELPERS ───
  const $ = (s, p = document) => p.querySelector(s);
  const scrollToBottom = () => {
    if (messagesContainer) {
      messagesContainer.scrollTop = messagesContainer.scrollHeight;
    }
  };

  // ─── CREATE TYPING INDICATOR ───
  const createTyping = () => {
    const el = document.createElement('div');
    el.className = 'chat-typing';
    el.innerHTML = '<div class="chat-message__avatar" aria-hidden="true">🤖</div><div class="chat-typing__wrap"><div class="chat-typing__dot"></div><div class="chat-typing__dot"></div><div class="chat-typing__dot"></div></div>';
    return el;
  };

  const showTyping = () => {
    hideTyping();
    typingIndicator = createTyping();
    messagesContainer.appendChild(typingIndicator);
    scrollToBottom();
  };

  const hideTyping = () => {
    if (typingIndicator && typingIndicator.parentNode) {
      typingIndicator.remove();
    }
    typingIndicator = null;
  };

  // ─── GET CSRF TOKEN ───
  const getCsrfToken = () => {
    const meta = document.querySelector('meta[name="csrf-token"]');
    return meta ? meta.getAttribute('content') : '';
  };

  // ─── ADD MESSAGE ───
  const addMessage = (text, isUser = false) => {
    if (!messagesContainer) return;

    hideTyping();

    const el = document.createElement('div');
    el.className = `chat-message ${isUser ? 'is-user' : 'is-assistant'}`;

    const avatar = document.createElement('div');
    avatar.className = 'chat-message__avatar';
    avatar.setAttribute('aria-hidden', 'true');
    avatar.textContent = isUser ? '👤' : '🤖';

    const bubble = document.createElement('div');
    bubble.className = 'chat-message__bubble';

    if (isUser) {
      // Use textContent for user messages to prevent XSS
      bubble.textContent = text;
    } else {
      // Only assistant messages get rich formatting from the backend
      let formatted = text
        .replace(/\n/g, '<br>')
        .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
        .replace(/^•\s(.+)$/gm, '<span style="display:block;padding-left:0.5rem;">• $1</span>');
      bubble.innerHTML = formatted;
    }
    el.appendChild(avatar);
    el.appendChild(bubble);
    messagesContainer.appendChild(el);
    scrollToBottom();
  };

  // ─── ADD ERROR MESSAGE ───
  const addError = (text) => {
    hideTyping();
    const el = document.createElement('div');
    el.className = 'chat-error';
    el.textContent = text;
    messagesContainer.appendChild(el);
    scrollToBottom();
  };

  // ─── UPDATE STATUS ───
  const setStatus = (text, isOnline = true) => {
    if (statusText) {
      statusText.textContent = text;
    }
    const dot = document.querySelector('.chat-status-dot');
    if (dot) {
      dot.style.background = isOnline ? '#22c55e' : '#ef4444';
    }
  };

  // ─── SEND MESSAGE TO API ───
  const sendToApi = async (message) => {
    try {
      const response = await fetch(API_ENDPOINT, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-CSRFToken': getCsrfToken(),
        },
        body: JSON.stringify({
          message: message,
          session_id: sessionId,
          resume_text: resumeContext,
        }),
      });

      let data;
      try {
        data = await response.json();
      } catch (parseErr) {
        throw new Error('Invalid response from server.');
      }

      if (!response.ok) {
        throw new Error(data.error || `Server error (${response.status})`);
      }

      // Check for application-level failure (HTTP 200 but success: false)
      if (data.success === false) {
        throw new Error(data.error || 'Request failed');
      }

      // Store session ID for conversation continuity
      if (data.session_id) {
        sessionId = data.session_id;
        try {
          localStorage.setItem(SESSION_STORAGE_KEY, sessionId);
        } catch (_) { /* ignore storage errors */ }
      }

      return data.answer || 'I\'m not sure how to answer that. Could you rephrase your question?';
    } catch (err) {
      // Return a friendly fallback message
      if (err.message.includes('429') || err.message.includes('Too many')) {
        return 'You\'re asking a lot of questions — which is great! 😊 Let me catch my breath for a moment. Please try again in a few seconds.';
      }
      if (err.message.includes('Failed to fetch') || err.message.includes('NetworkError')) {
        return 'I\'m having trouble connecting to the AI service. Please make sure Ollama is running, or try again later. In the meantime, here\'s a tip: focus on building skills that align with your target career path! 🚀';
      }
      return `I encountered an issue: ${err.message}. Could you try asking a different way?`;
    }
  };

  // ─── HANDLE USER INPUT ───
  const handleUserInput = async () => {
    if (!inputField) return;
    const text = inputField.value.trim();
    if (!text || isProcessing) return;

    inputField.value = '';
    isProcessing = true;
    sendBtn.disabled = true;

    // Add user message
    addMessage(text, true);

    // Show typing and get response
    showTyping();
    setStatus('Thinking...', true);

    const response = await sendToApi(text);

    hideTyping();
    addMessage(response);

    setStatus('Ready to help', true);
    isProcessing = false;
    sendBtn.disabled = false;
    inputField.focus();
  };

  // ─── HANDLE QUICK ACTION ───
  const handleQuickAction = async (question) => {
    if (isProcessing || !inputField) return;

    // Add user quick action as message
    addMessage(question, true);

    // Show typing
    showTyping();
    setStatus('Thinking...', true);
    isProcessing = true;
    sendBtn.disabled = true;

    const response = await sendToApi(question);

    hideTyping();
    addMessage(response);

    setStatus('Ready to help', true);
    isProcessing = false;
    sendBtn.disabled = false;
  };

  // ─── SEND GREETING ───
  const sendGreeting = () => {
    if (hasGreeted) return;
    hasGreeted = true;

    showTyping();
    setTimeout(() => {
      hideTyping();
      // The greeting HTML is already in the template, just scroll
      scrollToBottom();
    }, GREETING_DELAY);
  };

  // ─── TOGGLE PANEL ───
  const togglePanel = () => {
    isOpen = !isOpen;
    toggleBtn.classList.toggle('is-open', isOpen);
    panel.classList.toggle('is-visible', isOpen);

    if (isOpen) {
      scrollToBottom();
      if (!hasGreeted) {
        sendGreeting();
      }
      setTimeout(() => inputField?.focus(), 350);
    } else {
      // Mark as read
      const dot = toggleBtn.querySelector('.unread-dot');
      if (dot) dot.classList.remove('is-visible');
    }
  };

  // ─── MINIMIZE ───
  const minimizePanel = () => {
    isOpen = false;
    toggleBtn.classList.remove('is-open');
    panel.classList.remove('is-visible');
  };

  // ─── RESTORE SESSION ───
  const restoreSession = () => {
    try {
      const saved = localStorage.getItem(SESSION_STORAGE_KEY);
      if (saved) {
        sessionId = saved;
      }
    } catch (_) { /* ignore */ }
  };

  // ─── SETUP EVENT LISTENERS ───
  const setupListeners = () => {
    toggleBtn.addEventListener('click', togglePanel);
    minimizeBtn.addEventListener('click', minimizePanel);
    sendBtn.addEventListener('click', handleUserInput);

    inputField.addEventListener('keydown', (e) => {
      if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault();
        handleUserInput();
      }
    });

    // Quick action buttons (delegated)
    messagesContainer.addEventListener('click', (e) => {
      const quickBtn = e.target.closest('[data-chat-quick]');
      if (quickBtn) {
        const question = quickBtn.getAttribute('data-chat-quick');
        if (question) handleQuickAction(question);
      }
    });
  };

  // ─── EXPORT API ───
  const exposeApi = () => {
    window.CareerChat = {
      open: () => { if (!isOpen) togglePanel(); },
      close: () => { if (isOpen) minimizePanel(); },
      send: async (msg) => {
        if (inputField && !isProcessing) {
          inputField.value = msg;
          await handleUserInput();
        }
      },
      setResumeContext: (text) => { resumeContext = text; },
      getSessionId: () => sessionId,
    };
  };

  // ─── INIT ───
  const init = (options = {}) => {
    resumeContext = options.resumeText || '';

    // Cache DOM references
    toggleBtn = document.getElementById('career-chat-toggle');
    panel = document.getElementById('career-chat-panel');
    messagesContainer = document.getElementById('career-chat-messages');
    inputField = document.getElementById('career-chat-input');
    sendBtn = document.getElementById('career-chat-send');
    minimizeBtn = document.querySelector('[data-chat-minimize]');
    statusText = document.querySelector('[data-chat-status-text]');

    if (!toggleBtn || !panel || !messagesContainer) {
      console.warn('CareerChat: Required DOM elements not found.');
      return;
    }

    // Restore previous session
    restoreSession();

    // Setup event listeners
    setupListeners();

    // Expose public API
    exposeApi();

    console.log('Prayash Career Chat ready 💼');
  };

  // ─── AUTO-INIT ON DOM READY ───
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', () => init());
  } else {
    init();
  }

  // Expose init for manual calling
  window.CareerChat = window.CareerChat || { init };

})();
