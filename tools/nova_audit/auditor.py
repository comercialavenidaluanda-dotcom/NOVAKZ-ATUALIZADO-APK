from __future__ import annotations

import argparse
import json
import os
import re
import sys
import tempfile
import zipfile
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any
from urllib.parse import quote

import requests


SECRET_PATTERNS = (
    re.compile(r"service_role", re.I),
    re.compile(r"SUPABASE_(?:SERVICE|SECRET)_KEY", re.I),
    re.compile(r"\b(?:access|refresh)_token\b", re.I),
    re.compile(r"\b(?:password|passwd|pin)\b", re.I),
)

BALANCE_PATTERNS = (
    re.compile(r"\bdefault[_ ]?sandbox[_ ]?balance\b", re.I),
    re.compile(r"\b1000(?:\.0)?\b"),
    re.compile(r"balance\s*[-+]=\s*amount", re.I),
    re.compile(r"balance\s*=\s*balance\s*[-+]", re.I),
)

SUPABASE_PATTERNS = (
    re.compile(r"supabase", re.I),
    re.compile(r"auth\.uid\s*\(", re.I),
    re.compile(r"bank_accounts", re.I),
)

@dataclass
class Finding:
    severity: str
    check: str
    message: str
    path: str | None = None
    line: int | None = None

@dataclass
class AuditReport:
    module_version: str
    source: dict[str, Any]
    findings: list[Finding]
    live: dict[str, Any] | None = None

    @property
    def critical(self) -> int:
        return sum(f.severity == "CRITICAL" for f in self.findings)

    @property
    def high(self) -> int:
        return sum(f.severity == "HIGH" for f in self.findings)


def _safe_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""


def _scan_tree(root: Path) -> list[Finding]:
    findings: list[Finding] = []
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        if any(part in {".git", "build", ".gradle", "node_modules"} for part in path.parts):
            continue
        if path.suffix.lower() not in {".kt", ".kts", ".java", ".xml", ".json", ".properties", ".gradle", ".txt", ".md"}:
            continue

        text = _safe_text(path)
        if not text:
            continue

        for number, line in enumerate(text.splitlines(), 1):
            if any(p.search(line) for p in BALANCE_PATTERNS):
                findings.append(Finding(
                    "HIGH",
                    "balance-source-of-truth",
                    "Possible local/default balance logic detected. Supabase must remain the financial source of truth.",
                    str(path.relative_to(root)),
                    number,
                ))

            if re.search(r"(service_role|sb_secret_|SUPABASE_SERVICE_ROLE_KEY|SUPABASE_SECRET_KEY)\s*[:=]", line, re.I):
                findings.append(Finding(
                    "CRITICAL",
                    "secret-exposure",
                    "Possible privileged Supabase key reference found in application source.",
                    str(path.relative_to(root)),
                    number,
                ))

        if path.name.lower().endswith((".kt", ".java", ".kts")) and re.search(r"supabase", text, re.I):
            if "bank_accounts" in text and ("auth.uid" not in text and "getUser" not in text and "currentUser" not in text):
                findings.append(Finding(
                    "MEDIUM",
                    "auth-ownership-link",
                    "bank_accounts is referenced without an obvious nearby authenticated-user ownership check; inspect manually.",
                    str(path.relative_to(root)),
                ))

    if not any(f.check == "supabase-client" for f in findings):
        found = any(
            SUPABASE_PATTERNS[0].search(_safe_text(p))
            for p in root.rglob("*") if p.is_file() and p.suffix.lower() in {".kt", ".kts", ".java"}
        )
        if not found:
            findings.append(Finding(
                "HIGH",
                "supabase-client",
                "No obvious Supabase client reference was found in Kotlin/Java sources.",
            ))
    return findings


def _redact(value: Any) -> Any:
    if isinstance(value, dict):
        return {k: ("[REDACTED]" if SECRET_PATTERNS and any(p.search(str(k)) for p in SECRET_PATTERNS) else _redact(v)) for k, v in value.items()}
    if isinstance(value, list):
        return [_redact(v) for v in value]
    if isinstance(value, str):
        if len(value) > 120:
            return value[:32] + "…"
        return value
    return value


def _candidate_key(keys: list[str], names: tuple[str, ...]) -> str | None:
    lowered = {k.lower(): k for k in keys}
    for name in names:
        if name in lowered:
            return lowered[name]
    return None


def _live_supabase_audit(url: str, publishable_key: str, access_token: str) -> dict[str, Any]:
    base = url.rstrip("/")
    headers = {
        "apikey": publishable_key,
        "Authorization": f"Bearer {access_token}",
        "Accept": "application/json",
    }

    result: dict[str, Any] = {"read_only": True, "auth": {}, "bank_accounts": {}}

    auth = requests.get(f"{base}/auth/v1/user", headers=headers, timeout=15)
    result["auth"] = {
        "http_status": auth.status_code,
        "ok": auth.ok,
    }
    if not auth.ok:
        result["auth"]["error"] = auth.text[:300]
        return result

    user = auth.json()
    user_id = user.get("id")
    result["auth"]["user_id_present"] = bool(user_id)

    query = f"{base}/rest/v1/bank_accounts?select=*"
    accounts = requests.get(query, headers=headers, timeout=15)
    result["bank_accounts"]["http_status"] = accounts.status_code
    result["bank_accounts"]["ok"] = accounts.ok

    if not accounts.ok:
        result["bank_accounts"]["error"] = accounts.text[:500]
        return result

    data = accounts.json()
    if not isinstance(data, list):
        data = []

    result["bank_accounts"]["row_count"] = len(data)
    if data:
        keys = list(data[0].keys())
        owner_key = _candidate_key(keys, ("user_id", "auth_user_id", "profile_id", "customer_id"))
        balance_key = _candidate_key(keys, (
            "balance", "available_balance", "current_balance", "available_amount", "current_amount"
        ))
        result["bank_accounts"]["columns"] = keys
        result["bank_accounts"]["ownership_column_candidate"] = owner_key
        result["bank_accounts"]["balance_column_candidate"] = balance_key

        owned = [row for row in data if owner_key and str(row.get(owner_key)) == str(user_id)]
        result["bank_accounts"]["owned_row_count"] = len(owned)

        if balance_key:
            result["bank_accounts"]["balances"] = [
                {"row_index": i, "value": row.get(balance_key)}
                for i, row in enumerate(owned)
            ]

    return result


def run(zip_path: Path | None, source_path: Path | None, json_output: bool) -> int:
    findings: list[Finding] = []
    source_meta: dict[str, Any] = {}

    if zip_path:
        if not zip_path.exists():
            findings.append(Finding("CRITICAL", "input", f"ZIP not found: {zip_path}"))
        else:
            with tempfile.TemporaryDirectory(prefix="nova-kz-audit-") as temp:
                extract_root = Path(temp) / "project"
                with zipfile.ZipFile(zip_path) as archive:
                    archive.extractall(extract_root)
                source_meta = {
                    "mode": "zip",
                    "file": str(zip_path),
                    "entries": len(archive.namelist()),
                }
                findings.extend(_scan_tree(extract_root))
    elif source_path:
        source_meta = {"mode": "directory", "path": str(source_path)}
        findings.extend(_scan_tree(source_path))
    else:
        findings.append(Finding("CRITICAL", "input", "Provide --zip or --source."))

    live: dict[str, Any] | None = None
    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_PUBLISHABLE_KEY") or os.getenv("SUPABASE_ANON_KEY")
    token = os.getenv("SUPABASE_ACCESS_TOKEN")
    if any((url, key, token)):
        if not all((url, key, token)):
            findings.append(Finding(
                "HIGH",
                "live-config",
                "Live Supabase audit requires SUPABASE_URL, SUPABASE_PUBLISHABLE_KEY (or SUPABASE_ANON_KEY), and SUPABASE_ACCESS_TOKEN together.",
            ))
        else:
            try:
                live = _live_supabase_audit(url, key, token)
            except requests.RequestException as exc:
                findings.append(Finding("HIGH", "live-supabase", f"Supabase request failed: {type(exc).__name__}"))
            except Exception as exc:
                findings.append(Finding("HIGH", "live-supabase", f"Supabase audit failed: {type(exc).__name__}"))

    report = AuditReport("0.1.0", source_meta, findings, live)
    payload = {
        "module_version": report.module_version,
        "source": report.source,
        "summary": {
            "critical": report.critical,
            "high": report.high,
            "total_findings": len(report.findings),
        },
        "findings": [asdict(f) for f in report.findings],
        "live": _redact(report.live),
    }

    if json_output:
        print(json.dumps(payload, indent=2, ensure_ascii=False))
    else:
        print("NOVA KZ — Python Audit 0.1.0")
        print(f"Source: {source_meta}")
        print(f"Findings: {len(report.findings)} | Critical: {report.critical} | High: {report.high}")
        for finding in report.findings:
            location = f" [{finding.path}:{finding.line}]" if finding.path else ""
            print(f"{finding.severity}: {finding.check}: {finding.message}{location}")
        if live:
            print("\nLIVE SUPABASE (read-only)")
            print(json.dumps(_redact(live), indent=2, ensure_ascii=False))

    return 2 if report.critical else 1 if report.high else 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Read-only NOVA KZ source and Supabase audit.")
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--zip", type=Path, help="NOVA KZ source ZIP")
    group.add_argument("--source", type=Path, help="Extracted NOVA KZ source directory")
    parser.add_argument("--json", action="store_true", dest="json_output")
    args = parser.parse_args()
    return run(args.zip, args.source, args.json_output)


if __name__ == "__main__":
    sys.exit(main())
