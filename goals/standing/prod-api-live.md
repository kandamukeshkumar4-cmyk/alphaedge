# Standing goal: production API serves live Polymarket/Kalshi data
status: VIOLATED (2026-07-08 15:30 UTC)
predicate: py -3.13 scripts/verify_prod.py
graduated_from: e2e-ship loop 0 (2026-07-08)
note: verify_prod.py is created by e2e-ship Loop 0; until it exists this predicate fails loudly, which is correct.
