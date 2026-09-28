

---

## 21. Compatibility review of the user-proposed frontend tools

A detailed compatibility review was added at `PROPOSED_FRONTEND_TOOLS_COMPATIBILITY.md`.

The review concludes that the best direct fits for the current Flask/Jinja/vanilla-JavaScript application are Motion, AutoAnimate, selective Lottie, Animate.css for prototypes, Alpine.js for small local UI state, HTMX for later server-rendered fragments, Lucide icons, Figma, Realtime Colors, Coolors, Playwright, axe-core, and Lighthouse.

Framer Motion, shadcn/ui, DaisyUI, Preline UI, FlyonUI, Aceternity UI, and Tailwind Typography are not direct drop-ins because they rely on React, Tailwind, Radix, or a frontend build/component system. They should be deferred unless a deliberate React/Tailwind migration is approved. A migration is not required for the current project goals.

The recommended order is:

```text
Native CSS and Web Animations API
→ Lucide icons and design tokens
→ Playwright, axe-core, and Lighthouse
→ Motion and AutoAnimate where native motion is insufficient
→ Alpine.js for small template-local state
→ HTMX later for job/application HTML fragments
→ Lottie only for a few licensed illustrations
```

The review also records important security and accessibility rules: pin remote assets, preserve CSP, do not use Alpine `x-html` with untrusted content, preserve CSRF and ownership checks with HTMX, respect reduced motion, verify community snippet licenses, and keep animation away from evidence certainty or critical data interpretation.
