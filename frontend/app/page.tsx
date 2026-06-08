"use client";

/**
 * The one page. Composes header + left rail + reading column.
 *
 * Why everything lives on one page:
 *   v1 has no run history, no auth, no settings. A research session is
 *   stateless: ask once, read the report. Adding routes would imply state
 *   we don't have.
 *
 * Why "use client" at the page level:
 *   The whole experience is interactive (SSE, reducer, animations). The
 *   payoff of splitting client/server would be marginal; the cost (passing
 *   data across the boundary, two component flavors) is real.
 *
 * Layout:
 *   - Header: thin, masthead-style
 *   - Two-column grid below ~768px: collapses to single column on mobile
 *   - Left rail (220px): ProgressTimeline, sticky
 *   - Reading column: QueryBar → PlanView → ReportView → CitationList
 */

import { useResearchStream } from "@/lib/sse";
import { QueryBar } from "./components/QueryBar";
import { ProgressTimeline } from "./components/ProgressTimeline";
import { PlanView } from "./components/PlanView";
import { ReportView } from "./components/ReportView";
import { CitationList } from "./components/CitationList";

export default function Home() {
  const { state, start } = useResearchStream();
  const isRunning = state.phase !== "idle" && state.phase !== "done" && state.phase !== "error";

  return (
    <div className="min-h-dvh">
      <Header />

      <main className="mx-auto max-w-6xl px-6 md:px-10 pb-32">
        <div className="grid grid-cols-1 md:grid-cols-[220px_1fr] gap-12 mt-10">
          {/* Left rail — progress timeline, sticky */}
          <aside className="hidden md:block">
            <ProgressTimeline
              phase={state.phase}
              round={state.round}
              error={state.error}
            />
          </aside>

          {/* Reading column */}
          <div className="min-w-0">
            <QueryBar onSubmit={start} disabled={isRunning} />

            {/* Mobile-only progress block below the query */}
            <div className="md:hidden mt-8">
              <ProgressTimeline
                phase={state.phase}
                round={state.round}
                error={state.error}
              />
            </div>

            <PlanView subQuestions={state.subQuestions} />
            <ReportView markdown={state.reportMarkdown} isRunning={isRunning} />
            <CitationList findings={state.findings} />
          </div>
        </div>
      </main>

      <Footer />
    </div>
  );
}

function Header() {
  return (
    <header className="border-b border-rule">
      <div className="mx-auto max-w-6xl px-6 md:px-10 py-5 flex items-baseline justify-between">
        <h1 className="font-serif text-xl font-medium tracking-display">
          Research Copilot
          <span className="ml-3 text-xs uppercase tracking-[0.18em] text-ink-soft font-sans font-normal">
            v1 · paper
          </span>
        </h1>
        <a
          href="https://github.com"
          className="font-sans text-xs uppercase tracking-[0.18em] text-ink-soft hover:text-ink transition-colors"
          target="_blank"
          rel="noreferrer"
        >
          About
        </a>
      </div>
    </header>
  );
}

function Footer() {
  return (
    <footer className="border-t border-rule mt-20">
      <div className="mx-auto max-w-6xl px-6 md:px-10 py-6 font-sans text-xs text-ink-soft flex justify-between">
        <span>Planner → Retriever → Critic → Synthesizer</span>
        <span>Sources: web · Semantic Scholar · arXiv</span>
      </div>
    </footer>
  );
}
