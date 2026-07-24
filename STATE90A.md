# STATE90A — Backend node E-A (engagement / notifications)

Worktree: `E:/polymarket-worktrees/loop90-notif`  
Branch: `loop90/notif`  
Charter: backend/** + STATE90A.md  
Status: **DONE** (N1–N5)

Frozen FE contracts implemented (shapes unchanged):
- `GET /api/v1/notifications?limit=30` → `{items[{id,type,title,body,read,created_at,link}], unread}`
- `POST /api/v1/notifications/{id}/read` → 204
- `POST /api/v1/notifications/read-all` → `{marked}`
- `GET|PUT /api/v1/notifications/preferences` → `{email_digest,in_app,fired_alerts}`
- `POST /api/v1/notifications/push/subscribe` → `{stored:true}` (store only)

Migration head: `062_notif_engagement` (revises `061_scanner_test_runs`)

## Ticket log

### N1 — model + migration + feed CRUD
```
1db2b02e159d38ff700e5b4e790024518f5e2237
feat(loop90): N1 — notifications schema + frozen feed API
2026-07-23 21:00:12 -0400
```
```
......                                                                   [100%]
6 passed in 8.54s
```
(`uv run --extra dev pytest tests/test_notifications_api.py -q --basetemp=.../n1`)

### N2 — producers (scanner:fired / brief) + 1h idempotency
```
b342956f488f5a49692c75445da0b74f2d70bbbc
feat(loop90): N2 — scanner/brief in-app notification hooks
2026-07-23 21:02:16 -0400
```
```
0e2bb27147bb80ffac23052464cd6f008c33940a
feat(loop90): N2 — scanner/brief in-app notification producers
2026-07-23 21:02:54 -0400
```
```
............                                                             [100%]
12 passed in 14.60s
```
(`test_notifications_api.py` + `test_notification_producers_v90.py`)

### N3 — preferences API
```
2f54d060028ac27bb268e4fb490f0992a7ca2542
feat(loop90): N3 — notification preferences API tests
2026-07-23 21:02:49 -0400
```
```
...                                                                      [100%]
3 passed
```
(`tests/test_notification_preferences.py`)

### N4 — email digest (13:00 UTC dual-wire)
```
6676c3514205a8c2259822f543e8f20bb36fb710
feat(loop90): N4 — notification email digest at 13:00 UTC
2026-07-23 21:06:34 -0400
```
```
e09c2d845ed67244f1136018659f3a8385789746
feat(loop90): N4 — daily email notification digest at 13:00 UTC
2026-07-23 21:07:09 -0400
```
```
....                                                                     [100%]
4 passed in 11.45s
```
(`tests/test_notification_digest.py` — monkeypatched SMTP: 1 send when on, 0 when off)

### N5 — push subscribe store-only
```
6e95d0bf3574a5d17fda782a92096639b396ee3d
feat(loop90): N5 — push subscribe store-only endpoint tests
2026-07-23 21:07:28 -0400
```
```
...                                                                      [100%]
3 passed in 16.44s
```
(`tests/test_notification_push.py`)

## Aggregated proof

Notification cluster:
```
........................................                                 [100%]
40 passed in 29.52s
```

Full backend suite (`--basetemp` under this worktree):
```
2015 passed, 28 skipped, 4 warnings in 943.23s (0:15:43)
```

Ruff: `uv run --extra dev ruff check app tests` → All checks passed!

## Notes
- Paper-only; no order path; no web-push send; no new deps.
- Digest reuses `scanner_email_service` SMTP; skips silently when unconfigured.
- In-process `_notification_digest_loop` wall-clock to next 13:00 UTC + ARQ cron mirror.
- AutoLab: not applicable (no iterative measure)

## LOOP LOG
| loop | date | result | proof |
|------|------|--------|-------|
| V90 E-A N1–N5 | 2026-07-23 | DONE | 2015 passed / ruff clean / commits N1–N5 |
