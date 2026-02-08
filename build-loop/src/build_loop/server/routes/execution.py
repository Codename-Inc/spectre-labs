"""
Pipeline execution control endpoints.

Provides REST API for starting, stopping, and monitoring pipeline execution.
"""

import asyncio
import logging
import threading
from dataclasses import asdict
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from ...agent import get_agent
from ...pipeline import load_pipeline
from ...pipeline.executor import (
    PipelineEvent,
    PipelineExecutor,
    PipelineState,
    PipelineStatus,
)
from ...stats import BuildStats

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/execution", tags=["execution"])


# Global state for the current execution
class ExecutionState:
    """Singleton state for the currently running pipeline."""

    def __init__(self):
        self.executor: PipelineExecutor | None = None
        self.thread: threading.Thread | None = None
        self.events: list[dict[str, Any]] = []
        self.lock = threading.Lock()
        self.stats: BuildStats | None = None

    def is_running(self) -> bool:
        return self.thread is not None and self.thread.is_alive()

    def get_state(self) -> dict[str, Any]:
        with self.lock:
            if self.executor:
                state = self.executor.state
                return {
                    "status": state.status.value,
                    "current_stage": state.current_stage,
                    "total_iterations": state.total_iterations,
                    "stage_history": state.stage_history,
                    "artifacts": state.global_artifacts,
                }
            return {
                "status": "idle",
                "current_stage": None,
                "total_iterations": 0,
                "stage_history": [],
                "artifacts": {},
            }

    def add_event(self, event: PipelineEvent) -> None:
        with self.lock:
            # Convert event to dict for JSON serialization
            event_dict = {
                "type": type(event).__name__,
                **{k: v for k, v in asdict(event).items() if not k.startswith("_")},
            }
            self.events.append(event_dict)

    def get_events(self, since: int = 0) -> list[dict[str, Any]]:
        with self.lock:
            return self.events[since:]

    def clear(self) -> None:
        with self.lock:
            self.executor = None
            self.thread = None
            self.events = []
            self.stats = None


_execution_state = ExecutionState()


class StartRequest(BaseModel):
    """Request model for starting pipeline execution."""
    pipeline_name: str
    tasks_file: str
    context_files: list[str] = []
    agent: str = "claude"


class StatusResponse(BaseModel):
    """Response model for execution status."""
    status: str
    current_stage: str | None
    total_iterations: int
    stage_history: list[tuple[str, str | None]]
    artifacts: dict[str, Any]
    event_count: int


def _run_pipeline(
    pipeline_path: str,
    tasks_file: str,
    context_files: list[str],
    agent_name: str,
) -> None:
    """Run pipeline in background thread."""
    try:
        # Load pipeline
        config = load_pipeline(pipeline_path)

        # Build context
        if context_files:
            context_str = "\n".join(f"- `{f}`" for f in context_files)
        else:
            context_str = "None"

        context = {
            "tasks_file_path": tasks_file,
            "progress_file_path": str(Path(tasks_file).parent / "build_progress.md"),
            "additional_context_paths_or_none": context_str,
        }

        # Get agent runner
        runner = get_agent(agent_name)

        # Create executor
        stats = BuildStats()
        _execution_state.stats = stats

        executor = PipelineExecutor(
            config=config,
            runner=runner,
            on_event=_execution_state.add_event,
            context=context,
        )
        _execution_state.executor = executor

        # Run pipeline
        executor.run(stats)

    except Exception as e:
        logger.exception("Pipeline execution failed: %s", e)
        _execution_state.add_event(
            type("ErrorEvent", (), {"type": "error", "message": str(e)})()
        )


@router.post("/start")
async def start_execution(request: StartRequest) -> dict[str, str]:
    """Start executing a pipeline."""
    if _execution_state.is_running():
        raise HTTPException(
            status_code=409,
            detail="A pipeline is already running. Stop it first."
        )

    # Find pipeline file
    pipelines_dir = Path.cwd() / ".spectre" / "pipelines"
    pipeline_path = None
    for ext in [".yaml", ".yml"]:
        path = pipelines_dir / f"{request.pipeline_name}{ext}"
        if path.is_file():
            pipeline_path = str(path)
            break

    if not pipeline_path:
        raise HTTPException(
            status_code=404,
            detail=f"Pipeline not found: {request.pipeline_name}"
        )

    # Validate tasks file
    tasks_path = Path(request.tasks_file)
    if not tasks_path.is_file():
        raise HTTPException(
            status_code=400,
            detail=f"Tasks file not found: {request.tasks_file}"
        )

    # Clear previous state
    _execution_state.clear()

    # Start execution in background thread
    thread = threading.Thread(
        target=_run_pipeline,
        args=(pipeline_path, request.tasks_file, request.context_files, request.agent),
        daemon=True,
    )
    _execution_state.thread = thread
    thread.start()

    return {"status": "started", "pipeline": request.pipeline_name}


@router.post("/stop")
async def stop_execution() -> dict[str, str]:
    """Stop the currently running pipeline."""
    if not _execution_state.is_running():
        raise HTTPException(
            status_code=409,
            detail="No pipeline is currently running"
        )

    if _execution_state.executor:
        _execution_state.executor.stop()

    # Wait for thread to finish (with timeout)
    if _execution_state.thread:
        _execution_state.thread.join(timeout=5.0)

    return {"status": "stopped"}


@router.get("/status", response_model=StatusResponse)
async def get_status() -> StatusResponse:
    """Get current execution status."""
    state = _execution_state.get_state()
    return StatusResponse(
        status=state["status"],
        current_stage=state["current_stage"],
        total_iterations=state["total_iterations"],
        stage_history=state["stage_history"],
        artifacts=state["artifacts"],
        event_count=len(_execution_state.events),
    )


@router.get("/events")
async def get_events(since: int = 0) -> dict[str, Any]:
    """Get execution events since a given index."""
    events = _execution_state.get_events(since)
    return {
        "events": events,
        "total": len(_execution_state.events),
        "next_index": len(_execution_state.events),
    }


@router.get("/stats")
async def get_stats() -> dict[str, Any]:
    """Get execution statistics."""
    if _execution_state.stats:
        return {
            "iterations_completed": _execution_state.stats.iterations_completed,
            "iterations_failed": _execution_state.stats.iterations_failed,
            "total_input_tokens": _execution_state.stats.total_input_tokens,
            "total_output_tokens": _execution_state.stats.total_output_tokens,
            "tool_calls": dict(_execution_state.stats.tool_calls),
        }
    return {
        "iterations_completed": 0,
        "iterations_failed": 0,
        "total_input_tokens": 0,
        "total_output_tokens": 0,
        "tool_calls": {},
    }
