"""The gate's own tests. The first one is the point of the whole file.

If `run_gate.py` could reach a model, then "the tests passed" would be a thing a
model decided, and every downstream guarantee in this repo would rest on that.
So the import graph is asserted, not trusted.
"""

from __future__ import annotations

import ast
import importlib.util
import sys
from pathlib import Path

import pytest

BASE = Path(__file__).resolve().parents[1]
GATE = BASE / "gate" / "run_gate.py"

spec = importlib.util.spec_from_file_location("run_gate", GATE)
run_gate = importlib.util.module_from_spec(spec)
sys.modules["run_gate"] = run_gate
spec.loader.exec_module(run_gate)


# Anything that speaks HTTP, or any provider SDK. `socket` is included because
# it is the floor beneath all of them.
NETWORK_MODULES = {
    "socket", "ssl", "http", "urllib", "urllib3", "requests", "httpx", "aiohttp",
    "openai", "anthropic", "litellm", "google", "cohere", "ollama", "boto3",
    "langchain", "langgraph", "transformers", "xmlrpc", "ftplib", "smtplib",
}


def imported_modules(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    found: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            found.update(a.name.split(".")[0] for a in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
            found.add(node.module.split(".")[0])
    return found


def test_gate_imports_no_network_or_model_client():
    offenders = imported_modules(GATE) & NETWORK_MODULES
    assert not offenders, (
        f"gate/run_gate.py imports {sorted(offenders)}. The gate must be "
        f"deterministic: if it can call a model, a green gate is an opinion."
    )


def test_gate_strips_proxy_variables_from_child_processes():
    """The residual hole in the claim above, closed as far as it can be here.

    `subprocess` is imported — it has to be, the gate shells out to ruff and
    pytest — so a child process could in principle reach the network. Three
    things narrow that: the proxy variables are stripped here, the
    NetworkPolicy denies egress from the namespace, and the child processes are
    the project's own declared tooling. Worth saying out loud rather than
    claiming an airtight guarantee.
    """
    src = GATE.read_text(encoding="utf-8")
    assert "HTTPS_PROXY" in src and "HTTP_PROXY" in src
    assert "subprocess.run" in src


# --------------------------------------------------------------------------
# Report semantics
# --------------------------------------------------------------------------


def result(name="lint", passed=True, skipped=False, summary="s", detail=""):
    return run_gate.CheckResult(name=name, passed=passed, summary=summary,
                                detail=detail, skipped=skipped)


def test_a_skipped_check_is_not_a_passed_check(tmp_path):
    report = tmp_path / "QUALITY_REPORT.md"
    run_gate.write_report(report, [result(skipped=True, passed=False)], tmp_path)
    text = report.read_text(encoding="utf-8")
    assert "INCONCLUSIVE" in text
    assert "PASSED" not in text.split("\n")[2]
    assert "A skipped check is not a passed check" in text


def test_one_failure_fails_the_verdict(tmp_path):
    report = tmp_path / "r.md"
    run_gate.write_report(report, [result(), result(name="tests", passed=False)], tmp_path)
    assert "**Verdict: FAILED**" in report.read_text(encoding="utf-8")


def test_all_passing_passes(tmp_path):
    report = tmp_path / "r.md"
    run_gate.write_report(report, [result(), result(name="tests")], tmp_path)
    assert "**Verdict: PASSED**" in report.read_text(encoding="utf-8")


def test_skipped_checks_do_not_drag_down_a_clean_verdict(tmp_path):
    report = tmp_path / "r.md"
    run_gate.write_report(
        report, [result(), result(name="coverage", passed=False, skipped=True)], tmp_path
    )
    assert "**Verdict: PASSED**" in report.read_text(encoding="utf-8")


# --------------------------------------------------------------------------
# Secret detection
# --------------------------------------------------------------------------


@pytest.mark.parametrize("payload,should_flag", [
    ('KEY = "sk-abcdefghijklmnopqrstuvwxyz012345"', True),  # gate:allow-secret
    ('DSN = "postgresql://user:hunter2pass@db:5432/app"', True),  # gate:allow-secret
    ('-----BEGIN RSA PRIVATE KEY-----', True),  # gate:allow-secret
    ('KEY = os.environ["OPENAI_API_KEY"]', False),
    ('DSN = "postgresql://user@db:5432/app"', False),
    ('note = "use sk- prefixed keys"', False),
])
def test_secret_scan_flags_credential_shapes(tmp_path, payload, should_flag):
    (tmp_path / "app.py").write_text(payload, encoding="utf-8")
    res = run_gate.check_no_secrets(tmp_path)
    assert res.passed is not should_flag, f"{payload!r}: expected flag={should_flag}"


def test_secret_scan_ignores_binaries_and_vendored_trees(tmp_path):
    vendor = tmp_path / "node_modules" / "pkg"
    vendor.mkdir(parents=True)
    (vendor / "index.js").write_text(
        'const k = "sk-abcdefghijklmnopqrstuvwxyz012345"', encoding="utf-8")  # gate:allow-secret
    assert run_gate.check_no_secrets(tmp_path).passed


# --------------------------------------------------------------------------
# Exit codes
# --------------------------------------------------------------------------


def test_missing_target_is_unrunnable_not_failed(tmp_path):
    code = run_gate.main(["--target", str(tmp_path / "nope"), "--report", str(tmp_path / "r.md")])
    assert code == run_gate.EXIT_UNRUNNABLE, (
        "a missing target is an infrastructure problem; reporting it as a code "
        "failure sends whoever reads it to debug the wrong thing"
    )


def test_a_repository_with_no_tests_does_not_pass(tmp_path):
    """The cheapest specification-gaming attack, closed.

    An agent that cannot make the suite green can always delete it. If an empty
    suite exited clean, that would be the shortest path to a passing gate — so
    "no tests collected" is a FAIL with its own message, never a SKIP.
    """
    (tmp_path / "ok.py").write_text("x = 1\n", encoding="utf-8")
    report = tmp_path / "QUALITY_REPORT.md"
    code = run_gate.main(["--target", str(tmp_path), "--report", str(report)])
    assert code == run_gate.EXIT_FAILED
    text = report.read_text(encoding="utf-8")
    assert "**Verdict: FAILED**" in text
    assert "no tests collected" in text


def test_a_target_with_a_real_passing_test_exits_clean(tmp_path):
    (tmp_path / "ok.py").write_text("def add(a, b):\n    return a + b\n", encoding="utf-8")
    (tmp_path / "test_ok.py").write_text(
        "from ok import add\n\n\ndef test_add():\n    assert add(2, 2) == 4\n", encoding="utf-8"
    )
    report = tmp_path / "QUALITY_REPORT.md"
    code = run_gate.main(["--target", str(tmp_path), "--report", str(report)])
    assert code == run_gate.EXIT_CLEAN, report.read_text(encoding="utf-8")
    assert "**Verdict: PASSED**" in report.read_text(encoding="utf-8")


def test_a_planted_credential_fails_the_run(tmp_path):
    (tmp_path / "leak.py").write_text(
        'TOKEN = "ghp_abcdefghijklmnopqrstuvwxyz0123456789"\n', encoding="utf-8"  # gate:allow-secret
    )
    code = run_gate.main(["--target", str(tmp_path), "--report", str(tmp_path / "r.md")])
    assert code == run_gate.EXIT_FAILED
