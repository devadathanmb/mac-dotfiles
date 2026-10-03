---
name: web-artifacts-builder
description: Design and build a professional, self-contained web artifact (a single HTML file) such as a page, dashboard, report, prototype, or interactive tool. Use when the user explicitly asks for a web artifact or invokes this skill.
disable-model-invocation: true
license: Complete terms in LICENSE.txt
metadata:
  opencode/autoinvoke: "false"
---

# Web Artifacts Builder

Deliver one self-contained HTML file that looks designed for its subject, not generated from a template. Work through four stages: brief, design plan, build, visual review.

## 1. Brief

Identify the subject, the audience, and the artifact's primary job. If the request leaves these open, propose one concrete answer for each and state it before designing. The subject's industry, materials, and vernacular are where distinctive visual choices come from: a report for financial analysts and a toy for 8-year-olds should look nothing alike. Use the brief's real content throughout.

## 2. Design plan

Before writing code, write a compact plan:

- **Color:** 4–6 named hex values.
- **Type:** one or two typefaces and their roles. If two, make them clearly distinct.
- **Layout:** a one-sentence concept plus an ASCII wireframe, including alignment.
- **Signature:** the one memorable element. Spend boldness there; keep everything around it quiet.

Then review the plan against the brief. Revise any part that you would produce for any similar page rather than for this one, and say what changed. These are today's generated-design defaults; use one only when the brief asks for it:

- warm cream background (near `#F4F1EA`) with a serif display and a terracotta accent (near `#D97757`);
- near-black background with a single acid-green or vermilion accent;
- broadsheet layout with hairline rules, zero radius, and dense newspaper columns;
- identical rounded cards, one radius everywhere, the same soft grey shadow, gradient washes as decoration;
- purple gradients, everything centered, Inter or the scaffold's default font;
- template chrome: tracked ALL-CAPS eyebrows above headings, `A · B · C` meta strings, `WORD — fragment` labels, `→` appended to buttons, monospace for small labels, `01 / 02 / 03` markers on content that isn't a sequence;
- a big number with a small label and a gradient accent as the hero;
- fade-and-slide-up on every section and hover effects on every card.

The brief's own words always win, including when it asks for one of these looks.

## 3. Content rules

Every string on screen is real information or honest authored copy.

- Don't fabricate data that poses as real (invented users, telemetry, build numbers). Sample data must read as sample, or leave the slot empty.
- Cut filler labels: if removing a string removes no information, remove it.
- Use standard copy for standard actions ("Save changes", not "Commit Session"). Keep an action's name consistent through the flow.
- Use a real icon set (lucide-react in the React tier, inline SVG otherwise) or no icons, never unicode glyphs as icons.
- Write from the user's side, in plain language, active voice, sentence case. Errors say what happened and how to fix it; empty states say what to do next.

## 4. Build

Choose the lightest tier that fits.

**Default: single HTML file.** Hand-write `index.html` with inline `<style>` and `<script>`. Use this for pages, reports, dashboards with modest interactivity, and visualizations. Inline any font or image data the artifact needs, or use system font stacks, so the file works offline.

**React tier:** only for real application state, multiple views, or many interactive components.

```bash
bash <skill-dir>/scripts/init-react.sh <project-name> [parent-dir]
cd <project-name>
npx shadcn@latest add <component...>   # only the components you use
npm run build                          # -> dist/index.html, fully inlined
```

The scaffold is Vite + React 19 + TypeScript + Tailwind v4 + shadcn/ui (Radix), with `vite-plugin-singlefile`. Replace the scaffold's default theme tokens and Geist font in `src/index.css` with the design plan's palette and type; shadcn components are a base to restyle, not the look.

In both tiers, set a CSS custom-property token system from the plan and use it everywhere. Watch selector specificity so section and component spacing don't cancel each other out.

**Quality floor**, met without announcing it: responsive down to 360px, visible keyboard focus, `prefers-reduced-motion` respected, WCAG AA contrast, line length under ~80 characters. Use motion sparingly: one orchestrated moment beats scattered effects, and motion that answers a user action is welcome.

## 5. Visual review

Render and look at the result before presenting it:

```bash
bash <skill-dir>/scripts/screenshot.sh <path-to-html> [out-dir]   # prints desktop.png and mobile.png paths
```

View both screenshots and check them against the design plan: hierarchy, spacing rhythm, overflow, contrast, mobile layout, and any default from section 2 that crept in. Fix and re-shoot until nothing material remains, usually one or two passes. Before finishing, remove one decorative element that doesn't serve the brief.

If Playwright can't run, say so and present the artifact without claiming a visual check.

## Deliver

Give the path to the final HTML file, the design plan in brief (palette, type, signature), and what the visual review changed.

---

Design guidance adapted from Anthropic's `frontend-design` skill (Apache-2.0, https://github.com/anthropics/skills) and content rules from `Ilm-Alan/frontend-design` (MIT, https://github.com/Ilm-Alan/frontend-design).
