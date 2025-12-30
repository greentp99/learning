#!/usr/bin/env python3
"""
cne_healthcheck.py

Run repeatable Corvil CNE health checks via SSH, parse key indicators, and emit JSON.
Designed for cron/Splunk-friendly output.

Usage:
  python cne_healthcheck.py --host 10.0.0.10 --user admin --password '***'
  python cne_healthcheck.py --host cne01 --user admin --key ~/.ssh/id_rsa
"""

import argparse
import json
import re
import socket
import sys
import time
from dataclasses import dataclass, asdict
from typing import Dict, List, Optional, Tuple

import paramiko


# -------------------------
# Config: commands to run
# -------------------------
DEFAULT_COMMANDS = [
    # Adjust these to your CNE firmware/CLI vocabulary:
    ("version", "show version"),
    ("system", "show system"),
    ("uptime", "show uptime"),
    ("hardware", "show hardware"),
    ("ports", "show ports"),
    ("temps", "show temperatures"),
    ("fans", "show fans"),
    ("clock", "show clock"),
    ("ntp", "show ntp"),
    ("stats_ports", "show statistics ports"),
    ("stats_drops", "show statistics drops"),
]

# -------------------------
# Thresholds (tune for your environment)
# -------------------------
THRESHOLDS = {
    "max_temp_c": 80.0,            # flag if any sensor temp exceeds this
    "min_fan_rpm": 1500,           # flag if any fan below this (if RPM exposed)
    "max_port_errors": 0,          # flag if errors > this
    "max_drop_rate_pps": 0,        # flag if packet drops > this (if you can derive)
    "ntp_required_synced": True,   # require NTP/PTP/GPS synced
}


@dataclass
class Finding:
    severity: str  # "OK", "WARN", "CRIT"
    check: str
    message: str
    value: Optional[object] = None


@dataclass
class HealthReport:
    host: str
    ts_epoch: int
    duration_ms: int
    raw: Dict[str, str]
    metrics: Dict[str, object]
    findings: List[Finding]
    overall: str  # "OK"|"WARN"|"CRIT"


# -------------------------
# SSH runner
# -------------------------
def ssh_run_commands(
    host: str,
    username: str,
    password: Optional[str],
    key_path: Optional[str],
    port: int = 22,
    timeout: int = 10,
    commands: List[Tuple[str, str]] = None,
) -> Dict[str, str]:
    commands = commands or DEFAULT_COMMANDS
    out: Dict[str, str] = {}

    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())

    try:
        if key_path:
            pkey = paramiko.RSAKey.from_private_key_file(key_path)
            client.connect(hostname=host, port=port, username=username, pkey=pkey,
                           timeout=timeout, banner_timeout=timeout, auth_timeout=timeout)
        else:
            client.connect(hostname=host, port=port, username=username, password=password,
                           timeout=timeout, banner_timeout=timeout, auth_timeout=timeout)

        for label, cmd in commands:
            stdin, stdout, stderr = client.exec_command(cmd, timeout=timeout)
            stdout_str = stdout.read().decode(errors="replace")
            stderr_str = stderr.read().decode(errors="replace")

            # Some appliances write certain things to stderr even on success; keep both.
            combined = stdout_str.strip()
            if stderr_str.strip():
                combined = (combined + "\n" + ("[stderr]\n" + stderr_str.strip())).strip()

            out[label] = combined

    finally:
        try:
            client.close()
        except Exception:
            pass

    return out


# -------------------------
# Parsing helpers (edit these to match your CLI output)
# -------------------------
def parse_first_float(text: str) -> Optional[float]:
    m = re.search(r"(-?\d+(?:\.\d+)?)", text)
    return float(m.group(1)) if m else None

def parse_uptime_seconds(text: str) -> Optional[int]:
    """
    Try to extract uptime in seconds from common formats:
      'up 12 days, 03:04'
      'Uptime: 1d 02h 03m 04s'
    """
    # Format: "Uptime: 1d 02h 03m 04s"
    md = re.search(r"(\d+)\s*d", text)
    mh = re.search(r"(\d+)\s*h", text)
    mm = re.search(r"(\d+)\s*m", text)
    ms = re.search(r"(\d+)\s*s", text)
    if any([md, mh, mm, ms]):
        d = int(md.group(1)) if md else 0
        h = int(mh.group(1)) if mh else 0
        m_ = int(mm.group(1)) if mm else 0
        s = int(ms.group(1)) if ms else 0
        return d * 86400 + h * 3600 + m_ * 60 + s

    # Format: "up 12 days, 03:04"
    m = re.search(r"up\s+(\d+)\s+days?,\s+(\d{1,2}):(\d{2})", text, re.IGNORECASE)
    if m:
        days = int(m.group(1))
        hh = int(m.group(2))
        mins = int(m.group(3))
        return days * 86400 + hh * 3600 + mins * 60

    return None

def parse_temperatures(text: str) -> List[float]:
    """
    Extract all temperatures that look like: '45C', '45.5 C', 'Temp: 45'
    You WILL want to tune this to your CNE output.
    """
    temps = []
    for m in re.finditer(r"(\d+(?:\.\d+)?)\s*°?\s*C\b", text, re.IGNORECASE):
        temps.append(float(m.group(1)))
    return temps

def parse_fan_rpms(text: str) -> List[int]:
    rpms = []
    for m in re.finditer(r"(\d+)\s*rpm\b", text, re.IGNORECASE):
        rpms.append(int(m.group(1)))
    return rpms

def parse_port_errors(text: str) -> int:
    """
    Very generic: sums any 'errors' counters it can see.
    Better approach: identify specific port error fields in your output.
    """
    total = 0
    for m in re.finditer(r"\berrors?\b\s*[:=]?\s*(\d+)", text, re.IGNORECASE):
        total += int(m.group(1))
    return total

def parse_time_sync_ok(raw: Dict[str, str]) -> Optional[bool]:
    """
    Heuristic: check for 'synchronized', 'locked', 'synced', 'in sync' across NTP/PTP/GPS outputs.
    Adjust to your environment (NTP-only vs PTP+GPS).
    """
    text = "\n".join([raw.get("ntp", ""), raw.get("clock", "")]).lower()
    if not text.strip():
        return None
    good = any(k in text for k in ["synchronized", "synced", "in sync", "locked"])
    bad = any(k in text for k in ["unsynchronized", "not synced", "unlocked", "no sync", "stratum 16"])
    if bad:
        return False
    return True if good else None


# -------------------------
# Health logic
# -------------------------
def evaluate(raw: Dict[str, str]) -> Tuple[Dict[str, object], List[Finding], str]:
    metrics: Dict[str, object] = {}
    findings: List[Finding] = []

    # Uptime
    uptime_s = parse_uptime_seconds(raw.get("uptime", ""))
    metrics["uptime_seconds"] = uptime_s

    # Temps/Fans
    temps = parse_temperatures(raw.get("temps", ""))
    metrics["temps_c"] = temps
    if temps:
        max_temp = max(temps)
        metrics["max_temp_c"] = max_temp
        if max_temp >= THRESHOLDS["max_temp_c"]:
            findings.append(Finding("CRIT", "temperature", f"Max temp {max_temp}C exceeds threshold",
                                    value={"max_temp_c": max_temp, "threshold": THRESHOLDS["max_temp_c"]}))
        else:
            findings.append(Finding("OK", "temperature", f"Max temp {max_temp}C", value=max_temp))
    else:
        findings.append(Finding("WARN", "temperature", "No temperatures parsed (update parser?)"))

    rpms = parse_fan_rpms(raw.get("fans", ""))
    metrics["fan_rpms"] = rpms
    if rpms:
        min_rpm = min(rpms)
        metrics["min_fan_rpm"] = min_rpm
        if min_rpm < THRESHOLDS["min_fan_rpm"]:
            findings.append(Finding("WARN", "fans", f"Min fan {min_rpm} rpm below threshold",
                                    value={"min_fan_rpm": min_rpm, "threshold": THRESHOLDS["min_fan_rpm"]}))
        else:
            findings.append(Finding("OK", "fans", f"Min fan {min_rpm} rpm", value=min_rpm))
    else:
        findings.append(Finding("WARN", "fans", "No fan RPMs parsed (update parser?)"))

    # Port errors (generic)
    port_errs = parse_port_errors(raw.get("stats_ports", ""))
    metrics["port_errors_total"] = port_errs
    if port_errs > THRESHOLDS["max_port_errors"]:
        findings.append(Finding("WARN", "ports", f"Port errors detected: {port_errs}", value=port_errs))
    else:
        findings.append(Finding("OK", "ports", f"Port errors: {port_errs}", value=port_errs))

    # Drops (placeholder: depends heavily on your CLI output)
    drops_text = raw.get("stats_drops", "")
    metrics["drops_raw_present"] = bool(drops_text.strip())
    # You can add a real drop-rate parser here once you share a sample output.

    # Time sync
    sync_ok = parse_time_sync_ok(raw)
    metrics["time_sync_ok"] = sync_ok
    if THRESHOLDS["ntp_required_synced"]:
        if sync_ok is False:
            findings.append(Finding("CRIT", "time_sync", "Time sync indicates NOT synced/locked"))
        elif sync_ok is True:
            findings.append(Finding("OK", "time_sync", "Time sync appears healthy"))
        else:
            findings.append(Finding("WARN", "time_sync", "Could not confirm time sync from output (update parser?)"))

    # Determine overall
    overall = "OK"
    if any(f.severity == "CRIT" for f in findings):
        overall = "CRIT"
    elif any(f.severity == "WARN" for f in findings):
        overall = "WARN"

    return metrics, findings, overall


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--host", required=True)
    ap.add_argument("--user", required=True)
    ap.add_argument("--password", default=None)
    ap.add_argument("--key", default=None, help="Path to SSH private key (preferred over password)")
    ap.add_argument("--port", type=int, default=22)
    ap.add_argument("--timeout", type=int, default=10)
    ap.add_argument("--json", action="store_true", help="Emit JSON only (default)")
    args = ap.parse_args()

    start = time.time()
    try:
        raw = ssh_run_commands(
            host=args.host,
            username=args.user,
            password=args.password,
            key_path=args.key,
            port=args.port,
            timeout=args.timeout,
        )
    except (socket.timeout, paramiko.SSHException) as e:
        report = HealthReport(
            host=args.host,
            ts_epoch=int(time.time()),
            duration_ms=int((time.time() - start) * 1000),
            raw={},
            metrics={},
            findings=[Finding("CRIT", "ssh", f"SSH failure: {e}")],
            overall="CRIT",
        )
        print(json.dumps(asdict(report), indent=2))
        return 2

    metrics, findings, overall = evaluate(raw)

    report = HealthReport(
        host=args.host,
        ts_epoch=int(time.time()),
        duration_ms=int((time.time() - start) * 1000),
        raw=raw,  # keep for debugging; in production you might omit or truncate
        metrics=metrics,
        findings=findings,
        overall=overall,
    )

    print(json.dumps(asdict(report), indent=2))
    return 2 if overall == "CRIT" else 1 if overall == "WARN" else 0


if __name__ == "__main__":
    raise SystemExit(main())
