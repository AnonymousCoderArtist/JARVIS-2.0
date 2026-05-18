# WebUI Theme & Design System

The WebUI uses a centralized **CSS custom property** system for all colors and common UI patterns. Change one file — everything updates.

## Design Tokens

All tokens live in `interface/webui/src/globals.css` in the `:root` block. They use **RGB channel variables** so you can apply any alpha opacity:

```css
/* Example: change the primary accent from blue to cyan */
--brand-r: 0;   --brand-g: 200;   --brand-b: 255;
```

### Core Palette

| Variable | Default (RGB) | Use |
|----------|---------------|-----|
| `--brand-r/g/b` | `26, 90, 255` | Primary accent (buttons, borders, glows) |
| `--text-bright-r/g/b` | `200, 220, 255` | Titles, headings, bright labels |
| `--text-body-r/g/b` | `180, 200, 230` | Body text, paragraphs |
| `--text-muted-r/g/b` | `100, 140, 220` | Labels, secondary text, hints |
| `--success-r/g/b` | `50, 200, 100` | Success states, connected indicators |
| `--error-r/g/b` | `200, 80, 80` | Error states, recording indicators |
| `--warning-r/g/b` | `255, 180, 50` | Warnings, approval dialogs |
| `--info-r/g/b` | `100, 200, 255` | Info blue, progress bars |

### Surface Colors

| Variable | Default (RGB) | Use |
|----------|---------------|-----|
| `--panel-bg-start/end` | `8,16,38` → `5,10,24` | Open panels (ChatPanel, ToolCallBox) |
| `--dialog-bg-start/end` | `10,20,45` → `6,12,28` | Modal dialogs (ModelPicker, Config, etc.) |

### Using in Components

```tsx
// Inline style (rare cases)
style={{ color: "rgba(var(--brand-r), var(--brand-g), var(--brand-b), 0.8)" }}

// Tailwind arbitrary value
className="border-[rgba(var(--brand-r),var(--brand-g),var(--brand-b),0.3)]"

// CSS class (preferred for common patterns)
className="techy-dialog techy-header"
```

## Reusable CSS Classes

All defined in `@layer components` in `globals.css`.

### Panels & Dialogs

| Class | Use |
|-------|-----|
| `.techy-panel` | Open panel (glass blur, gradient bg, blue border, shadow) |
| `.techy-dialog` | Centered modal dialog |
| `.techy-dialog-amber` | Amber/warning dialog (approval requests) |
| `.techy-dialog-debug` | Debug console (darker bg) |
| `.techy-header` | Panel/dialog header (bottom border + subtle gradient) |
| `.techy-header-amber` | Amber-themed header |
| `.techy-header-debug` | Debug console header |

### Buttons

| Class | Use |
|-------|-----|
| `.techy-btn-active` | Active tab (blue gradient + glow) |
| `.techy-btn-selected` | Selected option (blue bg + border) |
| `.techy-btn-active-amber` | Amber action button |

### Text

| Class | Use |
|-------|-----|
| `.techy-text-title` | Bright heading text |
| `.techy-text-body` | Body text |
| `.techy-text-muted` | Muted label text |
| `.techy-text-dim` | Dim hint text |
| `.techy-text-badge` | Status badge text |

### Bubbles

| Class | Use |
|-------|-----|
| `.techy-bubble-user` | User message bubble |
| `.techy-bubble-assistant` | Assistant message bubble |
| `.techy-bubble-reasoning` | Reasoning block |

### Layout

| Class | Use |
|-------|-----|
| `.techy-topmenu` | Top navigation bar |
| `.techy-input-bar` | Bottom input bar |
| `.techy-suggestions` | Command suggestions dropdown |
| `.techy-connection-bar` | Connection status bar |
| `.techy-right-sidebar` | Right icon sidebar |
| `.techy-sphere-response` | Sphere tooltip popup |
| `.techy-feedback` | Feedback widget |

### Badges

| Class | Use |
|-------|-----|
| `.techy-badge-question` | "Question pending" badge |
| `.techy-badge-approval` | "Approval needed" badge |
