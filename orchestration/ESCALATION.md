# Escalation: authz matrix verification host failure

The authz matrix repair is blocked before behavioral verification. After the
test-only classification and matrix-harness updates, three independent command
attempts failed before execution with Windows process initialization exit code
`0xC0000142` (`-1073741502`), including a trivial `Get-Location` command.

No route code or authentication behavior was changed. Restore PowerShell/
process startup, then run the focused authz matrix followed by the full backend
suite from `backend/` using the basetemp paths recorded in `AUTHZ-FIX.md`.
