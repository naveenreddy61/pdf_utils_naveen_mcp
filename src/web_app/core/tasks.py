"""In-process store for long-running jobs that outlive a single HTTP request.

Chapter OCR and whole-document OCR can run for minutes. Doing that inside the
POST means a spinner with no feedback and a real risk of hitting the proxy's
read timeout. Instead the POST starts a task, returns a polling fragment, and
the browser asks for progress until a result is ready.

Per-process and in-memory, exactly like the upload flow it generalises: a
restart or a second worker loses in-flight jobs. That is accepted — the work is
re-runnable and the OCR cache makes the second attempt nearly free.
"""

import asyncio
import uuid
from typing import Any, Awaitable, Callable, Optional

# task_id -> {"phase": str, "pct": int}
#          | {"phase": "done",  "result": Any}
#          | {"phase": "error", "error": str}
_tasks: dict[str, dict] = {}

# How long a finished-but-uncollected task lingers before being dropped.
TASK_TTL_SECONDS = 900


def new_task(phase: str = "Starting…", pct: int = 0) -> str:
    """Register a task and return its id."""
    task_id = uuid.uuid4().hex[:12]
    _tasks[task_id] = {"phase": phase, "pct": pct}
    asyncio.get_event_loop().call_later(
        TASK_TTL_SECONDS, lambda: _tasks.pop(task_id, None)
    )
    return task_id


def set_progress(task_id: str, phase: str, pct: int) -> None:
    """Update a running task. Ignored once the task is done, errored or expired."""
    task = _tasks.get(task_id)
    if task is None or task["phase"] in ("done", "error"):
        return
    task["phase"] = phase
    task["pct"] = pct


def set_result(task_id: str, result: Any) -> None:
    if task_id in _tasks:
        _tasks[task_id] = {"phase": "done", "pct": 100, "result": result}


def set_error(task_id: str, error: str) -> None:
    if task_id in _tasks:
        _tasks[task_id] = {"phase": "error", "pct": 0, "error": error}


def get_task(task_id: str) -> Optional[dict]:
    return _tasks.get(task_id)


def pop_task(task_id: str) -> Optional[dict]:
    return _tasks.pop(task_id, None)


def start_task(
    work: Callable[[str], Awaitable[Any]],
    phase: str = "Starting…",
    pct: int = 0,
) -> str:
    """Run `work(task_id)` in the background; its return value becomes the result.

    Exceptions are captured into the task rather than lost to the event loop's
    default handler, so the poller can render them.
    """
    task_id = new_task(phase, pct)

    async def _runner():
        try:
            set_result(task_id, await work(task_id))
        except Exception as exc:
            import traceback
            traceback.print_exc()
            set_error(task_id, str(exc))

    asyncio.create_task(_runner())
    return task_id
