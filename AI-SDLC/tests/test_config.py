"""Gateway routing invariants.

`maker != checker` is the control this whole design rests on. It is one line in
a ConfigMap, which means it is one careless edit away from being untrue — and
the failure is silent: everything still works, the reviews just stop being
independent. So it is a test.
"""

from __future__ import annotations

from pathlib import Path

import yaml

BASE = Path(__file__).resolve().parents[1]
CONFIG = BASE / "litellm" / "config.yaml"
DEPLOY = BASE / "deploy"

config = yaml.safe_load(CONFIG.read_text(encoding="utf-8"))
MODELS = {m["model_name"]: m for m in config["model_list"]}


def underlying(role: str) -> str:
    return MODELS[role]["litellm_params"]["model"]


def test_the_four_roles_exist():
    assert set(MODELS) == {"maker", "checker", "judge", "embed"}


def test_role_names_are_unique():
    names = [m["model_name"] for m in config["model_list"]]
    assert len(names) == len(set(names)), f"duplicate role: {names}"


def test_maker_is_not_the_checker():
    assert underlying("maker") != underlying("checker"), (
        "the reviewer resolves to the same model as the author — reviews are no "
        "longer independent, and nothing else in the system will notice"
    )


def test_the_checker_and_judge_are_deterministic():
    # A reviewer that answers differently on identical input turns a rejected
    # change into a re-roll, and the loop learns to retry rather than to fix.
    for role in ("checker", "judge"):
        assert MODELS[role]["litellm_params"].get("temperature") == 0.0, (
            f"{role} must be temperature 0"
        )


def test_no_credential_is_written_into_the_config():
    text = CONFIG.read_text(encoding="utf-8")
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("#") or ":" not in stripped:
            continue
        value = stripped.split(":", 1)[1].strip().strip("\"'")
        if not value:
            continue
        assert not value.startswith("sk-"), f"literal key in config: {line!r}"
    assert config["general_settings"]["master_key"].startswith("os.environ/")
    assert config["general_settings"]["database_url"].startswith("os.environ/")


def test_every_upstream_resolves_through_the_configured_base_url():
    for role, m in MODELS.items():
        api_base = m["litellm_params"].get("api_base")
        assert api_base == "os.environ/OLLAMA_BASE_URL", (
            f"{role}: api_base is {api_base!r}; a hard-coded endpoint here is a "
            f"second egress path that the NetworkPolicy does not describe"
        )


def test_spend_is_persisted_and_a_budget_exists():
    settings = config["litellm_settings"]
    assert "postgres" in settings["success_callback"], "spend is not persisted"
    assert settings.get("max_budget", 0) > 0, "no cluster budget ceiling"


def test_roles_named_in_manifests_all_exist_in_the_config():
    """A workload asking for a role the gateway does not define fails at
    request time, in a pod, at demo o'clock. Catch it here instead."""
    referenced: set[str] = set()
    for path in DEPLOY.rglob("*.yaml"):
        if path.name == "kustomization.yaml":
            continue
        for doc in yaml.safe_load_all(path.read_text(encoding="utf-8")):
            if not isinstance(doc, dict):
                continue
            for env in _envs(doc):
                if env["name"].endswith("_MODEL") and "value" in env:
                    referenced.add(env["value"])
    assert referenced, "no *_MODEL env vars found — this test is checking nothing"
    missing = referenced - set(MODELS)
    assert not missing, f"manifests reference undefined roles: {sorted(missing)}"


def _envs(doc: dict):
    specs = []
    kind = doc.get("kind")
    try:
        if kind in {"Deployment", "StatefulSet", "Job"}:
            specs.append(doc["spec"]["template"]["spec"])
        elif kind == "CronJob":
            specs.append(doc["spec"]["jobTemplate"]["spec"]["template"]["spec"])
    except KeyError:
        return
    for spec in specs:
        for c in spec.get("containers", []):
            yield from c.get("env", [])
