# Phased delivery log

Running record of what has actually been built against [`DESIGN.md`](DESIGN.md).

**Rule for this file:** a checkbox is ticked only when something was run and
observed. Anything believed-but-unverified is written as a deviation, not a tick.

| Phase | Theme | Status |
| --- | --- | --- |
| 1 | Manifests, gateway routing, deterministic gate | ✅ Complete |
| 2 | Images and the coding-engineer entrypoint | ⬜ Not started |
| 3 | Cluster bring-up on Rancher, e2e suite | ⬜ Not started |
| 4 | Budget-kill and model-swap demo beats | ⬜ Not started |

---

## Phase 1 — Manifests, routing, gate ✅

<!-- phase: 1 -->
<!-- targets: AI-SDLC/deploy/**/*.yaml, AI-SDLC/litellm/*.yaml, AI-SDLC/gate/*.py, AI-SDLC/tests/*.py, AI-SDLC/eval/golden/*, AI-SDLC/scripts/*.sh, AI-SDLC/docker/*, AI-SDLC/*.md, AI-SDLC/.gitignore -->
<!-- frozen: -->

**Capability:** everything that can be made correct without a cluster, made
correct and asserted by a test that runs on a laptop.

### What shipped

| Area | Files |
| --- | --- |
| Namespaces + egress policy | `deploy/base/namespaces.yaml` |
| Gateway | `deploy/base/litellm/{deployment,service,env-configmap,secret.example}.yaml` |
| Audit store | `deploy/base/postgres/{statefulset,service,secret.example}.yaml` |
| Ephemeral state | `deploy/base/redis/{deployment,service}.yaml` |
| Workloads | `deploy/base/workloads/{coding-engineer-job,eval-harness-cronjob}.yaml` |
| Overlay | `deploy/overlays/local/kustomization.yaml` |
| Routing | `litellm/config.yaml` — roles `maker` / `checker` / `judge` / `embed` |
| Gate | `gate/run_gate.py` |
| Golden set | `eval/golden/{tasks.yaml,baseline.json}` |
| Tests | `tests/{test_manifests,test_config,test_gate}.py` |

### Definition of Done

- [x] Every container declares CPU and memory requests **and** limits
- [x] Every long-running workload declares all three probes
- [x] Every image is tagged and none is `latest`
- [x] Every pod sets `runAsNonRoot`; every container sets `allowPrivilegeEscalation: false`
- [x] The only committed Secrets are `*.example.yaml` with placeholder values, and
      the kustomization does not apply them
- [x] No workload in `ai-sdlc` receives an upstream provider credential — only a
      `litellm-virtual-keys` entry, with its base URL pointing at the gateway
- [x] `ai-sdlc` has a catch-all deny-egress NetworkPolicy with no open `to`-less rule
- [x] `maker` and `checker` resolve to different underlying models
- [x] `checker` and `judge` run at temperature 0
- [x] Every `*_MODEL` value in a manifest resolves to a role defined in the config
- [x] The gate imports no HTTP client and no provider SDK (asserted against the AST)
- [x] A repository with no tests **fails** the gate rather than skipping the check
- [x] The gate runs clean against this project itself

### Verification — run and observed, 2026-09-13

```
$ python3 -m pytest tests/ -q
51 passed in 1.44s

$ python3 gate/run_gate.py --target . --report QUALITY_REPORT.md
PASS  lint      no findings in E9,F821,F822,F823     (ruff 0.15.8)
PASS  tests     51 passed in 1.42s
SKIP  coverage  coverage not measured
PASS  secrets   no credential shapes found
exit=0
```

### Two defects the self-hosted run found

Worth recording because they are the argument for self-hosting the gate at all:
both were invisible to the test suite and appeared the first time the gate was
pointed at its own repository.

1. **The gate ran tests under the wrong interpreter.** It located `pytest` with
   `shutil.which`, which resolved to a console script belonging to a different
   Python than the one running the gate — so `import yaml` failed inside the
   child while working fine in the parent. Now `sys.executable -m pytest`, with
   `importlib.util.find_spec` for the availability check. In a container this
   would have surfaced as a mystery collection error at exactly the wrong moment.

2. **The secret scanner flagged its own fixtures.** Six false positives, all of
   them deliberately credential-shaped test data or a documented `kubectl create
   secret` example. A scanner that cries wolf gets switched off, so it grew a
   per-line `# gate:allow-secret` pragma — per-line specifically, so the excuse
   sits next to the thing it excuses and shows up in review.

### Deviations from DESIGN.md

| Deviation | Why | Consequence |
| --- | --- | --- |
| `docker/Dockerfile.coding-engineer` copies `coding_agent/`, which does not exist in this directory | The loop lives in `langgraph_ollama/coding_agent`; extracting it into an installable package is Phase 2 | **The image cannot build yet.** This is not a working Dockerfile, it is the target shape. |
| `docker/Dockerfile.eval-harness` entrypoints `eval/run_eval.py`, which is not written | Phase 2 | Same — the CronJob manifest is real, the thing it runs is not |
| `eval/golden/baseline.json` has `"status": "unrecorded"` | A baseline recorded against no model is a fiction | The drift threshold has nothing to compare against until Phase 3 |
| Coverage floor is configured but unmeasured | `--cov-package` needs a package; this phase is manifests and one script | Coverage reports SKIP, and SKIP is excluded from the verdict rather than counted as a pass |
| `checksum/config` annotation is a literal placeholder | Kustomize's ConfigMap hash suffix already rolls the Deployment; the annotation documents intent for a non-kustomize path | Harmless, but it is not doing the work the name implies |

### Not verified — no cluster or container runtime in this environment

None of the following was run, so none of it is ticked. `kubectl`, `kustomize`,
`helm`, `docker` and `k3d` are all absent here.

- [ ] `kustomize build deploy/overlays/local` renders
- [ ] `kubectl apply -k` brings every pod to Ready
- [ ] LiteLLM actually parses `litellm/config.yaml` — **the highest-risk untested
      assumption in the phase.** The schema is written from documentation, not from
      a successful boot, and the `postgres` success-callback name in particular
      should be treated as unconfirmed until a pod logs it.
- [ ] The NetworkPolicy actually blocks a direct provider call from `ai-sdlc`
- [ ] Ollama is reachable at `host.k3d.internal:11434` from inside the cluster
- [ ] A budget-exhausted virtual key returns 429 and the Job escalates

`scripts/preflight.sh` runs whichever of these the local machine can support and
says out loud which it skipped, rather than passing quietly.

---

## Phase 2 — Images and the entrypoint ⬜

Extract `coding_agent` into an installable package; write `eval/run_eval.py`;
make both images build. **Done when** `scripts/build_and_import.sh` produces two
SHA-tagged images and `docker run --rm <img> --help` exits 0 for each.

## Phase 3 — Cluster bring-up ⬜

Apply to a Rancher/k3s cluster; record the real bring-up failures. **Done when**
every pod reaches Ready from a clean cluster, and `tests/e2e/` proves the egress
policy blocks a direct provider call from `ai-sdlc`.

## Phase 4 — The two demo beats ⬜

Budget to zero → 429 → escalation with nothing committed. Model swapped in the
ConfigMap → nightly eval scores drop → drift alert. **Done when** both are
recorded on video, because neither should ever be attempted live.
