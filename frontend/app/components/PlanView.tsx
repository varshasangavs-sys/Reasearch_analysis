"use client";

/**
 * PlanView — shows the Planner's decomposition with live per-sub-question status.
 *
 * Why this exists as a separate component:
 *   The plan IS the proof that the system is "agentic" — it decomposes,
 *   doesn't just dump a search box's results. The user should see this
 *   thinking happen. Separating it from the report (which appears later)
 *   keeps the visual moment of "the system planned this" intact.
 *
 * Motion:
 *   Staggered fade-in. Each sub-question appears 80ms after the previous
 *   one. The CSS animation runs only on first mount; subsequent state
 *   changes (counts updating, "covered" chip appearing) don't re-trigger it.
 *   That's the "restrained motion" the brief asks for.
 */

import type { SubQuestionState } from "@/lib/sse";

interface Props {
  subQuestions: SubQuestionState[];
}

export function PlanView({ subQuestions }: Props) {
  if (subQuestions.length === 0) return null;

  return (
    <section className="mt-12">
      <h2 className="font-serif text-xs uppercase tracking-[0.18em] text-ink-soft mb-4">
        The plan
      </h2>
      <ol className="space-y-5">
        {subQuestions.map((sq, i) => (
          <li
            key={sq.id}
            style={{ animationDelay: `${i * 80}ms`, animationFillMode: "both" }}
            className="animate-fade-up flex gap-4"
          >
            <span className="font-serif text-ink-soft/60 mt-1 tabular-nums w-6 text-right">
              {String(i + 1).padStart(2, "0")}
            </span>
            <div className="flex-1">
              <p className="font-serif text-lg leading-snug text-ink">
                {sq.text}
              </p>
              <SubQuestionStatus sq={sq} />
            </div>
          </li>
        ))}
      </ol>
    </section>
  );
}

function SubQuestionStatus({ sq }: { sq: SubQuestionState }) {
  const total = sq.counts.web + sq.counts.semantic_scholar + sq.counts.arxiv;

  if (sq.covered) {
    return (
      <div className="mt-2 text-xs font-sans text-ink-soft">
        <span className="text-accent">●</span> covered · {total} findings
        {sq.retryCount > 0 && ` · after ${sq.retryCount} retry${sq.retryCount > 1 ? "ies" : ""}`}
      </div>
    );
  }

  if (total === 0) {
    return (
      <div className="mt-2 text-xs font-sans text-ink-soft/60 italic">
        awaiting findings…
      </div>
    );
  }

  return (
    <div className="mt-2 text-xs font-sans text-ink-soft flex gap-3">
      {sq.counts.web > 0 && <span>{sq.counts.web} web</span>}
      {sq.counts.semantic_scholar > 0 && <span>{sq.counts.semantic_scholar} S2</span>}
      {sq.counts.arxiv > 0 && <span>{sq.counts.arxiv} arXiv</span>}
      {sq.retryCount > 0 && (
        <span className="text-accent-soft">retrying ({sq.retryCount})</span>
      )}
    </div>
  );
}
