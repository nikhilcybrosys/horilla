"""Decorators for MCP tool auditing and permission checks."""

import functools
import json
import logging
import time

logger = logging.getLogger(__name__)


def log_mcp_call(func):
    """
    Decorator that logs every MCP tool invocation to MCPQueryLog.
    Captures tool name, arguments, result summary, latency, and errors.
    """

    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        start_time = time.time()
        tool_name = func.__name__
        success = True
        error_message = ""
        result = ""

        try:
            result = func(*args, **kwargs)
            return result
        except Exception as e:
            success = False
            error_message = str(e)
            logger.exception(f"MCP tool {tool_name} failed")
            return json.dumps({"error": f"Tool {tool_name} failed: {str(e)}"})
        finally:
            latency_ms = int((time.time() - start_time) * 1000)

            try:
                from horilla_mcp.models import MCPQueryLog

                # Truncate result for storage
                result_summary = str(result)[:500] if result else ""

                MCPQueryLog.objects.create(
                    tool_name=tool_name,
                    tool_args=kwargs
                    or (
                        {f"arg_{i}": str(a) for i, a in enumerate(args)} if args else {}
                    ),
                    result_summary=result_summary,
                    latency_ms=latency_ms,
                    success=success,
                    error_message=error_message,
                )
            except Exception:
                logger.exception("Failed to log MCP tool call")

    return wrapper
