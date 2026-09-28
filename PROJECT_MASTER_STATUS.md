

---

## 20. Frontend animation, styling, and UI/UX tools

A project-specific guide was added at `FRONTEND_UI_UX_TOOLS_GUIDE.md`. The recommended stack is native CSS design tokens, CSS transitions/keyframes, the Web Animations API, Lucide or Heroicons, Playwright, axe-core, Lighthouse, optional Open Props, and GSAP only for genuinely complex timelines.

The guide covers:

- Tool comparison and free/open-source status.
- Exact fit for the current Flask/Jinja/vanilla-JavaScript architecture.
- Landing-page, workspace, skills-gap, learning-roadmap, career-chat, and form improvements.
- Design-system tokens.
- CSS animation examples.
- Reduced-motion behavior.
- Web Animations API usage.
- Open Props setup and CDN risks.
- GSAP/Anime.js selection rules.
- Icon and asset guidance.
- Figma workflow.
- Storybook decision.
- Playwright and axe-core installation and examples.
- Lighthouse usage in Chrome DevTools and CLI.
- Animation duration budgets.
- Step-by-step UI implementation sequence.
- A Copilot/Codex UI implementation prompt.

The key decision is not to migrate the current project to React, Tailwind, Bootstrap, or another frontend framework merely to improve visual quality. The existing stack can be made substantially better with a tokenized CSS system, restrained native motion, accessibility testing, and a clearer information hierarchy.
