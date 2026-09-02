# MarketMitra Design System

## Purpose

This document defines the visual and interaction principles for MarketMitra. It is a design reference for future frontend work, not an implementation specification. It does not introduce a component library, styling framework, or application UI.

## 1. Design Philosophy

MarketMitra is a professional NEPSE market analytics product. Its design should help a user scan prices, compare changes, identify movement, and judge data freshness quickly and confidently.

### Data-first hierarchy

The primary value on a screen is market information, not decoration. Layout, typography, alignment, and contrast must establish a clear order: the market or instrument being viewed, its primary value, its change, supporting metrics, and context such as the last update time.

### Professional financial-product identity

The product should feel precise, durable, and operational rather than promotional. Prefer calm surfaces, consistent tables, descriptive labels, and intentional interaction states. Visual emphasis must communicate analytical importance, not novelty.

### NEPSE-specific context

Use Nepal Stock Exchange terminology where relevant: NEPSE Index, Turnover, Total Volume, Transactions, LTP, Change, Percentage Change, Market Status, and Last Updated. Date, number, market-status, and data-freshness presentation must make local market context clear without inventing unsupported information.

### Information density and readability

Density is useful when it improves comparison. Compact metric groups, tables, and charts are encouraged when they retain a readable hierarchy, adequate line height, and predictable scanning patterns. Reserve whitespace for separation and focus; do not use it to simulate a marketing page.

### Functional visual design

Every color, border, icon, and animation needs a purpose: communicate hierarchy, state, risk, action, or data meaning. If it does not help a market-analysis task, omit it.

## 2. Explicit Anti-Patterns

The following patterns are prohibited because they reduce the clarity and trust expected of a financial analytics application:

- **Excessive gradients:** gradients compete with price movement and make stable surfaces look promotional. Use flat, restrained surfaces by default.
- **Glassmorphism:** translucent, blurred cards reduce contrast, table readability, and visual precision.
- **Oversized hero sections:** application screens should lead to market data, not a landing-page message.
- **Excessive rounded cards:** highly rounded containers create a soft, consumer-app appearance and waste usable data area.
- **Bubble UI:** floating, isolated controls and circular data containers obscure grouping and weaken efficient scanning.
- **Excessive whitespace:** financial tools should be compact and legible, not sparse for its own sake.
- **Random colorful icons:** icon color must not become decoration or compete with market semantics.
- **Decorative illustrations without purpose:** illustrations consume attention without helping a user interpret market data.
- **Excessive animation:** motion can distract from changing values and create uncertainty about whether a number is current.
- **Neon colors:** neon tones cause visual fatigue and undermine a calm, trustworthy analytical environment.
- **Generic startup copy:** phrases such as “unlock growth” or “powerful insights” do not describe a market state or user task.
- **Unnecessary badges and pills:** small status treatments are for concise semantic state only; they must not replace a clear label or data hierarchy.

## 3. Color System

Color is semantic and restrained. Brand color establishes product identity and interactive affordance; market colors describe price movement only. Green is not a general-purpose financial-app accent.

| Role | Initial token | Intended use |
| --- | --- | --- |
| Application background | `#F6F7F8` | Main page canvas; quiet and neutral. |
| Elevated surface | `#FFFFFF` | Panels, tables, dialogs, and controls above the canvas. |
| Primary text | `#17212B` | Headings, primary values, and high-priority labels. |
| Secondary text | `#5E6B78` | Supporting labels, descriptions, timestamps, and metadata. |
| Borders | `#D9E0E6` | Structural separation for tables, inputs, and surfaces. |
| Primary brand | `#1E4E79` | Product navigation, primary action emphasis, links, and focus treatment. |
| Positive movement | `#167A4A` | Price gain, positive change, and favorable market movement only. |
| Negative movement | `#B42318` | Price loss, negative change, and critical financial decline only. |
| Neutral state | `#667085` | Unchanged movement and non-actionable neutral status. |
| Warning state | `#B54708` | Stale data, delayed data, or attention requiring review. |

Supporting tints may be derived for backgrounds and borders, but the foreground semantic colors must remain readable against their assigned surface. Do not infer positive or negative meaning from brand color.

## 4. Typography

### Primary UI font strategy

Use a system-oriented sans-serif stack for dependable rendering, compact metrics, and fast scanning. A practical initial stack is `Inter, "Segoe UI", system-ui, sans-serif`; no web font is required for the first implementation.

### Hierarchy

- **Page title:** one concise title identifying the current analytical context.
- **Section title:** compact and descriptive, used for groups such as Top Gainers or Market Summary.
- **Metric label:** smaller, muted, and stable across related values.
- **Body text:** reserved for instructions, explanations, empty states, and error recovery.

Do not use display-style headings or oversized typography on analytical screens.

### Tables and financial values

- Use a slightly smaller but readable table size than body copy when density requires it.
- Align monetary values, volume, percentages, and dates consistently by column.
- Apply `font-variant-numeric: tabular-nums;` to financial values, timestamps, tables, and chart tooltips.
- Use a medium or semibold weight for the primary price; use color and sign together for changes. Color alone must never carry gain/loss meaning.
- Maintain consistent decimal precision within a metric or table column.

## 5. Spacing System

Use a small, repeatable scale. Avoid one-off spacing values unless a layout constraint requires one.

| Token | Value | Typical use |
| --- | --- | --- |
| `--space-1` | `4px` | Tight icon/text gaps, table-cell internals. |
| `--space-2` | `8px` | Related label/value gaps. |
| `--space-3` | `12px` | Compact control and card padding. |
| `--space-4` | `16px` | Standard component padding and section gaps. |
| `--space-5` | `24px` | Distinct content groups. |
| `--space-6` | `32px` | Page-level separation. |
| `--space-8` | `48px` | Rare major layout separation. |

Use spacing to show grouping: values belong closer to their labels than to the next metric; a table title belongs closer to its controls than to the preceding section.

## 6. Border and Radius System

Borders establish structure in a dense product. Prefer one-pixel neutral borders and subtle surface contrast over shadows.

- **Inputs and buttons:** small radius, `4px`.
- **Cards and panels:** restrained radius, `6px` or `8px`.
- **Menus and dialogs:** `8px` where a contained surface needs separation.
- **Pills:** only for short semantic states such as Open, Closed, Stale, or Loading; use a full radius only in those cases.

Avoid large rounded rectangles, decorative shadows, and pills used solely to make ordinary labels look prominent.

## 7. Application Layout Principles

### Future application shell

**Top navigation** contains the MarketMitra identity, a stock search entry point, and concise market status or freshness information. It should remain compact and stable across screens.

**Sidebar** provides structured, grouped navigation for market views and analytical areas. Use icons sparingly; each icon must have an adjacent text label or accessible equivalent. Navigation is a structural aid, not a branded illustration.

**Main content** contains dashboard metrics, analytical controls, tables, and charts. It should use a predictable content width, clear section boundaries, and a layout that makes comparison easy.

### Responsive behavior

- Preserve primary data and actions before reducing density.
- At narrower widths, collapse the sidebar into a labelled navigation control and move lower-priority table columns into detail views or horizontal overflow.
- Keep market status, LTP, Change, and Percentage Change visible when possible.
- Do not turn data tables into stacks of decorative cards by default. Use a scrollable table or a deliberate compact row pattern when that preserves comparison.
- Charts may simplify secondary controls on mobile, but axes, values, and tooltips must remain usable.

## 8. Financial Metric Cards

Metric cards communicate a compact data hierarchy, not a decoration pattern. Every card follows this order:

1. **Metric label** — concise, muted, and unambiguous.
2. **Primary value** — largest and highest-contrast element.
3. **Change / percentage** — secondary to the primary value, with sign and semantic color.
4. **Timestamp or context** — low-emphasis information such as Last Updated, previous close, or data period.

Use cards only where grouped metrics improve scanning. Avoid redundant cards for data that belongs in a table or chart.

## 9. Tables

Tables are first-class analytical interfaces, not fallback content.

- Use compact but comfortable row density; rows should support scanning without crowding values.
- Left-align instrument names and descriptive text. Right-align prices, volumes, turnover, percentages, and other comparable numeric values.
- Apply tabular numerals to all financial columns.
- Show `+`/`−` signs and semantic color for positive/negative values; unchanged values use the neutral state.
- Use subtle hover states to support row tracking, not to imply selection. Selected rows need a distinct accessible state.
- Sorting controls must show the active column and direction, and must not rely on color alone.
- Separate header and body using contrast or borders; keep headers visible when table length and viewport make sticky headers useful.
- On small screens, preserve the most important columns and provide deliberate horizontal scrolling or a detail route for secondary values.

## 10. Charts and Data Visualization

Charts must explain a market pattern or support a decision. They are not decorative panels.

- Use a restrained series palette; reserve positive and negative colors for movement semantics.
- Use subtle grid lines and readable, high-contrast axes.
- Include meaningful tooltips with date/time, value, and the relevant financial context.
- Use clear, compact time-range selectors such as 1D, 1W, 1M, 3M, 1Y, and All only when the data supports them.
- Make gain/loss periods understandable through labels, signs, patterns, or annotations in addition to color.
- Ensure keyboard access to chart controls and provide text alternatives or summary data for critical visual information.
- Avoid rainbow palettes, decorative gradients, excessive animation, and charts that exist only to fill empty space.

## 11. Market Semantic States

| State | Treatment |
| --- | --- |
| Gain | Positive color, explicit `+` sign where relevant, and readable text contrast. |
| Loss | Negative color, explicit `−` sign where relevant, and readable text contrast. |
| Unchanged | Neutral color and an explicit `0.00` / `0%` value or “Unchanged” label as appropriate. |
| Market open | Concise semantic status, such as a restrained green-tinted status label; never use as the primary brand treatment. |
| Market closed | Neutral status label with the relevant last-update context. |
| Stale data | Warning treatment paired with a visible Last Updated timestamp and recovery context. |
| Unavailable data | Clear error or unavailable state explaining what cannot be shown; do not display misleading placeholder values. |
| Loading data | Calm progress indicator or skeleton that retains the expected content structure; avoid animated decoration. |

## 12. Component Guidelines

- **Buttons:** small radius, descriptive verbs, clear primary/secondary hierarchy, and visible keyboard focus. Primary actions use brand color; destructive actions use a dedicated destructive treatment only when needed.
- **Inputs:** clear labels, practical height, modest borders, and visible focus. Stock search should prioritize symbol/name clarity over visual ornament.
- **Badges:** reserved for short semantic states—market status, stale state, or data source condition—not categories or marketing labels.
- **Cards:** use only for meaningful metric groupings or contained analytical controls. Keep borders, padding, and headings consistent.
- **Tables:** follow the table rules above; a dense table is a primary user interface.
- **Charts:** follow the chart rules above; always expose context and avoid purely visual storytelling.
- **Loading states:** preserve layout shape and indicate that data is being retrieved without fabricating values.
- **Empty states:** explain why data is absent and provide one relevant next action where possible; avoid illustrations unless they add real instruction.
- **Error states:** state what failed, identify affected data when possible, and offer a retry or recovery action. Do not hide errors behind vague messages.

## 13. Content and Terminology

Prefer domain-specific terms that users of the Nepalese market can recognize:

- NEPSE Index
- Turnover
- Total Volume
- Transactions
- Top Gainers
- Top Losers
- Most Active
- Last Updated
- Market Status
- LTP
- Change
- Percentage Change

Avoid generic SaaS terminology such as Growth, Insights, Engagement, and Performance Overview unless it precisely describes an established financial concept in its immediate context. Labels should name the measure, period, or action directly.

## 14. Initial Design Tokens

These tokens are a starting design reference only. They must be reviewed against accessibility requirements before implementation.

```css
:root {
  --color-bg: #f6f7f8;
  --color-surface: #ffffff;
  --color-text-primary: #17212b;
  --color-text-secondary: #5e6b78;
  --color-border: #d9e0e6;
  --color-brand: #1e4e79;
  --color-positive: #167a4a;
  --color-negative: #b42318;
  --color-neutral: #667085;
  --color-warning: #b54708;

  --space-1: 4px;
  --space-2: 8px;
  --space-3: 12px;
  --space-4: 16px;
  --space-5: 24px;
  --space-6: 32px;
  --space-8: 48px;

  --font-ui: Inter, "Segoe UI", system-ui, sans-serif;
  --font-size-xs: 0.75rem;
  --font-size-sm: 0.875rem;
  --font-size-base: 1rem;
  --font-size-lg: 1.25rem;
  --font-size-xl: 1.5rem;
  --font-size-2xl: 2rem;

  --border-width: 1px;
  --radius-control: 4px;
  --radius-card: 6px;
  --radius-surface: 8px;
  --radius-pill: 999px;
}
```

Use `font-variant-numeric: tabular-nums;` for financial values and data-dense UI. Do not copy these tokens into application styles until the relevant frontend task is authorized.

## 15. Future Dark Mode

Dark mode should be added only after the core light theme is proven with real tables and charts. It must preserve the same semantic roles, hierarchy, data density, and movement meanings rather than merely inverting colors.

- Use dark neutral surfaces with sufficient separation between application background, panels, table headers, and input fields.
- Re-evaluate all text, border, positive, negative, neutral, and warning contrast ratios; do not mechanically reuse light-theme colors.
- Keep chart grids subtle and axes readable without making the chart visually loud.
- Preserve brand color as an interaction identity and market colors as data semantics.
- Test long table sessions, high-density screens, stale-data warnings, and focus states for visual fatigue and accessibility.
