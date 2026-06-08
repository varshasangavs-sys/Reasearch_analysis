# Frontend — File-by-File Guide for Claude

This document is the map for future sessions. Read it before editing.

## Architectural invariants (do not violate)

1. **Type contract mirrors the backend.** Every event shape and Pydantic model
   used over the wire is mirrored in [lib/types.ts](lib/types.ts). When
   `backend/app/schemas.py` changes, this file changes too.
2. **One reducer, one source of UI truth.** All SSE events go through the
   reducer in [lib/sse.ts](lib/sse.ts). Components read from the resulting
   `state` shape — they never parse events themselves.
3. **No design library.** The editorial brief is hand-rolled. Don't reach
   for shadcn / Material / Chakra — they fight the aesthetic.
4. **Design tokens in TWO places:** CSS variables in [app/globals.css](app/globals.css)
   (palette) and Tailwind theme in [tailwind.config.ts](tailwind.config.ts)
   (which references those vars). When changing a color, edit the CSS var —
   Tailwind classes pick it up automatically.
5. **Server components for static content, client components for state.**
   Only `layout.tsx` is a server component. Every other file uses `"use client"`
   because they all need React state, events, or browser APIs (fetch streams).

## Dependency graph

```
page.tsx ──┬──> components/*.tsx
           └──> lib/sse.ts ──> lib/types.ts
```

`lib/types.ts` has zero dependencies — it's the contract layer.
`lib/sse.ts` only depends on `lib/types.ts`.
Components depend on `lib/sse.ts` and `lib/types.ts`.
`page.tsx` composes everything.

## File map

### Entry / framework

- **[app/layout.tsx](app/layout.tsx)** — root HTML shell. Server component.
  Loads Newsreader (serif) + IBM Plex Sans (sans) via `next/font/google`.
  next/font self-hosts the fonts at build time → no FOUT, no third-party
  request, no layout shift. The CSS variables it injects (`--font-serif`,
  `--font-sans`) are referenced by Tailwind config + globals.css.

- **[app/globals.css](app/globals.css)** — Tailwind directives + design
  tokens as CSS variables. Palette, base body font/line-height, heading
  rules, citation-link styling, scroll behavior.

- **[app/page.tsx](app/page.tsx)** — the one page. Header + grid (left rail
  timeline + reading column) + footer. `"use client"` because the whole
  experience is interactive.

### Contracts + plumbing

- **[lib/types.ts](lib/types.ts)** — TypeScript mirrors of backend Pydantic
  models. `Source`, `Finding`, `SubQuestion`, plus a discriminated-union
  `ResearchEvent` for SSE events, plus a UI-level `PipelinePhase`.

- **[lib/sse.ts](lib/sse.ts)** — `useResearchStream()` hook. Uses
  `fetch` + `ReadableStream` to POST the query and stream SSE responses.
  Tiny SSE frame parser (handles `\n\n` and `\r\n\r\n` separators).
  `useReducer` translates events into a flat UI state shape.

### Components

- **[components/QueryBar.tsx](app/components/QueryBar.tsx)** — large
  textarea, serif placeholder. Cmd/Ctrl+Enter submits. Disabled during a run.

- **[components/ProgressTimeline.tsx](app/components/ProgressTimeline.tsx)** —
  left-rail vertical timeline with five fixed steps (Planning, Retrieving,
  Verifying, Synthesizing, Done). The active step has the soft pulse;
  completed steps go to ink-soft. Shows round number when retrieving > 1.

- **[components/PlanView.tsx](app/components/PlanView.tsx)** — numbered
  list of sub-questions with staggered fade-in (80ms apart). Each sub-q
  shows live per-source counts and its `covered` status as it updates.

- **[components/ReportView.tsx](app/components/ReportView.tsx)** — renders
  the markdown via `react-markdown`. Pre-processes inline `[n]` patterns
  outside the References section into `[\[n\]](#references)` links so
  clicking a citation scrolls to the bibliography. `rehype-slug` assigns
  `id="references"` to the References heading.

- **[components/CitationList.tsx](app/components/CitationList.tsx)** —
  structured bibliography from the backend's structured findings (not
  parsed from markdown). Grouped by `source.type` (Web / Semantic Scholar /
  arXiv). External links open in a new tab.

## Conventions

- **All numeric indices are 1-based in the UI.** Sub-questions display
  `01`, `02`, …; citations are `[1]`, `[2]`, …. The Synthesizer numbers
  findings in `state.findings` order, so the array index + 1 IS the citation.
- **`"use client"` at the TOP of every component file** that uses hooks,
  event handlers, or browser APIs. The Next.js App Router defaults to
  server components.
- **Tailwind class lists** are joined with `[...].join(" ")` arrays when
  they get long — keeps them readable and lintable. No `clsx`/`cn` helper
  to keep deps thin.
- **Imports use the `@/*` alias.** Configured in `tsconfig.json`. `@/lib/...`
  for shared modules, `./components/...` for sibling files.

## Extension hooks (designed-for, not built)

| Feature | Where it slots in | Why painless |
|---|---|---|
| Dark mode | Add `:root.dark { --paper: ...; }` block in `globals.css`; toggle the `dark` class on `<html>` | Every color references a CSS var — flip the vars, every component re-themes. |
| Run history | Add `app/runs/page.tsx` + a backend `GET /runs` endpoint | State is already serializable. The `findings` array + `report_markdown` are everything you'd need to persist. |
| Token-streamed report | Add a `report_chunk` SSE event in the backend; in `reducer.ts` append to `reportMarkdown` | The Markdown renderer re-renders cheaply on each chunk. No layout shift if max-width is fixed (it is). |
| Export to PDF / .md | Button next to "Researching…" → `URL.createObjectURL(new Blob([reportMarkdown]))` | All data needed is already in state. |
| Bibtex export | Map `Finding[]` → bibtex string in `lib/bibtex.ts` | Source metadata (authors, year, citation_count) is already populated. |
| Tooltip on `[n]` hover showing finding content | Custom `components.a` renderer in `ReactMarkdown` | The `[n]` text + `findings[n-1]` lookup gives you the content. |
| MCP for live tool exposure (advanced) | New module `lib/mcp.ts`; mount as a custom protocol in `lib/sse.ts` | The SSE hook is the only network surface — replace or augment in one place. |

## Pitfalls / gotchas

- **POST + SSE**: the native `EventSource` is GET-only. We use
  `fetch` + `ReadableStream`. If you ever switch to `EventSource`, you'd
  have to move the query into a URL param.
- **CORS**: backend allows `http://localhost:3000`. Deploying anywhere else
  needs a backend env tweak.
- **Markdown rendering**: `react-markdown` v9 requires `remark-gfm` for
  tables/strikethrough — already included. `rehype-raw` is NOT included
  (which would allow raw HTML in markdown) because we trust the LLM less
  than that.
- **`useReducer` + `useCallback`**: the `start` function is `useCallback`'d
  with no deps so it stays stable across renders. Don't accidentally close
  over `state` inside it — use `dispatch` to read or update.
