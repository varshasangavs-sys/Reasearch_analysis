"use client";

/**
 * QueryBar — the entry point. Large, inviting input.
 *
 * Why a textarea (not <input type="text">):
 *   Research queries can run a paragraph long. A textarea is honest about
 *   that. We auto-grow it with CSS field-sizing (a recent CSS feature) and
 *   fall back to a fixed min-height where it isn't supported.
 *
 * Why Cmd/Ctrl+Enter to submit (and not plain Enter):
 *   Plain Enter inside a textarea should add a newline — that's the platform
 *   convention. Cmd/Ctrl+Enter is the universally-understood "submit" combo
 *   in research tools (Notion, ChatGPT, Linear, etc).
 */

import { useState } from "react";

interface Props {
  onSubmit: (query: string) => void;
  disabled: boolean;
}

export function QueryBar({ onSubmit, disabled }: Props) {
  const [value, setValue] = useState("");

  const submit = () => {
    const trimmed = value.trim();
    if (trimmed.length < 3 || disabled) return;
    onSubmit(trimmed);
  };

  return (
    <form
      onSubmit={(e) => {
        e.preventDefault();
        submit();
      }}
      className="border-y border-rule py-6"
    >
      <label
        htmlFor="research-query"
        className="block font-serif text-sm uppercase tracking-[0.18em] text-ink-soft mb-3"
      >
        Research question
      </label>
      <textarea
        id="research-query"
        value={value}
        onChange={(e) => setValue(e.target.value)}
        onKeyDown={(e) => {
          if ((e.metaKey || e.ctrlKey) && e.key === "Enter") {
            e.preventDefault();
            submit();
          }
        }}
        disabled={disabled}
        placeholder="What do you want to understand?"
        rows={2}
        className="w-full resize-none bg-transparent font-serif text-2xl md:text-3xl leading-snug text-ink placeholder:text-ink-soft/60 focus:outline-none disabled:opacity-50"
      />
      <div className="mt-4 flex items-center justify-between text-sm text-ink-soft">
        <span className="font-sans">
          Three sources: web · Semantic Scholar · arXiv
        </span>
        <button
          type="submit"
          disabled={disabled || value.trim().length < 3}
          className="font-sans text-ink hover:text-accent disabled:opacity-40 disabled:hover:text-ink transition-colors"
        >
          {disabled ? "Researching…" : "Research →"}
          <span className="ml-3 text-xs text-ink-soft">⌘↵</span>
        </button>
      </div>
    </form>
  );
}
