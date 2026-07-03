const FLAGS: Record<string, string> = {
  canada: "🇨🇦",
  bosnia: "🇧🇦",
  "bosnia and herzegovina": "🇧🇦",
  usa: "🇺🇸",
  mexico: "🇲🇽",
  brazil: "🇧🇷",
  argentina: "🇦🇷",
  france: "🇫🇷",
  england: "🏴󠁧󠁢󠁥󠁮󠁧󠁿",
  germany: "🇩🇪",
  spain: "🇪🇸",
  portugal: "🇵🇹",
  netherlands: "🇳🇱",
  croatia: "🇭🇷",
  ghana: "🇬🇭",
  korea: "🇰🇷",
  japan: "🇯🇵",
  tie: "🤝",
  draw: "🤝",
};

export function flagForTeam(label: string): string {
  const key = label.trim().toLowerCase();
  if (FLAGS[key]) return FLAGS[key];
  for (const [name, flag] of Object.entries(FLAGS)) {
    if (key.includes(name) || name.includes(key)) return flag;
  }
  if (/tie|draw/i.test(label)) return "🤝";
  return "⚽";
}
