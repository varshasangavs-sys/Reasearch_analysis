"use client";

/**
 * ProgressTimeline — left-rail pipeline indicator.
 *
 * Why FIVE fixed steps (not one per backend event):
 *   The backend emits a dozen event types. Showing them all is noisy and
 *   teaches the user nothing. The five phases (Plan / Retrieve / Verify /
 *   Synthesize / Done) are the mental model — events feed them.
 *
 * Why a vertical timeline (not a horizontal stepper):
 *   The brief is editorial / document-like. Documents have margins, not
 *   centered hero progress bars. A left rail stays out of the reader's way
 *   and matches the column-of-marginalia feel of a research paper.
 *
 * Visual states:
 *   - completed: dot filled, ink-soft, checkmark
 *   - active:    dot ringed in accent, label inked, quiet pulse
 *   - pending:   dot hollow, label ink-soft
 */

import type { PipelinePhase } from "@/lib/types";

interface Step {
  key: PipelinePhase;
  label: string;
}

const STEPS: Step[] = [
  { key: "planning", label: "Planning" },
  { key: "retrieving", label: "Retrieving" },
  { key: "verifying", label: "Verifying" },
  { key: "synthesizing", label: "Synthesizing" },
  { key: "done", label: "Done" },
];

const ORDER: PipelinePhase[] = ["idle", "planning", "retrieving", "verifying", "synthesizing", "done"];

interface Props {
  phase: PipelinePhase;
  round: number;
  error: string | null;
}

export function ProgressTimeline({ phase, round, error }: Props) {
  const phaseIdx = ORDER.indexOf(phase);

  return (
    <nav
      aria-label="Pipeline progress"
      className="sticky top-12 font-sans text-sm"
    >
      <div className="font-serif text-xs uppercase tracking-[0.18em] text-ink-soft mb-6">
        Progress
      </div>

      <ol className="space-y-5 border-l border-rule pl-5 ml-[5px]">
        {STEPS.map((step) => {
          const stepIdx = ORDER.indexOf(step.key);
          const isCompleted = phase !== "error" && stepIdx < phaseIdx;
          const isActive = step.key === phase;

          return (
            <li
              key={step.key}
              className="relative"
            >
              {/* Dot — absolutely positioned over the rail */}
              <span
                aria-hidden
                className={[
                  "absolute -left-[26px] top-[6px] block h-3 w-3 rounded-full transition-colors",
                  isActive
                    ? "bg-accent ring-2 ring-accent/30 animate-soft-pulse"
                    : isCompleted
                    ? "bg-ink-soft"
                    : "bg-paper border border-rule",
                ].join(" ")}
              />
              <div
                className={[
                  "leading-snug",
                  isActive ? "text-ink" : isCompleted ? "text-ink-soft" : "text-ink-soft/70",
                ].join(" ")}
              >
                {step.label}
                {step.key === "retrieving" && (isActive || isCompleted) && round > 0 && (
                  <span className="ml-2 text-xs text-accent-soft">round {round + 1}</span>
                )}
              </div>
            </li>
          );
        })}
      </ol>

      {error && (
        <div className="mt-6 border-t border-rule pt-4 text-sm text-accent">
          <div className="font-serif uppercase tracking-[0.18em] text-xs mb-1">Error</div>
          <div className="text-ink-soft break-words">{error}</div>
        </div>
      )}
    </nav>
  );
}
