/**
 * Prayash — Auth Assistant
 * ==========================
 * Conversational AI guide for authentication pages.
 * Provides contextual help, security tips, and step-by-step walkthroughs.
 * 
 * Usage: Include in auth page templates and initialize with:
 *   AuthAssistant.init({ page: 'login'|'signup'|'verify'|'forgot'|'reset' });
 */
(() => {
  'use strict';

  // ─── CONTEXTUAL KNOWLEDGE BASE ───
  // Each page has a tailored set of dialogues, tips, and actions.
  const KB = {
    login: {
      greeting: "Hi there! 👋 Welcome back to Prayash. I can help you sign in, or if you're new here, you can create an account. What would you like to do?",
      tips: {
        email:    "Enter your email or username — whichever you used to sign up.",
        password: "Passwords are case-sensitive! Make sure Caps Lock is off. 🔑",
        submit:   "Click 'Sign In' when you're ready. I'll be here if anything goes wrong!"
      },
      actions: [
        { label: "Sign in", response: "Go ahead and enter your credentials below. Need help with a specific field?" },
        { label: "Create account", response: "Let's get you set up! Switch to the 'Sign Up' tab above and I'll guide you through it. 🎉", link: "signup" },
        { label: "Forgot password?", response: "No worries! Click the 'Forgot password?' link below the form and I'll help you reset it.", highlight: true },
        { label: "Sign in with Google", response: "Click the Google button above to sign in instantly — no password needed!", highlight: false },
      ],
      security: "🔒 Always check for the padlock icon in your browser bar before entering your password. Make sure you're on the real Prayash site!",
    },

    signup: {
      greeting: "Hey! 🎉 Ready to take charge of your career? I'll walk you through creating your account step by step. Let's start!",
      tips: {
        name:     "Enter your full name — this will appear on your profile. It should be at least 2 characters.",
        username: "Pick a unique username (min. 4 characters). Use letters, numbers, and underscores only.",
        email:    "Use an email you have access to — you'll need to verify it right after signing up!",
        phone:    "Optional, but recommended! A phone number adds an extra recovery option. 📱",
        password: "Make it strong! 8+ characters, uppercase, lowercase, a number, and a special character. Try a passphrase like 'Sunny$Day42!'",
        confirm:  "Type the same password again to confirm. Make sure there are no extra spaces!",
        terms:    "Please agree to the Privacy Policy & Terms to continue. We take your data privacy seriously."
      },
      actions: [
        { label: "What's a strong password?", response: "A strong password has:\n• At least 8 characters\n• Uppercase & lowercase letters\n• At least 1 number\n• At least 1 special character (!@#$%^&*)\n\nTry: 'BlueElephant$Jump42!' — it's strong AND memorable! 💪" },
        { label: "Why verify email?", response: "Email verification proves you own this email address. It's a security essential — and it's how we send you important updates and reset codes!" },
        { label: "Sign up with Google", response: "Prefer not to create another password? Use the Google button above — one click and you're in! ✅", highlight: true },
      ],
      security: "🔒 Your resume data stays on your device during analysis. We never share your personal information with third parties without your explicit consent.",
    },

    verify: {
      greeting: "📬 I've sent a 6-digit code to your email. It expires in 10 minutes, so check your inbox soon!",
      tips: {
        otp: "Enter all 6 digits. If you got the code via SMS or email, just type the numbers one by one.",
        resend: "Didn't get it? Click 'Resend' after 30 seconds. Check your Spam folder too!"
      },
      actions: [
        { label: "Haven't received the code?", response: "Here's what to do:\n1. Check your Spam / Promotions folder\n2. Wait 30 seconds and click 'Resend'\n3. Make sure you entered the right email\n\nStill stuck? Try signing up with Google instead!" },
        { label: "Why do I need to verify?", response: "Verifying your email confirms you're you — it prevents someone from signing up with your email address without your permission. 🔐" },
      ],
      security: "🔒 Prayash will NEVER call or text you asking for your verification code. Only enter codes on this website — never share them with anyone!",
    },

    forgot: {
      greeting: "No worries! 😊 I'll help you reset your password and get you back into your account. Let's start with your email.",
      tips: {
        email: "Enter the email address you used when you signed up. We'll send a 6-digit reset code there.",
        submit: "Click 'Send Reset Code' and check your inbox in a minute or two."
      },
      actions: [
        { label: "I don't remember my email", response: "Try any email you might have used. If you signed up with Google/GitHub, check that account's primary email." },
        { label: "Sign in with Google instead", response: "If your Google email is the same one you used for Prayash, you can sign in instantly!", highlight: true },
      ],
      security: "🔒 If you don't receive a reset email, check your Spam folder and make sure you're checking the right email account. We never send password reset links via SMS.",
    },

    reset: {
      greeting: "Great, your code is verified! ✅ Now let's create a new password. Make it strong and unique!",
      tips: {
        password: "Choose a password you haven't used before. Try a phrase with mixed characters!",
        confirm:  "Type it again to confirm. Make sure it matches exactly!"
      },
      actions: [
        { label: "Tips for a memorable password", response: "Create a passphrase! Pick 3-4 random words and add numbers & symbols:\n'Correct-Horse-Battery$42'\n'Happy_Yellow_Cat!99'\n\nThese are hard to crack but easy to remember! 🧠" },
        { label: "Use a password manager", response: "Password managers like Bitwarden, 1Password, or iCloud Keychain can generate and store strong passwords for you. Highly recommended! 🔐" },
      ],
      security: "🔒 After resetting your password, make sure to log out of any other devices where you might still be logged in. Use 'Sign out everywhere' if available.",
    }
  };

  // Forgot password - OTP step context (uses 'verify' KB)
  KB.forgot_otp = {
    greeting: "Check your inbox for the 6-digit reset code! It expires in 10 minutes. 📬",
    tips: {
      otp: "Enter the 6-digit code from your email. Check Spam/Promotions if you don't see it."
    },
    actions: [
      { label: "Resend code", response: "Click 'Resend code' below or go back to the forgot password page to request a new one." },
    ],
    security: "🔒 Password reset codes are single-use and expire after 10 minutes for your security. If you didn't request this, you can ignore the email.",
  };

  // ─── CHAT MESSAGES ───
  const STORAGE_KEY = 'prayash-assistant-dismissed';
  const TYPING_DELAY = 600;
  const GREETING_DELAY = 800;
  const CAREER_API = '/api/career-chat';
  const CAREER_SESSION_KEY = 'prayash-career-session';

  // ─── DOM ───
  let toggleBtn, panel, messagesContainer, inputField, sendBtn, statusText;
  let typingIndicator = null;
  let isOpen = false;
  let currentPage = 'login';
  let hasGreeted = false;
  let isProcessing = false;
  let currentMode = 'auth';  // 'auth' | 'career'
  let careerSessionId = '';

  // ─── HELPERS ───
  const $ = (s, p = document) => p.querySelector(s);
  const $$ = (s, p = document) => [...p.querySelectorAll(s)];
  const scrollToBottom = () => {
    if (messagesContainer) {
      requestAnimationFrame(() => {
        messagesContainer.scrollTop = messagesContainer.scrollHeight;
      });
    }
  };

  // ─── GET CSRF TOKEN ───
  const getCsrfToken = () => {
    const meta = document.querySelector('meta[name="csrf-token"]');
    return meta ? meta.getAttribute('content') : '';
  };

  // ─── CREATE TYPING INDICATOR ───
  const createTyping = () => {
    const el = document.createElement('div');
    el.className = 'auth-typing';
    el.innerHTML = '<div class="auth-message__avatar" aria-hidden="true">🤖</div><div class="auth-typing__wrap" style="display:flex;gap:4px;padding:10px 14px;background:white;border-radius:16px;border-bottom-left-radius:4px;"><div class="auth-typing__dot"></div><div class="auth-typing__dot"></div><div class="auth-typing__dot"></div></div>';
    return el;
  };

  const showTyping = () => {
    if (!typingIndicator) typingIndicator = createTyping();
    messagesContainer.appendChild(typingIndicator);
    scrollToBottom();
  };

  const hideTyping = () => {
    if (typingIndicator && typingIndicator.parentNode) {
      typingIndicator.remove();
    }
  };

  // ─── ADD MESSAGE ───
  const addMessage = (text, isUser = false) => {
    if (!messagesContainer) return;
    
    hideTyping();

    const el = document.createElement('div');
    el.className = `auth-message ${isUser ? 'is-user' : 'is-assistant'}`;

    const avatar = document.createElement('div');
    avatar.className = 'auth-message__avatar';
    avatar.setAttribute('aria-hidden', 'true');
    avatar.textContent = isUser ? '👤' : '🤖';

    const bubble = document.createElement('div');
    bubble.className = 'auth-message__bubble';
    
    if (isUser) {
      // Use textContent for user messages to prevent XSS
      bubble.textContent = text;
    } else {
      // Format assistant responses with rich formatting
      let formatted = text
        .replace(/\n/g, '<br>')
        .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>');
      // Highlight security tips (auth mode only)
      formatted = formatted.replace(/🔒(.+?)(?=<br>|$)/g, '<span class="security-tip">🔒$1</span>');
      formatted = formatted.replace(/✅/g, '<span class="success-badge">✅</span>');
      bubble.innerHTML = formatted;
    }

    el.appendChild(avatar);
    el.appendChild(bubble);
    messagesContainer.appendChild(el);
    scrollToBottom();

    // Update unread if panel is minimized/closed
    if (!isOpen) {
      const dot = document.querySelector('.unread-dot');
      if (dot) dot.classList.add('is-visible');
    }
  };

  // ─── ADD QUICK ACTIONS ───
  const addActions = (actions) => {
    if (!messagesContainer || !actions || !actions.length) return;

    const lastMsg = messagesContainer.lastElementChild;
    if (!lastMsg || !lastMsg.classList.contains('is-assistant')) return;

    const bubble = lastMsg.querySelector('.auth-message__bubble');
    if (!bubble) return;

    const actionsContainer = document.createElement('div');
    actionsContainer.className = 'auth-message__actions';

    actions.forEach(a => {
      const btn = document.createElement('button');
      btn.className = 'auth-quick-action';
      if (a.highlight) btn.style.cssText = 'background:var(--primary-container,#4c1d95);color:var(--on-primary,#fff);border-color:var(--primary-container,#4c1d95);';
      btn.textContent = a.label;
      btn.addEventListener('click', () => handleQuickAction(a));
      actionsContainer.appendChild(btn);
    });

    bubble.appendChild(actionsContainer);
    scrollToBottom();
  };

  const CAREER_STREAM_API = '/api/career-chat/stream';

  // ─── CAREER MODE: Create a live-updating message bubble ───
  const createLiveBubble = () => {
    if (!messagesContainer) return null;
    hideTyping();

    const el = document.createElement('div');
    el.className = 'auth-message is-assistant is-streaming';

    const avatar = document.createElement('div');
    avatar.className = 'auth-message__avatar';
    avatar.setAttribute('aria-hidden', 'true');
    avatar.textContent = '🤖';

    const bubble = document.createElement('div');
    bubble.className = 'auth-message__bubble auth-message__bubble--streaming';
    bubble.innerHTML = '<span class="streaming-cursor">|</span>';

    el.appendChild(avatar);
    el.appendChild(bubble);
    messagesContainer.appendChild(el);
    scrollToBottom();
    return bubble;
  };

  const updateLiveBubble = (bubble, text) => {
    if (!bubble) return;
    // Remove cursor, set text, re-add cursor
    const formatted = text
      .replace(/\n/g, '<br>')
      .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>');
    bubble.innerHTML = formatted + '<span class="streaming-cursor">|</span>';
    scrollToBottom();
  };

  const finalizeLiveBubble = (bubble, text) => {
    if (!bubble) return;
    const formatted = text
      .replace(/\n/g, '<br>')
      .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>');
    bubble.innerHTML = formatted;
    bubble.classList.remove('auth-message__bubble--streaming');
    const msgEl = bubble.closest('.auth-message');
    if (msgEl) msgEl.classList.remove('is-streaming');
    scrollToBottom();
  };

  // ─── CAREER MODE: Send message with streaming SSE ───
  const sendCareerMessageStream = async (message) => {
    let bubble = null;
    try {
      const response = await fetch(CAREER_STREAM_API, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-CSRFToken': getCsrfToken(),
        },
        body: JSON.stringify({
          message: message,
          session_id: careerSessionId,
        }),
      });

      if (!response.ok) {
        let errData;
        try { errData = await response.json(); } catch (_) {}
        throw new Error(errData?.error || `Server error (${response.status})`);
      }

      const reader = response.body.getReader();
      if (!reader) {
        throw new Error('Stream not supported by browser');
      }

      // Create live-updating bubble
      bubble = createLiveBubble();
      if (!bubble) throw new Error('Could not create message bubble');

      let fullAnswer = '';
      let sessionId = careerSessionId;
      const decoder = new TextDecoder();
      let buffer = '';

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });

        // Parse SSE events: event: <name>\ndata: <json>\n\n
        const parts = buffer.split('\n\n');
        buffer = parts.pop() || '';

        for (const part of parts) {
          const lines = part.split('\n');
          let eventType = '';
          let dataStr = '';

          for (const line of lines) {
            if (line.startsWith('event: ')) {
              eventType = line.slice(7).trim();
            } else if (line.startsWith('data: ')) {
              dataStr = line.slice(6).trim();
            }
          }

          if (!dataStr) continue;

          try {
            const parsed = JSON.parse(dataStr);

            if (eventType === 'meta' && parsed.session_id) {
              sessionId = parsed.session_id;
              careerSessionId = sessionId;
              try { localStorage.setItem(CAREER_SESSION_KEY, sessionId); } catch (_) {}
            } else if (eventType === 'token' && parsed.content) {
              fullAnswer += parsed.content;
              updateLiveBubble(bubble, fullAnswer);
            } else if (eventType === 'done') {
              if (parsed.session_id) {
                sessionId = parsed.session_id;
                careerSessionId = sessionId;
                try { localStorage.setItem(CAREER_SESSION_KEY, sessionId); } catch (_) {}
              }
              fullAnswer = parsed.answer || fullAnswer;
              finalizeLiveBubble(bubble, fullAnswer);
            }
          } catch (_) {
            // Skip malformed JSON
          }
        }
      }

      // If we never got a 'done' event but have text, finalize
      if (fullAnswer) {
        finalizeLiveBubble(bubble, fullAnswer);
      }

      return fullAnswer || "I'm not sure how to answer that. Could you rephrase?";

    } catch (err) {
      // Fallback to non-streaming endpoint
      hideTyping();
      const fbAnswer = err.message.includes('fetch') || err.message.includes('Network')
        ? "I'm having trouble connecting. Let me try a different way..."
        : await sendCareerMessage(message);
      // If a live bubble was created, fill it — otherwise display a new message
      if (bubble) {
        finalizeLiveBubble(bubble, fbAnswer);
      } else {
        addMessage(fbAnswer);
      }
      return fbAnswer;
    }
  };

  // ─── CAREER MODE: Send message to API (non-streaming fallback) ───
  const sendCareerMessage = async (message) => {
    try {
      const response = await fetch(CAREER_API, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-CSRFToken': getCsrfToken(),
        },
        body: JSON.stringify({
          message: message,
          session_id: careerSessionId,
        }),
      });

      let data;
      try {
        data = await response.json();
      } catch (_) {
        throw new Error('Invalid response from server.');
      }

      if (!response.ok) {
        throw new Error(data.error || `Server error (${response.status})`);
      }

      if (data.success === false) {
        throw new Error(data.error || 'Request failed');
      }

      // Persist session
      if (data.session_id) {
        careerSessionId = data.session_id;
        try { localStorage.setItem(CAREER_SESSION_KEY, careerSessionId); } catch (_) {}
      }

      return data.answer || "I'm not sure how to answer that. Could you rephrase?";
    } catch (err) {
      if (err.message.includes('429')) {
        return "You're asking a lot of questions — great! 😊 Let me catch up for a moment. Try again in a few seconds.";
      }
      if (err.message.includes('fetch') || err.message.includes('Network')) {
        return "I'm having trouble connecting to the AI service. Make sure Ollama is running, or try again later. Here's a quick tip: focus on building skills aligned with your target career! 🚀";
      }
      return `I encountered an issue: ${err.message}. Could you try asking a different way?`;
    }
  };

  // ─── CAREER MODE: Career quick action topics ───
  const CAREER_TOPICS = [
    { label: '💡 Skills', question: 'What skills should I learn for my career?' },
    { label: '📄 Resume', question: 'How can I improve my resume?' },
    { label: '🎯 Interviews', question: 'Tips for job interviews?' },
    { label: '🗺️ Career', question: 'Help me plan my career path' },
    { label: '💰 Salary', question: 'How do I negotiate salary?' },
    { label: '📚 Learning', question: 'What courses should I take to advance my career?' },
  ];

  const addCareerQuickActions = () => {
    if (!messagesContainer) return;
    const lastMsg = messagesContainer.lastElementChild;
    if (!lastMsg || !lastMsg.classList.contains('is-assistant')) return;
    const bubble = lastMsg.querySelector('.auth-message__bubble');
    if (!bubble) return;

    const container = document.createElement('div');
    container.className = 'auth-message__actions';

    CAREER_TOPICS.forEach(topic => {
      const btn = document.createElement('button');
      btn.className = 'auth-quick-action';
      btn.textContent = topic.label;
      btn.addEventListener('click', () => handleCareerQuickAction(topic.question));
      container.appendChild(btn);
    });

    bubble.appendChild(container);
    scrollToBottom();
  };

  // ─── CAREER MODE: Handle career quick action (uses streaming) ───
  const handleCareerQuickAction = async (question) => {
    if (isProcessing) return;
    addMessage(question, true);
    isProcessing = true;
    updateStatus('Thinking...');
    // Streaming handles its own bubble creation, so don't showTyping here
    await sendCareerMessageStream(question);
    isProcessing = false;
    updateStatus('Online');
  };

  // ─── HANDLE QUICK ACTION (auth mode) ───
  const handleQuickAction = (action) => {
    if (isProcessing) return;
    
    addMessage(action.label, true);

    if (action.link) {
      setTimeout(() => {
        window.location.href = action.link;
      }, 500);
      return;
    }

    isProcessing = true;
    showTyping();
    setTimeout(() => {
      addMessage(action.response);
      isProcessing = false;
    }, TYPING_DELAY + 400);
  };

  // ─── GET CONTEXT FOR CURRENT PAGE ───
  const getContext = () => {
    return KB[currentPage] || KB.login;
  };

  // ─── UPDATE STATUS ───
  const updateStatus = (text) => {
    if (statusText) {
      statusText.textContent = text;
    }
  };

  // ─── SWITCH MODE ───
  const switchMode = (mode) => {
    if (mode === currentMode) return;
    currentMode = mode;

    // Update mode button styles
    $$('.auth-mode-btn').forEach(btn => {
      const isActive = btn.getAttribute('data-mode') === mode;
      btn.classList.toggle('is-active', isActive);
      btn.setAttribute('aria-selected', isActive ? 'true' : 'false');
    });

    // Update placeholder
    if (inputField) {
      inputField.placeholder = mode === 'career'
        ? 'Ask about your career...'
        : 'Ask me anything...';
    }

    // Update header info
    const nameEl = document.querySelector('.auth-assistant__header-name');
    if (nameEl) {
      nameEl.textContent = mode === 'career' ? 'Career Advisor' : 'Prayash Guide';
    }
    const avatar = document.querySelector('.auth-assistant__avatar');
    if (avatar) {
      avatar.textContent = mode === 'career' ? '💼' : '🤖';
    }
    const header = document.querySelector('.auth-assistant__header');
    if (header) {
      header.style.background = mode === 'career'
        ? 'linear-gradient(135deg, var(--secondary-container, #8b4ef7), var(--secondary, #5c2cb8))'
        : 'linear-gradient(135deg, var(--primary-container, #4c1d95), var(--primary, #340075))';
    }

    // Clear messages and re-greet
    if (messagesContainer) {
      messagesContainer.innerHTML = '';
    }
    hasGreeted = false;
    updateStatus(mode === 'career' ? 'Career mode' : 'Online');
    if (isOpen) {
      setTimeout(() => sendGreeting(), 100);
    }
  };

  // ─── SEND GREETING (mode-aware) ───
  const sendGreeting = () => {
    if (hasGreeted || !messagesContainer) return;
    hasGreeted = true;

    if (currentMode === 'career') {
      // Career mode greeting — local welcome for instant response
      addMessage("👋 Hi! I'm your AI Career Advisor. I can help with:\n\n• Skill development & learning recommendations\n• Job search strategies & career advice\n• Resume improvement tips\n• Interview preparation\n• Salary & compensation questions\n\nWhat would you like to know?");
      addCareerQuickActions();
      isProcessing = false;
      return;
    }

    // Auth mode greeting — existing KB-based behavior
    showTyping();
    setTimeout(() => {
      const ctx = getContext();
      addMessage(ctx.greeting);
      
      if (ctx.actions && ctx.actions.length) {
        addActions(ctx.actions);
      }

      setTimeout(() => {
        if (ctx.security) {
          addMessage(ctx.security);
        }
      }, 1200);

      isProcessing = false;
    }, TYPING_DELAY + 200);
  };

  // ─── FIELD-LEVEL TIP ───
  const showFieldTip = (fieldName) => {
    const ctx = getContext();
    const tip = ctx.tips && ctx.tips[fieldName];
    if (!tip) return;

    // Find the closest field element
    const field = document.querySelector(`[data-field="${fieldName}"], #${fieldName}, [name="${fieldName}"]`)?.closest('.auth-field');
    if (!field) return;

    // Remove existing tip
    const existing = document.querySelector('.auth-context-tip');
    if (existing) existing.remove();

    const tipEl = document.createElement('div');
    tipEl.className = 'auth-context-tip';
    tipEl.textContent = '💡 ' + tip;

    // Position relative to the field
    field.style.position = 'relative';
    field.appendChild(tipEl);

    // Show with animation
    requestAnimationFrame(() => {
      tipEl.classList.add('is-visible');
    });

    // Auto-hide after 5 seconds
    setTimeout(() => {
      tipEl.classList.remove('is-visible');
      setTimeout(() => tipEl.remove(), 200);
    }, 5000);
  };

  // ─── HANDLE USER INPUT (mode-aware) ───
  const handleUserInput = async () => {
    if (!inputField) return;
    const text = inputField.value.trim();
    if (!text || isProcessing) return;

    inputField.value = '';
    isProcessing = true;

    // Add user message
    addMessage(text, true);
    showTyping();

    if (currentMode === 'career') {
      // Career mode: streaming API handles bubble creation & fallback internally
      updateStatus('Thinking...');
      await sendCareerMessageStream(text);
      isProcessing = false;
      updateStatus('Online');
      return;
    }

    // Auth mode: use KB-based contextual response
    const ctx = getContext();
    const response = generateResponse(text, ctx);
    // Simulate typing delay for natural feel
    setTimeout(() => {
      hideTyping();
      addMessage(response);
      if (ctx.actions && ctx.actions.length) {
        addActions(ctx.actions);
      }
      isProcessing = false;
    }, TYPING_DELAY + 300);
  };

  // ─── SIMPLE NLP: Generate contextual response ───
  const generateResponse = (input, ctx) => {
    const lower = input.toLowerCase().trim();
    
    // Common patterns
    if (/hi|hello|hey|greetings/i.test(lower)) {
      return `Hello! 👋 ${ctx.greeting.split('!')[0] || 'Welcome!'}`;
    }
    
    if (/thank|thanks|thx/i.test(lower)) {
      return "You're welcome! 😊 I'm here to help anytime. Got any other questions?";
    }

    if (/password|pw|pass/i.test(lower) && !/reset|forgot/i.test(lower)) {
      return "Looking for password tips? Here's what makes a great password:\n\n• At least 8 characters (more is better!)\n• Mix uppercase & lowercase\n• Include numbers & special characters\n• Use a passphrase like 'Coffee_Mug$42!'\n\n🔒 Never reuse passwords across different sites!";
    }

    if (/email|verify/i.test(lower)) {
      return "Email verification is important! It proves you own the email address and:\n✅ Enables password recovery\n✅ Prevents account takeovers\n✅ Keeps your career data safe\n\nCheck your inbox (and Spam folder!) for the 6-digit code.";
    }

    if (/oauth|google|github|linkedin|microsoft|social|single.?sign/i.test(lower)) {
      return "Social sign-in is super convenient! ✅\n\n• No extra password to remember\n• Uses your existing Google/GitHub security\n• Instant access — no email verification needed\n\nJust click any of the social buttons above to get started!";
    }

    if (/help|support|what can you do|options/i.test(lower)) {
      return "I can help you with:\n💬 Signing in or creating an account\n🔑 Resetting your password\n📧 Verifying your email\n🔒 Security tips & best practices\n\nWhat do you need help with?";
    }

    if (/security|safe|privacy|data/i.test(lower)) {
      return "🔒 **Security & Privacy at Prayash**\n\n" +
        "• Your analysis runs locally — no resume data is stored on our servers\n" +
        "• Passwords are hashed & salted (never stored in plain text)\n" +
        "• We never share your personal data with third parties\n" +
        "• Your session expires automatically for protection\n\n" +
        "Have specific concerns? Feel free to ask!";
    }

    if (/error|problem|issue|not working|stuck/i.test(lower)) {
      return "Let me help! Here are common fixes:\n\n1️⃣ **Can't log in?** Try resetting your password or use Google/GitHub sign-in\n2️⃣ **Didn't get the code?** Check Spam, wait 30s, then resend\n3️⃣ **Username taken?** Try adding numbers or initials\n4️⃣ **Still stuck?** The 🔗 'Forgot password' or Google sign-in options are your best backups!";
    }

    // Default: contextual fallback
    const ctxKeys = Object.keys(ctx.tips || {});
    if (ctxKeys.length > 0) {
      const randomTipKey = ctxKeys[Math.floor(Math.random() * ctxKeys.length)];
      const randomTip = ctx.tips[randomTipKey];
      return `Here's a helpful tip for this page: 💡\n\n${randomTip}\n\nIs there something specific I can help you with? Just ask! 😊`;
    }

    return "I'm your Prayash assistant! Here to help with sign-in, account creation, password issues, and more. What would you like to do? 😊";
  };

  // ─── TOGGLE PANEL ───
  const togglePanel = () => {
    isOpen = !isOpen;
    toggleBtn.classList.toggle('is-open', isOpen);
    panel.classList.toggle('is-visible', isOpen);

    if (isOpen) {
      // Clear unread dot
      const dot = document.querySelector('.unread-dot');
      if (dot) dot.classList.remove('is-visible');

      // Send greeting if not done
      if (!hasGreeted) {
        sendGreeting();
      }

      // Focus input
      setTimeout(() => inputField?.focus(), 300);
    }
  };

  // ─── MINIMIZE FROM HEADER ───
  const minimizePanel = () => {
    isOpen = false;
    toggleBtn.classList.remove('is-open');
    panel.classList.remove('is-visible');
  };

  // ─── Store observers for cleanup ───
  let _errorObserver = null;

  // ─── DETECT FIELD FOCUS ───
  const initFieldDetection = () => {
    // Map field IDs/names to tip keys
    const fieldMap = {
      'signup-name': 'name',
      'signup-username': 'username',
      'signup-email': 'email',
      'signup-phone': 'phone',
      'signup-password': 'password',
      'confirm-password': 'confirm',
      'terms-check': 'terms',
      'login-email': 'email',
      'login-password': 'password',
      'forgot-email': 'email',
      'new-password': 'password',
      'confirm-new-password': 'confirm',
    };

    // Pre-fill detection map based on current page
    const tips = getContext().tips || {};
    Object.keys(tips).forEach(key => {
      // Find matching element
      const el = document.querySelector(`[data-field="${key}"]`);
      if (el) {
        el.addEventListener('focus', () => {
          if (isOpen) showFieldTip(key);
        });
      }
    });

    // Also detect general field focus
    document.querySelectorAll('.auth-field__input, .otp-digit').forEach(input => {
      const id = input.id;
      const tipKey = fieldMap[id];
      if (tipKey && getContext().tips?.[tipKey]) {
        input.addEventListener('focus', () => {
          if (isOpen) showFieldTip(tipKey);
        });
      }
    });

    // Detect form errors and offer help
    const errorAlert = document.querySelector('.auth-error');
    if (errorAlert) {
      _errorObserver = new MutationObserver(() => {
        if (errorAlert.textContent.trim() && isOpen && !isProcessing) {
          const errorText = errorAlert.textContent.toLowerCase();
          let helpMsg = "I noticed an error! Let me help:";
          
          if (errorText.includes('password') && errorText.includes('match')) {
            helpMsg = "The passwords don't match. Make sure both fields are exactly the same — check for extra spaces at the end!";
          } else if (errorText.includes('invalid') || errorText.includes('credentials')) {
            helpMsg = "Hmm, those credentials didn't work. Double-check your email/username and password. Caps Lock is a common culprit! You can also try signing in with Google.";
          } else if (errorText.includes('email') && (errorText.includes('exist') || errorText.includes('taken'))) {
            helpMsg = "This email is already registered! Try signing in instead, or use the 'Forgot password' option if you've forgotten your credentials.";
          } else if (errorText.includes('code') || errorText.includes('otp')) {
            helpMsg = "The code wasn't accepted. Make sure you entered all 6 digits correctly. You can request a new code by clicking 'Resend'.";
          } else if (errorText.includes('lockout') || errorText.includes('attempt')) {
            helpMsg = "Too many failed attempts? No worries! You can:\n• Wait a few minutes and try again\n• Reset your password\n• Sign in with Google/GitHub instead";
          }

          addMessage(helpMsg);
        }
      });
      _errorObserver.observe(errorAlert, { childList: true, subtree: true, characterData: true });
    }
  };

  // ─── Cleanup observers ───
  const cleanupObservers = () => {
    if (_errorObserver) {
      _errorObserver.disconnect();
      _errorObserver = null;
    }
    if (idleTimer) {
      clearTimeout(idleTimer);
      idleTimer = null;
    }
  };

  // ─── DETECT PAGE CHANGES (form mode switch) ───
  const initPageDetection = () => {
    // Detect tab switches between login/signup
    document.querySelectorAll('.auth-tab').forEach(tab => {
      tab.addEventListener('click', () => {
        // Re-greet when switching pages
        hasGreeted = false;
      });
    });

    // Detect OTP auto-submit
    const otpCombined = document.getElementById('otp-combined');
    if (otpCombined) {
      const observer = new MutationObserver(() => {
        if (otpCombined.value.length === 6 && isOpen) {
          addMessage("All 6 digits entered! Checking your code... 🔍");
        }
      });
      observer.observe(otpCombined, { attributes: true, attributeFilter: ['value'] });
    }
  };

  // ─── IDLE DETECTION ───
  let idleTimer = null;
  const IDLE_TIMEOUT = 30000; // 30 seconds

  const resetIdleTimer = () => {
    if (idleTimer) clearTimeout(idleTimer);
    if (isOpen) {
      idleTimer = setTimeout(() => {
        if (isOpen && !isProcessing) {
          addMessage("Still here? 👋 Need any help with the form? I'm here if you have questions!");
        }
      }, IDLE_TIMEOUT);
    }
  };

  const initIdleDetection = () => {
    ['mousemove', 'keydown', 'touchstart', 'click', 'scroll'].forEach(evt => {
      document.addEventListener(evt, resetIdleTimer);
    });
  };

  // ─── INIT ───
  const init = (options = {}) => {
    currentPage = options.page || 'login';

    // Cache DOM references
    toggleBtn = document.getElementById('auth-assistant-toggle');
    panel = document.getElementById('auth-assistant-panel');
    messagesContainer = document.getElementById('auth-assistant-messages');
    inputField = document.getElementById('auth-assistant-input');
    sendBtn = document.getElementById('auth-assistant-send');
    statusText = document.querySelector('[data-auth-status-text]');
    const minimizeBtn = document.getElementById('auth-assistant-minimize');

    if (!toggleBtn || !panel || !messagesContainer) {
      console.warn('AuthAssistant: Required DOM elements not found.');
      return;
    }

    // Restore career session from localStorage
    try {
      const saved = localStorage.getItem(CAREER_SESSION_KEY);
      if (saved) careerSessionId = saved;
    } catch (_) {}

    // Set up event listeners
    toggleBtn.addEventListener('click', togglePanel);
    if (minimizeBtn) minimizeBtn.addEventListener('click', minimizePanel);
    if (sendBtn) sendBtn.addEventListener('click', handleUserInput);
    if (inputField) {
      inputField.addEventListener('keydown', (e) => {
        if (e.key === 'Enter' && !e.shiftKey) {
          e.preventDefault();
          handleUserInput();
        }
      });
    }

    // Mode button listeners
    $$('.auth-mode-btn').forEach(btn => {
      btn.addEventListener('click', () => {
        const mode = btn.getAttribute('data-mode');
        if (mode) switchMode(mode);
      });
    });

    // Open automatically on first visit (after short delay)
    const dismissed = localStorage.getItem(STORAGE_KEY);
    if (!dismissed) {
      setTimeout(() => {
        if (document.querySelector('.auth-error')) {
          togglePanel();
        }
      }, 1500);
    }

    // Initialize features
    initFieldDetection();
    initPageDetection();
    initIdleDetection();

    // Auto-open on mobile if there's an error
    if (window.innerWidth <= 520 && document.querySelector('.auth-error')) {
      setTimeout(togglePanel, 2000);
    }

    // Clean up on page unload
    window.addEventListener('beforeunload', cleanupObservers);
    // Use pagehide instead of unload — unload is deprecated and triggers CSP/permissions policy violations
    window.addEventListener('pagehide', cleanupObservers);

    // Make toggle button accessible
    toggleBtn.setAttribute('aria-label', 'Toggle auth assistant');

    // Expose for debugging
    window.AuthAssistant = {
      open: () => { if (!isOpen) togglePanel(); },
      close: () => { if (isOpen) togglePanel(); },
      sendMessage: async (msg) => {
        if (inputField) {
          inputField.value = msg;
          try {
            await handleUserInput();
          } catch (_) {
            // Prevent unhandled promise rejections from async handler
          }
        }
      },
      dismiss: () => {
        localStorage.setItem(STORAGE_KEY, 'true');
        toggleBtn.style.display = 'none';
        panel.style.display = 'none';
      }
    };

    console.log('Prayash Auth Assistant ready 🤖');
  };

  // ─── EXPORT ───
  window.AuthAssistant = window.AuthAssistant || { init };

})();
