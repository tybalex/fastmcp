from __future__ import annotations

from typing import TYPE_CHECKING, ParamSpec, TypeVar

from mcp.server.auth.middleware.auth_context import get_access_token
from mcp.server.auth.provider import AccessToken
from starlette.requests import Request

if TYPE_CHECKING:
    from fastmcp.server.context import Context

P = ParamSpec("P")
R = TypeVar("R")

__all__ = [
    "get_context",
    "get_http_request",
    "get_http_headers",
    "get_access_token",
    "AccessToken",
]


# --- Context ---


def get_context() -> Context:
    from fastmcp.server.context import _current_context

    context = _current_context.get()
    if context is None:
        raise RuntimeError("No active context found.")
    return context


# --- HTTP Request ---


def get_http_request() -> Request:
    import asyncio

    from fastmcp.server.http import _current_http_request, _global_request_store

    task = asyncio.current_task()
    task_name = getattr(task, "get_name", lambda: str(task))()

    # Check if we're in an MCP server task - if so, always use global store
    is_mcp_task = "mcp.server" in task_name if task_name else False

    # Try to get from ContextVar first (but skip if we're in MCP task)
    request = None if is_mcp_task else _current_http_request.get()

    if request is None or is_mcp_task:
        # Fallback: check global store (this is our workaround for cross-task access)

        # Get the most recent request
        result = _global_request_store.get_most_recent_request()
        if result:
            request, _, _ = result
        else:
            raise RuntimeError("No active HTTP request found.")

    return request


def get_http_headers(include_all: bool = False) -> dict[str, str]:
    """
    Extract headers from the current HTTP request if available.

    Never raises an exception, even if there is no active HTTP request (in which case
    an empty dict is returned).

    By default, strips problematic headers like `content-length` that cause issues if forwarded to downstream clients.
    If `include_all` is True, all headers are returned.
    """
    if include_all:
        exclude_headers = set()
    else:
        exclude_headers = {
            "host",
            "content-length",
            "connection",
            "transfer-encoding",
            "upgrade",
            "te",
            "keep-alive",
            "expect",
            "accept",
            # Proxy-related headers
            "proxy-authenticate",
            "proxy-authorization",
            "proxy-connection",
        }
        # (just in case)
        if not all(h.lower() == h for h in exclude_headers):
            raise ValueError("Excluded headers must be lowercase")
    headers = {}

    try:
        request = get_http_request()
        for name, value in request.headers.items():
            lower_name = name.lower()
            if lower_name not in exclude_headers:
                headers[lower_name] = str(value)
        return headers
    except RuntimeError:
        return {}
