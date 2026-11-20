"""Limited no-install Windows command heuristics when Tirith has no native build.

This is independent of approval_detection, but it is NOT a replacement for
Tirith's full rule engine. Positive findings require human review; unknown
patterns are not certified safe. No process spawning, network, or file writes.
"""
from __future__ import annotations

import re
import unicodedata
from urllib.parse import urlsplit

_MAX_LENGTH = 65536
_URL = re.compile(r"https?://[^\s\"'<>|]+", re.I)
_PIPE = re.compile(r"\b(?:curl|wget|iwr|invoke-webrequest)\b[^|]*\|\s*(?:sh|bash|zsh|python\d*|powershell|pwsh|iex|invoke-expression)\b", re.I)
_ENCODED = re.compile(r"\b(?:powershell(?:\.exe)?|pwsh(?:\.exe)?)\b[^;|]*?\s-(?:e|ec|en|enc|enco|encod|encode|encoded|encodedc|encodedco|encodedcom|encodedcomm|encodedcomma|encodedcomman|encodedcommand)(?=\s|$)", re.I)
_EXEC = re.compile(r"\b(?:invoke-expression|iex|frombase64string)\b", re.I)


def scan_windows_command(command: str) -> dict:
    findings: list[dict] = []

    def warn(rule: str, title: str) -> None:
        findings.append({"rule_id": "windows:" + rule, "severity": "HIGH",
                         "title": title, "description": title})

    if len(command) > _MAX_LENGTH:
        warn("length", "Command exceeds native scanner inspection limit")
    text = command[:_MAX_LENGTH]
    # PowerShell accepts slash and Unicode dash forms for switch prefixes.
    # Normalize only known encoded-command switches, not URLs or general text.
    text = re.sub(r"(?<=\s)[/–—―](?=e(?:[a-z]*)(?:\s|$))", "-", text, flags=re.I)
    if _PIPE.search(text):
        warn("download-pipe", "Download piped directly into interpreter")
    if _ENCODED.search(text):
        warn("encoded-powershell", "PowerShell encoded command")
    if _EXEC.search(text):
        warn("expression-execution", "PowerShell expression or base64 execution primitive")

    for match in _URL.finditer(text):
        try:
            host = urlsplit(match.group()).hostname or ""
        except ValueError:
            warn("malformed-url", "Malformed URL with ambiguous host")
            continue
        if "xn--" in host.lower():
            warn("punycode-domain", "Internationalized punycode domain")
            break
        scripts = set()
        for char in host:
            if ord(char) < 128:
                if char.isalpha():
                    scripts.add("LATIN")
                continue
            name = unicodedata.name(char, "")
            for script in ("LATIN", "CYRILLIC", "GREEK"):
                if name.startswith(script + " "):
                    scripts.add(script)
                    break
        if len(scripts) > 1:
            warn("mixed-script-domain", "Domain mixes writing scripts")
            break

    return {"action": "warn" if findings else "allow", "findings": findings[:8],
            "summary": "Windows native heuristic flags: " + ", ".join(f["rule_id"] for f in findings[:8])
            if findings else ""}
