# Conversational AI Flow — Prayash Auth Assistant

## Overview

The conversational AI auth assistant is a floating chat widget that guides users through registration, login, password recovery, and email verification using friendly, step-by-step natural language interactions. It augments the existing form-based auth system with human-like guidance, security tips, and proactive suggestions.

---

## 1. Welcome & Onboarding

### Entry Point
When a user visits any auth page (`/login`, `/signup`, `/forgot-password`, `/verify-otp`, `/reset-password`), the chat assistant greets them with a contextual message based on the current page.

**Sign In Page Greeting:**
> "Hi there! 👋 Welcome back to Prayash. I can help you sign in, or if you're new here, you can create an account. What would you like to do?"

**Sign Up Page Greeting:**
> "Hey! 🎉 Ready to take charge of your career? I'll walk you through creating your account step by step. It only takes a minute!"

**Forgot Password Greeting:**
> "No worries! 😊 I'll help you reset your password. Let's get you back into your account."

### User Response Options
- "Sign in" → Guides to login form, highlights key fields
- "Create account" → Guides to signup, explains each field
- "Sign in with Google/GitHub/LinkedIn/Microsoft" → Explains OAuth benefits
- "I forgot my password" → Guides to forgot password flow
- "What is Prayash?" → Brief platform description with value props

---

## 2. Sign Up Flow (Conversational)

### Step 1: Full Name
> "Let's start with your name! What's your full name?"
> *(User types or fills field)*
> "Great, nice to meet you, [Name]! ✅"

**Security Tip:** "We only use your name for your profile — it won't be shared publicly without your permission."

### Step 2: Username
> "Now, pick a username. This is how others might find you on Prayash. It should be at least 4 characters and can include letters, numbers, and underscores."

**Preventative:** If the username is taken or invalid:
> "That username is already taken! How about [suggestion1] or [suggestion2]?"
> or
> "Usernames can only have letters, numbers, and underscores — no spaces or special characters."

### Step 3: Email Address
> "What email address would you like to use? This is where we'll send your verification code and important updates."

**Security Tip:** "Make sure it's an email you have access to — you'll need to verify it in the next step!"

**Preventative — Common Email Typos:**
> "Did you mean **user@gmail.com**? I noticed you typed **user@gmal.com**." *(if pattern detected)*

### Step 4: Phone Number (Optional)
> "Want to add a phone number? It's optional, but it gives you an extra way to recover your account if you ever get locked out. 📱"

**Security Tip:** "Adding a phone is one of the best ways to protect your account — it's like having a backup key! 🗝️"

### Step 5: Password Creation
> "Time to create a strong password! Here's what makes a good one:
> • At least **8 characters** — longer is better!
> • Mix of **uppercase** (A-Z) and **lowercase** (a-z)
> • At least **one number** (0-9)
> • At least **one special character** (!@#$%^ etc.)

> As you type, I'll show you how strong your password is getting!"

**Real-time Feedback:**
- "Great start! Try adding an uppercase letter." (when only lowercase)
- "Almost there! Just need a special character." (when close)
- "Excellent! That's a very strong password! 💪" (when all criteria met)

**Security Tip:** "Pro tip: Use a passphrase like 'BlueElephant$Jump42!' — it's strong AND memorable. Avoid using your name, birthdate, or common words."

**Preventative — Common Pitfalls:**
> "I notice you're using '[name123]' — that contains your name, which makes it easier to guess. Want to try something different?"
> "The password you entered is commonly used in data breaches. Please choose something more unique."

### Step 6: Confirm Password
> "One more step! Please type your password again to confirm."

> (If mismatch) "The passwords don't match — let's try again. Make sure there are no extra spaces!"
> (If match) "Perfect, they match! ✅"

### Step 7: Terms & Privacy
> "Last step! Please agree to our Privacy Policy and Terms of Service to create your account."

**Security Tip:** "We take your privacy seriously. Your resume data stays on your device during analysis — we never share your personal information."

### Step 8: Account Created 🎉
> "You're all set, [Name]! Your account has been created. We've sent a verification code to **[email]** — check your inbox!"

---

## 3. Email Verification Flow

### After Sign Up
> "I've sent a **6-digit code** to your email. It expires in **10 minutes**, so check your inbox soon!"

**If code entered correctly:**
> "Email verified! ✅ Welcome to Prayash, [Name]! Let's get started on your career journey! 🚀"

**If wrong code:**
> "Hmm, that code doesn't seem right. Double-check the email we sent — it's a 6-digit number. You have 5 attempts before the code resets."

**If code expired:**
> "The code expired! No worries — I can send you a new one. Just click 'Resend' below."

**Resend confirmation:**
> "Fresh code sent! Check your inbox — it might take a minute or two. Don't forget to check your spam folder! 📬"

**Security Tip:** "Prayash will never text or call asking for your verification code. Only enter codes on this website."

---

## 4. Login Flow

### Standard Login
> "Welcome back! Enter your email or username and password to sign in."

**Success:**
> "Welcome back, [Name]! Great to see you again. Ready to continue your career journey? 🚀"

**Invalid credentials:**
> "That email/username and password combination didn't work. Let's try again — you have **[N] attempt(s)** remaining."

**Lockout warning:**
> "There have been too many failed login attempts. For security, please wait **5 minutes** before trying again. 
> 
> In the meantime, here are some options:
> • Reset your password
> • Sign in with Google/GitHub
> • Check Caps Lock — passwords are case-sensitive!"

**Security Tip:** "Always check that Caps Lock is off and you're on the real **prayash.app** website before entering your password."

### Post-Verification Login (unverified email)
> "Your email hasn't been verified yet! I've sent a new code to **[email]** — let's get that sorted first."

---

## 5. Forgot Password Flow

### Step 1: Email Entry
> "No problem! Enter the email address associated with your account, and I'll send a reset code."

**Anti-enumeration (always show):**
> "If that email is in our system, you'll receive a 6-digit code shortly."

### Step 2: Check Email
> "Check your inbox for the reset code! It expires in 10 minutes. 
> **Pro tip:** Check your **Spam** or **Promotions** folder if you don't see it."

### Step 3: Enter Code (via reset_password page)
> "Got the code? Enter the 6 digits and I'll verify it for you."

**Success:**
> "Code verified! ✅ Now let's create a new password."

### Step 4: New Password
> "Choose a new password. Remember:
> • At least 8 characters
> • Mix of uppercase & lowercase
> • Include a number & special character
> 
> And please don't reuse a password you've used elsewhere! 🔐"

**Success:**
> "Password reset complete! ✅ You can now sign in with your new password."

**Security Tip:** "After resetting your password, make sure to log out of any other devices where you might still be logged in."

---

## 6. OAuth Alternative Prompts

### When to Suggest OAuth
1. **After failed login attempts** — "Having trouble? You can sign in instantly with Google or GitHub instead!"
2. **During sign up** — "Prefer not to create another password? Sign up with Google, GitHub, LinkedIn, or Microsoft — one click and you're in!"
3. **On the login page idle** — "No account yet? Sign up in just 10 seconds with Google!"

### OAuth Benefits (as explained by the assistant)
> "Using Google or GitHub to sign in means:
> ✅ One fewer password to remember
> ✅ Already verified — no email confirmation needed
> ✅ Uses your existing security (2FA, etc.)
> ✅ Instant access — no waiting for emails!"

### OAuth Unconfigured Notice
> "Google sign-in isn't available right now — the admin needs to set up OAuth keys. You can still sign up with email!"

---

## 7. Preventative Measures & Proactive Tips

### Common Issues & Solutions

| Issue | Preventative Tip |
|-------|-----------------|
| Weak password | Real-time strength meter with visual feedback |
| Password reuse | "This might be a password you use elsewhere — consider a unique one for Prayash" |
| Email typos | "Did you mean [correction]?" for common domains (gmal→gmail, yaho→yahoo) |
| Caps Lock on | "Your Caps Lock is on!" detection on password fields |
| Session timeout | "You've been inactive for a while — your session may expire soon" |
| Browser password save | "Let your browser save your password so you don't forget it!" |

### Security Awareness Tips (rotated randomly)
> 🔒 "Did you know? Using **2-factor authentication** adds an extra layer of security to your account."
> 🔒 "Prayash will never ask for your password via email or phone."
> 🔒 "Check for the padlock icon 🔒 in your browser bar to make sure you're on the real site."
> 🔒 "Use a **password manager** to generate and store strong, unique passwords."
> 🔒 "Your career data is valuable — treat your account credentials with the same care as your bank login."

### Guided Recovery Options
When a user struggles:
> "Here are some ways to get back into your account:
> 1. **Reset your password** — we'll email you a code
> 2. **Sign in with Google** — if your email is the same
> 3. **Sign in with GitHub** — if you connected it earlier
> 4. **Contact support** — if nothing else works"

---

## 8. Message Timing & Context Awareness

| User Action | Assistant Response |
|-------------|-------------------|
| Page loads | Contextual greeting (1.5s delay) |
| User focuses a field | Brief tip about that field |
| User types | Validation hints (300ms debounce) |
| User blurs a field | Validation feedback if empty/error |
| Form submission (success) | Congratulations + next steps |
| Form submission (error) | Friendly error + suggestion |
| OTP verification | Real-time digit-by-digit guidance |
| 30s idle | Gentle nudge: "Need any help?" |
| 60s idle | Expanded help options |
| Field interaction | Context-aware mini-tips |

---

## 9. Chat Widget UI States

| State | Visual |
|-------|--------|
| **Collapsed** | Floating pill/circle button "💬" bottom-right |
| **Expanded** | Chat panel slides up, shows header + messages + input |
| **Typing** | Animated dots "..."
| **Context tip** | Small inline popup near active field |
| **Minimized** | Panel shrinks to small bar with latest message preview |

---

## 10. Integration Points

| Auth Page | Assistant Context | Primary Goal |
|-----------|------------------|------------|
| `/login` | Sign-in guidance | Help users log in or suggest alternatives |
| `/signup` | Registration walkthrough | Collect all fields with validation help |
| `/verify-otp` | Code entry guidance | Help with OTP entry, resend, errors |
| `/forgot-password` | Password recovery | Walk through email→code→password flow |
| `/reset-password` | New password creation | Guide strong password creation |

---

## 11. Implementation Architecture

```
┌─────────────────────────────────────────────────┐
│              Flask Backend (app.py)               │
│  POST /api/auth-assistant/converse               │
│  → Accepts: { message, context, page, fields }   │
│  → Returns: { reply, tips, actions }             │
└──────────────────────┬──────────────────────────┘
                       │
┌──────────────────────▼──────────────────────────┐
│           Chat Assistant (JavaScript)             │
│  - Manages conversation state                    │
│  - Detects page context & form state             │
│  - Provides field-level tips                     │
│  - Handles message templates & responses         │
│  - Integrates with existing form validation      │
└──────────────────────┬──────────────────────────┘
                       │
┌──────────────────────▼──────────────────────────┐
│            Auth Pages (Jinja2 Templates)          │
│  - Includes chat widget HTML                     │
│  - Loads assistant CSS & JS                      │
│  - Passes page context to assistant              │
└─────────────────────────────────────────────────┘
```
