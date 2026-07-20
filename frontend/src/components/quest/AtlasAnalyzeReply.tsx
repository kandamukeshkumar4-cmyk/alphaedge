/**
 * Loop V77 A4 — readable grouped rendering for sectioned analyze replies.
 * Numbers align in a simple label/value row; absent sections stay omitted.
 */

import { cn } from "@/lib/cn";
import {
  isSectionedAnalyzeReply,
  parseAtlasAnalyzeSections,
  splitMetricPairs,
  type AtlasAnalyzeSection,
} from "./atlas-analyze-sections";

function renderLiteMarkdown(text: string) {
  const parts = text.split(/(\*\*[^*]+\*\*)/g);
  return parts.map((part, i) => {
    if (part.startsWith("**") && part.endsWith("**")) {
      return <strong key={i}>{part.slice(2, -2)}</strong>;
    }
    return <span key={i}>{part}</span>;
  });
}

function SectionBlock({ section }: { section: AtlasAnalyzeSection }) {
  const isDrivers = section.key === "drivers";
  const body = section.lines.join("\n").trim();
  if (!body && !isDrivers) return null;

  if (isDrivers) {
    const items = section.lines
      .map((l) => l.trim())
      .filter((l) => l.startsWith("- "))
      .map((l) => l.slice(2));
    if (items.length === 0 && !body) return null;
    return (
      <div className="space-y-1.5">
        <p className="text-[10px] font-bold uppercase tracking-wider text-muted-2">{section.label}</p>
        <ul className="space-y-1">
          {(items.length > 0 ? items : [body]).map((item, i) => (
            <li key={i} className="text-[12px] leading-snug text-text">
              {item}
            </li>
          ))}
        </ul>
      </div>
    );
  }

  // Single-line metric sections → aligned pairs when possible
  if (section.lines.length <= 1) {
    const pairs = splitMetricPairs(body);
    const hasLabels = pairs.some((p) => p.label);
    return (
      <div className="space-y-1">
        <p className="text-[10px] font-bold uppercase tracking-wider text-muted-2">{section.label}</p>
        {hasLabels ? (
          <dl className="space-y-0.5">
            {pairs.map((p, i) => (
              <div key={i} className="flex items-baseline justify-between gap-2">
                {p.label ? (
                  <dt className="min-w-0 truncate text-[11px] text-muted">{p.label}</dt>
                ) : (
                  <dt className="sr-only">{section.label}</dt>
                )}
                <dd className="shrink-0 font-mono text-[12px] tabular-nums text-text">{p.value}</dd>
              </div>
            ))}
          </dl>
        ) : (
          <p className="text-[12px] leading-snug text-text">{body}</p>
        )}
      </div>
    );
  }

  return (
    <div className="space-y-1">
      <p className="text-[10px] font-bold uppercase tracking-wider text-muted-2">{section.label}</p>
      <p className="whitespace-pre-wrap text-[12px] leading-snug text-text">{body}</p>
    </div>
  );
}

export function AtlasAnalyzeReply({
  content,
  className,
}: {
  content: string;
  className?: string;
}) {
  if (!isSectionedAnalyzeReply(content)) {
    return (
      <div
        className={cn(
          "whitespace-pre-wrap text-text [&_strong]:font-bold [&_strong]:text-primary",
          className,
        )}
      >
        {renderLiteMarkdown(content)}
      </div>
    );
  }

  const { preamble, sections, footer } = parseAtlasAnalyzeSections(content);
  return (
    <div className={cn("space-y-3 text-text", className)} data-atlas-analyze="sectioned">
      {preamble.length > 0 ? (
        <p className="text-[13px] font-semibold text-text">{preamble.join(" ")}</p>
      ) : null}
      <div className="space-y-2.5 border-t border-border/60 pt-2">
        {sections.map((section) => (
          <SectionBlock key={section.key} section={section} />
        ))}
      </div>
      {footer.length > 0 ? (
        <div className="space-y-1 border-t border-border/60 pt-2 text-[11px] leading-relaxed text-muted">
          {footer.map((line, i) => (
            <p key={i}>{renderLiteMarkdown(line)}</p>
          ))}
        </div>
      ) : null}
    </div>
  );
}
