# AlphaEdge — Claude Code Instructions

> The canonical agent rules for this repo live in `AGENTS.md`. Read it first.
> This file gives Claude Code the same context as Codex and Cursor in
> `E:\polymarket clone`.

## Orchestration Constitution (binding)

Read `orchestration/ORCHESTRATION.md` before your first edit. Key laws:
done = `py -3.13 orchestration/gate.py` exit 0 with output pasted; 3 failed
attempts at one error = write `orchestration/ESCALATION.md` and stop; the
advisor model is called at most once per task and never implements; extra
scope is a defect; deploy-affecting work must pass
`py -3.13 scripts/verify_prod.py` against production.

## Pre-Implementation Workflow

Load `.agents/skills/pre-implementation-workflow/SKILL.md` before starting any
non-trivial implementation. Investigate the repository before asking the user
anything; then produce Goal / Blocking questions (0-3, each with a recommended
default) / Assumptions (max 5, load-bearing only) / Plan, and stop for
approval before implementing. Typo-class changes under ~20 lines with one
clear solution skip the process; new modules, schema changes, auth, money,
migrations, and deletions always use it in full.

## Codex First Skill

Load `.agents/skills/codex-first/SKILL.md` for any non-trivial implementation,
refactor, bug fix, CI fix, dependency/tooling change, test-writing pass, or bulk
codebase exploration. Claude writes the spec/work order, delegates hands-on work
to Codex when the skill says to, and then performs the diff review and
verification itself. Do not delegate design judgment, destructive operations,
secrets/MCP work, releases, pushes, GitHub mutations, or review of Codex output.

## Automatic Skill Use

Repo-local skills are installed in `.agents/skills/<skill-name>/SKILL.md`.
Claude shims in `.claude/skills/<skill-name>` point to those same folders. Before
planning, coding, reviewing, researching, operating tools, or preparing a
handoff, match the task against local skill `name` and `description` metadata and
load the relevant skills automatically. The user should not need to invoke a
slash command. Load only the smallest relevant set, keep AGENTS.md guardrails
higher priority, and skip platform-specific skills unless the task and current
environment actually match them.

## Truth-First Defaults

- Treat user claims, diagnoses, and plans as unverified until checked against
  code, tests, logs, or documentation.
- Use direct verdicts when useful: `Correct`, `Incorrect`, `Partially correct`,
  `Unknown`, `Bad approach`, `Better approach available`.
- Do not implement changes that make the project less secure, less testable, or
  less maintainable without flagging the issue first.
- Keep changes small, reviewable, and tied to a test or explicit documentation
  update.

## Scope & Guardrails (non-negotiable)

- Paper-trading prediction market **simulation** for NBA, broader sports, and
  election markets. Simulated funds only — no cash funding, payment rails, or
  external execution language.
- `PAPER_TRADING_ONLY=true` is required in local, CI, and deploy contexts.
- LLM/agent code cannot submit raw orders. The only allowed path is
  `RiskService` → validated `OrderIntent` → `OrderBookService`.
- Canonical test market: `nba-2025-01-15-lal-bos`.

## Verification

- Backend (from `backend/`): `uv run --extra dev pytest -q` and
  `uv run --extra dev ruff check app tests`.
- Frontend (from `frontend/`): `npm run lint`, `npm run typecheck`,
  `npm run build`.
- State which Execution Gate (see `AGENTS.md`) a PR claims; do not claim later
  gates unless verified by tests and runnable commands.

## AutoLab Persistence Loop (every improvement ticket)

For any ticket that improves a working artifact (backtest accuracy,
Brier/calibration, deploy smoke resilience, risk-unit coverage, API latency, or
UX), run the AutoLab persistence loop defined in `AGENTS.md` → "AutoLab
Persistence Loop" and `.agents/skills/autolab-persistence-loop/SKILL.md`.

The finding (AutoLab, long-horizon agents): long-task success is predicted by
persistence on the benchmark-edit-feedback loop, not by first-attempt quality.
Start from a green baseline gate, define the benchmark (use `verificationCommands`
or a metric API), then iterate measure → edit → re-measure → fold in feedback
under an explicit budget. Persist to the budget, but stop and reorganize after
`K` consecutive no-progress iterations (default `K=3`). Keep the best measured
artifact; never hand off worse than baseline.

Guardrail: never game the benchmark, and never weaken `PAPER_TRADING_ONLY`, the
order path, or any deploy gate to hit a metric. Record the AutoLab handoff line:

```text
AutoLab: baseline=<verified gate/measure> | benchmark=<metric/command> | iterations=<n + best result> | budget=<used/limit> | outcome=<improved / stalled-reorganized / retired>
```

For a one-shot fix with no measurable axis, state "AutoLab: not applicable (no
iterative measure)".

<!-- hyperresearch:start -->
## Research Base (hyperresearch) — Today is 2026-07-19

**CLI path: `hyperresearch`** — use this exact path for every hyperresearch command. It may not be on your system PATH.

**Paths in this document are relative to your current working directory**, not to the CLI binary's location. Use `research/notes/final_report_<vault_tag>.md` (not a prefix with the binary path) when you save files.

This project uses hyperresearch as an agent-driven research knowledge base. The `research/` directory contains markdown notes collected from web sources and original research. Append `--json` to any command for structured output.

### How to do research

**Run a research session with `/hyperresearch <query>`.** This invokes the V8 16-step pipeline. The entry skill at `.claude/skills/hyperresearch/SKILL.md` is a thin ROUTER. The step procedures live in their own skills (`hyperresearch-1-decompose` through `hyperresearch-16-readability-audit`, plus half-steps `1-5-chapter-partition` and `14-5-cite-check`) and are loaded fresh into context via the `Skill` tool when each step runs. This solves V7's context-compaction problem: each step's procedure lands in context only when needed. Read the entry skill before you start a research session; it explains the chain mechanics.

Step 1 classifies the query into a tier (`light` or `full`; `dissertation` is opt-in per run, never auto-classified) and the rest of the pipeline scales accordingly — short bounded queries skip the depth investigations, critics, and patcher (~30-40 min); argumentative deep-research queries run all 16 steps with adversarial review; dissertation runs loop steps 2-10 per chapter. Orthogonal to tiers, the installed **scale gear** (`full` ~55-80 sources, or `premier` ~100-130 sources with doubled depth budget) sets the numbers rendered into the step skills — the user switches it with `hyperresearch profile use <full|premier>`; inspect with `hyperresearch profile list -j`.

**Do NOT use WebFetch for source pages** — use `hyperresearch fetch` instead. The skill files explain when to fetch vs. search.

### Run management and verification

Every run owns a workspace at `research/runs/<vault_tag>/` and a manifest (`run.json`) — the durable record of pipeline position and spend:

```bash
hyperresearch run status -j                 # Newest run: step status, spend, escalation queue depth
hyperresearch run resume -j                 # Exact next step + Skill invocation to continue with
hyperresearch run report -j                 # Per-step wall-time / spend / event telemetry
hyperresearch run verify <vault_tag> -j     # Ship gate: headings, length, citation density, cite-check resolution
```

Blocked fetches (login walls, bot walls, captchas) queue as escalations instead of dying: `hyperresearch escalation list --status queued -j`. The browser-fetcher agent drains them via the user's real Chrome; CAPTCHAs / logins / 2FA are ALWAYS handed to the human, consolidated into one message.

### What the skill files own

The skill files own everything about how to research. That includes:
- The pipeline phases and what each phase does
- Which subagents exist and what each one is for (fetcher, source-analyst, loci-analyst, depth-investigator, corpus-critic, draft-orchestrators, synthesizer, 4 critics, patcher, cite-checker, polish-auditor, readability-recommender, browser-fetcher)
- The tool-lock invariant (patcher and polish-auditor can only Read + Edit, never Write)
- The subagent spawn contract (every Task call passes the verbatim research_query + pipeline position + inputs)
- Artifact locations — everything run-scoped lives under `research/runs/<vault_tag>/` (scaffold.md, prompt-decomposition.json, loci.json, comparisons.md, critic findings, patch / polish logs); final reports at `research/notes/final_report_<vault_tag>.md`
- The curation pass after every research session

If you need to know how hyperresearch works, read the skill file. This document does NOT duplicate that content — when the skill file and this file disagree, the skill file wins.

### Canonical research query

In a normal run, the canonical research query is the user's verbatim prompt. In wrapped runs, if `research/prompt.txt` exists, that file is gospel and overrides any wrapping instructions. The pipeline persists the query as `research/runs/<vault_tag>/query.md` with YAML frontmatter — this is the canonical query reference for all downstream steps. Wrapper requirements (save path, citation format, terminal sections) are a separate contract, captured in the scaffold — not pasted into the `## User Prompt (VERBATIM — gospel)` section.

### Academic APIs before web search

For any topic with a research literature, hit academic APIs BEFORE running web searches. They return citation-ranked canonical papers; web search returns derivative commentary.

- **Semantic Scholar:** `https://api.semanticscholar.org/graph/v1/paper/search?query=<q>&fields=title,year,citationCount,externalIds&limit=10` — then citation-chain the top papers forward + backward.
- **arXiv:** `https://export.arxiv.org/api/query?search_query=cat:cs.LG+AND+all:<q>&sortBy=relevance&max_results=25`
- **OpenAlex:** `https://api.openalex.org/works?search=<q>&sort=cited_by_count:desc&per-page=15&mailto=research@example.com`
- **PubMed:** `https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi?db=pubmed&term=<q>&retmode=json&retmax=20`

After the academic sweep, run web searches for context, news, non-academic angles, and at least one adversarial search ("criticism of X", "limitations of X").

### PDFs fetch directly

`hyperresearch fetch` auto-detects PDF URLs (arXiv, NBER, SSRN, direct `.pdf` links) and extracts full text via pymupdf. Fetch them aggressively. Raw PDFs land in `research/raw/<note-id>.pdf` and the note's frontmatter links back via `raw_file:`.

### Searching the vault

```bash
hyperresearch search "query" --json                # Full-text search
hyperresearch search "query" --tag ml --json       # Filter by tag / status / date / parent
hyperresearch search "query" --include-body --json # Full-body search, not just titles
hyperresearch note show <id> --json                # Read one note
hyperresearch note show <id1> <id2> <id3> --json   # Batch-read notes in one call
hyperresearch note list --json                     # List all notes with summaries
hyperresearch tags --json                          # Existing tag vocabulary
```

### Images, screenshots, and assets

```bash
hyperresearch fetch "<url>" --tag <topic> --save-assets -j   # Saves screenshot + top images
hyperresearch assets list --note <note-id> --json            # Assets for a specific note
hyperresearch assets path <note-id> --type screenshot -j     # Get screenshot path (viewable with Read)
```

### Authenticated crawling

Login-gated content (LinkedIn, Twitter, paywalled news) needs a browser profile. Set up once via `hyperresearch setup` or `crwl profiles`. Config in `.hyperresearch/config.toml` under `[web]`: `profile = "research"`, `magic = true`. LinkedIn / Twitter / Facebook / Instagram / TikTok auto-use a visible browser to avoid session kills.

If a fetch returns a login wall, tell the user to run `hyperresearch setup` and create a login profile.

### Curate after every session

Every research session must end with a curation pass:

```bash
hyperresearch note list --status draft -j                                        # Find unprocessed notes
hyperresearch note show <id> -j                                                  # Read the content
hyperresearch note update <id> --summary "<specific summary>" --add-tag <t> -j   # Add summary + tags
hyperresearch lint -j                                                            # Find missing tags / summaries / broken links
hyperresearch repair -j                                                          # Auto-fix broken links, rebuild indexes
hyperresearch sources score -j                                                   # Enrich DOI-bearing sources (citations, venue, retractions) + recompute quality
hyperresearch graph rank -j                                                      # Recompute vault PageRank centrality
hyperresearch status -j                                                          # Overall vault health
```

Lifecycle: `draft` → `review` → `evergreen` (or `stale` → `deprecated` → `archive` for outdated material).

Summaries must be specific — "Mamba achieves linear-time sequence modeling via selective state spaces" beats "Paper about Mamba". Reuse the existing tag vocabulary (`hyperresearch tags -j`) rather than inventing new tags.

### Key conventions

- Notes live in `research/notes/` as markdown with YAML frontmatter
- Link notes with `[[note-id]]` syntax
- After editing `.md` files directly, run `hyperresearch sync` to update the index
- Run `hyperresearch --help` for the full command list
<!-- hyperresearch:end -->
