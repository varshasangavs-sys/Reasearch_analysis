"use client";

/**
 * CitationList — structured references grouped by source.
 *
 * Why this exists when the markdown already has a "## References" section:
 *   The markdown's references are LLM-formatted text — fragile, not always
 *   consistent, hard to interact with. The backend's `report` event now
 *   includes the structured `findings` array (one entry per citation, in
 *   citation order). With real objects we can:
 *     - guarantee correct grouping by source.type
 *     - render external-link icons reliably
 *     - hover to preview content (future: tooltip with the finding's content)
 *     - export to BibTeX (future)
 *
 * The numeric [n] in the report still corresponds 1:1 with the index here
 * because the Synthesizer numbers them in `state.findings` order.
 */

import type { Finding, SourceType } from "@/lib/types";

interface Props {
  findings: Finding[];
}

const GROUP_ORDER: SourceType[] = ["web", "semantic_scholar", "arxiv"];
const GROUP_LABELS: Record<SourceType, string> = {
  web: "Web",
  semantic_scholar: "Semantic Scholar",
  arxiv: "arXiv",
};

export function CitationList({ findings }: Props) {
  if (findings.length === 0) return null;

  // Group while preserving original numbering.
  const numbered = findings.map((f, i) => ({ ...f, n: i + 1 }));
  const grouped = new Map<SourceType, typeof numbered>();
  for (const f of numbered) {
    const list = grouped.get(f.source.type) ?? [];
    list.push(f);
    grouped.set(f.source.type, list);
  }

  return (
    <section id="references" className="mt-16 max-w-reading scroll-mt-12">
      <h2 className="font-serif text-2xl font-medium mb-6">References</h2>

      {GROUP_ORDER.map((type) => {
        const list = grouped.get(type);
        if (!list || list.length === 0) return null;
        return (
          <div key={type} className="mb-8">
            <h3 className="font-serif text-sm uppercase tracking-[0.18em] text-ink-soft mb-3">
              {GROUP_LABELS[type]}
            </h3>
            <ol className="space-y-3">
              {list.map((f) => (
                <li key={f.id} className="font-sans text-sm leading-relaxed flex gap-3">
                  <span className="text-ink-soft/60 tabular-nums w-8 shrink-0 text-right">
                    [{f.n}]
                  </span>
                  <div className="flex-1">
                    <a
                      href={f.source.url}
                      target="_blank"
                      rel="noreferrer noopener"
                      className="citation-link"
                    >
                      {f.source.title}
                    </a>
                    {f.source.authors.length > 0 && (
                      <span className="text-ink-soft">
                        {" "}
                        — {formatAuthors(f.source.authors)}
                        {f.source.year && ` (${f.source.year})`}
                      </span>
                    )}
                    {type === "semantic_scholar" && f.source.citation_count != null && (
                      <span className="text-ink-soft/60 ml-2">
                        · {f.source.citation_count} citations
                      </span>
                    )}
                  </div>
                </li>
              ))}
            </ol>
          </div>
        );
      })}
    </section>
  );
}

function formatAuthors(authors: string[]): string {
  if (authors.length <= 3) return authors.join(", ");
  return `${authors.slice(0, 3).join(", ")} et al.`;
}
