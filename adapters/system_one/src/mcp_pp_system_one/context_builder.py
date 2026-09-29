"""Expose only the CIDs the slice already kept."""

from typing import Any

from mcp_pp_system_one.ports import ToolSlice


def _get(obj: Any, key: str, default: Any = None) -> Any:
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)


def build_tool_list(
    selected: ToolSlice, descriptors_by_cid: dict[str, Any]
) -> list[dict[str, Any]]:
    tools = []
    for cid in selected.interface_cids:
        desc = descriptors_by_cid.get(cid)
        if desc is None:
            continue
        description = _get(desc, "description") or _get(desc, "summary") or ""
        tools.append(
            {
                "name": str(_get(desc, "name") or cid),
                "description": str(description),
                "inputSchema": {"type": "object", "properties": {}},
            }
        )
    return tools
