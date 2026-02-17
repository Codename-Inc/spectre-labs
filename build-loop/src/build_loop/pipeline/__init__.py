"""
Pipeline module for stage-based execution workflows.

Provides abstractions for defining and executing multi-stage pipelines
with configurable completion strategies and signal-based transitions.
"""

from .completion import (
    CompletionResult,
    CompletionStrategy,
    JsonCompletion,
    PromiseCompletion,
)
from .executor import PipelineExecutor, PipelineState
from .loader import create_default_pipeline, load_pipeline
from .stage import Stage, StageConfig

__all__ = [
    "CompletionResult",
    "CompletionStrategy",
    "JsonCompletion",
    "PromiseCompletion",
    "Stage",
    "StageConfig",
    "PipelineExecutor",
    "PipelineState",
    "create_default_pipeline",
    "load_pipeline",
]
