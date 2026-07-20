/**
 * Loop V77 A4 — parse ATLAS analyze reply into labeled sections.
 * Absent sections are omitted (never invent "N/A" rows).
 */

export type AtlasAnalyzeSection = {
  key: string;
  label: string;
  /** Body lines for the section (drivers keep list markers). */
  lines: string[];
};

const SECTION_RE = /^\*\*([^*]+):\*\*\s*(.*)$/;

const KNOWN_LABELS = new Set([
  "Price",
  "24h move",
  "7d range",
  "Model",
  "Model gate",
  "Drivers",
  "Market context",
  "Brief",
  "Time",
  "What would change this",
]);

/** Split a deterministic analyze reply into ordered, labeled sections. */
export function parseAtlasAnalyzeSections(reply: string): {
  preamble: string[];
  sections: AtlasAnalyzeSection[];
  footer: string[];
} {
  const lines = reply.split("\n");
  const preamble: string[] = [];
  const sections: AtlasAnalyzeSection[] = [];
  const footer: string[] = [];
  let current: AtlasAnalyzeSection | null = null;
  let seenSection = false;

  const flush = () => {
    if (current && current.lines.some((l) => l.trim().length > 0)) {
      sections.push(current);
    }
    current = null;
  };

  for (const raw of lines) {
    const m = raw.match(SECTION_RE);
    if (m) {
      const label = m[1].trim();
      if (KNOWN_LABELS.has(label)) {
        flush();
        seenSection = true;
        const rest = m[2] ?? "";
        current = {
          key: label.toLowerCase().replace(/\s+/g, "-"),
          label,
          lines: rest.trim() ? [rest.trim()] : [],
        };
        continue;
      }
    }

    if (current) {
      const trimmed = raw.trim();
      // Drivers may span multiple "- " lines; other sections are single-shot.
      if (current.key === "drivers") {
        if (trimmed.startsWith("- ") || trimmed === "") {
          current.lines.push(raw);
          continue;
        }
        // Non-driver content after drivers → footer / next section territory
        flush();
        if (trimmed) footer.push(raw);
        continue;
      }
      // Already captured the inline body — further prose is footer.
      if (current.lines.length > 0) {
        flush();
        if (trimmed) footer.push(raw);
        continue;
      }
      if (trimmed) current.lines.push(raw);
      continue;
    }

    if (!seenSection) {
      if (raw.trim()) preamble.push(raw);
      continue;
    }

    if (raw.trim()) footer.push(raw);
  }
  flush();

  return { preamble, sections, footer };
}

/** True when the reply looks like a sectioned analyze payload. */
export function isSectionedAnalyzeReply(reply: string): boolean {
  return /^\*\*(Price|Model|Drivers):\*\*/m.test(reply);
}

/** Format a metric line as label / value pairs when "key: value" or "a, b". */
export function splitMetricPairs(line: string): { label: string; value: string }[] {
  // Split on comma+space before a letter so "$1,000" stays intact.
  const chunks = line.split(/,\s+(?=[A-Za-z])/);
  if (chunks.length <= 1) {
    return [{ label: "", value: line }];
  }
  return chunks.map((chunk) => {
    const trimmed = chunk.trim().replace(/\.$/, "");
    const m = trimmed.match(/^([^0-9+~\-$]*?)\s+([+\-~$\d].*)$/);
    if (m) return { label: m[1].trim(), value: m[2].trim() };
    return { label: "", value: trimmed };
  });
}
