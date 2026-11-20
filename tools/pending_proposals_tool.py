"""pending_proposals: see, read, reject, or ask the user to approve writes staged for approval (2026-11-13).

The agent can LIST and READ what is waiting, REJECT one on purpose (a reason is required and logged), or ASK the user to approve one
(a note is stored on the record and shown in /skills pending). It cannot approve: approving is the user's decision.
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any, Dict, List

from hermes_constants import get_hermes_home
from tools import write_approval as wa
from tools.registry import registry, tool_error
from utils import atomic_json_write

_KINDS = {"skills": wa.SKILLS, "memory": wa.MEMORY}
_PREVIEW_CHARS = 1500
_READ_TOTAL_CHARS = 12000


def _day(ts) -> str:
    try:
        return time.strftime("%Y-%m-%d %H:%M", time.localtime(float(ts)))
    except Exception:
        return "?"


def _ops_of(payload: Dict[str, Any]) -> List[Dict[str, Any]]:
    ops = payload.get("operations")
    if isinstance(ops, list) and ops:
        return [op for op in ops if isinstance(op, dict)]
    return [payload] if payload else []


def _op_view(op: Dict[str, Any]) -> Dict[str, Any]:
    body = ""
    for key in ("content", "new_string", "file_content", "new_text"):
        if op.get(key):
            body = str(op[key])
            break
    view = {k: op[k] for k in ("action", "name", "target", "file_path", "old_string", "old_text") if op.get(k)}
    view["old_string"] = str(view["old_string"])[:300] if "old_string" in view else None
    view = {k: v for k, v in view.items() if v is not None}
    view["text_chars"] = len(body)
    view["text_preview"] = body[:_PREVIEW_CHARS] + (" ...[cut]" if len(body) > _PREVIEW_CHARS else "")
    return view


def _kind(args: Dict[str, Any]) -> str:
    return _KINDS.get(str(args.get("kind") or "skills").lower(), "")


def _log_decision(entry: Dict[str, Any]) -> None:
    try:
        path = get_hermes_home() / "pending" / "decisions.jsonl"
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(entry, ensure_ascii=False) + "\n")
    except Exception:
        pass  # the log is a courtesy; the decision itself already happened


def pending_proposals(args: Dict[str, Any]) -> str:
    action = str(args.get("action") or "").lower()
    subsystem = _kind(args)
    if not subsystem:
        return tool_error("kind must be 'skills' or 'memory'.", success=False)
    if action not in {"list", "read", "reject", "ask_approval"}:
        return tool_error("action must be list, read, reject or ask_approval. Approving is the user's decision.", success=False)
    if action in {"reject", "ask_approval"}:
        try:
            from tools.skill_provenance import is_unattended_review
            if is_unattended_review():
                return tool_error("Not available inside an unattended background review.", success=False)
        except Exception:
            pass
    if action == "list":
        recs = sorted(wa.list_pending(subsystem), key=lambda r: r.get("created_at", 0))
        items = []
        for r in recs[:100]:
            ask = wa.get_approval_request(subsystem, r)
            items.append({"id": r.get("id"), "created": _day(r.get("created_at")), "origin": r.get("origin"),
                          "summary": str(r.get("summary") or "")[:160], "asked_for_approval": ask.get("note") if ask else None})
        return json.dumps({"success": True, "kind": subsystem, "count": len(recs), "shown": len(items), "pending": items},
                          ensure_ascii=False)
    pid = str(args.get("id") or "").strip()
    rec = wa.get_pending(subsystem, pid) if pid else None
    if not rec:
        return tool_error(f"No pending {subsystem} proposal with id '{pid}'. Use action 'list'.", success=False)
    if action == "read":
        ops = [_op_view(op) for op in _ops_of(rec.get("payload") or {})]
        text = json.dumps({"success": True, "id": rec["id"], "kind": subsystem, "created": _day(rec.get("created_at")),
                           "origin": rec.get("origin"), "summary": rec.get("summary"),
                           "asked_for_approval": wa.get_approval_request(subsystem, rec), "operations": ops}, ensure_ascii=False)
        if len(text) > _READ_TOTAL_CHARS:
            text = json.dumps({"success": True, "id": rec["id"], "summary": rec.get("summary"),
                               "note": "Proposal too long to show in full; previews cut.",
                               "operations": [{k: v for k, v in op.items() if k != "text_preview"} for op in ops]},
                              ensure_ascii=False)
        return text
    if action == "reject":
        reason = str(args.get("reason") or "").strip()
        if len(reason) < 3:
            return tool_error("reject needs a reason (a few words), so the decision is deliberate and on record.", success=False)
        if not wa.discard_pending(subsystem, rec["id"]):
            return tool_error("Could not discard that proposal.", success=False)
        _log_decision({"at": time.time(), "id": rec["id"], "kind": subsystem, "decision": "reject", "reason": reason[:300],
                       "summary": str(rec.get("summary") or "")[:200]})
        return json.dumps({"success": True, "rejected": rec["id"], "summary": rec.get("summary"),
                           "message": "Discarded. Nothing was applied."}, ensure_ascii=False)
    note = str(args.get("note") or "").strip()
    if len(note) < 3:
        return tool_error("ask_approval needs a note saying why you want the user to approve it.", success=False)
    if not wa.set_approval_request(subsystem, rec, note[:300]):
        return tool_error("That proposal is gone (approved or rejected meanwhile); nothing was recorded.", success=False)
    _log_decision({"at": time.time(), "id": rec["id"], "kind": subsystem, "decision": "ask_approval", "reason": note[:300],
                   "summary": str(rec.get("summary") or "")[:200]})
    return json.dumps({"success": True, "id": rec["id"], "message": "Marked. The user will see your note in /skills pending "
                       "and decides whether to approve."}, ensure_ascii=False)


PENDING_PROPOSALS_SCHEMA = {
    "name": "pending_proposals",
    "description": ("See and act on writes that are waiting for the user's approval (skill and memory changes, many staged by "
                    "your own background review). Actions: list; read (full preview of one); reject (permanently discards it; "
                    "needs a short reason that is logged); ask_approval (flags it with a note so the user sees it in "
                    "/skills pending). You cannot approve: that is the user's decision."),
    "parameters": {
        "type": "object",
        "properties": {
            "action": {"type": "string", "enum": ["list", "read", "reject", "ask_approval"]},
            "kind": {"type": "string", "enum": ["skills", "memory"], "description": "Default skills."},
            "id": {"type": "string", "description": "The 8-character pending id (read, reject, ask_approval)."},
            "reason": {"type": "string", "description": "Why you are rejecting it (required for reject)."},
            "note": {"type": "string", "description": "Why the user should approve it (required for ask_approval)."},
        },
        "required": ["action"],
    },
}

registry.register(
    name="pending_proposals", toolset="skills", schema=PENDING_PROPOSALS_SCHEMA, emoji="🗂️",
    handler=lambda args, **kw: pending_proposals(args))
