"""Tests for tool allow/deny list configuration (Task tool unblock)."""

from build_loop.agent import CLAUDE_ALLOWED_TOOLS, CLAUDE_DENIED_TOOLS
from build_loop.pipeline.loader import PLAN_DENIED_TOOLS, PLAN_RESEARCH_DENIED_TOOLS


class TestClaudeToolLists:
    """Tests for global Claude tool allow/deny lists in agent.py."""

    def test_task_not_in_denied_tools(self):
        """Happy: Task tool is not globally denied — subagent dispatch is possible."""
        assert "Task" not in CLAUDE_DENIED_TOOLS

    def test_task_in_allowed_tools(self):
        """Happy: Task tool is explicitly allowed for permission-free execution."""
        assert "Task" in CLAUDE_ALLOWED_TOOLS

    def test_denied_tools_still_block_interactive(self):
        """Failure: Interactive/hanging tools remain blocked."""
        for tool in ["AskUserQuestion", "EnterPlanMode", "NotebookEdit"]:
            assert tool in CLAUDE_DENIED_TOOLS, (
                f"'{tool}' should remain in CLAUDE_DENIED_TOOLS"
            )

    def test_denied_tools_still_block_web(self):
        """Failure: Web tools remain blocked at global level."""
        for tool in ["WebFetch", "WebSearch"]:
            assert tool in CLAUDE_DENIED_TOOLS, (
                f"'{tool}' should remain in CLAUDE_DENIED_TOOLS"
            )

    def test_denied_tools_exact_contents(self):
        """Happy: CLAUDE_DENIED_TOOLS contains exactly the expected tools."""
        expected = {"AskUserQuestion", "WebFetch", "WebSearch", "EnterPlanMode", "NotebookEdit"}
        assert set(CLAUDE_DENIED_TOOLS) == expected


class TestPlanDeniedToolLists:
    """Tests for pipeline-level tool deny lists in loader.py."""

    def test_task_not_in_plan_denied_tools(self):
        """Happy: Task is not in PLAN_DENIED_TOOLS — pipeline stages can dispatch subagents."""
        assert "Task" not in PLAN_DENIED_TOOLS

    def test_plan_denied_tools_exact_contents(self):
        """Happy: PLAN_DENIED_TOOLS contains exactly the expected tools."""
        expected = {"AskUserQuestion", "WebFetch", "WebSearch", "EnterPlanMode", "NotebookEdit"}
        assert set(PLAN_DENIED_TOOLS) == expected

    def test_task_not_in_research_denied_tools(self):
        """Happy: Task is not in PLAN_RESEARCH_DENIED_TOOLS — research stage can dispatch subagents."""
        assert "Task" not in PLAN_RESEARCH_DENIED_TOOLS

    def test_research_denied_tools_exact_contents(self):
        """Happy: PLAN_RESEARCH_DENIED_TOOLS contains exactly the expected tools."""
        expected = {"AskUserQuestion", "EnterPlanMode", "NotebookEdit"}
        assert set(PLAN_RESEARCH_DENIED_TOOLS) == expected
