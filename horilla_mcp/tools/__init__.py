"""
MCP tools package.

Provides logged_tool() — a wrapper around mcp.tool() that adds audit logging.
Usage in tool files:

    from horilla_mcp.tools import logged_tool

    @logged_tool()
    def my_tool(arg: str) -> str:
        ...
"""

import functools
import json
import logging
import time

logger = logging.getLogger("horilla_mcp.tools")


def logged_tool(**tool_kwargs):
    """
    Decorator that combines @mcp.tool() registration with audit logging.
    Logs every tool call to MCPQueryLog with tool name, args, latency, success.
    """
    from horilla_mcp.server import mcp

    def decorator(func):
        @mcp.tool(**tool_kwargs)
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            start = time.time()
            tool_name = func.__name__
            success = True
            error_msg = ""
            result = ""

            try:
                result = func(*args, **kwargs)
                return result
            except Exception as e:
                success = False
                error_msg = str(e)
                logger.exception(f"MCP tool {tool_name} failed")
                return json.dumps({"error": f"{tool_name} failed: {error_msg}"})
            finally:
                latency_ms = int((time.time() - start) * 1000)
                try:
                    from horilla_mcp.models import MCPQueryLog

                    MCPQueryLog.objects.create(
                        tool_name=tool_name,
                        tool_args=kwargs or {},
                        result_summary=(str(result) or "")[:500],
                        latency_ms=latency_ms,
                        success=success,
                        error_message=error_msg,
                    )
                except Exception:
                    pass  # Don't fail the tool call because of logging

        return wrapper

    return decorator
