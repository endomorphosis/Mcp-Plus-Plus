"""Expose only the redacted text the ranker already judged."""

from typing import Any

from mcp_pp_system_one.ports import ToolSlice
from mcp_pp_system_one.redact import redact_serialized


def _get(obj: Any, key: str, default: Any = None) -> Any:
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)


def _judged_text(desc: Any) -> str:
    text = _get(desc, "description") or _get(desc, "summary") or ""
    methods = _get(desc, "methods") or []
    names = []
    for method in methods:
        name = _get(method, "name")
        if name:
            names.append(str(name))
    joined = str(text)
    if names:
        joined = f"{joined} — {', '.join(names)}"
    return joined[:700]


def build_tool_list(
    selected: ToolSlice, descriptors_by_cid: dict[str, Any]
) -> list[dict[str, Any]]:
    tools = []
    for cid in selected.interface_cids:
        desc = descriptors_by_cid.get(cid)
        if desc is None:
            continue
        name = redact_serialized(str(_get(desc, "name") or cid))
        description = redact_serialized(_judged_text(desc))
        tools.append(
            {
                "name": name,
                "description": description,
                "inputSchema": {"type": "object", "properties": {}},
            }
        )
    return tools
