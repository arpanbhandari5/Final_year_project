/**
 * Prayash — Career Assistant (ChatGPT-style page)
 * ===============================================
 * Drives the full-page chat at /chatbot:
 *   - Conversation sidebar (search, create, rename, delete, clear)
 *   - Token streaming over SSE (POST /api/chat/conversations/<id>/stream)
 *   - Message edit / regenerate / like-dislike feedback
 *   - File attachments (POST /api/chat/context) fed back as file_ids
 *   - Career tools (POST /api/chat/tools/<tool>)
 *   - Conversation export (TXT / DOCX / PDF)
 *
 * Security notes:
 *   - All server text is rendered through escapeHtml() first, then a small
 *     safe subset of markdown is applied — no raw innerHTML with user text.
 *   - Every state-changing request carries the CSRF token header.
 */
(() => {
  'use strict';

  // ─── Config ─────────────────────────────────────────────────────
  const MAX_FILE_SIZE = 20 * 1024 * 1024; // 20 MB (matches server)
  const ALLOWED_EXTS = ['pdf', 'docx', 'txt', 'csv', 'xlsx', 'png', 'jpg', 'jpeg'];
  const IMAGE_EXTS = ['png', 'jpg', 'jpeg'];

  // ─── State ──────────────────────────────────────────────────────
  let conversations = [];
  let currentId = null;
  let currentMessages = [];
  let attachedFiles = [];        // {id, filename, is_image, raw_text, char_count, skill_count}
  let streamAbort = null;        // AbortController for in-flight stream
  let isStreaming = false;
  let isSending = false;

  // ─── DOM refs ───────────────────────────────────────────────────
  let app, listEl, listEmptyEl, searchEl, titleEl, messagesEl,
      emptyEl, inputEl, sendBtn, stopBtn, attachBtn, fileInput,
      contextBar, contextName, contextRemove, toolsToggle, toolsMenu,
      exportToggle, exportMenu, sidebarToggle, sidebarBackdrop;

  // ─── Helpers ────────────────────────────────────────────────────
  const $ = (s, p = document) => p.querySelector(s);
  const $$ = (s, p = document) => Array.from(p.querySelectorAll(s));

  const csrfToken = () => {
    const meta = document.querySelector('meta[name="csrf-token"]');
    return meta ? meta.getAttribute('content') : '';
  };

  const toast = (message, type = 'info', duration = 4000) => {
    const container = document.querySelector('[data-toast-container]');
    if (!container) return;
    const el = document.createElement('div');
    el.className = `toast toast--${type}`;
    el.innerHTML =
      '<span class="toast__icon" aria-hidden="true"></span>' +
      '<span class="toast__msg"></span>' +
      '<button class="toast__close" aria-label="Dismiss">&times;</button>';
    const icons = { info: 'ℹ️', success: '✅', error: '❌', warning: '⚠️' };
    el.querySelector('.toast__icon').textContent = icons[type] || '';
    el.querySelector('.toast__msg').textContent = message;
    const dismiss = () => {
      el.classList.remove('toast--visible');
      setTimeout(() => el.remove(), 300);
    };
    el.querySelector('.toast__close').addEventListener('click', dismiss);
    container.appendChild(el);
    requestAnimationFrame(() => el.classList.add('toast--visible'));
    setTimeout(dismiss, duration);
  };

  const escapeHtml = (str) => {
    const div = document.createElement('div');
    div.appendChild(document.createTextNode(str == null ? '' : String(str)));
    return div.innerHTML;
  };

  /**
   * Minimal, XSS-safe markdown renderer.
   * The input is HTML-escaped FIRST, then a small whitelist of patterns is
   * applied (headings, bold, italic, inline code, code blocks, lists, links).
   */
  const markdown = (src) => {
    let h = escapeHtml(src);
    // Code blocks (before inline transforms so backticks inside stay safe)
    h = h.replace(/```([\s\S]*?)```/g, (m, code) => '<pre><code>' + code + '</code></pre>');
    // Headings
    h = h.replace(/^#####? (.*)$/gm, '<h4>$1</h4>');
    h = h.replace(/^#### (.*)$/gm, '<h4>$1</h4>');
    h = h.replace(/^### (.*)$/gm, '<h3>$1</h3>');
    h = h.replace(/^## (.*)$/gm, '<h3>$1</h3>');
    h = h.replace(/^# (.*)$/gm, '<h2>$1</h2>');
    // Bold
    h = h.replace(/\*\*([^*\n]+)\*\*/g, '<strong>$1</strong>');
    // Italic (avoid clashing with list markers)
    h = h.replace(/(^|[\s(])\*([^*\n]+)\*(?=[\s).,!?]|$)/g, '$1<em>$2</em>');
    // Inline code
    h = h.replace(/`([^`\n]+)`/g, '<code>$1</code>');
    // Links — only http(s) URLs are allowed
    h = h.replace(/\[([^\]]+)\]\((https?:\/\/[^\s)]+)\)/g,
      '<a href="$2" target="_blank" rel="noopener noreferrer">$1</a>');
    // Lists
    h = h.replace(/^\s*[-*]\s+(.*)$/gm, '<li>$1</li>');
    h = h.replace(/^\s*\d+[.)]\s+(.*)$/gm, '<li>$1</li>');
    h = h.replace(/((?:<li>.*<\/li>\n?)+)/g, '<ul>$1</ul>');
    // Blockquotes (already escaped &gt;)
    h = h.replace(/^&gt;\s?(.*)$/gm, '<blockquote>$1</blockquote>');
    // Paragraphs from double newlines
    h = h.split(/\n{2,}/).map((p) => {
      p = p.trim();
      if (!p) return '';
      if (/^<(h\d|ul|ol|pre|blockquote)/.test(p)) return p;
      return '<p>' + p.replace(/\n/g, '<br>') + '</p>';
    }).join('');
    return h;
  };

  const timeAgo = (iso) => {
    if (!iso) return '';
    const t = new Date(iso.replace(' ', 'T') + (iso.includes('T') ? '' : 'Z'));
    if (isNaN(t)) return '';
    const s = (Date.now() - t.getTime()) / 1000;
    if (s < 60) return 'now';
    if (s < 3600) return Math.floor(s / 60) + 'm';
    if (s < 86400) return Math.floor(s / 3600) + 'h';
    return Math.floor(s / 86400) + 'd';
  };

  // ─── API ────────────────────────────────────────────────────────
  const api = async (url, opts = {}) => {
    const headers = Object.assign({ 'X-CSRFToken': csrfToken() }, opts.headers || {});
    if (opts.json !== undefined) {
      headers['Content-Type'] = 'application/json';
      opts.body = JSON.stringify(opts.json);
      delete opts.json;
    }
    const res = await fetch(url, Object.assign({ headers }, opts));
    let data;
    try { data = await res.json(); }
    catch (_) { data = {}; }
    if (!res.ok || data.success === false) {
      throw new Error(data.error || `Server error (${res.status})`);
    }
    return data;
  };

  // ─── Sidebar: conversations ─────────────────────────────────────
  const loadConversations = async (q = '') => {
    try {
      const data = await api('/api/chat/conversations' + (q ? `?q=${encodeURIComponent(q)}` : ''));
      conversations = data.conversations || [];
    } catch (err) {
      conversations = [];
    }
    renderConversationList();
  };

  const renderConversationList = () => {
    listEl.innerHTML = '';
    if (listEmptyEl.parentNode !== listEl) listEl.appendChild(listEmptyEl);
    if (!conversations.length) {
      listEmptyEl.style.display = '';
      return;
    }
    listEmptyEl.style.display = 'none';
    conversations.forEach((conv) => {
      const btn = document.createElement('button');
      btn.type = 'button';
      btn.className = 'chatbot-conv' + (conv.id === currentId ? ' is-active' : '');
      btn.setAttribute('role', 'listitem');

      const title = document.createElement('span');
      title.className = 'chatbot-conv__title';
      title.textContent = conv.title || 'New conversation';

      const time = document.createElement('span');
      time.className = 'chatbot-conv__time';
      time.textContent = timeAgo(conv.updated_at);

      btn.appendChild(title);
      btn.appendChild(time);
      btn.addEventListener('click', () => openConversation(conv.id));
      btn.addEventListener('dblclick', () => renameConversation(conv.id, conv.title));
      listEl.appendChild(btn);
    });
  };

  const createConversation = async () => {
    try {
      const data = await api('/api/chat/conversations', { method: 'POST', json: {} });
      conversations.unshift(data.conversation);
      if (searchEl.value) searchEl.value = '';
      await openConversation(data.conversation.id);
      renderConversationList();
    } catch (err) {
      toast(err.message || 'Could not create conversation', 'error');
    }
  };

  const renameConversation = async (id, currentTitle) => {
    const title = (window.prompt('Rename conversation', currentTitle) || '').trim();
    if (!title || title === currentTitle) return;
    try {
      await api(`/api/chat/conversations/${id}`, { method: 'PATCH', json: { title } });
      if (id === currentId) titleEl.textContent = title;
      await loadConversations(searchEl.value);
    } catch (err) {
      toast(err.message || 'Could not rename conversation', 'error');
    }
  };

  const deleteConversation = async (id) => {
    if (!window.confirm('Delete this conversation and its files?')) return;
    try {
      await api(`/api/chat/conversations/${id}`, { method: 'DELETE' });
      if (id === currentId) {
        currentId = null;
        currentMessages = [];
        attachedFiles = [];
        titleEl.textContent = 'New conversation';
        renderThread();
      }
      await loadConversations(searchEl.value);
    } catch (err) {
      toast(err.message || 'Could not delete conversation', 'error');
    }
  };

  const clearAll = async () => {
    if (!conversations.length) return;
    if (!window.confirm('Delete ALL conversations and their files? This cannot be undone.')) return;
    try {
      await api('/api/chat/clear', { method: 'POST', json: {} });
      currentId = null;
      currentMessages = [];
      attachedFiles = [];
      titleEl.textContent = 'New conversation';
      renderThread();
      await loadConversations();
    } catch (err) {
      toast(err.message || 'Could not clear history', 'error');
    }
  };

  // ─── Thread ─────────────────────────────────────────────────────
  const openConversation = async (id) => {
    currentId = id;
    renderConversationList();
    try {
      const data = await api(`/api/chat/conversations/${id}`);
      const conv = data.conversation;
      currentMessages = conv.messages || [];
      attachedFiles = (conv.files || []).map((f) => ({
        id: f.id,
        filename: f.filename,
        is_image: f.is_image,
        raw_text: '',
        char_count: f.char_count || 0,
        skill_count: 0,
      }));
      titleEl.textContent = conv.title || 'New conversation';
      renderThread();
      if (window.innerWidth <= 860) closeSidebar();
    } catch (err) {
      toast(err.message || 'Could not load conversation', 'error');
    }
  };

  const renderThread = () => {
    messagesEl.innerHTML = '';
    updateContextBar();
    if (!currentId || !currentMessages.length) {
      messagesEl.appendChild(emptyEl);
      emptyEl.style.display = '';
      return;
    }
    if (emptyEl.parentNode === messagesEl) emptyEl.remove();
    currentMessages.forEach(renderMessage);
    scrollToBottom();
  };

  const renderMessage = (msg) => {
    const isUser = msg.role === 'user';
    const row = document.createElement('div');
    row.className = 'chat-message-row' + (isUser ? ' is-user' : '');

    const avatar = document.createElement('div');
    avatar.className = 'chat-message-row__avatar';
    avatar.setAttribute('aria-hidden', 'true');
    avatar.textContent = isUser ? '👤' : '🤖';

    const body = document.createElement('div');
    body.className = 'chat-message-row__body';

    const bubble = document.createElement('div');
    bubble.className = 'chat-message-row__bubble';
    if (isUser) {
      bubble.textContent = msg.content;
    } else {
      bubble.innerHTML = markdown(msg.content);
    }
    body.appendChild(bubble);

    // Actions row
    const actions = document.createElement('div');
    actions.className = 'chat-message-row__actions';

    if (isUser) {
      if (msg.id) {
        const editBtn = document.createElement('button');
        editBtn.type = 'button';
        editBtn.className = 'chat-message-row__action';
        editBtn.textContent = '✎ Edit';
        editBtn.title = 'Edit message and regenerate';
        editBtn.addEventListener('click', () => editMessage(msg.id, msg.content));
        actions.appendChild(editBtn);
      }
    } else {
      const feedbackValue = msg.feedback || null;

      if (msg.id) {
        const regenBtn = document.createElement('button');
        regenBtn.type = 'button';
        regenBtn.className = 'chat-message-row__action';
        regenBtn.textContent = '🔄 Regenerate';
        regenBtn.title = 'Regenerate this reply';
        regenBtn.addEventListener('click', () => regenerate(msg.id));
        actions.appendChild(regenBtn);
      }

      if (msg.id) {
        const likeBtn = document.createElement('button');
        likeBtn.type = 'button';
        likeBtn.className = 'chat-message-row__action' + (feedbackValue === 'like' ? ' is-selected' : '');
        likeBtn.textContent = '👍';
        likeBtn.title = 'Helpful';
        likeBtn.addEventListener('click', () => sendFeedback(msg.id, likeBtn, 'like'));
        actions.appendChild(likeBtn);

        const dislikeBtn = document.createElement('button');
        dislikeBtn.type = 'button';
        dislikeBtn.className = 'chat-message-row__action' + (feedbackValue === 'dislike' ? ' is-selected' : '');
        dislikeBtn.textContent = '👎';
        dislikeBtn.title = 'Not helpful';
        dislikeBtn.addEventListener('click', () => sendFeedback(msg.id, dislikeBtn, 'dislike'));
        actions.appendChild(dislikeBtn);
      }
    }

    body.appendChild(actions);

    if (msg.edited) {
      const meta = document.createElement('div');
      meta.className = 'chat-message-row__meta';
      meta.textContent = 'edited';
      body.appendChild(meta);
    }

    row.appendChild(avatar);
    row.appendChild(body);
    messagesEl.appendChild(row);
  };

  const scrollToBottom = () => {
    messagesEl.scrollTop = messagesEl.scrollHeight;
  };

  // ─── Stream engine (shared by send / regenerate / edit) ─────────
  const showTyping = () => {
    const el = document.createElement('div');
    el.className = 'chat-typing';
    el.setAttribute('data-typing', '');
    el.innerHTML = '<span>🤖</span><span class="chat-typing__dots"><span></span><span></span><span></span></span>';
    messagesEl.appendChild(el);
    scrollToBottom();
    return el;
  };

  const removeTyping = () => {
    const t = messagesEl.querySelector('[data-typing]');
    if (t) t.remove();
  };

  const setBusy = (busy) => {
    isSending = busy;
    sendBtn.disabled = busy || isStreaming || !inputEl.value.trim();
    stopBtn.hidden = !(busy || isStreaming);
    sendBtn.hidden = busy || isStreaming;
  };

  /**
   * POST /api/chat/conversations/<id>/stream and render tokens as they
   * arrive. On completion, the assistant message is appended to
   * currentMessages and the thread is re-rendered so action buttons appear.
   */
  const streamGeneration = async (payload) => {
    isStreaming = true;
    setBusy(true);
    streamAbort = new AbortController();

    let full = '';
    let row = null;
    let bubble = null;

    try {
      const res = await fetch(`/api/chat/conversations/${currentId}/stream`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'X-CSRFToken': csrfToken() },
        body: JSON.stringify(payload),
        signal: streamAbort.signal,
      });
      if (!res.ok) {
        let data;
        try { data = await res.json(); } catch (_) { data = {}; }
        throw new Error(data.error || `Server error (${res.status})`);
      }

      const reader = res.body.getReader();
      const decoder = new TextDecoder();
      let buffer = '';
      let doneContent = null;
      let doneMessageId = null;

      const handleFrame = (frame) => {
        let event = 'message';
        let dataStr = '';
        frame.split('\n').forEach((line) => {
          if (line.startsWith('event: ')) event = line.slice(7).trim();
          else if (line.startsWith('data: ')) dataStr += line.slice(6);
        });
        if (!dataStr.trim()) return;
        let parsed;
        try { parsed = JSON.parse(dataStr); } catch (_) { return; }

        if (event === 'meta') {
          if (parsed.title) titleEl.textContent = parsed.title;
          return;
        }
        if (event === 'token') {
          if (!row) {
            removeTyping();
            row = document.createElement('div');
            row.className = 'chat-message-row';
            const avatar = document.createElement('div');
            avatar.className = 'chat-message-row__avatar';
            avatar.setAttribute('aria-hidden', 'true');
            avatar.textContent = '🤖';
            const body = document.createElement('div');
            body.className = 'chat-message-row__body';
            bubble = document.createElement('div');
            bubble.className = 'chat-message-row__bubble';
            body.appendChild(bubble);
            row.appendChild(avatar);
            row.appendChild(body);
            messagesEl.appendChild(row);
          }
          full += parsed.content || '';
          bubble.innerHTML = markdown(full);
          scrollToBottom();
          return;
        }
        if (event === 'error') {
          throw new Error(parsed.error || 'Generation failed');
        }
        if (event === 'done') {
          doneContent = parsed.content || '';
          doneMessageId = parsed.message_id || null;
        }
      };

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });
        let idx;
        while ((idx = buffer.indexOf('\n\n')) !== -1) {
          const frame = buffer.slice(0, idx);
          buffer = buffer.slice(idx + 2);
          handleFrame(frame);
        }
      }
      buffer += decoder.decode();
      if (buffer.trim()) handleFrame(buffer);

      if (row) row.remove();
      const content = (doneContent != null ? doneContent : full).trim();
      if (content) {
        currentMessages.push({
          id: doneMessageId,
          role: 'assistant',
          content,
          edited: false,
          feedback: null,
        });
        renderThread();
      }
      await loadConversations(searchEl.value);
    } catch (err) {
      removeTyping();
      if (row) { row.remove(); row = null; }
      if (err.name === 'AbortError') {
        toast('Generation stopped', 'warning', 2500);
        if (full.trim()) {
          currentMessages.push({ id: null, role: 'assistant', content: full.trim(), edited: false, feedback: null });
          renderThread();
        }
      } else {
        toast(err.message || 'Something went wrong', 'error');
      }
    } finally {
      isStreaming = false;
      streamAbort = null;
      removeTyping();
      setBusy(false);
    }
  };

  const ensureConversation = async () => {
    if (currentId) return true;
    try {
      const data = await api('/api/chat/conversations', { method: 'POST', json: {} });
      currentId = data.conversation.id;
      renderConversationList();
      return true;
    } catch (err) {
      toast(err.message || 'Could not start conversation', 'error');
      return false;
    }
  };

  const fileIds = () => attachedFiles.map((f) => f.id);

  const sendMessage = async (text) => {
    if (!(await ensureConversation())) return;
    currentMessages.push({ id: null, role: 'user', content: text, edited: false, feedback: null });
    renderThread();
    removeTyping();
    showTyping();
    await streamGeneration({ message: text, file_ids: fileIds() });
  };

  // Regenerate the assistant reply that follows the given user message id
  const regenerate = async (assistantMessageId) => {
    if (!currentId || isStreaming) return;
    const idx = currentMessages.findIndex((m) => m.id === assistantMessageId);
    const anchor = idx > 0 ? currentMessages[idx - 1] : null;
    if (!anchor || anchor.role !== 'user') {
      toast('Nothing to regenerate from', 'warning');
      return;
    }
    // Server-side: regenerate pops the last assistant message and regenerates
    // from the last user message. We prune locally to stay in sync.
    currentMessages = currentMessages.slice(0, idx);
    renderThread();
    removeTyping();
    showTyping();
    await streamGeneration({ message: anchor.content, regenerate: true, file_ids: fileIds() });
  };

  const editMessage = async (messageId, content) => {
    const newContent = (window.prompt('Edit message', content) || '').trim();
    if (!newContent || newContent === content || !currentId || isStreaming) return;
    try {
      await api(`/api/chat/messages/${messageId}?conversation_id=${currentId}`, {
        method: 'PATCH',
        json: { content: newContent, prune: true },
      });
      // Anchor the generation at this (edited) user message
      const idx = currentMessages.findIndex((m) => m.id === messageId);
      currentMessages = currentMessages.slice(0, idx);
      currentMessages[idx] = { id: messageId, role: 'user', content: newContent, edited: true, feedback: null };
      renderThread();
      removeTyping();
      showTyping();
      await streamGeneration({ regenerate_from: messageId, file_ids: fileIds() });
    } catch (err) {
      toast(err.message || 'Could not edit message', 'error');
    }
  };

  const sendFeedback = async (messageId, btn, value) => {
    try {
      await api(`/api/chat/messages/${messageId}/feedback`, { method: 'POST', json: { value } });
      const msg = currentMessages.find((m) => m.id === messageId);
      if (msg) msg.feedback = value;
      $$('.chat-message-row__action', btn.parentNode).forEach((b) => b.classList.remove('is-selected'));
      btn.classList.add('is-selected');
      toast(value === 'like' ? 'Thanks for the feedback!' : 'Thanks — we\u2019ll use this to improve.', 'success', 2500);
    } catch (err) {
      toast(err.message || 'Could not save feedback', 'error');
    }
  };

  const stopStream = async () => {
    if (streamAbort) {
      try {
        if (currentId) await fetch(`/api/chat/conversations/${currentId}/stop`, {
          method: 'POST',
          headers: { 'X-CSRFToken': csrfToken() },
        });
      } catch (_) { /* best effort */ }
      streamAbort.abort();
    }
  };

  // ─── Attachments ────────────────────────────────────────────────
  const updateContextBar = () => {
    if (!attachedFiles.length) {
      contextBar.hidden = true;
      return;
    }
    contextName.textContent = attachedFiles.map((f) => f.filename).join(', ');
    contextBar.hidden = false;
  };

  const attachFile = async (file) => {
    if (!file) return;
    const ext = (file.name.split('.').pop() || '').toLowerCase();
    if (!ALLOWED_EXTS.includes(ext)) {
      toast('Unsupported file type. Use PDF, DOCX, TXT, CSV, XLSX, or an image (PNG/JPG/JPEG).', 'error', 6000);
      return;
    }
    if (file.size > MAX_FILE_SIZE) {
      toast('File is too large (max 20 MB).', 'error');
      return;
    }
    const formData = new FormData();
    formData.append('file', file);
    try {
      const data = await api('/api/chat/context', { method: 'POST', body: formData });
      if (!data.file || !data.file.id) throw new Error('Upload did not return a file id');
      attachedFiles = attachedFiles.filter((f) => f.id !== data.file.id);
      attachedFiles.push({
        id: data.file.id,
        filename: data.file.filename,
        is_image: data.file.is_image,
        raw_text: data.text || '',
        char_count: data.char_count || 0,
        skill_count: data.skill_count || 0,
      });
      updateContextBar();
      const icon = data.file.is_image ? '🖼️' : '📎';
      const detail = data.file.is_image
        ? 'Image attached (no text extracted locally)'
        : `${data.char_count.toLocaleString()} chars · ${data.skill_count} skills found`;
      toast(`${icon} ${data.file.filename} — ${detail}`, 'success', 4000);
      if (data.file.is_image) return;
      const skills = (data.skills || []).slice(0, 8).join(', ');
      currentMessages.push({
        id: null,
        role: 'assistant',
        content: `📎 Loaded **${data.file.filename}** (${data.char_count.toLocaleString()} characters).` +
          (data.skill_count ? ` I spotted ${data.skill_count} skill${data.skill_count === 1 ? '' : 's'}: ${skills}.` : '') +
          ' Ask me anything about it — I\u2019ll base my advice on the document.',
        edited: false,
        feedback: null,
      });
      renderThread();
    } catch (err) {
      toast(err.message || 'Upload failed', 'error', 6000);
    }
  };

  const clearContext = () => {
    attachedFiles = [];
    updateContextBar();
  };

  // ─── Tools ──────────────────────────────────────────────────────
  const runTool = async (tool) => {
    if (!currentId) {
      toast('Start a conversation first — I\u2019ll create one when you send.', 'warning');
      return;
    }
    const resumeText = attachedFiles
      .filter((f) => !f.is_image && f.raw_text)
      .map((f) => f.raw_text)
      .join('\n');
    if (!resumeText || resumeText.trim().length < 20) {
      toast('Attach a resume/document first — career tools need your document content.', 'warning', 5000);
      return;
    }

    const payload = { resume_text: resumeText };
    if (tool === 'gap') {
      const role = (window.prompt('Target role (e.g. Data Scientist):', '') || '').trim();
      if (!role) { toast('Target role is required for skill-gap analysis.', 'warning'); return; }
      payload.target_role = role;
    } else if (tool === 'compare') {
      const jd = (window.prompt('Paste the job description:', '') || '').trim();
      if (!jd || jd.length < 20) { toast('A job description (20+ chars) is required.', 'warning'); return; }
      payload.jd_text = jd;
    } else if (tool === 'cover-letter') {
      const job = (window.prompt('Job title (optional):', '') || '').trim();
      const company = (window.prompt('Company (optional):', '') || '').trim();
      if (job) payload.job_title = job;
      if (company) payload.company = company;
    }

    removeTyping();
    showTyping();
    try {
      const data = await api(`/api/chat/tools/${tool}`, { method: 'POST', json: payload });
      removeTyping();
      const content = data.markdown || JSON.stringify(data.data || data, null, 2);
      currentMessages.push({ id: null, role: 'assistant', content, edited: false, feedback: null });
      renderThread();
    } catch (err) {
      removeTyping();
      toast(err.message || 'Tool failed', 'error', 6000);
    }
  };

  // ─── Export ─────────────────────────────────────────────────────
  const exportConversation = (format) => {
    if (!currentId) { toast('Nothing to export yet.', 'warning'); return; }
    window.location.href = `/api/chat/conversations/${currentId}/export?format=${format}`;
  };

  // ─── Sidebar (mobile) ───────────────────────────────────────────
  const closeSidebar = () => app.classList.remove('is-sidebar-open');
  const toggleSidebar = () => app.classList.toggle('is-sidebar-open');

  // ─── Suggestions ────────────────────────────────────────────────
  const SUGGESTION_ICONS = {
    'Analyse my resume': '📄',
    'ATS score': '🏷️',
    'Skill gaps': '🧩',
    'Interview prep': '🎯',
    'Cover letter': '✉️',
    'Learning roadmap': '🗺️',
  };

  const loadSuggestions = async () => {
    try {
      const data = await api('/api/chat/suggestions');
      const container = messagesEl.querySelector('.chatbot-suggestions');
      if (!container || !data.suggestions) return;
      container.innerHTML = '';
      data.suggestions.forEach((s) => {
        const btn = document.createElement('button');
        btn.type = 'button';
        btn.className = 'chatbot-suggestion';
        const icon = SUGGESTION_ICONS[s.label] || '';
        if (icon) {
          const iconSpan = document.createElement('span');
          iconSpan.className = 'chatbot-suggestion__icon';
          iconSpan.textContent = icon;
          btn.appendChild(iconSpan);
        }
        const textSpan = document.createElement('span');
        textSpan.className = 'chatbot-suggestion__text';
        textSpan.textContent = s.label;
        btn.appendChild(textSpan);
        btn.addEventListener('click', () => {
          inputEl.value = s.prompt;
          autoResize();
          sendBtn.disabled = false;
          handleSend();
        });
        container.appendChild(btn);
      });
    } catch (_) { /* keep static suggestions */ }
  };

  // ─── Input handling ─────────────────────────────────────────────
  const autoResize = () => {
    inputEl.style.height = 'auto';
    inputEl.style.height = Math.min(inputEl.scrollHeight, 160) + 'px';
  };

  const handleSend = async () => {
    const text = inputEl.value.trim();
    if (!text || isSending || isStreaming) return;
    inputEl.value = '';
    autoResize();
    await sendMessage(text);
  };

  const setupListeners = () => {
    $('[data-chat-new]', app).addEventListener('click', createConversation);
    $('[data-chat-clear]', app).addEventListener('click', clearAll);
    $('[data-chat-rename]', app).addEventListener('click', () => {
      if (currentId) renameConversation(currentId, titleEl.textContent);
    });
    $('[data-chat-delete]', app).addEventListener('click', () => {
      if (currentId) deleteConversation(currentId);
    });

    let searchTimer = null;
    searchEl.addEventListener('input', () => {
      clearTimeout(searchTimer);
      searchTimer = setTimeout(() => loadConversations(searchEl.value), 250);
    });

    sendBtn.addEventListener('click', handleSend);
    stopBtn.addEventListener('click', stopStream);
    inputEl.addEventListener('keydown', (e) => {
      if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault();
        handleSend();
      }
    });
    inputEl.addEventListener('input', () => {
      autoResize();
      sendBtn.disabled = isSending || isStreaming || !inputEl.value.trim();
    });

    attachBtn.addEventListener('click', () => fileInput.click());
    fileInput.addEventListener('change', (e) => {
      const file = e.target.files && e.target.files[0];
      if (file) attachFile(file);
      e.target.value = '';
    });
    contextRemove.addEventListener('click', clearContext);

    toolsToggle.addEventListener('click', (e) => {
      e.stopPropagation();
      const willOpen = toolsMenu.hidden;
      closeMenus();
      toolsMenu.hidden = !willOpen;
    });
    $$('[data-tool]', toolsMenu).forEach((btn) => {
      btn.addEventListener('click', () => {
        closeMenus();
        runTool(btn.getAttribute('data-tool'));
      });
    });

    exportToggle.addEventListener('click', (e) => {
      e.stopPropagation();
      const willOpen = exportMenu.hidden;
      closeMenus();
      exportMenu.hidden = !willOpen;
    });
    $$('[data-export-format]', exportMenu).forEach((btn) => {
      btn.addEventListener('click', () => {
        closeMenus();
        exportConversation(btn.getAttribute('data-export-format'));
      });
    });

    document.addEventListener('click', (e) => {
      if (!e.target.closest('.chatbot-export') && !e.target.closest('.chatbot-tools')) {
        closeMenus();
      }
    });

    sidebarToggle.addEventListener('click', toggleSidebar);
    sidebarBackdrop.addEventListener('click', closeSidebar);
  };

  const closeMenus = () => {
    toolsMenu.hidden = true;
    exportMenu.hidden = true;
  };

  // ─── Init ───────────────────────────────────────────────────────
  const init = () => {
    app = document.querySelector('[data-chatbot-app]');
    if (!app) return;
    listEl = $('[data-chat-list]', app);
    listEmptyEl = $('[data-chat-list-empty]', app);
    searchEl = $('[data-chat-search]', app);
    titleEl = $('[data-chat-title]', app);
    messagesEl = $('[data-chat-messages]', app);
    emptyEl = $('[data-chat-empty]', app);
    inputEl = $('[data-chat-input]', app);
    sendBtn = $('[data-chat-send]', app);
    stopBtn = $('[data-chat-stop]', app);
    attachBtn = $('[data-chat-attach]', app);
    fileInput = $('[data-chat-file]', app);
    contextBar = $('[data-chat-context]', app);
    contextName = $('[data-chat-context-name]', app);
    contextRemove = $('[data-chat-context-remove]', app);
    toolsToggle = $('[data-chat-tools-toggle]', app);
    toolsMenu = $('[data-chat-tools-menu]', app);
    exportToggle = $('[data-chat-export-toggle]', app);
    exportMenu = $('[data-chat-export-menu]', app);
    sidebarToggle = $('[data-chat-sidebar-toggle]', app);
    sidebarBackdrop = $('[data-chat-sidebar-backdrop]', app);

    if (!messagesEl || !inputEl) {
      console.warn('Chatbot: required DOM elements missing.');
      return;
    }

    setupListeners();
    loadSuggestions();
    loadConversations();
    inputEl.focus();
  };

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
