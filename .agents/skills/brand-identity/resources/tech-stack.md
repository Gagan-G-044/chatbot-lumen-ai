# Preferred Tech Stack & Implementation Rules

When generating code or UI components for this brand, you **MUST** strictly adhere to the following technology choices.

## Core Stack
* **Framework:** React (TypeScript preferred) or Vanilla HTML/Modern JS when maintaining lightweight single-page applications.
* **Styling Engine:** Tailwind CSS or Modern CSS Design Tokens & Glassmorphism variables matching `design-tokens.json`.
* **Component Library:** shadcn/ui primitives when in React environments.
* **Icons:** Lucide Icons / SVG feather-style modern strokes.

## Implementation Guidelines

### 1. Token & Style Usage
* Always map colors and gradients to established tokens (`--accent-start`, `--accent-end`, `--bg-surface`, `--txt-0`, etc.).
* Avoid arbitrary unmapped colors; use semantic tokens from `design-tokens.json`.
* **Dark Mode & Light Mode:** Ensure high contrast, ambient glow, and subtle glassmorphism borders (`--glass-border`).

### 2. Component Patterns
* **Buttons:** Primary actions use gradient accent (`#6366f1` to `#a855f7`) with subtle drop glow. Secondary actions use glass outline / ghost style.
* **Forms & Inputs:** Labels above inputs or clean floating placeholders with subtle glowing focus ring.
* **Layout:** Flexbox and CSS Grid with consistent responsive padding and card depth.

### 3. Forbidden Patterns
* Do NOT use jQuery.
* Do NOT use outdated Bootstrap classes.
* Do NOT use unstyled default browser controls.
