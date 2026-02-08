"""
Completion strategies for pipeline stages.

Defines how to detect when a stage has completed and what signal/artifacts
were produced. Supports promise-based (regex tags) and JSON-based detection.
"""

import json
import re
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


@dataclass
class CompletionResult:
    """Result from evaluating stage completion.

    Attributes:
        is_complete: Whether the stage should be considered complete
        signal: The completion signal detected (e.g., "TASK_COMPLETE", "APPROVED")
        artifacts: Key-value artifacts extracted from output (e.g., {"gaps_file": "/path/..."})
    """
    is_complete: bool
    signal: str | None = None
    artifacts: dict[str, Any] = field(default_factory=dict)


class CompletionStrategy(ABC):
    """Base class for completion detection strategies."""

    @abstractmethod
    def evaluate(self, output: str, exit_code: int) -> CompletionResult:
        """Evaluate whether output indicates stage completion.

        Args:
            output: Full text output from the agent
            exit_code: Process exit code

        Returns:
            CompletionResult with completion status, signal, and artifacts
        """


class PromiseCompletion(CompletionStrategy):
    """Detects completion via [[PROMISE:SIGNAL]] tags in output.

    Extracts promise tags matching the pattern [[PROMISE:...]] and treats
    specific signals as completion indicators.

    Args:
        complete_signals: List of signals that indicate completion
                         (e.g., ["TASK_COMPLETE", "BUILD_COMPLETE"])
        require_success: If True, requires exit_code == 0 for completion
    """

    # Regex pattern for promise tags
    PROMISE_PATTERN = re.compile(r"\[\[PROMISE:(.*?)\]\]", re.DOTALL)

    def __init__(
        self,
        complete_signals: list[str] | None = None,
        require_success: bool = False,
    ):
        self.complete_signals = complete_signals or ["TASK_COMPLETE", "BUILD_COMPLETE"]
        self.require_success = require_success

    def evaluate(self, output: str, exit_code: int) -> CompletionResult:
        """Detect promise tags in output.

        Scans output for [[PROMISE:...]] patterns. If a matching signal
        is found, returns completion with that signal.
        """
        # Extract all promise tags
        matches = self.PROMISE_PATTERN.findall(output)
        signals = [m.strip() for m in matches]

        # Check for completion signals
        for signal in signals:
            if signal in self.complete_signals:
                # Check exit code requirement
                if self.require_success and exit_code != 0:
                    return CompletionResult(
                        is_complete=False,
                        signal=signal,
                        artifacts={"exit_code": exit_code}
                    )
                return CompletionResult(
                    is_complete=True,
                    signal=signal,
                )

        # No completion signal found
        return CompletionResult(
            is_complete=False,
            signal=signals[-1] if signals else None,
        )


class JsonCompletion(CompletionStrategy):
    """Detects completion via JSON blocks in output.

    Looks for ```json code blocks and extracts structured results.
    The JSON must contain a "status" field that matches one of the
    complete_statuses to be considered complete.

    Args:
        complete_statuses: List of status values indicating completion
                          (e.g., ["COMPLETE", "APPROVED"])
        signal_field: Field name containing the signal (default: "status")
        artifact_fields: Fields to extract as artifacts (default: all fields)
        require_success: If True, requires exit_code == 0 for completion
    """

    # Regex pattern for JSON code blocks
    JSON_BLOCK_PATTERN = re.compile(r"```json\s*\n(.*?)\n```", re.DOTALL)

    def __init__(
        self,
        complete_statuses: list[str] | None = None,
        signal_field: str = "status",
        artifact_fields: list[str] | None = None,
        require_success: bool = False,
    ):
        self.complete_statuses = complete_statuses or ["COMPLETE", "APPROVED"]
        self.signal_field = signal_field
        self.artifact_fields = artifact_fields  # None means extract all
        self.require_success = require_success

    def evaluate(self, output: str, exit_code: int) -> CompletionResult:
        """Parse JSON blocks from output.

        Searches for the last ```json ... ``` block and extracts
        the status signal and artifacts.
        """
        # Find all JSON blocks
        matches = list(self.JSON_BLOCK_PATTERN.finditer(output))

        if not matches:
            return CompletionResult(is_complete=False)

        # Use the last JSON block
        json_str = matches[-1].group(1).strip()

        try:
            data = json.loads(json_str)
        except json.JSONDecodeError:
            return CompletionResult(is_complete=False)

        if not isinstance(data, dict):
            return CompletionResult(is_complete=False)

        # Extract signal
        signal = data.get(self.signal_field)
        if isinstance(signal, str):
            signal = signal.upper()

        # Extract artifacts
        if self.artifact_fields:
            artifacts = {k: data[k] for k in self.artifact_fields if k in data}
        else:
            # Extract all fields as artifacts
            artifacts = dict(data)

        # Check for completion
        is_complete = signal in self.complete_statuses

        # Check exit code requirement
        if is_complete and self.require_success and exit_code != 0:
            is_complete = False
            artifacts["exit_code"] = exit_code

        return CompletionResult(
            is_complete=is_complete,
            signal=signal,
            artifacts=artifacts,
        )


class CompositeCompletion(CompletionStrategy):
    """Combines multiple completion strategies.

    Tries each strategy in order until one detects completion.
    Useful for backward compatibility (e.g., JSON with promise fallback).

    Args:
        strategies: List of CompletionStrategy instances to try
    """

    def __init__(self, strategies: list[CompletionStrategy]):
        self.strategies = strategies

    def evaluate(self, output: str, exit_code: int) -> CompletionResult:
        """Try each strategy until one reports completion."""
        for strategy in self.strategies:
            result = strategy.evaluate(output, exit_code)
            if result.is_complete:
                return result

        # Return last non-complete result, or default
        if self.strategies:
            return self.strategies[-1].evaluate(output, exit_code)
        return CompletionResult(is_complete=False)
