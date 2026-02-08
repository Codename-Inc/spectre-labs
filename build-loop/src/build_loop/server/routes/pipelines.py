"""
Pipeline CRUD endpoints.

Provides REST API for listing, reading, and saving pipeline configurations.
"""

import logging
from pathlib import Path
from typing import Any

import yaml
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/pipelines", tags=["pipelines"])

# Default pipeline directory
PIPELINES_DIR = Path.cwd() / ".spectre" / "pipelines"


class PipelineResponse(BaseModel):
    """Response model for a single pipeline."""
    name: str
    description: str
    path: str
    config: dict[str, Any]


class PipelineListItem(BaseModel):
    """Summary item for pipeline listing."""
    name: str
    description: str
    path: str
    stages: list[str]


class PipelineSaveRequest(BaseModel):
    """Request model for saving a pipeline."""
    config: dict[str, Any]


def get_pipelines_dir() -> Path:
    """Get the pipelines directory, creating if needed."""
    pipelines_dir = Path.cwd() / ".spectre" / "pipelines"
    pipelines_dir.mkdir(parents=True, exist_ok=True)
    return pipelines_dir


def ensure_demo_pipelines() -> None:
    """Create demo pipelines if none exist."""
    pipelines_dir = get_pipelines_dir()
    existing = list(pipelines_dir.glob("*.yaml")) + list(pipelines_dir.glob("*.yml"))

    if existing:
        return  # Already have pipelines

    # Create demo build-validate pipeline
    demo_build_validate = {
        "name": "demo-build-validate",
        "description": "Demo: Build tasks then validate implementation",
        "start_stage": "build",
        "end_signals": ["COMPLETE", "BUILD_COMPLETE"],
        "stages": [
            {
                "name": "build",
                "prompt": "prompts/build.md",
                "completion": {
                    "type": "promise",
                    "signals": ["TASK_COMPLETE", "BUILD_COMPLETE"]
                },
                "max_iterations": 10,
                "transitions": {
                    "BUILD_COMPLETE": "validate",
                    "TASK_COMPLETE": "build"
                }
            },
            {
                "name": "validate",
                "prompt": "prompts/validate.md",
                "completion": {
                    "type": "json",
                    "statuses": ["COMPLETE", "GAPS_FOUND"]
                },
                "max_iterations": 1,
                "transitions": {
                    "GAPS_FOUND": "build"
                }
            }
        ]
    }

    # Create demo full-feature pipeline with code review
    demo_full_feature = {
        "name": "demo-full-feature",
        "description": "Demo: Build → Code Review → Validate cycle",
        "start_stage": "build",
        "end_signals": ["COMPLETE"],
        "stages": [
            {
                "name": "build",
                "prompt": "prompts/build.md",
                "completion": {
                    "type": "promise",
                    "signals": ["TASK_COMPLETE", "BUILD_COMPLETE"]
                },
                "max_iterations": 10,
                "transitions": {
                    "BUILD_COMPLETE": "code_review",
                    "TASK_COMPLETE": "build"
                }
            },
            {
                "name": "code_review",
                "prompt": "prompts/code_review.md",
                "completion": {
                    "type": "json",
                    "statuses": ["APPROVED", "CHANGES_REQUESTED"]
                },
                "max_iterations": 1,
                "transitions": {
                    "APPROVED": "validate",
                    "CHANGES_REQUESTED": "build"
                }
            },
            {
                "name": "validate",
                "prompt": "prompts/validate.md",
                "completion": {
                    "type": "json",
                    "statuses": ["COMPLETE", "GAPS_FOUND"]
                },
                "max_iterations": 1,
                "transitions": {
                    "GAPS_FOUND": "build"
                }
            }
        ]
    }

    # Save demo pipelines
    save_pipeline_file(pipelines_dir / "demo-build-validate.yaml", demo_build_validate)
    save_pipeline_file(pipelines_dir / "demo-full-feature.yaml", demo_full_feature)
    logger.info("Created demo pipelines in %s", pipelines_dir)


def list_pipeline_files() -> list[Path]:
    """List all YAML pipeline files in the pipelines directory."""
    pipelines_dir = get_pipelines_dir()
    files = []
    for pattern in ["*.yaml", "*.yml"]:
        files.extend(pipelines_dir.glob(pattern))
    return sorted(files, key=lambda p: p.name)


def load_pipeline_file(path: Path) -> dict[str, Any]:
    """Load and parse a pipeline YAML file."""
    if not path.is_file():
        raise FileNotFoundError(f"Pipeline not found: {path}")

    content = path.read_text(encoding="utf-8")
    return yaml.safe_load(content) or {}


def save_pipeline_file(path: Path, config: dict[str, Any]) -> None:
    """Save a pipeline configuration to YAML file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    content = yaml.dump(config, default_flow_style=False, sort_keys=False)
    path.write_text(content, encoding="utf-8")


@router.get("", response_model=list[PipelineListItem])
async def list_pipelines() -> list[PipelineListItem]:
    """List all available pipeline configurations."""
    # Create demo pipelines if none exist
    ensure_demo_pipelines()

    pipelines = []

    for path in list_pipeline_files():
        try:
            config = load_pipeline_file(path)
            stages = [s.get("name", "unnamed") for s in config.get("stages", [])]
            pipelines.append(PipelineListItem(
                name=config.get("name", path.stem),
                description=config.get("description", ""),
                path=str(path.relative_to(Path.cwd())),
                stages=stages,
            ))
        except Exception as e:
            logger.warning("Failed to load pipeline %s: %s", path, e)
            continue

    return pipelines


@router.get("/{name}", response_model=PipelineResponse)
async def get_pipeline(name: str) -> PipelineResponse:
    """Get a specific pipeline configuration by name."""
    pipelines_dir = get_pipelines_dir()

    # Try both .yaml and .yml extensions
    for ext in [".yaml", ".yml"]:
        path = pipelines_dir / f"{name}{ext}"
        if path.is_file():
            try:
                config = load_pipeline_file(path)
                return PipelineResponse(
                    name=config.get("name", name),
                    description=config.get("description", ""),
                    path=str(path.relative_to(Path.cwd())),
                    config=config,
                )
            except Exception as e:
                raise HTTPException(
                    status_code=500,
                    detail=f"Failed to load pipeline: {e}"
                )

    raise HTTPException(status_code=404, detail=f"Pipeline not found: {name}")


@router.put("/{name}", response_model=PipelineResponse)
async def save_pipeline(name: str, request: PipelineSaveRequest) -> PipelineResponse:
    """Save or update a pipeline configuration."""
    pipelines_dir = get_pipelines_dir()
    path = pipelines_dir / f"{name}.yaml"

    try:
        # Ensure name in config matches filename
        config = dict(request.config)
        config["name"] = name

        save_pipeline_file(path, config)

        return PipelineResponse(
            name=name,
            description=config.get("description", ""),
            path=str(path.relative_to(Path.cwd())),
            config=config,
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to save pipeline: {e}"
        )


@router.delete("/{name}")
async def delete_pipeline(name: str) -> dict[str, str]:
    """Delete a pipeline configuration."""
    pipelines_dir = get_pipelines_dir()

    # Try both extensions
    for ext in [".yaml", ".yml"]:
        path = pipelines_dir / f"{name}{ext}"
        if path.is_file():
            try:
                path.unlink()
                return {"status": "deleted", "name": name}
            except Exception as e:
                raise HTTPException(
                    status_code=500,
                    detail=f"Failed to delete pipeline: {e}"
                )

    raise HTTPException(status_code=404, detail=f"Pipeline not found: {name}")


@router.post("/{name}/validate")
async def validate_pipeline(name: str) -> dict[str, Any]:
    """Validate a pipeline configuration."""
    from ...pipeline import load_pipeline

    pipelines_dir = get_pipelines_dir()

    # Find the file
    for ext in [".yaml", ".yml"]:
        path = pipelines_dir / f"{name}{ext}"
        if path.is_file():
            try:
                # Use the loader to validate
                config = load_pipeline(str(path))
                return {
                    "valid": True,
                    "name": config.name,
                    "stages": list(config.stages.keys()),
                    "start_stage": config.start_stage,
                }
            except ValueError as e:
                return {
                    "valid": False,
                    "error": str(e),
                }
            except Exception as e:
                return {
                    "valid": False,
                    "error": f"Unexpected error: {e}",
                }

    raise HTTPException(status_code=404, detail=f"Pipeline not found: {name}")
