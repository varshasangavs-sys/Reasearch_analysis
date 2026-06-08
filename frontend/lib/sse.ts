"use client";

/**
 * useResearchStream — the live pipe between the backend and the UI.
 *
 * Why fetch + ReadableStream instead of the native EventSource:
 *   EventSource is GET-only. Our backend uses POST so the query can be
 *   arbitrarily long (URLs have practical length limits and bad cache
 *   behavior). The trade-off is we implement a tiny SSE frame parser
 *   ourselves (~10 LOC) — small price.
 *
 * Why useReducer (not multiple useStates):
 *   Server-Sent Events can arrive bursty. With separate useStates, two events
 *   in the same tick can produce a torn render (one slice updated, another
 *   not yet). A reducer makes each event one atomic transition.
 *
 * Why the state shape mirrors the pipeline (not the events):
 *   Components want to ask "what phase are we in?", "what sub-questions do
 *   we have?", "what's the report?". They don't want to think about events.
 *   The reducer translates the event stream into UI state once, and every
 *   consumer reads from the cleaner shape.
 */

import { useCallback, useReducer } from "react";
import type { Finding, PipelinePhase, ResearchEvent, SubQuestion } from "./types";

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

// --- UI state ---

export interface SubQuestionState {
  id: string;
  text: string;
  covered: boolean;
  retryCount: number;
  // Per-source counts accumulated from `retrieved` events.
  counts: { web: number; semantic_scholar: number; arxiv: number };
}

export interface ResearchState {
  phase: PipelinePhase;
  query: string | null;
  round: number;
  subQuestions: SubQuestionState[];
  reportMarkdown: string | null;
  findings: Finding[]; // structured citations from the `report` event
  error: string | null;
  runId: string | null;
}

const initial: ResearchState = {
  phase: "idle",
  query: null,
  round: 0,
  subQuestions: [],
  reportMarkdown: null,
  findings: [],
  error: null,
  runId: null,
};

type Action =
  | { type: "reset" }
  | { type: "event"; event: ResearchEvent };

function reducer(state: ResearchState, action: Action): ResearchState {
  if (action.type === "reset") return initial;

  const ev = action.event;
  switch (ev.step) {
    case "run_started":
      return { ...initial, phase: "planning", query: ev.query, runId: ev.run_id };

    case "plan_ready":
      return {
        ...state,
        subQuestions: ev.sub_questions.map((sq) => ({
          id: sq.id,
          text: sq.text,
          covered: false,
          retryCount: 0,
          counts: { web: 0, semantic_scholar: 0, arxiv: 0 },
        })),
      };

    case "retrieving":
      return { ...state, phase: "retrieving", round: ev.round };

    case "retrieved": {
      const counts = {
        web: ev.per_source.web ?? 0,
        semantic_scholar: ev.per_source.semantic_scholar ?? 0,
        arxiv: ev.per_source.arxiv ?? 0,
      };
      return {
        ...state,
        subQuestions: state.subQuestions.map((sq) =>
          sq.id === ev.sub_question_id
            ? { ...sq, retryCount: ev.retry_count, counts }
            : sq,
        ),
      };
    }

    case "verifying":
      return { ...state, phase: "verifying" };

    case "verified": {
      const byId = new Map(ev.verdicts.map((v) => [v.sub_question_id, v]));
      return {
        ...state,
        subQuestions: state.subQuestions.map((sq) => {
          const v = byId.get(sq.id);
          return v
            ? { ...sq, covered: v.covered, retryCount: v.retry_count }
            : sq;
        }),
      };
    }

    case "synthesizing":
      return { ...state, phase: "synthesizing" };

    case "report":
      return {
        ...state,
        reportMarkdown: ev.report,
        findings: ev.findings ?? [],
      };

    case "done":
      return { ...state, phase: "done" };

    case "error":
      return { ...state, phase: "error", error: ev.message };

    default:
      // Other events (synthesized, synthesized_empty, critic_failed) carry
      // observability info but don't drive UI — ignore in the reducer.
      return state;
  }
}

// --- SSE wire-format parser ---
// Each backend frame is:
//   event: <NAME>\n
//   data: <JSON>\n
//   \n
// We accumulate bytes in a buffer and emit a frame whenever we see "\n\n".
//
// Why we tolerate "\r\n\r\n" too: some proxies normalize line endings.

function parseFrame(frame: string): ResearchEvent | null {
  const lines = frame.split(/\r?\n/);
  let data = "";
  for (const line of lines) {
    if (line.startsWith("data:")) data += line.slice(5).trimStart();
  }
  if (!data) return null;
  try {
    return JSON.parse(data) as ResearchEvent;
  } catch {
    return null;
  }
}

// --- The hook ---

export function useResearchStream() {
  const [state, dispatch] = useReducer(reducer, initial);

  const start = useCallback(async (query: string) => {
    dispatch({ type: "reset" });

    let res: Response;
    try {
      res = await fetch(`${API_URL}/research`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ query }),
      });
    } catch (e) {
      dispatch({
        type: "event",
        event: {
          step: "error",
          message: `network: ${(e as Error).message}`,
          run_id: "",
          ts: Date.now() / 1000,
        },
      });
      return;
    }

    if (!res.ok || !res.body) {
      dispatch({
        type: "event",
        event: {
          step: "error",
          message: `HTTP ${res.status}`,
          run_id: "",
          ts: Date.now() / 1000,
        },
      });
      return;
    }

    const reader = res.body
      .pipeThrough(new TextDecoderStream())
      .getReader();
    let buffer = "";

    while (true) {
      const { value, done } = await reader.read();
      if (done) break;
      buffer += value;
      let sep: number;
      while ((sep = buffer.indexOf("\n\n")) !== -1 || (sep = buffer.indexOf("\r\n\r\n")) !== -1) {
        const isCrlf = buffer.slice(sep, sep + 4) === "\r\n\r\n";
        const frame = buffer.slice(0, sep);
        buffer = buffer.slice(sep + (isCrlf ? 4 : 2));
        const event = parseFrame(frame);
        if (event) dispatch({ type: "event", event });
      }
    }
  }, []);

  return { state, start };
}
