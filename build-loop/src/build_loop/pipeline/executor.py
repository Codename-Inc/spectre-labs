"""
Pipeline executor for stage-based workflows.

Orchestrates the execution of a multi-stage pipeline, managing transitions
between stages based on completion signals and maintaining global state.
"""

import logging
import sys
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable

from ..agent import AgentRunner
from ..stats import BuildStats
from .completion import CompletionResult
from .stage import Stage, StageConfig

logger = logging.getLogger(__name__)


class PipelineStatus(str, Enum):
    """Pipeline execution status."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    STOPPED = "stopped"


@dataclass
class PipelineState:
    """Current state of pipeline execution.

    Attributes:
        current_stage: Name of the stage currently executing (or last executed)
        global_artifacts: Accumulated artifacts from all stages
        status: Overall pipeline status
        stage_history: List of (stage_name, signal) tuples for execution trace
        total_iterations: Total iterations across all stages
    """
    current_stage: str | None = None
    global_artifacts: dict[str, Any] = field(default_factory=dict)
    status: PipelineStatus = PipelineStatus.PENDING
    stage_history: list[tuple[str, str | None]] = field(default_factory=list)
    total_iterations: int = 0


@dataclass
class PipelineConfig:
    """Configuration for a complete pipeline.

    Attributes:
        name: Pipeline identifier
        description: Human-readable description
        stages: Dictionary of stage name -> StageConfig
        start_stage: Name of the initial stage
        end_signals: Signals that indicate pipeline completion
    """
    name: str
    stages: dict[str, StageConfig]
    start_stage: str
    description: str = ""
    end_signals: list[str] = field(default_factory=lambda: ["BUILD_COMPLETE", "COMPLETE"])


# Event types for callbacks
@dataclass
class PipelineEvent:
    """Base class for pipeline events."""
    pass


@dataclass
class StageStartedEvent(PipelineEvent):
    """Emitted when a stage begins execution."""
    stage: str
    iteration: int = 1


@dataclass
class StageCompletedEvent(PipelineEvent):
    """Emitted when a stage completes."""
    stage: str
    signal: str | None
    iterations: int
    artifacts: dict[str, Any] = field(default_factory=dict)


@dataclass
class StageIterationEvent(PipelineEvent):
    """Emitted for each iteration within a stage."""
    stage: str
    iteration: int
    max_iterations: int


@dataclass
class OutputEvent(PipelineEvent):
    """Emitted for streaming output text."""
    stage: str
    text: str


@dataclass
class PipelineCompletedEvent(PipelineEvent):
    """Emitted when pipeline finishes."""
    status: PipelineStatus
    total_iterations: int
    final_signal: str | None = None


class PipelineExecutor:
    """Executes a multi-stage pipeline.

    Manages the overall pipeline execution, transitioning between stages
    based on completion signals and accumulating artifacts.

    Args:
        config: PipelineConfig defining the pipeline structure
        runner: AgentRunner for executing prompts
        on_event: Optional callback for pipeline events
        context: Initial context variables for prompt substitution
    """

    def __init__(
        self,
        config: PipelineConfig,
        runner: AgentRunner,
        on_event: Callable[[PipelineEvent], None] | None = None,
        context: dict[str, Any] | None = None,
    ):
        self.config = config
        self.runner = runner
        self.on_event = on_event
        self.initial_context = context or {}
        self._state = PipelineState()
        self._stages: dict[str, Stage] = {}
        self._should_stop = False

        # Build stage instances
        for name, stage_config in config.stages.items():
            self._stages[name] = Stage(
                config=stage_config,
                runner=runner,
                on_iteration=lambda it, max_it, name=name: self._emit(
                    StageIterationEvent(stage=name, iteration=it, max_iterations=max_it)
                ),
            )

    @property
    def state(self) -> PipelineState:
        """Current pipeline state."""
        return self._state

    def _emit(self, event: PipelineEvent) -> None:
        """Emit an event to the callback if registered."""
        if self.on_event:
            try:
                self.on_event(event)
            except Exception as e:
                logger.warning("Event callback error: %s", e)

    def stop(self) -> None:
        """Request pipeline to stop after current iteration."""
        self._should_stop = True

    def run(self, stats: BuildStats | None = None) -> PipelineState:
        """Execute the pipeline to completion.

        Runs stages in sequence, following transitions based on
        completion signals until an end signal is reached or
        no valid transition exists.

        Args:
            stats: Optional BuildStats for tracking usage

        Returns:
            Final PipelineState with status and artifacts
        """
        stats = stats or BuildStats()
        self._state.status = PipelineStatus.RUNNING
        self._should_stop = False

        # Build execution context
        context = dict(self.initial_context)

        # Start with initial stage
        current_stage_name = self.config.start_stage

        print(f"\n{'='*60}")
        print(f"🚀 PIPELINE: {self.config.name}")
        print(f"   Starting stage: {current_stage_name}")
        print(f"{'='*60}\n")

        while current_stage_name and not self._should_stop:
            # Get stage instance
            stage = self._stages.get(current_stage_name)
            if not stage:
                print(f"❌ Unknown stage: {current_stage_name}", file=sys.stderr)
                self._state.status = PipelineStatus.FAILED
                break

            self._state.current_stage = current_stage_name
            self._emit(StageStartedEvent(stage=current_stage_name))

            # Run the stage
            try:
                result, iterations = stage.run(context, stats)
            except Exception as e:
                logger.error("Stage '%s' execution failed: %s", current_stage_name, e)
                self._state.status = PipelineStatus.FAILED
                self._emit(PipelineCompletedEvent(
                    status=PipelineStatus.FAILED,
                    total_iterations=self._state.total_iterations,
                ))
                break

            self._state.total_iterations += iterations

            # Merge artifacts into global state
            self._state.global_artifacts.update(result.artifacts)

            # Record in history
            self._state.stage_history.append((current_stage_name, result.signal))

            self._emit(StageCompletedEvent(
                stage=current_stage_name,
                signal=result.signal,
                iterations=iterations,
                artifacts=result.artifacts,
            ))

            # Check for pipeline end signals
            if result.signal and result.signal in self.config.end_signals:
                print(f"\n{'='*60}")
                print(f"✅ PIPELINE COMPLETE: {result.signal}")
                print(f"   Total iterations: {self._state.total_iterations}")
                print(f"{'='*60}\n")
                self._state.status = PipelineStatus.COMPLETED
                self._emit(PipelineCompletedEvent(
                    status=PipelineStatus.COMPLETED,
                    total_iterations=self._state.total_iterations,
                    final_signal=result.signal,
                ))
                break

            # Get next stage from transition
            next_stage_name = stage.get_next_stage(result)

            if next_stage_name:
                print(f"\n➡️ Transitioning: {current_stage_name} → {next_stage_name}")
                print(f"   Signal: {result.signal}")
                current_stage_name = next_stage_name

                # Update context with artifacts for next stage
                context.update(result.artifacts)
            else:
                # No transition defined
                if result.is_complete:
                    print(f"\n⚠️ Stage '{current_stage_name}' complete but no transition for signal: {result.signal}")
                    self._state.status = PipelineStatus.COMPLETED
                else:
                    print(f"\n⚠️ Stage '{current_stage_name}' incomplete, no transition available")
                    self._state.status = PipelineStatus.FAILED
                break

        # Handle stop request
        if self._should_stop:
            self._state.status = PipelineStatus.STOPPED
            self._emit(PipelineCompletedEvent(
                status=PipelineStatus.STOPPED,
                total_iterations=self._state.total_iterations,
            ))

        stats.print_summary()
        return self._state


def create_pipeline_executor(
    config: PipelineConfig,
    agent_name: str = "claude",
    on_event: Callable[[PipelineEvent], None] | None = None,
    context: dict[str, Any] | None = None,
) -> PipelineExecutor:
    """Factory function to create a PipelineExecutor.

    Args:
        config: PipelineConfig defining the pipeline
        agent_name: Agent backend name ("claude" or "codex")
        on_event: Optional callback for pipeline events
        context: Initial context variables

    Returns:
        Configured PipelineExecutor instance
    """
    from ..agent import get_agent

    runner = get_agent(agent_name)
    return PipelineExecutor(
        config=config,
        runner=runner,
        on_event=on_event,
        context=context,
    )
