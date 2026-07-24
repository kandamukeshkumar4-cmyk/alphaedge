# STATE90A — Backend node E-A (engagement / notifications)

Worktree: `E:/polymarket-worktrees/loop90-notif`  
Branch: `loop90/notif`  
Charter: `backend/**` + this file. Migration owner this wave.  
Status: **N1–N5 DONE** — STOP (no push/deploy).

Frozen FE contracts implemented (shapes unchanged):
- `GET /api/v1/notifications?limit=30` → `{items:[{id,type,title,body,read,created_at,link}], unread:N}`
- `POST /api/v1/notifications/{id}/read` → `204`
- `POST /api/v1/notifications/read-all` → `{marked:N}`
- `GET|PUT /api/v1/notifications/preferences` → `{email_digest,in_app,fired_alerts}`
- `POST /api/v1/notifications/push/subscribe` → `{stored:true}` (store JSON only)

Migration head chained: `061_scanner_test_runs` → `062_notif_engagement` (id ≤32).

Paper-only: no orders / RiskService / OrderBookService. No new deps. Web-push send not built.

---

## Commits

```
6e95d0b feat(loop90): N5 — push subscribe store-only endpoint tests
e09c2d8 feat(loop90): N4 — daily email notification digest at 13:00 UTC
6676c35 feat(loop90): N4 — notification email digest at 13:00 UTC
0e2bb27 feat(loop90): N2 — scanner/brief in-app notification producers
2f54d06 feat(loop90): N3 — notification preferences API tests
b342956 feat(loop90): N2 — scanner/brief in-app notification hooks
1db2b02 feat(loop90): N1 — notifications schema + frozen feed API
```

---

## N1 — model + migration + CRUD

**git log -1** (at N1):
```
1db2b02 feat(loop90): N1 — notifications schema + frozen feed API
```

**pytest** (`tests/test_notifications_api.py`, basetemp under worktree):
```
.......                                                                  [100%]
7 passed in 9.60s
```

Schema: `notifications(user str(64), type(24), title(200), body(1000), read bool, link(300), created_at)` + `notification_preferences` + `push_subscriptions`.

---

## N2 — in-app feed + scanner/brief hooks

**git log -1**:
```
b342956 feat(loop90): N2 — scanner/brief in-app notification hooks
0e2bb27 feat(loop90): N2 — scanner/brief in-app notification producers
```

**pytest** (`tests/test_notification_hooks.py` + related):
```
...........                                                              [100%]
11 passed in 12.51s
```

Hooks: `record_scanner_fired_alert` → `notify_scanner_fired` (`scanner:fired`); analyst `persist_publish` → `notify_watchers_brief_created` (`brief`). Respects `in_app` (+ `fired_alerts` for scanner). Idempotent `(user,type,link)` within 1h.

---

## N3 — preferences API

**git log -1**:
```
2f54d06 feat(loop90): N3 — notification preferences API tests
```

**pytest** (`tests/test_notification_preferences.py`):
```
...                                                                      [100%]
3 passed in 11.99s
```

---

## N4 — email digest dual-wire (13:00 UTC)

**git log -1**:
```
6676c35 feat(loop90): N4 — notification email digest at 13:00 UTC
e09c2d8 feat(loop90): N4 — daily email notification digest at 13:00 UTC
```

**pytest** (`tests/test_notification_digest.py`):
```
....                                                                     [100%]
4 passed in 12.66s
```

- Task: `async def send_notification_digest_task(ctx)`
- In-process: `_notification_digest_loop` — seconds-to-next-13:00 (no sleep-first-24h)
- ARQ: `cron(send_notification_digest_task, hour={13}, minute={0})`
- SMTP via existing helper; skip silently if unconfigured

---

## N5 — push subscribe (store only)

**git log -1**:
```
6e95d0bf3574a5d17fda782a92096639b396ee3d
feat(loop90): N5 — push subscribe store-only endpoint tests
```

**pytest** (`tests/test_notification_push.py`):
```
...                                                                      [100%]
3 passed in 8.90s
```

---

## Full suite (end)

```text
cd backend && uv run --extra dev pytest -q --basetemp=../.pytest-basetemp/full
2015 passed, 28 skipped in 992.59s (0:16:32)
```

AutoLab: not applicable (no iterative measure — contract implementation tickets).

---

## STOP

N1–N5 complete. No push / no deploy.
