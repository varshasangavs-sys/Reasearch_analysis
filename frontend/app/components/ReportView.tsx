"use client";

/**
 * ReportView — renders the final cited markdown report.
 *
 * Why we PRE-PROCESS the markdown before handing it to react-markdown:
 *   The Synthesizer emits `[1]`, `[2]`, … as plain text citations. We want
 *   those to be clickable links that jump to the References section.
 *   The simplest, most robust way is a regex pre-pass that rewrites
 *   `[1]` -> `[\[1\]](#references)`. That keeps react-markdown's text-handling
 *   simple and avoids writing a custom inline-text renderer (which would
 *   need to walk every paragraph's children).
 *
 * Why rehype-slug:
 *   It assigns id="references" to the "## References" heading automatically,
 *   so #references in the rewritten links actually points somewhere.
 *
 * Typography:
 *   max-w-reading (68ch) enforces a single readable column — paper-like.
 *   Default browser margins on h2/h3/p inside <article> tuned via Tailwind
 *   typography-ish classes (we don't use @tailwindcss/typography to keep
 *   the bundle thin and the design under our control).
 */

import ReactMarkdown from "react-markdown";
import rehypeSlug from "rehype-slug";
import remarkGfm from "remark-gfm";

interface Props {
  markdown: string | null;
  isRunning: boolean;
}

const CITATION_RE = /\[(\d+)\]/g;

function linkifyCitations(md: string): string {
  // Inside the References section, the leading "[1]" labels would also match.
  // Strip our rewriting after "## References" so the bibliography stays plain.
  const refsIdx = md.search(/^##\s+References/im);
  const head = refsIdx === -1 ? md : md.slice(0, refsIdx);
  const tail = refsIdx === -1 ? "" : md.slice(refsIdx);
  const rewritten = head.replace(CITATION_RE, (_, n) => `[\\[${n}\\]](#references)`);
  return rewritten + tail;
}

export function ReportView({ markdown, isRunning }: Props) {
  if (!markdown) {
    return (
      <section className="mt-16 max-w-reading">
        <p className="font-serif italic text-ink-soft/70">
          {isRunning
            ? "Synthesizing the report…"
            : "Your cited report will appear here."}
        </p>
      </section>
    );
  }

  const prepared = linkifyCitations(markdown);

  return (
    <article
      className={[
        "mt-16 max-w-reading font-sans text-body text-ink",
        // Hand-rolled typography — keeps the editorial brief intact.
        "[&_h1]:font-serif [&_h1]:text-4xl [&_h1]:mt-0 [&_h1]:mb-6 [&_h1]:font-medium",
        "[&_h2]:font-serif [&_h2]:text-2xl [&_h2]:mt-10 [&_h2]:mb-3 [&_h2]:font-medium",
        "[&_h3]:font-serif [&_h3]:text-lg [&_h3]:mt-6 [&_h3]:mb-2 [&_h3]:font-medium [&_h3]:text-ink-soft",
        "[&_p]:my-4",
        "[&_ul]:my-4 [&_ul]:pl-6 [&_ul]:list-disc [&_ul]:marker:text-ink-soft/50",
        "[&_ol]:my-4 [&_ol]:pl-6 [&_ol]:list-decimal [&_ol]:marker:text-ink-soft/50",
        "[&_li]:my-1",
        "[&_a]:text-accent [&_a]:underline [&_a]:decoration-accent-soft [&_a]:underline-offset-2",
        "[&_a]:hover:decoration-accent",
        "[&_strong]:font-semibold",
        "[&_em]:italic",
        "[&_code]:font-mono [&_code]:text-sm [&_code]:bg-bg-card [&_code]:px-1 [&_code]:rounded-sm",
      ].join(" ")}
    >
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        rehypePlugins={[rehypeSlug]}
      >
        {prepared}
      </ReactMarkdown>
    </article>
  );
}
