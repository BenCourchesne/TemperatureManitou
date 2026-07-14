> **Statut de ce document** : ceci est la **spec technique détaillée** de la
> navigation temporelle du graphique historique (déplacée le 2026-07-14 depuis
> `D:\Claude desktop\ESPHome\plan.md`, qui était hors dépôt git). Le **statut
> d'avancement / backlog vivant** (quoi est fait, quoi reste à faire) est suivi
> **uniquement dans [`PLAN.md`](PLAN.md)**, pas ici — ne pas dupliquer les cases
> à cocher de statut entre les deux fichiers. Ce document reste la référence
> pour le détail d'implémentation (règles, edge cases, formats) une fois qu'une
> étape est reprise en main.

# Historical dashboard — time-travel navigation

Spec for adding "go back in time" to the weather-station history view.
Written for the developer. Covers the interaction model, components, states,
behaviour rules, mobile layout, compare mode, and edge cases.

---

## 1. The core idea

The user needs to browse *past* periods, not just the most recent one. The
naive fix — one date picker that re-anchors all five range buttons — merges two
separate decisions and creates ambiguous semantics (does a picked date mean the
start / end / middle of a "Year"?).

**Split the two decisions:**

| Decision | Control | Question it answers |
|----------|---------|---------------------|
| **Granularity** | The five range buttons (24 h / 7 jours / Mois / Saison / Année) | *How much* time is shown |
| **Position** | A prev/next stepper + a clickable period label | *Which* window is shown |

The range buttons stop meaning "last N hours/days" and start meaning "one
day / week / month / season / year at a time." Position is then moved with
`‹ ›` arrows (one unit per click) or by clicking the label to open a picker.

---

## 2. Windows are aligned to natural calendar boundaries

This is the rule that makes stepping predictable and makes compare mode free.
A window is **not** "now minus N." It snaps to a real calendar period:

| Granularity | Window shown | Step size (`‹ ›`) | Label format |
|-------------|--------------|-------------------|--------------|
| 24 h        | a single calendar day (00:00–24:00) | 1 day | `9 juillet 2026` |
| 7 jours     | one week (define week start, e.g. Mon) | 1 week | `Semaine du 3–9 juil.` |
| Mois        | one calendar month | 1 month | `Juillet 2026` |
| Saison      | one meteorological season | 1 season | `Été 2026` |
| Année       | one calendar year | 1 year | `2026` |

Benefit: stepping back on "Mois" always lands on a clean whole month, and
"this July vs last July" is a like-for-like comparison.

> Decisions to confirm with product: week start (Mon vs Sun) and season
> definitions (meteorological: summer = Jun/Jul/Aug, or local/custom).
> Note that winter spans two calendar years (Dec–Feb): define the label
> (suggest `Hiver 2025–2026`) and which year "owns" it for stepping and
> compare mode (suggest: the year of January).

---

## 3. Desktop layout — the navigation bar

A single row above the chart, three groups:

```
[ 24h | 7j | Mois | Saison | Année ]      [ ‹  📅 9 juillet 2026 ⌄  › ]      [ 🕐 Aujourd'hui ]
   granularity (segmented)                     stepper + period label            now reset
```

- **Granularity**: segmented button group. Active segment uses the accent
  fill (`--bg-accent` / `--text-accent`), matching the current design.
- **Stepper**: `‹` prev button, center label button, `›` next button.
  - The center label shows the current period and a chevron; clicking it opens
    the period picker (section 4).
  - `‹` / `›` move by exactly one step of the active granularity.
- **Aujourd'hui (Now)**: snaps back to the period containing the present moment.

---

## 4. The period picker (opens from the label)

The picker **adapts to the active granularity** so the user always selects a
whole, aligned period — never a raw date that has to be interpreted:

| Granularity | Picker UI |
|-------------|-----------|
| 24 h        | day calendar (month grid of days) |
| 7 jours     | day calendar; selecting any day selects its whole week |
| Mois        | 3×4 grid of months, with year stepper at top |
| Saison      | 4 season blocks, with year stepper at top |
| Année       | list/grid of years |

Rules:
- Future periods are **disabled** (greyed), not hidden.
- Include an "Aujourd'hui" shortcut inside the picker footer.
- Popover anchored under the label; dismiss on outside-click / Esc.

---

## 5. Compare mode (year-over-year) — optional but high value

A single toggle ("Comparer") overlays the **same aligned period from the
previous year** behind the current line.

- Current period = solid, full-weight line (existing styling).
- Comparison period = thin **dashed, muted/grey** line drawn *behind* the
  current one. It must never compete visually with "now."
- Legend shows both years.
- **Deltas are the payload**: under each summary stat show the difference vs the
  comparison period, e.g. `Moy 21.4 °C  (+2.4 °C vs 2025)`. Many users read the
  tiles, not the lines.
- Default **off**. It adds clutter; keep it opt-in.
- Because windows are boundary-aligned, "previous year" is unambiguous for every
  granularity (last July, last week-of-year, last summer, etc.).
- Compare is only meaningful for period-shaped granularities. For "24 h" either
  compare to the same date last year or hide the toggle — confirm with product.
- **Data availability**: the database only goes back to **June 28 2026**, so
  "vs last year" has nothing to show until mid-2027. Keep this last in the
  build order, and define the empty case now: when the comparison window has
  **no data**, show the toggle disabled with a tooltip ("données historiques
  insuffisantes") rather than an empty overlay; when it has **partial data**,
  draw what exists and show `—` for delta stats that can't be computed.
- Implementation note: to overlay both periods on one time axis, shift the
  comparison series' timestamps forward by one year so the lines align.

**Future extension:** swap "vs last year" for a rolling multi-year average band
("la normale", 5- or 10-yr mean ± range). Same overlay slot, more credible for a
weather audience. Out of scope for v1.

---

## 6. Mobile layout (≤ ~480px)

The desktop single row does not fit. Stack into three full-width rows inside
the card:

1. **Granularity** — horizontally scrollable pill row. Active pill auto-scrolls
   into view. Do **not** wrap to two lines and do **not** collapse to a native
   `<select>` unless testing shows the scroll row is missed.
2. **Stepper** — full-width, its own row. `‹` and `›` are 44×44px at the edges;
   the center label flexes to fill and is the primary tap target. This is the
   hero control on mobile — time-travel is the main mobile job.
3. **Secondary actions** — "Aujourd'hui" and "Comparer" as two equal halves.

Touch targets ≥ 44px. Picker popover becomes a bottom sheet on mobile.

---

## 7. Behaviour & edge cases

- **Future edge**: when the current window already contains the present, disable
  `›` (and the equivalent picker cells). This doubles as the "you are at the
  live edge" indicator. Never show an empty future chart.
- **"24 h" must not regress to a mostly-empty chart**: today's view is a
  rolling last-24-h window that is always full; a strict calendar day is ~70%
  empty at 7 a.m. Keep the rolling window when viewing the *current* period
  (label it "Dernières 24 h"); calendar-day alignment applies only once the
  user steps into the past. Confirm this hybrid with product.
- **Live data on the current period**: when viewing the period that contains
  "now" at 24 h granularity, the chart may still be filling — keep the existing
  live behaviour; only past periods are fully static.
- **Auto-refresh must respect time-travel**: the app refetches every 5 min.
  When a past window is displayed, the refresh must not re-anchor the chart to
  the present — skip the chart refetch entirely (past windows are immutable).
  The condition cards (Air, Pression, Eau…) always show *live* current
  conditions regardless of the chart's window; only the chart and its
  Min/Avg/Max stats follow the selected window.
- **Changing granularity keeps position**: switching 24 h → Mois while viewing
  9 July 2026 should land on July 2026 (the month containing the current
  window's anchor), not jump to today. Confirm this feels right in testing.
- **Data gaps / start of record**: disable `‹` (and picker cells) before the
  first date with data, so users can't page into empty history.
- **Deep-link / shareable state**: encode granularity + period (+ compare flag)
  in the URL query so a view can be bookmarked/shared. Formats per granularity:
  `?g=day&start=2026-07-09` · `?g=week&start=2026-07-06` (the week's first
  day) · `?g=month&start=2026-07` · `?g=season&start=2026-ete` ·
  `?g=year&start=2026`, plus `&cmp=1` when compare is on. Use `replaceState`
  (not `pushState`) on stepper/range changes to avoid history spam; the live
  default view keeps a clean URL (no params).
- **Timezone**: define day/week/month boundaries in the station's local
  timezone (`America/Toronto`), not UTC and **not the visitor's timezone**, so
  "a day" matches what the user sees at the lake even when viewed from abroad.
  Compute boundaries with the `Intl` APIs so DST days (23 h / 25 h) stay
  correct.
- **Keyboard & accessibility**: `←`/`→` step periods when the nav bar has
  focus; `aria-label` on `‹ ›` ("Période précédente/suivante"); the picker
  popover traps focus and closes on Esc; same for the mobile bottom sheet.
- **Chart axes are pinned to the window**: set the x-scale `min`/`max` to the
  window edges so a partially-empty period (data gap, sparse history) doesn't
  collapse the axis. Tick/tooltip formats adapt to granularity (`HH:mm` for a
  day, `dd MMM` for week/month, `MMM` for season/year — the current fixed
  `dd MMM HH:mm` tooltip is wrong beyond 24 h).
- **i18n**: every new string (period labels, picker, "Aujourd'hui",
  "Comparer", tooltips) goes through the existing FR/EN `i18n` table. Label
  formats need EN variants: `Week of Jul 3–9`, `July 2026`, `Summer 2026`,
  `Today`.

---

## 8. Data layer

The current fetch code only knows "last N from now" (`limitToLast`) — there is
no way to load an arbitrary past window. This section is the backend half of
the feature.

### 8.1 Fetching a window

| Granularity | Past-window source | Query |
|-------------|--------------------|-------|
| 24 h, 7 jours | `/readings` (raw / hourly-bucketed, as today) | `orderBy="$key"&startAt="{startMs}"&endAt="{endMs}"` |
| Mois, Saison, Année | `/daily` | keep the single full fetch (≤365 keys, ~35 KB) and filter client-side |

- `/readings` keys are 13-digit epoch-ms strings, so RTDB's lexicographic
  `$key` comparison equals numeric order — pass `startAt`/`endAt` as quoted
  strings.
- Current-period views keep their existing fetch paths; only past windows use
  range queries.
- Note "Mois" moves from raw `/readings` (today's 30 d view) to `/daily` —
  30 daily points are enough at month scale and avoid a multi-MB fetch for
  past months.

### 8.2 Responsiveness while stepping

- **Cancel stale requests**: rapid `‹ ‹ ‹` clicks must not race — abort the
  in-flight fetch (`AbortController`) or drop any response whose window no
  longer matches the displayed one. Without this, a slow earlier response can
  overwrite the correct window.
- **Cache visited windows** in memory (`Map` keyed by `granularity|startMs`).
  Past windows are immutable, so the cache never needs invalidating; only the
  current period is refetched.
- **Loading & error states**: show a lightweight loading state on the chart
  when the window changes; on fetch failure show a retry message — never a
  silent empty chart. A window that loads successfully but contains no rows
  shows an explicit "aucune donnée" state.

### 8.3 Start of record

Earliest data is **June 28 2026** (both `/readings` and `/daily`). Detect it
with one `orderBy="$key"&limitToFirst=1` query at startup and cache the
result; it drives the `‹` / picker-cell disabling from section 7.

### 8.4 `/daily` is aggregated on UTC days — decide

Home Assistant buckets `/daily` at **UTC midnight**, ~4–5 h off a Québec
calendar day, while section 7 mandates local-day boundaries. Options:

1. **Accept the skew** for Mois/Saison/Année — a daily-mean line shifted a few
   hours is invisible at that scale. *Recommended for v1.*
2. Change the HA aggregation to local-midnight buckets — touches the pipeline
   and existing keys; not worth it now.

Document the choice; it also affects compare-mode deltas at those
granularities.

### 8.5 Sparse fields in older data

Sensors were added over time: `airv`/`hum` exist from ~Jul 6 2026,
pressure/wind/UV/solar from ~Jul 7 2026. A past window may lack whole series:

- Legend toggles for series with **no data in the window** are greyed with a
  tooltip ("pas de données pour cette période"), not hidden — layout stays
  stable while stepping.
- Min/Avg/Max stat tiles show `—` for those series.

---

## 9. Suggested build order

1. Data layer: range queries + request cancellation + first-data detection
   (section 8). Refactor range buttons from "last N" to "aligned window +
   anchor date" (section 2). Add the stepper `‹ ›` + label + Aujourd'hui.
   Ship this alone — it already fully solves "go back in time."
2. Add the granularity-adaptive period picker (section 4).
3. Add mobile stacking + scrollable granularity row (section 6).
4. Add compare mode + delta stats (section 5).
5. (Later) rolling-normal band.

## 10. Acceptance criteria (v1 = steps 1–3)

- [x] Each granularity shows a whole, calendar-aligned window.
- [x] `‹ ›` move by exactly one unit of the active granularity.
- [x] The period label reflects the window and opens a granularity-appropriate
      picker; future periods are disabled.
- [x] "Aujourd'hui" returns to the live/current period from any point.
- [x] `›` is disabled at the present edge; `‹` disabled before first data.
- [x] Switching granularity preserves the viewed position.
- [x] View state is reflected in the URL and restores on reload.
- [x] On phone widths: granularity scrolls, stepper is full-width, targets ≥44px.
- [x] Rapid stepping never renders a stale window (in-flight fetches cancelled).
- [x] The 5-min auto-refresh never moves a past view back to the present.
- [ ] Series absent from a past window are greyed, not hidden; stats show `—`.
      (existing behaviour omits the stat block entirely rather than showing
      `—`; not yet changed — **tracked as a backlog item in [PLAN.md](PLAN.md),
      not here**)
- [x] Every new string exists in both FR and EN.
