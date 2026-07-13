# B3 — Watchlists completed

CRUD already existed (J01 + migration 035). This ticket adds additive
`watching_count` on `GET /api/v1/markets/{slug}/detail` (count of distinct
watchlist rows for the slug). Duplicate adds do not inflate the count.
