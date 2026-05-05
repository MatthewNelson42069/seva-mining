# Phase 3: React Approval Dashboard - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-03-31
**Phase:** 03-react-approval-dashboard
**Areas discussed:** Card layout & density, Interaction flow, Visual identity, Dashboard chrome

---

## Card Layout & Density

| Option | Description | Selected |
|--------|-------------|----------|
| Full-width stack | One card per row, full width. Like Linear issues. | Yes |
| Two-column grid | Cards in 2-column masonry grid. | |
| Compact list + detail panel | Left sidebar summaries, right panel detail. | |

**User's choice:** Full-width stack
**Notes:** Matches Linear/Notion aesthetic. Best for scanning lots of info quickly.

### Draft Alternatives Display

| Option | Description | Selected |
|--------|-------------|----------|
| Tabbed | Small tabs within card, one visible at a time | Yes |
| Stacked vertically | All alternatives visible at once | |
| Radio select | All visible as radio buttons | |

**User's choice:** Tabbed

### Urgency Display

| Option | Description | Selected |
|--------|-------------|----------|
| Color-coded left border | Red/amber/green strip | |
| Countdown badge + color | Explicit countdown in header | |
| Sort order only | Most urgent at top, no styling | Yes |

**User's choice:** Sort order only

### Post Excerpt

| Option | Description | Selected |
|--------|-------------|----------|
| Full text (~280 chars) | Show entire original tweet/caption | |
| First 2 lines + expand | ~140 chars, click to expand | Yes |
| Claude decides | Let Claude pick | |

**User's choice:** First 2 lines + expand

### Rationale Visibility

| Option | Description | Selected |
|--------|-------------|----------|
| Collapsed by default | "Why this post?" toggle | Yes |
| Always visible | 1-2 line always shown | |
| Hover tooltip | Appears on hover over score | |

**User's choice:** Collapsed by default

### Score Display

| Option | Description | Selected |
|--------|-------------|----------|
| Numeric badge (8.7/10) | Clean number in header | Yes |
| Colored dot only | Green/amber/red dot | |
| Both (number + color) | Numeric with color backing | |

**User's choice:** Numeric badge (8.7/10)

### Related Cards (DASH-08)

| Option | Description | Selected |
|--------|-------------|----------|
| Subtle connector line + badge | Line connects related cards | |
| Grouped together | Stacked in a group | |
| Badge only | "Also on Instagram" badge | Yes |

**User's choice:** What Claude recommends (badge approach selected)

### Content Tab Display

| Option | Description | Selected |
|--------|-------------|----------|
| Full preview inline | Entire draft renders in card | |
| Summary card + expand modal | Card shows summary, click for modal | Yes |
| Claude decides | Format-dependent | |

**User's choice:** Summary card + expand modal

---

## Interaction Flow

### Card Action (Approve/Reject)

| Option | Description | Selected |
|--------|-------------|----------|
| Fade out + toast | 300ms fade, toast, 5s undo | Yes |
| Instant removal | Immediate disappear | |
| Move to Done section | Collapsed reviewed section | |

**User's choice:** Fade out + toast

### Inline Editing

| Option | Description | Selected |
|--------|-------------|----------|
| Click draft text to edit | Read-only default, click to edit | Yes |
| Always editable | Always in textarea | |
| Edit button opens edit mode | Explicit edit button | |

**User's choice:** Click draft text to edit

### Rejection Reason UX

| Option | Description | Selected |
|--------|-------------|----------|
| Dropdown + optional notes | Inline dropdown with 5 categories + notes | Yes |
| Quick-tap categories | 5 buttons, tap to reject immediately | |
| Modal dialog | Full modal with select and notes | |

**User's choice:** Dropdown + optional notes

---

## Visual Identity

### Color Mode

| Option | Description | Selected |
|--------|-------------|----------|
| Light mode only | White background, dark text | Yes |
| Dark mode only | Dark background, light text | |
| Both (toggle) | User toggle, system preference | |

**User's choice:** Light mode only

### Accent Color

| Option | Description | Selected |
|--------|-------------|----------|
| Gold / amber | Ties into gold mining brand | |
| Blue (Linear-style) | Classic SaaS blue | Yes |
| Claude decides | Let Claude pick | |

**User's choice:** Blue (Linear-style)

---

## Dashboard Chrome

### Login Page

**User's choice:** Claude decides (simplest approach matching aesthetic)

### Tab Navigation

| Option | Description | Selected |
|--------|-------------|----------|
| Top tabs with counts | Horizontal tabs at top | |
| Left sidebar | Vertical sidebar with icons | |
| Top tabs + sidebar combo | Platform tabs top, sidebar for pages | Yes |

**User's choice:** Top tabs + sidebar combo

### Empty State

| Option | Description | Selected |
|--------|-------------|----------|
| Clean message + status | "Queue is clear" with agent run times | Yes |
| Just "No items" | Minimal text | |
| Claude decides | Let Claude design | |

**User's choice:** Clean message + status

### Mock Data

| Option | Description | Selected |
|--------|-------------|----------|
| Realistic gold sector mock data | 10-15 items across platforms | Yes |
| Minimal placeholder data | Few generic placeholders | |
| No mock data | Start empty | |

**User's choice:** Realistic gold sector mock data

---

## Claude's Discretion

- Login page design
- Sidebar layout details and page routing
- Animation easing and timing
- Typography scale and spacing
- Card border, shadow, spacing
- Toast positioning and styling
- Modal design for content review

## Deferred Ideas

None — discussion stayed within phase scope
