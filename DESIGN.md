# Design

Visual system for "Where did I stop?". Product register, restrained color.
Source of truth is `site/style.css`; this file describes it.

## Visual Theme & Atmosphere

A quiet reference tool with one warm voice. Pure white (light) or near-black
(dark) surfaces with no tint; warmth comes from the typeface and a single deep
red that marks the one thing you can do next. The probe card is the product:
it is the largest text on any screen and everything else steps back from it.
No imagery, no posters, no decoration.

## Color Palette & Roles

OKLCH throughout. Light values first; dark in parentheses.

| Role | Value | Used for |
|---|---|---|
| bg | `oklch(1 0 0)` (`oklch(0.13 0 0)`) | Page |
| surface | `oklch(0.975 0.003 10)` (`oklch(0.175 0 0)`) | Probe card, hover fills |
| surface-2 | `oklch(0.955 0.004 10)` (`oklch(0.21 0 0)`) | Skeleton shimmer |
| ink | `oklch(0.21 0.01 10)` (`oklch(0.94 0 0)`) | Text |
| ink-2 | `oklch(0.46 0.01 10)` (`oklch(0.70 0 0)`) | Secondary text, notes, footer. ≥ 7:1 on bg |
| line / line-strong | `oklch(0.89 0.006 10)` / `oklch(0.78 0.008 10)` (`0.27` / `0.36`) | Borders; strong on inputs and buttons |
| primary | `oklch(0.50 0.17 8)` (`oklch(0.70 0.16 16)`) | The primary answer, progress dots, focus, the episode title in a result |
| primary-soft / -line | `oklch(0.96 0.025 8)` / `oklch(0.88 0.05 8)` (`0.21 0.035 10` / `0.32 0.07 10`) | Consent card and result panel only |
| focus | primary at 55% (60%) | 3px outline on every focusable element |

Rules: the primary appears at most once as a fill per screen. Nothing else
carries chroma. No gradients, no shadows beyond the focus ring.

## Typography

One family: **Bricolage Grotesque** (variable, optical size 12–96, weights
400–700), falling back to the system sans. Tabular figures on. Fixed rem
scale, ratio ≈ 1.2:

| Token | Size | Use |
|---|---|---|
| t-xs | 13px | Footer, attribution, kbd hints |
| t-s | 15px | Notes, prompts, catalog chips |
| t-m | 17px | Body, buttons |
| t-l | 20px | Search input, consent card, h2 |
| t-xl | 24px (21.6 on small screens) | Probe card, result headline |
| t-2xl | 30px (27 on small screens) | h1 |

Weights: 400 body, 500 buttons and probe text, 600 headings and the primary
button. Headings use `text-wrap: balance`, prose `text-wrap: pretty`. Body
line length is capped by the 34rem column.

## Components

- **Button** (`.btn`): full-width, 52px min height, 12px radius, 1px strong
  border, label left and keyboard hint right. Variants: `primary` (filled),
  `quiet` (borderless, centered, secondary text). States: hover (border to
  ink-2, surface fill), active (1px press), focus-visible (ring), disabled
  (50%). Links styled as buttons share every state.
- **Probe card** (`.card`): surface fill, 1px line, 18px radius, t-xl at
  weight 500. `.consent` variant uses primary-soft for the one card that asks
  a different kind of question.
- **Result panel** (`.result`): primary-soft, headline at t-xl 600 with the
  episode title in primary.
- **Search**: t-l input with strong border; focus swaps to primary + ring.
  Results list below with row hover; empty state is the catalog as chips.
- **Progress dots**: 8px, line color, primary when done. No numbers, no
  percentages.
- **Skeleton** for the catalog fetch; inline **error** box with a retry link.

## Layout & Spacing

Single 34rem column, centered, 1.25rem side padding. Vertical rhythm on a
0.25rem base: 0.6rem between stacked buttons, 1rem under the card, 1.25rem
under the dots, 1.75rem under the lede, 3.5rem top padding (2.25rem on
phones). Answer buttons stack in a grid; season buttons wrap in an auto-fill
grid at 6.5rem minimum. Footer shares the column.

## Motion

State changes only. Each new card and answer set fades and rises 6px over
180ms with an ease-out quint curve; button hover/press transitions in
120–180ms. Skeleton shimmer while loading. `prefers-reduced-motion` removes
every animation and transition.

## Accessibility

AA contrast throughout (secondary text ≥ 7:1). 3px focus ring on every
interactive element. The walk is fully keyboard-driven (1/2/3 or y/u/n).
Keyboard hints hide on touch devices. Color scheme follows the system; both
themes are first-class.
