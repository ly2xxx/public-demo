# AI-SDLC control plane — design

One cluster where every AI call in the estate leaves through a single metered door,
and the thing that writes code is never the thing that judges it.

## 1. Boundaries & directory layout

Two namespaces, one trust boundary. `ai-sdlc` runs work; `ai-platform` runs the
shared services work depends on. The boundary that matters is egress: no workload
in `ai-sdlc` may reach a model provider directly — only `litellm` in `ai-platform`
holds the upstream credential, and a NetworkPolicy enforces it.

```
AI-SDLC/
  deploy/base/          namespaces · litellm · postgres · redis · workloads
  deploy/overlays/local kustomize overlay for a Rancher/k3s dev cluster
  litellm/config.yaml   role→model routing, budgets, callbacks
  gate/run_gate.py      deterministic quality gate (NO model calls, enforced by test)
  eval/                 frozen golden task set + nightly runner
  tests/                manifest invariants + gate unit tests (no cluster needed)
  scripts/              build, import, seed keys, smoke
```

## 2. Core objects

| Object | Kind | Why it is shaped this way |
|---|---|---|
| `litellm` | Deployment | The single egress. Holds the provider key, mints per-role virtual keys, enforces budgets, writes spend to Postgres. |
| `postgres` | StatefulSet + PVC | Spend and audit. Logs rotate; an audit trail must be queryable. |
| `redis` | Deployment | Checkpoints, rate limit, cache. Loss is degradation, not data loss — so no PVC. |
| `coding-engineer` | Job, one per run | A run is a Job: budget, worktree and audit record all get the same lifecycle. Not a long-lived pod. |
| `gate-runner` | Job (or container in CI) | Lint, tests, coverage, contract. Deterministic by construction. |
| `eval-harness` | CronJob | Nightly frozen golden set against whatever the gateway currently routes to. |

**Roles, not models.** Callers ask for `maker`, `checker` or `judge`; the gateway maps
those to concrete models. Swapping a model is a ConfigMap change, which is what makes
the eval gate in front of it meaningful — and what makes maker≠checker a deployment
property rather than a convention someone has to remember.

## 3. Cross-cutting contracts

- **Egress.** Exactly one pod may reach a provider. NetworkPolicy denies egress from
  `ai-sdlc` except DNS and `litellm`. This is the demo's central claim, so it is a
  test, not a sentence.
- **Budget.** Every virtual key carries `max_budget`. Exhaustion returns 429; the
  agent escalates and commits nothing. Fails closed — the opposite of rate limiting,
  and deliberately so.
- **Determinism.** `gate/run_gate.py` imports no HTTP or model client, asserted
  statically by `tests/test_gate.py`. "The tests passed" can never be a model's opinion.
- **Provenance.** Every run emits `run-report.md`: goal, frozen criteria, plans tried
  and scored, gate results, review findings, tokens and cost. It becomes the PR body.
- **Config vs secrets.** Config in ConfigMap, secrets out-of-band. Only
  `secret.example.yaml` is committed, with placeholder values, asserted by test.
- **Images.** Tagged with a git SHA, never `latest`, so rollback is real.

## 4. Test strategy & boundary matrix

| Layer | Runs where | Needs a cluster |
|---|---|---|
| Manifest invariants — limits, all three probes, non-root, no literal secrets, no `latest` | `pytest tests/test_manifests.py` | no |
| Gate determinism — no model-reaching import, report shape, exit codes | `pytest tests/test_gate.py` | no |
| Config coherence — every role in `litellm/config.yaml` resolves; maker ≠ checker | `pytest tests/test_config.py` | no |
| Egress policy — a pod in `ai-sdlc` cannot reach the internet directly | `tests/e2e/` | yes |
| Budget exhaustion — key at zero returns 429 and the Job escalates | `tests/e2e/` | yes |

Everything above the line is the Definition of Done for Phase 1 and runs on a laptop.
Everything below needs the cluster and is Phase 3 — recorded as not-run until it is.
