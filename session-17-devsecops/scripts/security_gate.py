#!/usr/bin/env python3
"""Security gate – reads the JSON reports of every security stage and decides
whether the pipeline may continue (exit 0) or must stop (exit 1).

Policy (Session 17, Saniya Sanjiv Patil – 24bcs10246):
  * SAST (Semgrep)        : block on any finding with severity ERROR
  * SCA  (pip-audit)      : block on any known vulnerability in a dependency
  * SCA  (Trivy fs)       : block on HIGH / CRITICAL with a fix available
  * Secrets (gitleaks)    : block on any leaked secret
  * Image (Trivy image)   : block on HIGH / CRITICAL with a fix available
A missing report also blocks (a scan that did not run is not a pass).
"""
import json
import pathlib
import sys

REPORTS = pathlib.Path(sys.argv[1] if len(sys.argv) > 1 else "reports")
BLOCKING = {"CRITICAL", "HIGH"}


def load(name):
    path = REPORTS / name
    if not path.exists():
        return None
    text = path.read_text().strip()
    return json.loads(text) if text else []


def semgrep(data):
    results = data.get("results", [])
    errors = [r for r in results if r.get("extra", {}).get("severity") == "ERROR"]
    return len(errors), f"{len(results)} finding(s), {len(errors)} ERROR"


def pip_audit(data):
    vulns = [(d["name"], v["id"]) for d in data.get("dependencies", []) for v in d.get("vulns", [])]
    return len(vulns), f"{len(data.get('dependencies', []))} package(s) audited, {len(vulns)} vulnerable"


def trivy(data):
    sev = {}
    for result in data.get("Results", []) or []:
        for v in result.get("Vulnerabilities", []) or []:
            sev[v["Severity"]] = sev.get(v["Severity"], 0) + 1
    blocking = sum(n for s, n in sev.items() if s in BLOCKING)
    summary = ", ".join(f"{s}={n}" for s, n in sorted(sev.items())) or "0 vulnerabilities"
    return blocking, summary


def gitleaks(data):
    return len(data), f"{len(data)} secret(s) found"


CHECKS = [
    ("SAST", "Semgrep", "semgrep.json", semgrep),
    ("SCA", "pip-audit", "pip-audit.json", pip_audit),
    ("SCA", "Trivy fs", "trivy-fs.json", trivy),
    ("Secrets", "gitleaks", "gitleaks.json", gitleaks),
    ("Image", "Trivy image", "trivy-image.json", trivy),
]

failed = False
print(f"{'Stage':<8} {'Tool':<12} {'Result':<7} Details")
print("-" * 72)
for stage, tool, report, check in CHECKS:
    data = load(report)
    if data is None:
        blocking, details = 1, f"report {report} missing -> scan did not run"
    else:
        blocking, details = check(data)
    status = "FAIL" if blocking else "PASS"
    failed |= bool(blocking)
    print(f"{stage:<8} {tool:<12} {status:<7} {details}")
print("-" * 72)
if failed:
    print("SECURITY GATE: FAILED - pipeline stopped, image will NOT be pushed or deployed")
    sys.exit(1)
print("SECURITY GATE: PASSED - image may be pushed and deployed")
