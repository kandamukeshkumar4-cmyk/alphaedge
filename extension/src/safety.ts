const FORBIDDEN_PATTERNS = [
  /\/orders?\b/i,
  /\bplace[_\s-]?(bet|wager)\b/i,
  /\bsubmit[_\s-]?order\b/i,
  /\bwallet\b/i,
  /\bprivate[_\s-]?key\b/i,
  /\bseed[_\s-]?phrase\b/i,
  /\bpayment\b/i,
  /\bcredit[_\s-]?card\b/i,
  /\baccount[_\s-]?(balance|number|id)\b/i,
  /\bcopy[_\s-]?trading\b/i,
  /\bquerySelector(All)?\([^)]*(odds|price|balance|account)/i,
];

export function findForbiddenCapabilities(source: string): string[] {
  return FORBIDDEN_PATTERNS.filter((pattern) => pattern.test(source)).map(String);
}
