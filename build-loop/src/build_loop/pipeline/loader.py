"""
YAML pipeline configuration loader.

Parses pipeline definitions from YAML files and validates them using Pydantic.
"""

import logging
from pathlib import Path
from typing import Any, Literal

import yaml
from pydantic import BaseModel, Field, field_validator, model_validator

from .completion import (
    CompositeCompletion,
    CompletionStrategy,
    JsonCompletion,
    PromiseCompletion,
)
from .executor import PipelineConfig
from .stage import StageConfig

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Pydantic Schema Models
# ---------------------------------------------------------------------------


class CompletionSchema(BaseModel):
    """Schema for completion strategy configuration."""

    type: Literal["promise", "json", "composite"]
    signals: list[str] | None = None  # For promise: completion signals
    statuses: list[str] | None = None  # For json: completion statuses
    signal_field: str = "status"  # For json: field containing signal
    artifact_fields: list[str] | None = None  # For json: fields to extract
    require_success: bool = False
    strategies: list["CompletionSchema"] | None = None  # For composite

    def to_strategy(self) -> CompletionStrategy:
        """Convert schema to CompletionStrategy instance."""
        if self.type == "promise":
            return PromiseCompletion(
                complete_signals=self.signals or ["TASK_COMPLETE", "BUILD_COMPLETE"],
                require_success=self.require_success,
            )
        elif self.type == "json":
            return JsonCompletion(
                complete_statuses=self.statuses or ["COMPLETE", "APPROVED"],
                signal_field=self.signal_field,
                artifact_fields=self.artifact_fields,
                require_success=self.require_success,
            )
        elif self.type == "composite":
            if not self.strategies:
                raise ValueError("Composite completion requires 'strategies' list")
            return CompositeCompletion(
                strategies=[s.to_strategy() for s in self.strategies]
            )
        else:
            raise ValueError(f"Unknown completion type: {self.type}")


class StageSchema(BaseModel):
    """Schema for a single pipeline stage."""

    name: str
    prompt: str = Field(..., description="Path to prompt template or inline template")
    completion: CompletionSchema
    max_iterations: int = Field(default=10, ge=1, le=100)
    transitions: dict[str, str] = Field(default_factory=dict)
    allowed_tools: list[str] | None = None
    denied_tools: list[str] | None = None

    @field_validator("prompt")
    @classmethod
    def validate_prompt(cls, v: str) -> str:
        """Validate prompt is non-empty."""
        if not v.strip():
            raise ValueError("Prompt cannot be empty")
        return v

    def to_config(self, base_path: Path | None = None) -> StageConfig:
        """Convert schema to StageConfig instance.

        Args:
            base_path: Base path for resolving relative prompt paths

        Returns:
            StageConfig instance
        """
        prompt_template = self.prompt

        # Resolve relative paths
        if base_path and not Path(prompt_template).is_absolute():
            candidate = base_path / prompt_template
            if candidate.is_file():
                prompt_template = str(candidate)

        return StageConfig(
            name=self.name,
            prompt_template=prompt_template,
            completion=self.completion.to_strategy(),
            max_iterations=self.max_iterations,
            transitions=self.transitions,
            allowed_tools=self.allowed_tools,
            denied_tools=self.denied_tools,
        )


class PipelineSchema(BaseModel):
    """Schema for a complete pipeline definition."""

    name: str
    description: str = ""
    start_stage: str
    end_signals: list[str] = Field(default_factory=lambda: ["BUILD_COMPLETE", "COMPLETE"])
    stages: list[StageSchema]

    @model_validator(mode="after")
    def validate_stages(self) -> "PipelineSchema":
        """Validate stage references are valid."""
        stage_names = {s.name for s in self.stages}

        # Check start_stage exists
        if self.start_stage not in stage_names:
            raise ValueError(f"start_stage '{self.start_stage}' not found in stages")

        # Check all transition targets exist
        for stage in self.stages:
            for signal, target in stage.transitions.items():
                if target not in stage_names:
                    raise ValueError(
                        f"Stage '{stage.name}' transition '{signal}' -> '{target}': "
                        f"target stage not found"
                    )

        return self

    def to_config(self, base_path: Path | None = None) -> PipelineConfig:
        """Convert schema to PipelineConfig instance.

        Args:
            base_path: Base path for resolving relative prompt paths

        Returns:
            PipelineConfig instance
        """
        stages = {
            stage.name: stage.to_config(base_path)
            for stage in self.stages
        }

        return PipelineConfig(
            name=self.name,
            description=self.description,
            stages=stages,
            start_stage=self.start_stage,
            end_signals=self.end_signals,
        )


# ---------------------------------------------------------------------------
# Loader Functions
# ---------------------------------------------------------------------------


def load_pipeline(path: str | Path) -> PipelineConfig:
    """Load a pipeline configuration from a YAML file.

    Args:
        path: Path to the YAML pipeline definition file

    Returns:
        Validated PipelineConfig instance

    Raises:
        FileNotFoundError: If the file doesn't exist
        ValueError: If the YAML is invalid or fails validation
    """
    path = Path(path)

    if not path.is_file():
        raise FileNotFoundError(f"Pipeline file not found: {path}")

    try:
        content = path.read_text(encoding="utf-8")
        data = yaml.safe_load(content)
    except yaml.YAMLError as e:
        raise ValueError(f"Invalid YAML in {path}: {e}") from e

    if not isinstance(data, dict):
        raise ValueError(f"Pipeline file must contain a YAML mapping: {path}")

    try:
        schema = PipelineSchema(**data)
    except Exception as e:
        raise ValueError(f"Pipeline validation failed: {e}") from e

    # Use file's directory as base for resolving relative paths
    base_path = path.parent

    return schema.to_config(base_path)


def load_pipeline_from_dict(data: dict[str, Any], base_path: Path | None = None) -> PipelineConfig:
    """Load a pipeline configuration from a dictionary.

    Useful for programmatic pipeline creation or testing.

    Args:
        data: Dictionary conforming to PipelineSchema
        base_path: Optional base path for resolving relative prompt paths

    Returns:
        Validated PipelineConfig instance

    Raises:
        ValueError: If validation fails
    """
    try:
        schema = PipelineSchema(**data)
    except Exception as e:
        raise ValueError(f"Pipeline validation failed: {e}") from e

    return schema.to_config(base_path)


def create_default_pipeline(
    tasks_file: str,
    context_files: list[str] | None = None,
    build_prompt_path: str | None = None,
    code_review_prompt_path: str | None = None,
    validate_prompt_path: str | None = None,
    max_build_iterations: int = 10,
) -> PipelineConfig:
    """Create a default build -> code_review -> validate pipeline.

    This is the recommended pipeline for builds with --validate.
    Includes code review between build and validation with
    phase-aware signals.

    Args:
        tasks_file: Path to the tasks file
        context_files: Optional list of context file paths
        build_prompt_path: Optional custom build prompt template path
        code_review_prompt_path: Optional custom code review prompt path
        validate_prompt_path: Optional custom validate prompt template path
        max_build_iterations: Max iterations for the build stage

    Returns:
        PipelineConfig for build -> code_review -> validate workflow
    """
    prompts_dir = Path(__file__).parent.parent / "prompts"
    build_prompt = build_prompt_path or str(prompts_dir / "build.md")
    review_prompt = code_review_prompt_path or str(prompts_dir / "code_review.md")
    validate_prompt = validate_prompt_path or str(prompts_dir / "validate.md")

    stages = {
        "build": StageConfig(
            name="build",
            prompt_template=build_prompt,
            completion=PromiseCompletion(
                complete_signals=["TASK_COMPLETE", "PHASE_COMPLETE", "BUILD_COMPLETE"],
                extract_artifacts=True,
            ),
            max_iterations=max_build_iterations,
            transitions={
                "TASK_COMPLETE": "build",
                "PHASE_COMPLETE": "code_review",
                "BUILD_COMPLETE": "code_review",
            },
        ),
        "code_review": StageConfig(
            name="code_review",
            prompt_template=review_prompt,
            completion=JsonCompletion(
                complete_statuses=["APPROVED", "CHANGES_REQUESTED"],
                signal_field="status",
            ),
            max_iterations=1,
            transitions={
                "APPROVED": "validate",
                "CHANGES_REQUESTED": "build",
            },
        ),
        "validate": StageConfig(
            name="validate",
            prompt_template=validate_prompt,
            completion=CompositeCompletion([
                JsonCompletion(
                    complete_statuses=["ALL_VALIDATED", "VALIDATED", "GAPS_FOUND"],
                    signal_field="status",
                ),
                PromiseCompletion(
                    complete_signals=["VALIDATION:ALL_VALIDATED", "VALIDATION:VALIDATED", "VALIDATION:GAPS_FOUND"],
                ),
            ]),
            max_iterations=1,
            transitions={
                "VALIDATED": "build",
                "GAPS_FOUND": "build",
            },
        ),
    }

    return PipelineConfig(
        name="build-review-validate",
        description="Build with code review and phase-aware validation",
        stages=stages,
        start_stage="build",
        end_signals=["ALL_VALIDATED"],
    )


def create_default_build_validate_pipeline(
    tasks_file: str,
    context_files: list[str] | None = None,
    build_prompt_path: str | None = None,
    validate_prompt_path: str | None = None,
) -> PipelineConfig:
    """Create a default build→validate pipeline configuration.

    This provides backward compatibility with the existing CLI behavior.

    Args:
        tasks_file: Path to the tasks file
        context_files: Optional list of context file paths
        build_prompt_path: Optional custom build prompt template path
        validate_prompt_path: Optional custom validate prompt template path

    Returns:
        PipelineConfig for build→validate workflow
    """
    # Default prompt paths
    prompts_dir = Path(__file__).parent.parent / "prompts"
    build_prompt = build_prompt_path or str(prompts_dir / "build.md")
    validate_prompt = validate_prompt_path or str(prompts_dir / "validate.md")

    # Format context paths
    if context_files:
        context_str = "\n".join(f"- `{f}`" for f in context_files)
    else:
        context_str = "None"

    stages = {
        "build": StageConfig(
            name="build",
            prompt_template=build_prompt,
            completion=PromiseCompletion(
                complete_signals=["TASK_COMPLETE", "BUILD_COMPLETE"],
            ),
            max_iterations=10,
            transitions={
                "BUILD_COMPLETE": "validate",
                "TASK_COMPLETE": "build",  # Loop back for more tasks
            },
        ),
        "validate": StageConfig(
            name="validate",
            prompt_template=validate_prompt,
            completion=CompositeCompletion([
                JsonCompletion(
                    complete_statuses=["COMPLETE", "GAPS_FOUND"],
                    signal_field="status",
                ),
                PromiseCompletion(
                    complete_signals=["VALIDATION:COMPLETE", "VALIDATION:GAPS_FOUND"],
                ),
            ]),
            max_iterations=1,  # Validation is single-pass
            transitions={
                "GAPS_FOUND": "build",  # Loop back to fix gaps
                "COMPLETE": None,  # End pipeline
            },
        ),
    }

    return PipelineConfig(
        name="build-validate",
        description="Standard build with post-build validation",
        stages=stages,
        start_stage="build",
        end_signals=["COMPLETE", "BUILD_COMPLETE"],
    )


# ---------------------------------------------------------------------------
# Planning Pipeline Denied Tools
# ---------------------------------------------------------------------------

# Standard denied tools for planning stages (same as build loop)
PLAN_DENIED_TOOLS = [
    "AskUserQuestion",
    "WebFetch",
    "WebSearch",
    "Task",
    "EnterPlanMode",
    "NotebookEdit",
]

# Research stage gets WebSearch/WebFetch access for external docs
PLAN_RESEARCH_DENIED_TOOLS = [
    "AskUserQuestion",
    "Task",
    "EnterPlanMode",
    "NotebookEdit",
]


def create_ship_pipeline(max_iterations: int = 10) -> PipelineConfig:
    """Create a ship pipeline: clean -> test -> rebase.

    The ship pipeline takes a feature branch from "works on branch" to
    "landed on main" by running three stages autonomously:
    - Clean: dead code removal, lint, duplication analysis (7 tasks)
    - Test: risk-tiered test coverage (4 tasks)
    - Rebase: rebase onto parent, resolve conflicts, land via PR or merge (single context window)

    Args:
        max_iterations: Max iterations for clean and test stages.
            Rebase is capped at min(max_iterations, 3) since conflict
            resolution requires continuous context.

    Returns:
        PipelineConfig for the 3-stage ship workflow.
    """
    prompts_dir = Path(__file__).parent.parent / "prompts" / "shipping"
    rebase_max = min(max_iterations, 3)

    stages = {
        "clean": StageConfig(
            name="clean",
            prompt_template=str(prompts_dir / "clean.md"),
            completion=JsonCompletion(
                complete_statuses=["CLEAN_TASK_COMPLETE", "CLEAN_COMPLETE"],
                signal_field="status",
            ),
            max_iterations=max_iterations,
            transitions={
                "CLEAN_TASK_COMPLETE": "clean",
                "CLEAN_COMPLETE": "test",
            },
            denied_tools=PLAN_DENIED_TOOLS,
        ),
        "test": StageConfig(
            name="test",
            prompt_template=str(prompts_dir / "test.md"),
            completion=JsonCompletion(
                complete_statuses=["TEST_TASK_COMPLETE", "TEST_COMPLETE"],
                signal_field="status",
            ),
            max_iterations=max_iterations,
            transitions={
                "TEST_TASK_COMPLETE": "test",
                "TEST_COMPLETE": "rebase",
            },
            denied_tools=PLAN_DENIED_TOOLS,
        ),
        "rebase": StageConfig(
            name="rebase",
            prompt_template=str(prompts_dir / "rebase.md"),
            completion=JsonCompletion(
                complete_statuses=["SHIP_COMPLETE"],
                signal_field="status",
            ),
            max_iterations=rebase_max,
            transitions={},
            denied_tools=PLAN_DENIED_TOOLS,
        ),
    }

    return PipelineConfig(
        name="ship",
        description="Ship pipeline: clean, test, rebase to land feature branch",
        stages=stages,
        start_stage="clean",
        end_signals=["SHIP_COMPLETE"],
    )


def create_plan_pipeline() -> PipelineConfig:
    """Create a planning pipeline: research -> assess -> [create_plan] -> create_tasks -> plan_review -> req_validate -> [update_docs].

    The planning pipeline transforms scope documents into a build-ready manifest.
    Complexity assessment (assess stage) determines routing:
    - LIGHT: skips create_plan, goes straight to create_tasks
    - STANDARD/COMPREHENSIVE: routes through create_plan first

    The update_docs stage is included but only used via the resume pipeline
    (create_plan_resume_pipeline). It's present here for completeness so
    transitions can reference it.

    Returns:
        PipelineConfig for the 7-stage planning workflow.
    """
    prompts_dir = Path(__file__).parent.parent / "prompts" / "planning"

    stages = {
        "research": StageConfig(
            name="research",
            prompt_template=str(prompts_dir / "research.md"),
            completion=JsonCompletion(
                complete_statuses=["RESEARCH_COMPLETE"],
                signal_field="status",
            ),
            max_iterations=1,
            transitions={"RESEARCH_COMPLETE": "assess"},
            denied_tools=PLAN_RESEARCH_DENIED_TOOLS,
        ),
        "assess": StageConfig(
            name="assess",
            prompt_template=str(prompts_dir / "assess.md"),
            completion=JsonCompletion(
                complete_statuses=["LIGHT", "STANDARD", "COMPREHENSIVE"],
                signal_field="status",
            ),
            max_iterations=1,
            transitions={
                "LIGHT": "create_tasks",
                "STANDARD": "create_plan",
                "COMPREHENSIVE": "create_plan",
            },
            denied_tools=PLAN_DENIED_TOOLS,
        ),
        "create_plan": StageConfig(
            name="create_plan",
            prompt_template=str(prompts_dir / "create_plan.md"),
            completion=JsonCompletion(
                complete_statuses=["PLAN_COMPLETE"],
                signal_field="status",
            ),
            max_iterations=1,
            transitions={"PLAN_COMPLETE": "create_tasks"},
            denied_tools=PLAN_DENIED_TOOLS,
        ),
        "create_tasks": StageConfig(
            name="create_tasks",
            prompt_template=str(prompts_dir / "create_tasks.md"),
            completion=JsonCompletion(
                complete_statuses=["TASKS_COMPLETE"],
                signal_field="status",
            ),
            max_iterations=1,
            transitions={"TASKS_COMPLETE": "plan_review"},
            denied_tools=PLAN_DENIED_TOOLS,
        ),
        "plan_review": StageConfig(
            name="plan_review",
            prompt_template=str(prompts_dir / "plan_review.md"),
            completion=JsonCompletion(
                complete_statuses=["REVIEW_COMPLETE"],
                signal_field="status",
            ),
            max_iterations=1,
            transitions={"REVIEW_COMPLETE": "req_validate"},
            denied_tools=PLAN_DENIED_TOOLS,
        ),
        "req_validate": StageConfig(
            name="req_validate",
            prompt_template=str(prompts_dir / "req_validate.md"),
            completion=JsonCompletion(
                complete_statuses=["PLAN_VALIDATED", "CLARIFICATIONS_NEEDED"],
                signal_field="status",
            ),
            max_iterations=1,
            transitions={},
            denied_tools=PLAN_DENIED_TOOLS,
        ),
        "update_docs": StageConfig(
            name="update_docs",
            prompt_template=str(prompts_dir / "update_docs.md"),
            completion=JsonCompletion(
                complete_statuses=["PLAN_READY"],
                signal_field="status",
            ),
            max_iterations=1,
            transitions={},
            denied_tools=PLAN_DENIED_TOOLS,
        ),
    }

    return PipelineConfig(
        name="plan",
        description="Planning pipeline: scope docs to build-ready manifest",
        stages=stages,
        start_stage="research",
        end_signals=["PLAN_VALIDATED", "PLAN_READY"],
    )


def create_plan_resume_pipeline() -> PipelineConfig:
    """Create a single-stage pipeline for post-clarification resume.

    After the planning pipeline pauses for clarifications, this pipeline
    runs only the update_docs stage to incorporate answers and produce
    the final manifest.

    Returns:
        PipelineConfig with single update_docs stage.
    """
    prompts_dir = Path(__file__).parent.parent / "prompts" / "planning"

    stages = {
        "update_docs": StageConfig(
            name="update_docs",
            prompt_template=str(prompts_dir / "update_docs.md"),
            completion=JsonCompletion(
                complete_statuses=["PLAN_READY"],
                signal_field="status",
            ),
            max_iterations=1,
            transitions={},
            denied_tools=PLAN_DENIED_TOOLS,
        ),
    }

    return PipelineConfig(
        name="plan-resume",
        description="Resume planning after clarifications",
        stages=stages,
        start_stage="update_docs",
        end_signals=["PLAN_READY"],
    )
