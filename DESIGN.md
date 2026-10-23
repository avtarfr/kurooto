---
name: Kurooto (public site)
description: An assistant that fits your day; the landing page is one day, from before dawn to the next night.
colors:
  kuro-0: "#0B0F0A"
  kuro-1: "#10150E"
  kuro-2: "#151B12"
  kuro-3: "#1B2317"
  kuro-4: "#26311F"
  bone: "#F2EEE8"
  bone-dim: "#C9C2B6"
  day-0: "#F4F2EC"
  day-1: "#EAE6DD"
  day-2: "#E1DBCF"
  day-ink: "#172012"
  day-ink-2: "#3D4A33"
  day-accent: "#3F5626"
  moss: "#6B8A42"
  moss-hi: "#A6C07A"
  moss-ink: "#0A0E08"
typography:
  display:
    fontFamily: "Libre Franklin, Franklin Gothic Medium, system-ui, sans-serif"
    fontSize: "clamp(3rem, 1rem + 6.2vw, 6.75rem)"
    fontWeight: 700
    lineHeight: 0.95
    letterSpacing: "-0.035em"
  headline:
    fontFamily: "Libre Franklin, Franklin Gothic Medium, system-ui, sans-serif"
    fontSize: "clamp(2.25rem, 1.4rem + 3.4vw, 4.25rem)"
    fontWeight: 700
    lineHeight: 0.95
    letterSpacing: "-0.035em"
  hour:
    fontFamily: "Libre Franklin, Franklin Gothic Medium, system-ui, sans-serif"
    fontSize: "clamp(2.75rem, 1.6rem + 3.4vw, 5.5rem)"
    fontWeight: 700
    lineHeight: 1
    letterSpacing: "-0.04em"
    fontFeature: "tnum"
  title:
    fontFamily: "Libre Franklin, Franklin Gothic Medium, system-ui, sans-serif"
    fontSize: "clamp(1.375rem, 1.1rem + 0.6vw, 1.75rem)"
    fontWeight: 700
    lineHeight: 1.1
    letterSpacing: "-0.02em"
  lead:
    fontFamily: "Source Serif 4, Georgia, serif"
    fontSize: "clamp(1.25rem, 1.1rem + 0.7vw, 1.625rem)"
    fontWeight: 400
    lineHeight: 1.4
  body:
    fontFamily: "Source Serif 4, Georgia, serif"
    fontSize: "clamp(1.0625rem, 1rem + 0.25vw, 1.1875rem)"
    fontWeight: 400
    lineHeight: 1.55
  label:
    fontFamily: "Libre Franklin, Franklin Gothic Medium, system-ui, sans-serif"
    fontSize: "1.0625rem"
    fontWeight: 600
    lineHeight: 1
rounded:
  full: "999px"
  panel-lg: "36px"
  panel: "28px"
  row: "22px"
  fragment: "18px"
  well: "16px"
  code: "6px"
spacing:
  margin: "clamp(16px, 3.4vw, 48px)"
  section-gap: "clamp(120px, 14vw, 200px)"
  xs: "8px"
  sm: "14px"
  md: "28px"
  lg: "48px"
components:
  button-primary:
    backgroundColor: "{colors.moss}"
    textColor: "{colors.moss-ink}"
    typography: "{typography.label}"
    rounded: "{rounded.full}"
    padding: "16px 28px"
  button-primary-hover:
    backgroundColor: "{colors.moss-hi}"
    textColor: "{colors.moss-ink}"
  chooser-option:
    backgroundColor: "{colors.kuro-3}"
    textColor: "{colors.bone}"
    rounded: "{rounded.full}"
    padding: "12px 20px"
  chooser-option-selected:
    backgroundColor: "{colors.bone}"
    textColor: "{colors.kuro-0}"
  tab-day:
    backgroundColor: "transparent"
    textColor: "{colors.day-ink-2}"
    rounded: "{rounded.full}"
    padding: "10px 16px"
  tab-day-selected:
    backgroundColor: "{colors.day-ink}"
    textColor: "{colors.day-0}"
  question:
    backgroundColor: "{colors.kuro-3}"
    textColor: "{colors.bone}"
    rounded: "{rounded.panel}"
    padding: "18px 28px"
  question-open:
    backgroundColor: "{colors.moss}"
    textColor: "{colors.moss-ink}"
  install-panel:
    backgroundColor: "{colors.kuro-3}"
    textColor: "{colors.bone}"
    rounded: "{rounded.panel}"
    padding: "28px"
---

# Design System: Kurooto (public site)

Scope: the public landing page (`installer/index.html`). The dashboard, setup pages and phone app keep their own existing styles; their screenshots and the fragments marked `data-ui` on this page show those styles and do not follow this document's rules.

## Overview

**Creative North Star: "One day, wake to sleep"**

The page is one day and the scroll is the clock. Each section is a flat field of colour at an hour: the hero is pre-dawn kuro, the live day is the light ground, the task runs across four fields from morning to night, the screens sit in afternoon light, and the questions and the install close the page at night. A fixed bar carries a live clock that rolls to each section's hour, and the bar's ground and ink switch to that section's sky.

There is one motif: the moss circle from Kurooto's own icon, used as the sun. It appears at four scales: a giant sun cropped off a section's edge (150vh in the hero, rising; setting under the install field), the image masks that show product screens, the full-round controls, and the small dot bullets. Pieces of the real product (a Telegram message, task cards, the install panel) sit on the fields at true size and are marked `data-ui`.

Density is low and the type is large. A bold grotesque does the talking in headings and controls; a text serif carries the sentences.

**Key Characteristics:**
- Full-bleed fields of flat colour, each one an hour; night is kuro, day is the light theme.
- The moss circle is the single motif and the single action colour.
- Libre Franklin 700 display with tight tracking; Source Serif 4 for reading.
- Every control is fully round; containers are softly rounded; no hairline borders.
- Motion follows the clock: rising sun, rolling clock digits, an iris opening on the screens.

## Colors

Two grounds, night and day, and one green that is the sun.

### Primary
- **Moss Sun** (moss): the sun discs, the primary button, the open question, the slider thumb, the "now" row in the timeline, dot bullets on night fields. It is the one action colour.
- **Moss Light** (moss-hi): the primary button's hover and the focus ring on every ground.
- **Moss Ink** (moss-ink): text on moss; never used as a ground.

### Neutral: night
- **Kuro Ground** (kuro-0): the hero, the install field, the footer, and the inside of image masks.
- **Kuro Deep / Kuro Mid** (kuro-1, kuro-2): the questions field, the "where it lives" field, the first task field, the install panel's inner wells.
- **Kuro Raised** (kuro-3): surfaces resting on a night field (chooser options, question rows, the install panel, odd footer blocks), and the dimmed sun in the night task field.
- **Kuro Lift** (kuro-4): hover state on kuro-3 surfaces and the faint sun in the last task field.
- **Bone** (bone): ink on night; also the selected state of night controls (chooser, OS toggle, star link).
- **Bone Dim** (bone-dim): captions and secondary notes on night.

### Neutral: day
- **Day Ground** (day-0): the live-day field and the third task field.
- **Day Alt** (day-1): the screens field, the second task field, missed-class rows.
- **Day Well** (day-2): slider track, secondary cells, tab hover, and the faint sun on day fields.
- **Day Ink / Day Ink 2** (day-ink, day-ink-2): text on day; day-ink is also the selected tab and the main cell.
- **Day Accent** (day-accent): the wake-time number and the timeline's dot bullets on day.

### Named Rules
**The One Sun Rule.** Moss marks the sun and the action, nothing else. A second accent hue is not part of this world.

**The Sky Rule.** A section's ground is chosen by the hour it represents: kuro values for night, day values for day. Text on a field switches with it (bone on night, day-ink on day).

**The Tonal Sun Rule.** Inside the task fields the sun is drawn in the next tone of the field's own ground (kuro-3 on kuro-1, day-2 on day-1), so the motif stays present without competing with the moss action.

## Typography

**Display Font:** Libre Franklin (with Franklin Gothic Medium, system-ui)
**Body Font:** Source Serif 4 (with Georgia)
**Label/Mono Font:** Libre Franklin 500-600 for controls, nav and labels; ui-monospace for install lines and inline code.

**Character:** a heavy, tightly tracked grotesque for what the page says out loud, against a warm optical-size serif for what it explains.

### Hierarchy
- **Display** (700, clamp 3rem to 6.75rem, 0.95): the hero line only; 12vw under 560px. The closing "Try it tonight" runs larger (up to 8rem, 0.9).
- **Headline** (700, clamp 2.25rem to 4.25rem, 0.95): each section's h2, kept to a few words with a narrow measure (6-10em).
- **Hour** (700, clamp 2.75rem to 5.5rem, tabular): the clock times on the task fields; the wake-time readout uses the same voice.
- **Title** (700, clamp 1.375rem to 1.75rem, 1.1): h3s within a field.
- **Lead** (Source Serif 4 400, clamp 1.25rem to 1.625rem, 1.4): the sentence under a headline, 30-36ch.
- **Body** (Source Serif 4 400, clamp 1.0625rem to 1.1875rem, 1.55): running text, 44-60ch.
- **Label** (Libre Franklin 600, about 1.0625rem): buttons, tabs, chooser options, question summaries; 500 for nav links.

### Named Rules
**The Two Voices Rule.** Libre Franklin speaks (headings, hours, controls); Source Serif 4 explains (leads, body, notes). Do not set paragraphs in the grotesque or controls in the serif.

**The Tabular Clock Rule.** Every time of day (bar clock, timeline, field hours, wake readout) uses tabular figures.

## Layout

A centred wrap (max 1680px) with fluid side margins (spacing.margin). Sections are full-bleed fields; space between sections is the field change itself, with generous vertical padding (spacing.section-gap, or clamp 96px to 160px on night fields). Inside a field, content sits in a two-column asymmetric grid (for example 0.9fr / 1.1fr, 4fr / 8fr, 5fr / 6fr) that collapses to one column at 1000px. The task section is four equal fields side by side at 92svh, stacking to 64svh each on narrow screens. The bar is fixed at 64px, respects the safe-area inset, and hides secondary links under 760px.

Spacing rhythm within a field: 8px between sibling controls, 14px for tight stacks, 28px from headline to lead, 48px between groups.

## Elevation & Depth

Flat. Depth comes from tone: a surface on a field is one step lighter (kuro-3 on kuro-1) or, on day, one step deeper. The giant sun sits behind content (pointer-events off) and is cropped by its field. There are no site shadows; the only drop shadow on the page belongs to the Telegram message fragment, which is the product's own chrome.

### Named Rules
**The Tone Not Shadow Rule.** To raise a surface, step its ground tone; never add a drop shadow to site surfaces.

## Shapes

The circle governs everything. Controls are fully round (rounded.full) or circular (50%): buttons, chooser options, tabs, the OS toggle and its sliding thumb, the star row, link cells, the slider track and thumb, dot bullets, the wordmark's dot. Containers take generous radii: 36px for the screens iris, 28px for questions, the install panel and image discs, 22px for timeline rows, 18px for task cards, 16px for the install line well. The large image of "where it lives" is masked to a full circle. Bullets are filled 10-12px circles; a hollow ring marks a missed or moved item. The footer wordmark is seven blocks with round tops (999px over 18px) rising from the ground.

Borders are not used to divide space; fields, tones and radius do that work.

## Components

### Buttons
- **Shape:** fully round (999px).
- **Primary:** moss with moss-ink text, Libre Franklin 600, padding 16px 28px; may lead with a small currentColor dot.
- **Hover / Focus / Active:** moss-hi on hover (fine pointers only), a 3px moss-hi ring at 3px offset on focus, scale 0.97 on press (160ms ease-out).
- **Quiet:** transparent, inherits ink, underlined; for the secondary action beside a primary.

### Chooser (who the page is for)
- **Style:** full-round options on kuro-3 with bone text; the primary audience option is larger (1.375rem, 18px 30px).
- **State:** selected flips to bone ground with kuro ink; hover to kuro-4.

### Tabs and segmented toggle
- **Tabs (day):** transparent full-round labels in day-ink-2; selected is day-ink with day-0 text.
- **Segmented toggle (night):** kuro-1 full-round track with 4px inset; a bone thumb slides 260ms ease-out under the pressed option.

### Questions (disclosure)
- **Style:** kuro-3 rows at 28px radius, min 72px tall, Libre Franklin summary with a drawn plus that turns into a minus.
- **State:** open rows fill with moss and moss-ink text; hover kuro-4.

### Timeline
- **Style:** rows at 22px radius with a tabular time column and a dot bullet; transparent by default on day.
- **Kinds:** missed is day-1 with a hollow ring; night rows are kuro-2 with bone; the current row is moss.

### Wake slider
A 14px full-round day-2 track with a 40px moss thumb that grows 1.12 on press; the readout above it is in the hour voice in day-accent.

### Sun (signature)
An absolutely positioned circle behind a field's content, cropped by the field: 150vh in the hero (150vw on narrow screens), 30vw on the live day, 150% of a task field's width in tonal colours, 64vw setting under the install field. It drifts with the scroll and rises once on load; reduced motion holds it still.

### Image masks
Product screenshots sit in kuro-0 masks (rounded rectangles at 28-36px or a full circle) and are cropped by position rather than scaled to fit. The screens iris opens with a circular clip the first time it enters view (1100ms in-out) and cross-fades between tabs (320ms).

### Product fragments (`data-ui`)
Real product surfaces at true size: the Telegram message, the task cards, the install panel. They keep the product's own colours and shapes and are exempt from the site palette.

## Do's and Don'ts

### Do:
- **Do** give every section an hour and a sky (night or day) so the bar clock and bar colour follow the scroll.
- **Do** use the moss circle as the only motif, at the four scales: sun, mask, control, bullet.
- **Do** make every control fully round and every focus state the 3px moss-hi ring.
- **Do** raise surfaces by stepping tone (kuro-1 to kuro-3, kuro-3 to kuro-4 on hover).
- **Do** show the product through real screens and true-size fragments marked `data-ui`.
- **Do** honour reduced motion: the sun, rises, iris and clock roll all fall back to still states.

### Don't:
- **Don't** introduce a second accent hue; moss is the sun and the action.
- **Don't** divide space with hairline borders or rules; change the field or the tone instead.
- **Don't** lay site content out as rows of equal feature cards; the four task fields are hours of one day, each holding one product fragment.
- **Don't** add drop shadows to site surfaces; only product fragments may carry their own.
- **Don't** set paragraphs in Libre Franklin or controls in Source Serif 4.
