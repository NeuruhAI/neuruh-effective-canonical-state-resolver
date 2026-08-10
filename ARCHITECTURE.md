# Architecture

026 lifecycle tip ──┐
                    ├─→ 036 resolve() ─→ effective canonical truth (or fail-closed ambiguous)
035 revision lineage┘

036 independently re-verifies every revision lineage against the exact Release 035 v0.1 schema (chain, threading, anchor constancy, single consumption, content hashes) — it trusts no producer. Lifecycle evidence arrives as an explicit bounded tip claim; the resolver never reads live systems.

Resolution is a pure function: same evidence in any order yields the same `resolution_digest`. The output is sealed, content-bound, and carries no authority.
