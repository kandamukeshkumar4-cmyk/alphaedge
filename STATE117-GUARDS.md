# STATE117-GUARDS — D2: clarify loop never silently ready with zero steps

Tester defect D2: the loop116 conversational compile clarify loop could return
`status:"ready"` for a draft whose spec has `steps: []`; testfire then rejected
it with 400 "draft has no steps". Fix in
`backend/app/services/scanner_compiler_service.py` (route untouched — the
testfire 400 stays as the last-line guard):

- When the loop would return ready with zero steps and clarify rounds remain
  (`round < MAX_CLARIFY_ROUNDS`), it now returns `needs_clarification` with a
  kind-`"other"` question: "What signal should this scanner watch for?" —
  suggestions are the human labels of all 7 step types (Whale flow, Price
  trend, News sentiment, Model edge, Direction alignment, Cross-venue
  divergence, Closing soon).
- After the max-2-rounds best-effort rule, if still zero steps, the draft goes
  ready but carries the warning `no signal steps — add one before test-firing`
  so the UI can surface it (never a silent empty-ready).

Tests added to `backend/tests/test_loop116_convo.py`:
`test_vague_prompt_without_steps_asks_signal_question`,
`test_best_effort_ready_with_no_steps_carries_warning`.

## Verify (verbatim)

```text
$ cd backend && uv run --extra dev pytest -q tests/test_loop116_convo.py --basetemp=E:/polymarket-worktrees/loop117-guards/.pt ; uv run --extra dev ruff check app tests
Using CPython 3.12.13
Creating virtual environment at: .venv
   Building alphaedge @ file:///E:/polymarket-worktrees/loop117-guards/backend
      Built alphaedge @ file:///E:/polymarket-worktrees/loop117-guards/backend
warning: Failed to hardlink files; falling back to full copy. This may lead to degraded performance.
         If the cache and target directories are on different filesystems, hardlinking may not be supported.
         If this is intentional, set `export UV_LINK_MODE=copy` or use `--link-mode=copy` to suppress this warning.
Installed 95 packages in 25.98s
........                                                                 [100%]
8 passed in 45.77s
All checks passed!
```
