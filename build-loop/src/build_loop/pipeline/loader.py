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
