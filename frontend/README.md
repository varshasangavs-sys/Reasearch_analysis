# Research Copilot — Frontend

Next.js 14 (App Router) + TypeScript + Tailwind. Renders the live research
pipeline as an editorial document — paper-like background, serif headings,
single reading column, left-rail progress timeline.

For the project overview, see [../CLAUDE.md](../CLAUDE.md).
For the file-by-file architecture, see [CLAUDE.md](CLAUDE.md).

## Setup

```powershell
cd frontend
npm install
```

`.env.local` already points at `http://localhost:8000` — change it if your
backend lives elsewhere.

## Run

In one terminal — backend:
```powershell
cd backend
.\venv\Scripts\Activate.ps1
uvicorn app.main:app --reload
```

In a second terminal — frontend:
```powershell
cd frontend
npm run dev
```

Open http://localhost:3000.

## Build

```powershell
npm run build
npm run start
```

## Stack

| Layer | Choice |
|---|---|
| Framework | Next.js 14.2 (App Router) |
| Language | TypeScript (strict) |
| Styling | Tailwind CSS 3.4 + CSS variables |
| Fonts | Newsreader (serif headings) + IBM Plex Sans (body), via `next/font` |
| Markdown | `react-markdown` + `remark-gfm` + `rehype-slug` |
| State | React `useReducer` (no external store) |
| SSE | `fetch` + `ReadableStream` (POST + SSE — native `EventSource` is GET-only) |

## Project structure

```
frontend/
├── app/
│   ├── layout.tsx               # font loading, HTML shell
│   ├── page.tsx                 # the one page — composes the layout
│   ├── globals.css              # tailwind + design tokens (CSS vars)
│   └── components/
│       ├── QueryBar.tsx
│       ├── ProgressTimeline.tsx
│       ├── PlanView.tsx
│       ├── ReportView.tsx
│       └── CitationList.tsx
├── lib/
│   ├── types.ts                 # event shapes mirroring backend schemas
│   └── sse.ts                   # useResearchStream() — POST+SSE hook
├── tailwind.config.ts
├── next.config.mjs
└── tsconfig.json
```
