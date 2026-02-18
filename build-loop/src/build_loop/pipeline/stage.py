"""
Stage definition and execution for pipeline workflows.

A stage represents a single phase in a pipeline with its own prompt template,
completion strategy, and transition rules.
"""

import logging
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

from ..agent import AgentRunner
from ..stats import BuildStats
from .completion import CompletionResult, CompletionStrategy

logger = logging.getLogger(__name__)


@dataclass
class StageConfig:
    """Configuration for a pipeline stage.

    Attributes:
        name: Unique identifier for this stage (e.g., "build", "code_review")
        prompt_template: Path to the prompt template file or inline template string
        completion: Strategy for detecting stage completion
        max_iterations: Maximum iterations before forcing stage exit (default: 10)
        transitions: Signal-to-stage mapping (e.g., {"BUILD_COMPLETE": "code_review"})
        allowed_tools: Tool allowlist for this stage (None = use defaults)
        denied_tools: Tool denylist for this stage (None = use defaults)
    """
    name: str
    prompt_template: str
    completion: CompletionStrategy
    max_iterations: int = 10
    transitions: dict[str, str] = field(default_factory=dict)
    allowed_tools: list[str] | None = None
    denied_tools: list[str] | None = None


class Stage:
    """Executes a single pipeline stage.

    Manages iteration loop within a stage, running the agent until
    completion is detected or max iterations reached.

    Args:
        config: StageConfig defining this stage's behavior
        runner: AgentRunner instance for executing prompts
        on_iteration: Optional callback for iteration events
        on_output: Optional callback for streaming output
    """

    def __init__(
        self,
        config: StageConfig,
        runner: AgentRunner,
        on_iteration: Callable[[int, int], None] | None = None,
        on_output: Callable[[str], None] | None = None,
    ):
        self.config = config
        self.runner = runner
        self.on_iteration = on_iteration
        self.on_output = on_output
        self._template_cache: str | None = None
        self._cumulative_iterations: int = 0

    @property
    def name(self) -> str:
        """Stage identifier."""
        return self.config.name

    def load_template(self) -> str:
        """Load the prompt template.

        If prompt_template is a file path, reads the file.
        Otherwise treats it as an inline template string.

        Returns:
            The template string.

        Raises:
            FileNotFoundError: If template file doesn't exist.
        """
        if self._template_cache is not None:
            return self._template_cache

        template_path = Path(self.config.prompt_template)

        # Check if it's a file path
        if template_path.is_file():
            self._template_cache = template_path.read_text(encoding="utf-8")
        elif template_path.suffix == ".md" and not template_path.exists():
            # Looks like a path but doesn't exist
            raise FileNotFoundError(
                f"Stage '{self.name}' prompt template not found: {self.config.prompt_template}"
            )
        else:
            # Treat as inline template
            self._template_cache = self.config.prompt_template

        return self._template_cache

    def build_prompt(self, context: dict[str, Any]) -> str:
        """Build the prompt from template and context.

        Substitutes {variable} placeholders in the template with
        values from the context dictionary.

        Args:
            context: Dictionary of variable substitutions

        Returns:
            The constructed prompt string.
        """
        template = self.load_template()

        # Substitute variables
        prompt = template
        for key, value in context.items():
            placeholder = f"{{{key}}}"
            if placeholder in prompt:
                prompt = prompt.replace(placeholder, str(value))

        return prompt

    def run_iteration(
        self,
        context: dict[str, Any],
        stats: BuildStats | None = None,
    ) -> tuple[CompletionResult, str]:
        """Run a single iteration of this stage.

        Builds the prompt, runs the agent, and evaluates completion.

        Args:
            context: Variables for prompt template substitution
            stats: Optional BuildStats for tracking usage

        Returns:
            Tuple of (CompletionResult, full_output_text)
        """
        prompt = self.build_prompt(context)

        try:
            exit_code, output, stderr = self.runner.run_iteration(
                prompt, stats=stats, denied_tools=self.config.denied_tools
            )
        except Exception as e:
            logger.error("Stage '%s' iteration failed: %s", self.name, e)
            raise

        # Evaluate completion
        result = self.config.completion.evaluate(output, exit_code)

        return result, output

    def run(
        self,
        context: dict[str, Any],
        stats: BuildStats | None = None,
    ) -> tuple[CompletionResult, int]:
        """Run this stage until completion or max iterations.

        Iterates until the completion strategy indicates completion
        or max_iterations is reached.

        Args:
            context: Variables for prompt template substitution
            stats: Optional BuildStats for tracking usage

        Returns:
            Tuple of (final_CompletionResult, iterations_completed)
        """
        stats = stats or BuildStats()
        iterations = 0
        last_result = CompletionResult(is_complete=False)

        while iterations < self.config.max_iterations:
            iterations += 1
            self._cumulative_iterations += 1

            # Notify iteration start
            if self.on_iteration:
                self.on_iteration(self._cumulative_iterations, self.config.max_iterations)

            # Print iteration header
            print(f"\n{'='*60}")
            print(f"🔄 [{self.name}] Iteration {self._cumulative_iterations}/{self.config.max_iterations}")
            print(f"{'='*60}\n")

            try:
                result, output = self.run_iteration(context, stats)
            except Exception as e:
                print(f"❌ Stage '{self.name}' failed: {e}", file=sys.stderr)
                last_result = CompletionResult(
                    is_complete=False,
                    artifacts={"error": str(e)}
                )
                break

            last_result = result

            # Check completion
            if result.is_complete:
                stats.iterations_completed += 1
                print(f"\n✅ [{self.name}] Complete: {result.signal}")
                break
            else:
                if result.signal:
                    print(f"\n⏳ [{self.name}] Signal: {result.signal}, continuing...")
                else:
                    print(f"\n⏳ [{self.name}] No completion signal, continuing...")

        if iterations >= self.config.max_iterations and not last_result.is_complete:
            print(f"\n⚠️ [{self.name}] Max iterations ({self.config.max_iterations}) reached")

        return last_result, iterations

    def get_next_stage(self, result: CompletionResult) -> str | None:
        """Determine the next stage based on completion signal.

        Looks up the signal in the transitions map to determine
        which stage should run next.

        Args:
            result: CompletionResult from this stage

        Returns:
            Next stage name, or None if no transition defined
        """
        if not result.signal:
            return None

        return self.config.transitions.get(result.signal)

    def should_continue(self, result: CompletionResult) -> bool:
        """Check if the stage loop should continue.

        Returns True if the stage is not complete and iterations
        haven't been exhausted.

        Args:
            result: Latest CompletionResult

        Returns:
            True if should continue iterating
        """
        return not result.is_complete
