"""Manifest invariants. No cluster required — this is the pre-flight gate.

Every failure here is one that would otherwise surface as a CrashLoopBackOff or
an evicted pod ten minutes into a demo. They are cheap to assert and expensive
to discover live, which is the whole argument for static manifest tests.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

BASE = Path(__file__).resolve().parents[1]
DEPLOY = BASE / "deploy"

# Probes are required of long-running workloads. A Job or CronJob is exempt:
# it runs to completion, so "is it still alive" is answered by the Job
# controller and a liveness probe would only add a way to kill healthy work.
LONG_RUNNING = {"Deployment", "StatefulSet", "DaemonSet"}
POD_BEARING = LONG_RUNNING | {"Job", "CronJob"}

PLACEHOLDER = {"REPLACE_ME", "", None}


def load_all(path: Path) -> list[dict]:
    docs = yaml.safe_load_all(path.read_text(encoding="utf-8"))
    return [d for d in docs if isinstance(d, dict)]


def manifest_files() -> list[Path]:
    return sorted(p for p in DEPLOY.rglob("*.yaml") if p.name != "kustomization.yaml")


def all_docs() -> list[tuple[Path, dict]]:
    return [(p, d) for p in manifest_files() for d in load_all(p)]


def pod_spec(doc: dict) -> dict | None:
    kind = doc.get("kind")
    if kind in LONG_RUNNING:
        return doc["spec"]["template"]["spec"]
    if kind == "Job":
        return doc["spec"]["template"]["spec"]
    if kind == "CronJob":
        return doc["spec"]["jobTemplate"]["spec"]["template"]["spec"]
    return None


def workloads() -> list[tuple[Path, dict, dict]]:
    out = []
    for path, doc in all_docs():
        if doc.get("kind") in POD_BEARING:
            out.append((path, doc, pod_spec(doc)))
    return out


def ids(items) -> list[str]:
    return [f"{p.relative_to(DEPLOY)}::{d.get('kind')}/{d['metadata']['name']}"
            for p, d, *_ in items]


# --------------------------------------------------------------------------
# Structural sanity
# --------------------------------------------------------------------------


def test_every_manifest_parses_and_is_a_kubernetes_object():
    assert manifest_files(), "no manifests found — the test is pointing at nothing"
    for path, doc in all_docs():
        where = path.relative_to(DEPLOY)
        assert doc.get("apiVersion"), f"{where}: missing apiVersion"
        assert doc.get("kind"), f"{where}: missing kind"
        assert doc.get("metadata", {}).get("name"), f"{where}: missing metadata.name"


def test_every_namespaced_object_declares_its_namespace():
    cluster_scoped = {"Namespace", "ClusterRole", "ClusterRoleBinding", "StorageClass"}
    for path, doc in all_docs():
        if doc["kind"] in cluster_scoped:
            continue
        ns = doc["metadata"].get("namespace")
        assert ns in {"ai-sdlc", "ai-platform"}, (
            f"{path.relative_to(DEPLOY)}: {doc['kind']}/{doc['metadata']['name']} "
            f"has namespace {ns!r}; relying on the kubectl context is how objects "
            f"land in `default`"
        )


def test_there_is_at_least_one_workload_to_check():
    assert len(workloads()) >= 4


# --------------------------------------------------------------------------
# The invariants that stop a demo dying
# --------------------------------------------------------------------------


@pytest.mark.parametrize("path,doc,spec", workloads(), ids=ids(workloads()))
def test_every_container_sets_requests_and_limits(path, doc, spec):
    for c in spec["containers"]:
        res = c.get("resources", {})
        for side in ("requests", "limits"):
            assert side in res, f"{c['name']}: no resources.{side}"
            for dim in ("cpu", "memory"):
                assert dim in res[side], f"{c['name']}: no resources.{side}.{dim}"


@pytest.mark.parametrize(
    "path,doc,spec",
    [w for w in workloads() if w[1]["kind"] in LONG_RUNNING],
    ids=ids([w for w in workloads() if w[1]["kind"] in LONG_RUNNING]),
)
def test_long_running_workloads_define_all_three_probes(path, doc, spec):
    # The startup probe is the one people omit, and it is the one that matters:
    # without it, a container with a slow first boot (migrations, a model load)
    # is killed by liveness before it ever becomes ready, and the symptom looks
    # like a broken image rather than a too-short window.
    for c in spec["containers"]:
        for probe in ("startupProbe", "livenessProbe", "readinessProbe"):
            assert probe in c, f"{doc['metadata']['name']}/{c['name']}: no {probe}"


@pytest.mark.parametrize("path,doc,spec", workloads(), ids=ids(workloads()))
def test_images_are_tagged_and_never_latest(path, doc, spec):
    for c in spec["containers"]:
        image = c["image"]
        assert ":" in image.rsplit("/", 1)[-1], f"{image}: untagged, so not rollback-able"
        tag = image.rsplit(":", 1)[-1]
        assert tag != "latest", f"{image}: `latest` makes a rollback a coin toss"


@pytest.mark.parametrize("path,doc,spec", workloads(), ids=ids(workloads()))
def test_every_pod_runs_as_non_root(path, doc, spec):
    sc = spec.get("securityContext", {})
    assert sc.get("runAsNonRoot") is True, (
        f"{doc['metadata']['name']}: pod securityContext.runAsNonRoot must be true "
        f"— the namespaces enforce the restricted PSS profile, so a root pod is "
        f"rejected at admission and the failure is far less legible there"
    )
    for c in spec["containers"]:
        csc = c.get("securityContext", {})
        assert csc.get("allowPrivilegeEscalation") is False, \
            f"{c['name']}: allowPrivilegeEscalation must be explicitly false"


# --------------------------------------------------------------------------
# Secrets
# --------------------------------------------------------------------------


def test_no_manifest_contains_a_real_secret_value():
    for path, doc in all_docs():
        if doc["kind"] != "Secret":
            continue
        assert path.name.endswith("secret.example.yaml"), (
            f"{path.relative_to(DEPLOY)}: a committed Secret must be named "
            f"`secret.example.yaml` so it reads as a template at a glance"
        )
        for field in ("stringData", "data"):
            for key, value in (doc.get(field) or {}).items():
                assert value in PLACEHOLDER, (
                    f"{path.relative_to(DEPLOY)}: {field}.{key} is not a placeholder"
                )


def test_secret_templates_are_not_applied_by_kustomize():
    # Applying the template would create a Secret whose value is the literal
    # string REPLACE_ME, and the pods would start and fail authentication in a
    # way that looks like a provider outage.
    for kfile in DEPLOY.rglob("kustomization.yaml"):
        resources = (yaml.safe_load(kfile.read_text(encoding="utf-8")) or {}).get("resources", [])
        for r in resources:
            assert "secret.example" not in r, f"{kfile.relative_to(DEPLOY)} applies {r}"


def test_no_workload_takes_a_provider_credential_directly():
    """Agents get a scoped virtual key, never the upstream provider key.

    This is the manifest-level half of the single-egress claim: even before the
    NetworkPolicy, nothing in ai-sdlc is handed a credential that would work
    against a provider if it did get out.
    """
    upstream = {"OPENAI_API_KEY", "ANTHROPIC_API_KEY", "GEMINI_API_KEY"}
    for path, doc, spec in workloads():
        if doc["metadata"].get("namespace") != "ai-sdlc":
            continue
        for c in spec["containers"]:
            for env in c.get("env", []):
                if env["name"] not in upstream:
                    continue
                src = env.get("valueFrom", {}).get("secretKeyRef", {}).get("name")
                assert src == "litellm-virtual-keys", (
                    f"{doc['metadata']['name']}/{c['name']}: {env['name']} must come "
                    f"from litellm-virtual-keys, got {src!r}"
                )
                base = next((e for e in c["env"] if e["name"] == "OPENAI_BASE_URL"), None)
                assert base and "litellm" in base.get("value", ""), (
                    f"{doc['metadata']['name']}/{c['name']}: has a key but its base URL "
                    f"does not point at the gateway"
                )


# --------------------------------------------------------------------------
# Egress — the central claim of the cluster
# --------------------------------------------------------------------------


def test_ai_sdlc_denies_egress_by_default():
    policies = [d for _, d in all_docs()
                if d["kind"] == "NetworkPolicy" and d["metadata"]["namespace"] == "ai-sdlc"]
    assert policies, "ai-sdlc has no NetworkPolicy — the single-egress claim is prose"
    catch_all = [p for p in policies if p["spec"].get("podSelector") == {}]
    assert catch_all, "no policy selects all pods in ai-sdlc, so new pods are unrestricted"
    for p in catch_all:
        assert "Egress" in p["spec"]["policyTypes"]
        for rule in p["spec"].get("egress", []):
            assert "to" in rule, (
                f"{p['metadata']['name']}: an egress rule with no `to` allows the "
                f"whole internet on those ports"
            )


def test_only_the_gateway_may_reach_a_provider():
    allow = [d for _, d in all_docs()
             if d["kind"] == "NetworkPolicy" and d["metadata"]["namespace"] == "ai-platform"]
    assert allow, "ai-platform has no NetworkPolicy"
    selectors = [p["spec"]["podSelector"].get("matchLabels", {}) for p in allow]
    assert {"app.kubernetes.io/name": "litellm"} in selectors, (
        "no policy grants the gateway its outbound exception, so either nothing "
        "can reach a provider or everything can"
    )
