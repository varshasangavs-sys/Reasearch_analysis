/**
 * Frontend type contract. Mirrors the Pydantic models in backend/app/schemas.py.
 *
 * Why duplicate the types instead of generating them:
 *   For a 5-model contract, the maintenance cost of a generator (openapi-ts,
 *   pydantic-to-typescript, etc.) is higher than the cost of updating two
 *   files when something changes. If the contract grows past ~10 models, swap
 *   in a generator — but only then.
 *
 * Why a "source of truth" pointer in the comment:
 *   When backend/app/schemas.py changes, future you needs to know to update
 *   this file. The comment is the breadcrumb.
 */

export type SourceType = "web" | "semantic_scholar" | "arxiv";

export interface Source {
  type: SourceType;
  title: string;
  url: string;
  authors: string[];
  year: number | null;
  citation_count: number | null;
  reliability_score: number | null;
}

export interface Finding {
  id: string;
  sub_question_id: string;
  content: string;
  source: Source;
  retrieved_at: string;
}

export interface SubQuestion {
  id: string;
  text: string;
  covered: boolean;
  retry_count: number;
  suggested_new_query: string | null;
}

// --- SSE event shapes ---
// The backend emits {"step": "<name>", "ts": ..., "run_id": ..., ...extra}.
// We model each step as a discriminated union member so TypeScript's narrowing
// works in the reducer switch statement.

interface BaseEvent {
  run_id: string;
  ts: number;
}

export type ResearchEvent =
  | (BaseEvent & { step: "run_started"; query: string })
  | (BaseEvent & {
      step: "plan_ready";
      prompt_version: string;
      sub_questions: { id: string; text: string }[];
    })
  | (BaseEvent & { step: "retrieving"; round: number })
  | (BaseEvent & {
      step: "retrieved";
      sub_question_id: string;
      sub_question: string;
      retry_count: number;
      findings_count: number;
      per_source: Partial<Record<SourceType, number>>;
    })
  | (BaseEvent & { step: "verifying"; round: number })
  | (BaseEvent & {
      step: "verified";
      prompt_version: string;
      verdicts: { sub_question_id: string; covered: boolean; retry_count: number }[];
    })
  | (BaseEvent & { step: "critic_failed"; error: string })
  | (BaseEvent & { step: "synthesizing" })
  | (BaseEvent & {
      step: "synthesized";
      prompt_version: string;
      findings_used: number;
      report_chars: number;
    })
  | (BaseEvent & { step: "synthesized_empty" })
  | (BaseEvent & {
      step: "report";
      report: string;
      findings?: Finding[]; // present when backend tweak is applied
    })
  | (BaseEvent & { step: "done" })
  | (BaseEvent & { step: "error"; message: string });

export type ResearchEventStep = ResearchEvent["step"];

// --- UI-level pipeline phases ---
// Coarser than backend events. The progress timeline only cares about these
// five buckets — the inner `retrieving/retrieved/verifying/verified` events
// inform sub-question chips, not the high-level phase marker.

export type PipelinePhase =
  | "idle"
  | "planning"
  | "retrieving"
  | "verifying"
  | "synthesizing"
  | "done"
  | "error";
