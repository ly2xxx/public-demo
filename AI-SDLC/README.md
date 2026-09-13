# AI-SDLC control plane

One cluster where every AI call leaves through a single metered door, and the
thing that writes code is never the thing that judges it.

This is the deployable form of the workflow in
[`../deterministic-coding/`](../deterministic-coding/): plan before code,
freeze the definition of done, gate deterministically, review adversarially,
keep the evidence. Those are habits in a prompt file. Here they are objects in
a cluster, which is the difference between discipline someone has to remember
and discipline that holds when the release date gets tight.

```
Developer ──goal──▶ coding-engineer (one Job per run) ──/v1──▶ LiteLLM ──▶ Ollama Cloud
                          │                                      │          (only egress)
                          ├──diff──▶ gate-runner                 └──spend──▶ Postgres
                          │          (no model call — ever)
                          └──green──▶ git server: branch + run-report.md as the PR body

eval-harness (nightly CronJob) ──frozen golden set──▶ LiteLLM ──▶ drift panel
```

## The four claims, and where each is enforced

| Claim | Enforced by | Asserted by |
| --- | --- | --- |
| Exactly one egress point, metered and budgeted | `NetworkPolicy` in both namespaces; every workload gets a scoped virtual key, never a provider key | `test_manifests.py` |
| Maker is never checker | Roles resolve to different models in `litellm/config.yaml`; callers cannot name a model | `test_config.py` |
| "The tests passed" is never a model's opinion | `gate/run_gate.py` imports no HTTP client and no provider SDK | `test_gate.py` |
| An empty test suite is not a pass | pytest's no-tests-collected code is a FAIL with its own message | `test_gate.py` |

The fourth one is the specification-gaming defence. An agent that cannot make
the suite green can always delete it, so "no tests" and "tests passed" must
never reach the same verdict.

## Why a Job per run

One Job is one run is one worktree is one budget is one audit record. That
collapses four lifecycles into one that Kubernetes already manages:
`activeDeadlineSeconds` is the wall-clock budget, `backoffLimit: 0` means a
failed run escalates instead of silently retrying, and the pod's resource
limits are the blast radius. An agent can argue its way past a prompt. It
cannot argue its way past a kubelet.

## Run what can be run without a cluster

```bash
python3 -m pytest tests/ -q          # 51 manifest, routing and gate invariants
python3 gate/run_gate.py --target .  # the gate, gating itself
./scripts/preflight.sh               # both, plus kustomize/kubectl if present
```

`preflight.sh` names the checks it had to skip rather than passing quietly — a
skipped check is not a passed check, and the report says so.

## Deploy

```bash
./scripts/build_and_import.sh                  # SHA-tagged images into k3d
kubectl apply -k deploy/overlays/local
```

Secrets are created out of band; only `*.example.yaml` templates are committed,
and a test fails if one of them ever contains a real value:

```bash
kubectl -n ai-platform create secret generic litellm-secrets \
  --from-literal=master-key="sk-$(openssl rand -hex 24)" \
  --from-literal=salt-key="$(openssl rand -hex 16)" \
  --from-literal=database-url="postgresql://litellm:$PW@postgres:5432/litellm"
```

## State of play

Phase 1 is complete and verified on a laptop. Phases 2–4 are not started, and
[`PHASED.md`](PHASED.md) lists exactly what has and has not been run —
including the highest-risk untested assumption, which is that LiteLLM parses
`litellm/config.yaml` at all. That schema was written from documentation, not
from a successful boot.

Two defects turned up the first time the gate was pointed at its own repository,
and both are recorded in `PHASED.md`. That is the argument for self-hosting a
gate: the test suite passed throughout.
