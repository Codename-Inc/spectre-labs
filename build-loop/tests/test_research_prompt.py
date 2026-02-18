"""Tests for research stage prompt template."""

from pathlib import Path

from build_loop.pipeline.loader import create_plan_pipeline
from build_loop.pipeline.stage import Stage


PROMPTS_DIR = Path(__file__).parent.parent / "src" / "build_loop" / "prompts" / "planning"


class TestResearchPromptContent:
    """Tests for research.md prompt template content."""

    def _load_template(self) -> str:
        """Load the research prompt template."""
        return (PROMPTS_DIR / "research.md").read_text(encoding="utf-8")

    def test_template_contains_required_variables(self):
        """Happy: Template uses {context_files} and {output_dir} variables."""
        template = self._load_template()
        assert "{context_files}" in template
        assert "{output_dir}" in template

    def test_template_instructs_structured_output_file(self):
        """Happy: Template specifies structured sections for task_context.md output."""
        template = self._load_template()
        lower = template.lower()
        # Must instruct writing to task_context.md with structured sections
        assert "task_context.md" in template
        # Must require architecture/patterns section
        assert "pattern" in lower
        # Must require dependencies section
        assert "dependenc" in lower
        # Must require integration points section
        assert "integration" in lower
        # Must require constraints/risks section
        assert "constraint" in lower or "risk" in lower

    def test_template_contains_json_completion_block(self):
        """Happy: Template shows RESEARCH_COMPLETE JSON with task_context_path artifact."""
        template = self._load_template()
        assert "RESEARCH_COMPLETE" in template
        assert "task_context_path" in template
        assert '"status"' in template

    def test_template_instructs_codebase_exploration_tools(self):
        """Happy: Template tells agent to use Read, Grep, Glob for exploration."""
        template = self._load_template()
        assert "Read" in template
        # At least one search tool mentioned
        assert "Grep" in template or "Glob" in template

    def test_template_instructs_reading_scope_docs(self):
        """Happy: Template explicitly instructs agent to read all scope documents."""
        template = self._load_template()
        lower = template.lower()
        assert "scope" in lower or "context" in lower
        assert "read" in lower

    def test_template_has_autonomous_instructions(self):
        """Happy: Template gives clear step-by-step instructions for autonomous execution."""
        template = self._load_template()
        # Should have numbered steps or clear sections for autonomous agent
        # At minimum: read docs, explore codebase, write findings, emit JSON
        lower = template.lower()
        assert "read" in lower
        assert "explore" in lower or "search" in lower or "investigate" in lower
        assert "write" in lower or "output" in lower

    def test_template_has_sufficient_depth(self):
        """Failure: Template must be comprehensive enough for autonomous operation (>500 chars)."""
        template = self._load_template()
        # A proper autonomous prompt needs meaningful instructions, not just a skeleton
        assert len(template) > 500, (
            f"Research prompt is too short ({len(template)} chars) for autonomous operation"
        )

    def test_template_specifies_task_context_file_structure(self):
        """Failure: Template must describe the expected structure of task_context.md."""
        template = self._load_template()
        # Should specify what sections to include in the output file
        # The task requires: architecture patterns, dependencies, integration points
        assert "##" in template or "###" in template or "section" in template.lower(), (
            "Template should specify structured sections for task_context.md output"
        )


class TestResearchSubagentDispatch:
    """Tests for parallel subagent dispatch instructions in research.md."""

    def _load_template(self) -> str:
        """Load the research prompt template."""
        return (PROMPTS_DIR / "research.md").read_text(encoding="utf-8")

    # --- Subagent dispatch presence ---

    def test_template_contains_step_2b_dispatch_section(self):
        """Happy: Template has a Step 2b section for dispatching parallel research agents."""
        template = self._load_template()
        # Should have a clearly labeled sub-step after Step 2
        assert "Step 2b" in template or "Dispatch" in template

    def test_template_does_not_remove_step_2(self):
        """Failure: Original Step 2 (manual codebase exploration) must be preserved as fallback."""
        template = self._load_template()
        # Step 2 should still exist with its original exploration instructions
        assert "### Step 2:" in template or "### Step 2 " in template
        assert "Glob" in template
        assert "Grep" in template

    # --- Agent types ---

    def test_template_dispatches_finder_agent(self):
        """Happy: Template dispatches a @finder agent for locating files and components."""
        template = self._load_template()
        lower = template.lower()
        assert "finder" in lower

    def test_template_dispatches_analyst_agent(self):
        """Happy: Template dispatches an @analyst agent for understanding code."""
        template = self._load_template()
        lower = template.lower()
        assert "analyst" in lower

    def test_template_dispatches_patterns_agent(self):
        """Happy: Template dispatches a @patterns agent for finding similar implementations."""
        template = self._load_template()
        lower = template.lower()
        assert "patterns" in lower or "pattern" in lower

    # --- Task tool dispatch ---

    def test_template_mentions_task_tool(self):
        """Happy: Template explicitly instructs use of the Task tool for subagent dispatch."""
        template = self._load_template()
        assert "Task tool" in template or "Task(" in template

    def test_template_instructs_single_message_dispatch(self):
        """Happy: Template instructs dispatching all agents in a single message for parallelism."""
        template = self._load_template()
        lower = template.lower()
        assert "single message" in lower or "single response" in lower or "one message" in lower

    # --- Conditional dispatch ---

    def test_template_has_conditional_scope_check(self):
        """Happy: Template conditionally dispatches subagents only for larger scopes."""
        template = self._load_template()
        lower = template.lower()
        # Should mention scope size condition
        assert ("multiple module" in lower or "large" in lower or "complex" in lower
                or "multiple file" in lower or "scope" in lower)
        # Should preserve Step 2 as fallback for small scopes
        assert "small" in lower or "simple" in lower or "single" in lower

    # --- Synchronization ---

    def test_template_instructs_wait_for_all(self):
        """Happy: Template instructs waiting for all subagents before proceeding."""
        template = self._load_template()
        lower = template.lower()
        assert "wait" in lower or "all" in lower
        assert "consolidat" in lower or "synthesiz" in lower or "combin" in lower

    # --- Subagent prompt content ---

    def test_template_includes_subagent_prompt_template(self):
        """Happy: Template includes embedded prompt templates for subagent dispatch."""
        template = self._load_template()
        lower = template.lower()
        # Each subagent should know what to look for
        assert "file" in lower and "search" in lower or "find" in lower

    def test_template_preserves_consolidation_into_task_context(self):
        """Happy: Subagent findings are consolidated into task_context.md (Step 3)."""
        template = self._load_template()
        assert "task_context.md" in template
        # Step 3 should still reference writing findings
        assert "Step 3" in template


class TestResearchPromptSubstitution:
    """Tests for research prompt variable substitution via Stage."""

    def test_substitution_replaces_all_variables(self):
        """Happy: All template variables are replaced when context is provided."""
        config = create_plan_pipeline()
        research_config = config.stages["research"]
        stage = Stage(config=research_config, runner=None)

        context = {
            "context_files": "- `scope.md`\n- `design.md`",
            "output_dir": "/tmp/plan_output",
        }
        prompt = stage.build_prompt(context)

        assert "{context_files}" not in prompt
        assert "{output_dir}" not in prompt
        # Substituted values should be present
        assert "scope.md" in prompt
        assert "/tmp/plan_output" in prompt

    def test_substitution_missing_variable_leaves_placeholder(self):
        """Failure: Missing context variables leave {placeholder} in output."""
        config = create_plan_pipeline()
        research_config = config.stages["research"]
        stage = Stage(config=research_config, runner=None)

        prompt = stage.build_prompt({})
        assert "{context_files}" in prompt
        assert "{output_dir}" in prompt
