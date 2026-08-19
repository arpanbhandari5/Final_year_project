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
  const CONTEXT_ENDPOINT = '/api/career-chat/context';
  const SESSION_STORAGE_KEY = 'prayash-career-session';
  const TYPING_DELAY = 800;
  const GREETING_DELAY = 600;
  const MAX_FILE_SIZE = 20 * 1024 * 1024; // 20 MB (matches server MAX_CONTENT_LENGTH)
  const ALLOWED_EXTS = ['pdf', 'docx', 'txt', 'md', 'csv', 'rtf', 'xlsx', 'png', 'jpg', 'jpeg'];
  const IMAGE_EXTS = ['png', 'jpg', 'jpeg'];

  // ─── STATE ───
  let toggleBtn, panel, messagesContainer, inputField, sendBtn, minimizeBtn, statusText;
  let attachBtn, fileInput, contextBar, contextName, contextMeta, contextRemove, contextIcon;
  let progressEl, progressBar;
  let typingIndicator = null;
  let isOpen = false;
  let isProcessing = false;
  let isUploading = false;
  let dragDepth = 0;
  let sessionId = '';
  let resumeContext = '';
  let attachFileName = '';
  let attachCharCount = 0;
  let attachSkillCount = 0;
  let attachFileSize = 0;
  let attachIsImage = false;
  let isAuthenticated = true;
  let hasGreeted = false;

  // ─── DOM HELPERS ───
  const $ = (s, p = document) => p.querySelector(s);
  const scrollToBottom = () => {
    if (messagesContainer) {
      messagesContainer.scrollTop = messagesContainer.scrollHeight;
    }
  };

  // ─── TOAST NOTIFICATIONS ───
  // Reuses the site-wide .toast styles from styles.css so upload success /
  // error and the guest login prompt look consistent with the rest of Prayash.
  const showToast = (message, type = 'info', duration = 4000) => {
    const container = document.querySelector('[data-toast-container]');
    if (!container) return;

    const el = document.createElement('div');
    el.className = `toast toast--${type}`;
    el.innerHTML =
      '<span class="toast__icon" aria-hidden="true"></span>' +
      '<span class="toast__msg"></span>' +
      '<button class="toast__close" aria-label="Dismiss">&times;</button>';

    el.querySelector('.toast__msg').textContent = message;
    const icons = { info: 'ℹ️', success: '✅', error: '❌', warning: '⚠️' };
    el.querySelector('.toast__icon').textContent = icons[type] || '';

    const dismiss = () => {
      el.classList.remove('toast--visible');
      setTimeout(() => el.remove(), 300);
    };
    el.querySelector('.toast__close').addEventListener('click', dismiss);

    container.appendChild(el);
    requestAnimationFrame(() => el.classList.add('toast--visible'));
    setTimeout(dismiss, duration);
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
        return 'I couldn\'t reach the server just now — it may be restarting. Please try again in a moment. Tip: focus on building skills that align with your target career path! 🚀';
      }
      return `I encountered an issue: ${err.message}. Could you try asking a different way?`;
    }
  };

  // ─── ATTACH A DOCUMENT FOR CONTEXT ───
  // Simple text chat is available to everyone; uploading a file for personalised
  // guidance is a signed-in feature. Guests who try to attach get a toast prompt.
  const requireAuth = () => {
    if (!isAuthenticated) {
      showToast('Login to access file attachments', 'warning', 3500);
      return false;
    }
    return true;
  };

  const openFilePicker = () => {
    if (isUploading || !fileInput) return;
    if (!requireAuth()) return;
    fileInput.value = '';
    fileInput.click();
  };

  const formatBytes = (bytes) => {
    if (!bytes) return '';
    if (bytes < 1024) return bytes + ' B';
    if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB';
    return (bytes / (1024 * 1024)).toFixed(1) + ' MB';
  };

  // Pick a type-specific icon for the attached-file chip.
  const fileTypeMeta = (name) => {
    const ext = (name.split('.').pop() || '').toLowerCase();
    if (IMAGE_EXTS.indexOf(ext) !== -1) return { icon: '🖼️', label: 'Image' };
    if (ext === 'pdf') return { icon: '📄', label: 'PDF' };
    if (ext === 'docx' || ext === 'rtf') return { icon: '📝', label: 'Document' };
    if (ext === 'txt' || ext === 'md') return { icon: '📃', label: 'Text' };
    if (ext === 'csv' || ext === 'xlsx') return { icon: '📊', label: 'Spreadsheet' };
    return { icon: '📎', label: 'File' };
  };

  const updateContextBar = () => {
    if (!contextBar) return;
    if (attachFileName) {
      contextName.textContent = attachFileName;
      const meta = fileTypeMeta(attachFileName);
      if (contextIcon) contextIcon.textContent = meta.icon;
      const metaParts = [];
      if (attachIsImage) {
        metaParts.push('Image attached');
      } else {
        if (attachCharCount) metaParts.push(attachCharCount.toLocaleString() + ' chars');
        if (attachSkillCount) metaParts.push(attachSkillCount + ' skills found');
      }
      if (attachFileSize) metaParts.push(formatBytes(attachFileSize));
      contextMeta.textContent = metaParts.join(' · ');
      contextBar.hidden = false;
    } else {
      contextBar.hidden = true;
    }
  };

  const clearContext = (notify = true) => {
    resumeContext = '';
    attachFileName = '';
    attachCharCount = 0;
    attachSkillCount = 0;
    attachFileSize = 0;
    attachIsImage = false;
    if (fileInput) fileInput.value = '';
    updateContextBar();
    if (notify && messagesContainer) {
      addMessage('Removed the attached document. I\u2019ll answer from general career knowledge now.', false);
    }
  };

  const showProgress = (pct) => {
    if (!progressEl || !progressBar) return;
    progressEl.hidden = false;
    progressBar.style.width = Math.min(100, Math.max(0, pct)) + '%';
  };

  const hideProgress = () => {
    if (!progressEl || !progressBar) return;
    progressBar.style.width = '100%';
    setTimeout(() => { progressEl.hidden = true; }, 350);
  };

  const uploadFile = (file) => new Promise((resolve, reject) => {
    const formData = new FormData();
    formData.append('file', file);

    const xhr = new XMLHttpRequest();
    showProgress(0);
    xhr.open('POST', CONTEXT_ENDPOINT);
    xhr.setRequestHeader('X-CSRFToken', getCsrfToken());
    xhr.upload.onprogress = (e) => {
      if (e.lengthComputable) showProgress((e.loaded / e.total) * 100);
    };
    xhr.onload = () => {
      let data;
      try {
        data = JSON.parse(xhr.responseText);
      } catch (_) {
        reject(new Error('Invalid response from server.'));
        return;
      }
      if (xhr.status >= 400) {
        reject(new Error(data.error || `Server error (${xhr.status})`));
      } else if (data.success === false) {
        reject(new Error(data.error || 'Could not read the file.'));
      } else {
        resolve(data);
      }
    };
    xhr.onerror = () => reject(new Error('Network error while uploading.'));
    xhr.send(formData);
  });

  const processFile = async (file) => {
    if (!file) return;
    // Single choke point for the picker, drag-and-drop and the file input.
    if (!requireAuth()) return;

    // Validate extension
    const ext = (file.name.split('.').pop() || '').toLowerCase();
    if (ALLOWED_EXTS.indexOf(ext) === -1) {
      addError('Unsupported file type. Please attach a PDF, DOCX, TXT, MD, CSV, RTF, XLSX, or an image (PNG/JPG/JPEG).');
      return;
    }

    // Validate size
    if (file.size > MAX_FILE_SIZE) {
      addError('File is too large (max 20 MB). Please choose a smaller file.');
      return;
    }

    if (isUploading) return;
    isUploading = true;
    attachBtn.disabled = true;
    setStatus('Uploading...', true);
    showTyping();

    try {
      const data = await uploadFile(file);

      resumeContext = data.text || '';
      attachFileName = data.filename || file.name;
      attachCharCount = data.char_count || resumeContext.length;
      attachSkillCount = data.skill_count || 0;
      attachFileSize = file.size;
      attachIsImage = data.is_image === true || IMAGE_EXTS.indexOf(ext) !== -1;
      updateContextBar();
      showToast(`📎 ${attachFileName} (${formatBytes(file.size)}) loaded.`, 'success', 3000);

      const skillLine = !attachIsImage && data.skill_count
        ? ` I spotted ${data.skill_count} skill${data.skill_count === 1 ? '' : 's'}: ${(data.skills || []).slice(0, 8).join(', ')}.`
        : '';
      const loadedLine = attachIsImage
        ? `📎 I've attached ${attachFileName}. I can't read text from images, but I'm happy to give general career advice.`
        : `📎 I've loaded ${attachFileName} (${attachCharCount.toLocaleString()} characters).${skillLine} Ask me anything about it \u2014 I'll base my advice on your document.`;
      addMessage(loadedLine, false);
    } catch (err) {
      addError(err.message || 'Could not read that file. Try a PDF, DOCX, TXT, or XLSX document.');
      showToast(err.message || 'Upload failed. Please try a different file.', 'error', 6000);
    } finally {
      hideTyping();
      hideProgress();
      isUploading = false;
      attachBtn.disabled = false;
      if (fileInput) fileInput.value = '';
      setStatus('Ready to help', true);
    }
  };

  const handleFileSelect = (event) => {
    const file = event.target.files && event.target.files[0];
    if (file) processFile(file);
  };

  const handleRemoveContext = () => {
    clearContext(true);
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
    if (isProcessing || isUploading || !inputField) return;

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
    // Everyone can chat (guests get simple text chat); only attachments require
    // a signed-in account, so there is no gate here — see requireAuth() below.
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

    // Attach a document for personalised guidance
    if (attachBtn) attachBtn.addEventListener('click', openFilePicker);
    if (fileInput) fileInput.addEventListener('change', handleFileSelect);
    if (contextRemove) contextRemove.addEventListener('click', handleRemoveContext);

    // Drag-and-drop a file onto the chat panel
    if (panel) {
      panel.addEventListener('dragenter', (e) => {
        e.preventDefault();
        dragDepth += 1;
        panel.classList.add('is-dragging');
      });
      panel.addEventListener('dragover', (e) => {
        e.preventDefault();
      });
      panel.addEventListener('dragleave', (e) => {
        e.preventDefault();
        dragDepth = Math.max(0, dragDepth - 1);
        if (dragDepth === 0) panel.classList.remove('is-dragging');
      });
      panel.addEventListener('drop', (e) => {
        e.preventDefault();
        dragDepth = 0;
        panel.classList.remove('is-dragging');
        const file = e.dataTransfer && e.dataTransfer.files && e.dataTransfer.files[0];
        if (file) processFile(file);
      });
    }

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
      setResumeContext: (text) => { resumeContext = text || ''; },
      attach: () => openFilePicker(),
      clearContext: () => clearContext(false),
      getSessionId: () => sessionId,
      hasContext: () => Boolean(resumeContext),
    };
  };

  // ─── INIT ───
  const init = (options = {}) => {
    resumeContext = options.resumeText || '';

    // Whether the current user is logged in (set by the template on the widget
    // root). Guests can use simple text chat; file attachments are login-only.
    const rootEl = document.getElementById('career-chat');
    isAuthenticated = rootEl ? rootEl.getAttribute('data-authenticated') !== 'false' : true;

    // Cache DOM references
    toggleBtn = document.getElementById('career-chat-toggle');
    panel = document.getElementById('career-chat-panel');
    messagesContainer = document.getElementById('career-chat-messages');
    inputField = document.getElementById('career-chat-input');
    sendBtn = document.getElementById('career-chat-send');
    minimizeBtn = document.querySelector('[data-chat-minimize]');
    statusText = document.querySelector('[data-chat-status-text]');
    attachBtn = document.getElementById('career-chat-attach');
    fileInput = document.getElementById('career-chat-file');
    contextBar = document.getElementById('career-chat-context');
    contextName = document.querySelector('[data-chat-context-name]');
    contextMeta = document.querySelector('[data-chat-context-meta]');
    contextRemove = document.querySelector('[data-chat-context-remove]');
    contextIcon = document.querySelector('.career-chat__context-icon');
    progressEl = document.getElementById('career-chat-progress');
    progressBar = document.getElementById('career-chat-progress-bar');

    if (!toggleBtn || !panel || !messagesContainer) {
      console.warn('CareerChat: Required DOM elements not found.');
      return;
    }

    // Let guests know they can chat but not attach files yet.
    if (!isAuthenticated) {
      setStatus('Guest — sign in for file uploads', true);
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
