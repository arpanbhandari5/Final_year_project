# Free Frontend Animation, Styling, and UI/UX Tools for Final_year_project

## 1. Recommendation for this project

Final_year_project currently uses Flask, Jinja templates, vanilla JavaScript, and CSS. The safest approach is to improve the existing frontend without migrating to React, Tailwind, or a new component framework.

Use this order:

1. **Native CSS design tokens and transitions** for most styling and micro-interactions.
2. **Web Animations API** for small JavaScript-controlled animations.
3. **Open Props** for optional free design tokens, easing, sizes, colors, and animation utilities.
4. **Lucide or Heroicons** for consistent open-source icons.
5. **Playwright and axe-core** for browser and accessibility validation.
6. **Lighthouse** for performance and accessibility audits.
7. **Figma Starter or Education** for wireframes and design review.
8. **GSAP** only when a complex timeline, SVG, or scroll sequence genuinely needs it.
9. **Storybook** only if the project grows into a reusable component library; it is optional for the current Jinja/vanilla stack.

Do not add all of these at once. Begin with native CSS, Playwright, axe-core, and Lighthouse. Add Open Props or GSAP only when a concrete need exists.

---

## 2. Tool comparison

| Tool | Free status | Best use in this project | Recommendation |
|---|---|---|---|
| CSS transitions/keyframes | Browser-native and free | Buttons, cards, modals, progress states, loading | Use first |
| Web Animations API | Browser-native and free | JS-controlled reveal, score ring, staggered cards | Use before a library |
| Open Props | Open-source CSS properties and utilities | Design tokens, spacing, shadows, colors, easings, animation presets | Recommended optional addition |
| GSAP | Core library currently free under its published license; verify license for your use | Complex timelines, SVG charts, scroll storytelling | Optional, not default |
| Anime.js | Free/open-source animation library | Lightweight sequenced DOM/SVG animation | Alternative to GSAP, not both |
| Motion | Free/open-source ecosystem with JS animation APIs; strongest fit in React/Vue | Interactive gestures and framework apps | Not needed for current vanilla stack |
| Lucide | Free/open-source icon set | UI icons with consistent stroke style | Recommended |
| Heroicons | Free/open-source icon set | Alternative icon set | Choose either Lucide or Heroicons |
| Figma Starter | Free with limits | Wireframes, user flows, design tokens, feedback | Recommended |
| Figma Education | Free for eligible students/educators after verification | More education features | Apply if eligible |
| Storybook | Free/open-source | Isolated components and visual states | Optional later |
| Playwright | Free/open-source | End-to-end browser tests and screenshots | Strongly recommended |
| `@axe-core/playwright` | Free/open-source | Automated accessibility scans | Strongly recommended |
| Lighthouse | Free/open-source | Performance, accessibility, SEO, best-practice audit | Strongly recommended |
| Lighthouse CI | Free/open-source | Regression checks in GitHub Actions | Add after stable pages |
| Open Props CDN | Free usage option, but external CDN creates runtime dependency | Quick experiment | Prefer local/pinned copy before production |
| Tailwind CSS | Free/open-source | Utility-first styling | Do not migrate the current project now |
| Bootstrap | Free/open-source | Component framework | Do not introduce unless the existing CSS is replaced deliberately |

Official references:

- [MDN Web Animations API](https://developer.mozilla.org/en-US/docs/Web/API/Web_Animations_API)
- [Open Props](https://open-props.style/)
- [GSAP](https://gsap.com/)
- [Figma pricing FAQ](https://www.figma.com/pricing-faq/)
- [Storybook documentation](https://storybook.js.org/docs)
- [Chrome Lighthouse](https://developer.chrome.com/docs/lighthouse/overview)
- [Playwright accessibility testing](https://playwright.dev/docs/accessibility-testing)

---

## 3. What to improve in this particular project

### 3.1 Landing page

Current problem: the landing page exposes many surfaces before the first useful result.

Improve it to show:

1. One clear value statement.
2. One intent question.
3. Persona or target-role selection.
4. Resume upload or paste area.
5. Optional target role.
6. One primary analysis button.
7. Short privacy reassurance.
8. A small preview of the resulting Career Plan.

Animations:

- Fade/slide the upload panel in once.
- Animate the primary button on hover and focus.
- Show a clear progress state after analysis starts.
- Do not animate every marketing card.
- Do not use a continuously moving background behind the upload form.

### 3.2 Workspace and analysis result

Create a hierarchy:

1. Recommended direction
2. Why this direction was suggested
3. Confidence and freshness
4. Do this next
5. Skill gaps
6. Learning routes
7. Application readiness
8. Evidence and methodology details

Animations:

- Reveal the primary recommendation first.
- Reveal supporting sections after the analysis state is complete.
- Use a small stagger for cards, not a long cinematic sequence.
- Animate progress bars only when the value changes.
- Make the evidence drawer open/close without layout jumps.

### 3.3 Skills-gap page

Improve the page with:

- Required, preferred, developing, and optional skill categories.
- Skill evidence excerpt.
- Source badge.
- Confidence badge.
- One action per gap.
- “Replace recommendation” control.
- “Mark as already known” control.
- “Add evidence” control.

Use color plus text/icon labels. Never communicate state by color alone.

### 3.4 Learning roadmap

Replace a flat list with:

- Fastest practical route
- Credential route
- Foundation route

Each route should show:

- Estimated effort
- Prerequisites
- Skills addressed
- Course/project/practice type
- Expected outcome
- Re-check condition
- Progress state

Animations:

- Expand prerequisites on demand.
- Use a subtle connecting line for a learning path.
- Animate completion checkmarks briefly.
- Respect reduced-motion preferences.

### 3.5 Career chat

Keep chat contextual rather than decorative. Add quick actions such as:

- Explain this score
- Show resume evidence
- Suggest another role
- Replace this course
- Turn this gap into a project
- Prepare me for this job

Animate only:

- Message arrival
- Typing/loading state
- Expand/collapse of source details

Do not use a floating animated bubble that constantly distracts the user.

### 3.6 Authentication and forms

Improve:

- Inline validation
- Clear error placement
- Password visibility toggle
- Password-strength explanation
- Focus states
- Loading state on submit
- Disabled state after submit
- OTP resend countdown
- Keyboard and screen-reader announcements

Avoid shaking invalid forms. A short border/color transition and useful message are better.

---

## 4. Design system to create before styling pages

Create one project-owned design specification, for example:

```text
docs/DESIGN_SYSTEM.md
```

Define:

- Brand colors
- Surface colors
- Text colors
- Border colors
- Focus color
- Error/warning/success colors
- Typography scale
- Spacing scale
- Border radii
- Shadow levels
- Button variants
- Badge variants
- Card variants
- Form controls
- Modal behavior
- Toast behavior
- Empty states
- Loading states
- Motion rules
- Reduced-motion behavior
- Breakpoints
- Icon rules

Do not define a different shade or radius on every page. Use tokens.

Example token layer for the existing CSS:

```css
:root {
  --color-primary: #6d5dfc;
  --color-primary-strong: #5748e8;
  --color-surface: #ffffff;
  --color-surface-soft: #f7f7fb;
  --color-text: #171721;
  --color-text-muted: #686879;
  --color-border: #e6e6ef;
  --color-success: #16855b;
  --color-warning: #a96d00;
  --color-danger: #c33b4a;
  --radius-sm: 0.5rem;
  --radius-md: 0.875rem;
  --radius-lg: 1.25rem;
  --shadow-sm: 0 1px 3px rgb(20 20 40 / 0.08);
  --shadow-md: 0 12px 30px rgb(20 20 40 / 0.12);
  --space-1: 0.25rem;
  --space-2: 0.5rem;
  --space-3: 0.75rem;
  --space-4: 1rem;
  --space-6: 1.5rem;
  --space-8: 2rem;
  --motion-fast: 140ms;
  --motion-normal: 220ms;
  --motion-slow: 420ms;
  --ease-standard: cubic-bezier(.2, .8, .2, 1);
}

[data-theme="dark"] {
  --color-surface: #15151e;
  --color-surface-soft: #1d1d29;
  --color-text: #f6f6fb;
  --color-text-muted: #b6b6c7;
  --color-border: #343447;
}
```

Use existing project tokens if they already exist. Do not create a second competing token system.

---

## 5. Native CSS animation patterns

### 5.1 Button interaction

```css
.button {
  transition:
    transform var(--motion-fast) var(--ease-standard),
    background-color var(--motion-fast) ease,
    box-shadow var(--motion-fast) ease;
}

.button:hover {
  transform: translateY(-1px);
  box-shadow: var(--shadow-sm);
}

.button:active {
  transform: translateY(0);
}

.button:focus-visible {
  outline: 3px solid color-mix(in srgb, var(--color-primary) 45%, transparent);
  outline-offset: 3px;
}
```

### 5.2 Reveal animation

```css
.reveal {
  opacity: 0;
  transform: translateY(0.75rem);
  animation: reveal-in var(--motion-slow) var(--ease-standard) forwards;
}

@keyframes reveal-in {
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

@media (prefers-reduced-motion: reduce) {
  .reveal {
    opacity: 1;
    transform: none;
    animation: none;
  }
}
```

### 5.3 Staggered cards

Use a maximum of 3–5 cards in a staggered group. Do not apply a large delay to every page element.

```css
.result-card:nth-child(1) { --delay: 0ms; }
.result-card:nth-child(2) { --delay: 60ms; }
.result-card:nth-child(3) { --delay: 120ms; }

.result-card {
  animation-delay: var(--delay, 0ms);
}
```

### 5.4 Expandable evidence drawer

Prefer native `<details>` when possible:

```html
<details class="evidence-drawer">
  <summary>Show evidence and source</summary>
  <div class="evidence-drawer__content">
    Resume evidence → role requirement → Prayash inference
  </div>
</details>
```

This improves keyboard and screen-reader behavior without custom JavaScript.

### 5.5 Loading state

```css
.skeleton {
  min-height: 1rem;
  border-radius: var(--radius-sm);
  background:
    linear-gradient(90deg,
      var(--color-surface-soft) 25%,
      color-mix(in srgb, var(--color-surface-soft) 65%, white) 50%,
      var(--color-surface-soft) 75%);
  background-size: 200% 100%;
  animation: skeleton-shimmer 1.2s linear infinite;
}

@keyframes skeleton-shimmer {
  to { background-position: -200% 0; }
}

@media (prefers-reduced-motion: reduce) {
  .skeleton { animation: none; }
}
```

Do not use skeletons for instant operations. Use them only when the wait is meaningful.

---

## 6. Web Animations API for vanilla JavaScript

Use the native API when the animation must be started from JavaScript.

```js
function revealAnalysisSection(element) {
  if (!element || window.matchMedia('(prefers-reduced-motion: reduce)').matches) {
    element?.removeAttribute('hidden');
    return;
  }

  element.removeAttribute('hidden');
  element.animate(
    [
      { opacity: 0, transform: 'translateY(12px)' },
      { opacity: 1, transform: 'translateY(0)' },
    ],
    {
      duration: 360,
      easing: 'cubic-bezier(.2, .8, .2, 1)',
      fill: 'both',
    },
  );
}
```

Use it for:

- Analysis sections appearing after SSE completion
- Evidence drawers if native `<details>` is insufficient
- Short score-ring updates
- Progress changes
- Toast entry and exit

Do not use it for:

- Essential information that would be hidden from users who disable motion
- Long decorative page sequences
- Rapidly moving text
- Infinite background effects

---

## 7. Open Props setup

Open Props is useful because it supplies reusable CSS custom properties for colors, sizes, easings, gradients, and animations. Its official documentation supports CDN and npm imports.

### Safer local setup

Prefer installing and pinning it locally if it becomes part of production:

```bash
npm init -y
npm install open-props
```

Then either copy only the required variables into the project CSS or import selected files through the project’s build process. Because the current application has no frontend package file, do not introduce npm only for a one-line CDN import without deciding how assets are pinned and deployed.

### Quick prototype option

For a temporary local experiment, add selected imports in a development stylesheet:

```css
@import "https://unpkg.com/open-props/easings.min.css";
@import "https://unpkg.com/open-props/sizes.min.css";
@import "https://unpkg.com/open-props/animations.min.css";
```

Do not leave an unpinned external CDN dependency in a production release without considering:

- Offline/PWA behavior
- Content Security Policy
- Network failure
- Version pinning
- Supply-chain risk

Recommended use in this project: copy or recreate only the small subset of tokens needed for spacing, shadows, easings, and animation. Keep the application’s existing brand tokens as the source of truth.

---

## 8. GSAP and Anime.js decision

### Use GSAP when

- A role-match or learning-path SVG needs a complex timeline.
- A multi-step onboarding sequence must be choreographed.
- An interactive chart or scroll narrative needs coordinated motion.
- Native CSS/Web Animations become difficult to maintain.

### Do not use GSAP when

- A button needs a hover state.
- A card needs a simple reveal.
- A modal needs a fade.
- A skeleton needs a shimmer.
- A progress bar needs a simple width transition.

### If adding GSAP

```bash
npm install gsap
```

Keep animation code in one module, for example:

```text
static/js/motion.js
```

Use a small public API:

```js
export function animatePlanIntro(root) {}
export function animateProgressChange(element, value) {}
export function destroyMotion(root) {}
```

Always implement reduced motion and cleanup. Do not scatter GSAP calls throughout templates.

### Anime.js alternative

Choose Anime.js instead of GSAP if you want a smaller, straightforward DOM/SVG sequencing library. Do not install both libraries. For this project, native CSS/Web Animations should be tried first.

---

## 9. Icons and visual assets

### Recommended icons

Choose one icon library:

- **Lucide** for a clean stroke-based interface.
- **Heroicons** for a compact outline/solid pair.

Use icons as supporting labels, not as the only label. Provide accessible names for icon-only buttons:

```html
<button class="icon-button" type="button" aria-label="Show evidence">
  <!-- SVG icon -->
</button>
```

Avoid mixing several icon styles. The current project should use one stroke width, one visual size scale, and one alignment rule.

### Decorative assets

Use restrained decorations:

- Abstract gradients in CSS
- Small geometric background shapes
- Simple inline SVG illustrations
- Open-source illustrations with verified licenses

Avoid adding stock-image-heavy sections to a career-analysis product. The strongest visual material is the user’s plan, evidence, progress, and actions.

---

## 10. Figma workflow

Figma Starter is suitable for individual work and small collaboration with plan limits. Eligible students may apply for Figma Education.

Create one Figma file with no more than three main pages if using the free Starter collaboration limits:

1. **Flows** — onboarding, analysis, learning, applications
2. **Design system** — tokens, components, states
3. **Screens** — desktop/mobile designs

Design these states before coding:

- Empty
- Loading
- Success
- Error
- Low evidence
- No matching role
- Existing user
- New user
- Mobile navigation open
- Dark mode
- Reduced motion
- Long text
- Failed upload
- External model unavailable
- No course match
- Completed learning item
- Follow-up overdue

Use Figma to decide hierarchy and content before asking Copilot/Codex to edit CSS. Export only the assets actually needed. Do not export a whole design as a replacement for semantic HTML.

---

## 11. Storybook decision

Storybook is free/open source and supports Web Components, but the current project is server-rendered Jinja plus vanilla JavaScript. Introducing Storybook now may add more build tooling than value.

Use Storybook later if:

- The project has 15–20 reusable UI components.
- Multiple pages use the same cards, badges, dialogs, forms, and progress components.
- You want isolated testing for loading/error/empty states.
- You are willing to model UI pieces as Web Components or move to a component-oriented frontend.

Do not install Storybook just for a visual redesign of the current pages. Playwright screenshots and Figma are sufficient initially.

---

## 12. Quality workflow with Playwright, axe-core, and Lighthouse

### Install browser testing

From the repository root:

```bash
npm init -y
npm install -D @playwright/test
npx playwright install chromium
npm install -D @axe-core/playwright
```

Create:

```text
playwright.config.ts
e2e/
  smoke.spec.ts
  accessibility.spec.ts
```

### Example smoke test

```ts
import { test, expect } from '@playwright/test';

test('landing page presents the main analysis action', async ({ page }) => {
  await page.goto('http://127.0.0.1:5000/');
  await expect(page.getByRole('heading', { name: /career|future/i })).toBeVisible();
  await expect(page.getByRole('button', { name: /analy/i })).toBeVisible();
});
```

### Example accessibility scan

```ts
import { test, expect } from '@playwright/test';
import AxeBuilder from '@axe-core/playwright';

test('landing page has no automatically detectable WCAG violations', async ({ page }) => {
  await page.goto('http://127.0.0.1:5000/');
  const results = await new AxeBuilder({ page })
    .withTags(['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa'])
    .analyze();
  expect(results.violations).toEqual([]);
});
```

Automated accessibility testing is not enough. Also test keyboard navigation and real screen-reader behavior manually.

### Lighthouse

Use Chrome DevTools first because authenticated workspace pages can be audited after login:

1. Start the Flask application.
2. Open the desired page in Chrome.
3. Open DevTools.
4. Open Lighthouse.
5. Run Performance, Accessibility, Best Practices, and SEO.
6. Save the report as JSON or HTML.
7. Record the date, viewport, page, and build commit.

Optional CLI:

```bash
npm install -g lighthouse
lighthouse http://127.0.0.1:5000/ --view
```

Do not chase a perfect score by removing useful functionality. Fix real issues first:

- Large blocking assets
- Missing labels
- Poor contrast
- Layout shifts
- Excessive JavaScript
- Unoptimized images
- Missing document title/meta
- Inaccessible interactive controls

---

## 13. Recommended animation budget

Use motion to communicate state, not to decorate every element.

| Interaction | Duration target |
|---|---:|
| Button hover/focus | 100–160 ms |
| Tooltip | 120–180 ms |
| Toast entry | 180–240 ms |
| Modal entry | 180–260 ms |
| Card reveal | 240–420 ms |
| Page section reveal | 300–500 ms |
| Progress update | 400–800 ms |
| Skeleton shimmer | 1.0–1.4 s loop |
| Large background animation | Avoid or pause |

Rules:

- Animate `transform` and `opacity` where possible.
- Avoid animating layout-heavy properties such as `width`, `height`, `top`, and `left` for large regions.
- Keep animations interruptible.
- Do not delay access to critical information.
- Respect `prefers-reduced-motion: reduce`.
- Never use flashing content.
- Do not auto-play sound.

---

## 14. Step-by-step implementation sequence

### Step 1 — Record the current UI

Before changes:

- Start Flask.
- Capture screenshots of `/`, `/workspace`, `/workspace/skills-gap`, `/login`, `/signup`, and `/privacy`.
- Capture desktop and mobile widths.
- Run Lighthouse.
- Run the current test suite.
- Commit or tag a visual baseline.

### Step 2 — Create design tokens

- Inspect the current CSS for existing colors and spacing.
- Move repeated values into one token block.
- Add dark-mode token overrides.
- Add motion duration and easing tokens.
- Add focus, error, warning, and success tokens.
- Do not change layout yet.

### Step 3 — Improve shared components

Start with:

- Buttons
- Form controls
- Cards
- Badges
- Alerts
- Toasts
- Progress indicators
- Loading/skeleton states
- Modal/dialog
- Navigation

Test these shared styles on every page.

### Step 4 — Simplify the landing page

- Remove duplicate mode controls.
- Move secondary content below the first analysis action.
- Add one intent question.
- Keep privacy reassurance close to upload.
- Add a clear empty/loading/error flow.

### Step 5 — Improve result hierarchy

- Add the recommended-direction section.
- Add confidence/freshness labels.
- Add the prioritized next action.
- Add evidence drawers.
- Move methodology details into progressive disclosure.

### Step 6 — Add restrained animation

- Add CSS hover/focus states.
- Add section reveals.
- Add loading states.
- Add progress transitions.
- Add reduced-motion fallback.
- Avoid adding GSAP until native motion is insufficient.

### Step 7 — Test accessibility and responsiveness

- Keyboard pass.
- Focus pass.
- Axe scan.
- Lighthouse audit.
- Playwright screenshots at mobile/tablet/desktop.
- Fix overflow and long-text issues.

### Step 8 — Checkpoint

```bash
git diff --check
pytest -q
python -m compileall -q .
npx playwright test
npm run lint --if-present
git add static templates docs package.json package-lock.json playwright.config.ts e2e
git commit -m "ui: improve design system, motion, and accessibility"
git tag -a checkpoint-phase-08-ui-green -m "UI and accessibility checkpoint"
git push origin develop/final-year-enhancement --tags
```

---

## 15. Recommended free tool setup for VS Code

Install:

- Python
- Pylance
- Python Debugger
- Ruff
- Playwright Test for VS Code
- GitHub Copilot if already available
- Continue optionally

Use Chrome DevTools Lighthouse rather than adding a Lighthouse extension immediately. Use Figma for design planning. Use native CSS and Web Animations API before adding GSAP.

For MCP, Playwright MCP is optional. Only install from a trusted source, use workspace scope, do not hardcode secrets, and disable it when browser automation is not needed.

---

## 16. Copilot/Codex prompt for UI improvement

```text
You are improving the existing Final_year_project Flask/Jinja/vanilla-JavaScript frontend. Do not migrate to React, Tailwind, Bootstrap, or another frontend framework. Do not rewrite the whole CSS file. Preserve existing backend routes and response formats.

Goal:
Create a calmer, more accessible, action-centered Career Plan interface with one clear next action, progressive disclosure, trustworthy evidence labels, and restrained motion.

Before editing:
1. Inspect templates/base.html, templates/index.html, templates/workspace.html, templates/skills_gap.html, relevant static CSS, static JavaScript, manifest, service worker, and existing tests.
2. Identify the current token system and reuse it.
3. List the exact files you will change.
4. State any visual behavior that may affect existing tests.

Implement only this phase:
- Consolidate repeated design tokens.
- Improve buttons, forms, cards, badges, alerts, loading, error, and empty states.
- Remove duplicate analysis mode controls.
- Make the first action obvious.
- Add one prioritized “Do this next” presentation area without changing backend semantics.
- Add source, freshness, confidence, and fact-versus-inference labels where data already exists.
- Use CSS transitions and the Web Animations API only when needed.
- Respect prefers-reduced-motion.
- Preserve keyboard navigation, focus visibility, labels, live regions, and dark mode.
- Never use unsafe innerHTML for user, resume, job-description, or LLM content.
- Do not add a large animation library unless a concrete animation cannot be implemented safely with CSS/native APIs.

Testing:
- Run Python compile checks.
- Run pytest if dependencies are installed.
- Run Playwright smoke tests if available.
- Run axe-core accessibility scans if available.
- Test desktop and mobile widths.
- Inspect the diff and report every changed file.
- Report tests that could not run instead of claiming success.
- Propose a checkpoint commit only after the gate is green.
```

---

## 17. Final recommendation

For Final_year_project, the best free stack is:

```text
Figma Starter/Education
+ native CSS design tokens
+ CSS transitions/keyframes
+ Web Animations API
+ Lucide icons
+ Playwright
+ axe-core
+ Lighthouse
+ optional Open Props
+ optional GSAP only for genuinely complex timelines
```

This stack is free or has a useful free tier, works with the existing Flask/Jinja/vanilla-JavaScript architecture, preserves the PWA and offline direction, avoids an unnecessary frontend rewrite, and supports the roadmap’s most important goals: clarity, trust, accessibility, performance, and one coherent user journey.
