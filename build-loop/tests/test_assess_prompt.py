"""Tests for assess stage prompt template."""

from pathlib import Path

from build_loop.pipeline.loader import create_plan_pipeline
from build_loop.pipeline.stage import Stage


PROMPTS_DIR = Path(__file__).parent.parent / "src" / "build_loop" / "prompts" / "planning"


class TestAssessPromptContent:
    """Tests for assess.md prompt template content."""

    def _load_template(self) -> str:
        """Load the assess prompt template."""
        return (PROMPTS_DIR / "assess.md").read_text(encoding="utf-8")

    def test_template_contains_required_variables(self):
        """Happy: Template uses {task_context_path} and {context_files} variables."""
        template = self._load_template()
        assert "{task_context_path}" in template
        assert "{context_files}" in template

    def test_template_contains_complexity_scoring_dimensions(self):
        """Happy: Template describes scoring criteria for each dimension with enough detail."""
        template = self._load_template()
        lower = template.lower()
        # Must describe each dimension with enough context for autonomous scoring
        assert "files impacted" in lower or "files changed" in lower or "files affected" in lower
        assert "pattern match" in lower or "existing pattern" in lower
        assert "component" in lower
        assert "data model" in lower
        assert "integration point" in lower

    def test_template_contains_hard_stop_conditions(self):
        """Happy: Template lists specific hard-stop conditions that force COMPREHENSIVE."""
        template = self._load_template()
        lower = template.lower()
        # Must describe multiple hard-stop triggers — not just mention them
        hard_stop_terms = ["new service", "auth", "pii", "public api"]
        matches = sum(1 for term in hard_stop_terms if term in lower)
        assert matches >= 3, (
            f"Template mentions only {matches}/4 hard-stop conditions; "
            "needs at least 3 for autonomous assessment"
        )

    def test_template_defines_tier_criteria_with_thresholds(self):
        """Happy: Each tier has concrete criteria (file counts, pattern guidance)."""
        template = self._load_template()
        assert "LIGHT" in template
        assert "STANDARD" in template
        assert "COMPREHENSIVE" in template
        # Must have quantitative or qualitative thresholds for tiers
        assert "<5" in template or "fewer than 5" in template.lower() or "1-4" in template
        assert "5-15" in template or "5 to 15" in template.lower()
        assert ">15" in template or "more than 15" in template.lower() or "15+" in template

    def test_template_contains_json_completion_with_all_artifact_fields(self):
        """Happy: Template shows JSON output with status, depth, and tier fields."""
        template = self._load_template()
        assert '"status"' in template
        assert '"depth"' in template
        assert '"tier"' in template
        # depth should be lowercase tier name
        assert "light" in template  # lowercase depth value

    def test_template_instructs_architecture_design_for_comprehensive(self):
        """Happy: Template tells agent to write architecture section into task_context.md for COMPREHENSIVE."""
        template = self._load_template()
        lower = template.lower()
        # Must instruct updating task_context.md with architecture design
        assert "architecture" in lower
        assert "task_context" in lower
        # Must be specific about COMPREHENSIVE triggering this
        assert "comprehensive" in lower

    def test_template_has_step_by_step_instructions(self):
        """Happy: Template provides numbered steps for autonomous execution."""
        template = self._load_template()
        # Must have clear numbered steps (Step 1, Step 2, etc. or ### Step patterns)
        assert "Step 1" in template or "### Step" in template or "step 1" in template.lower()

    def test_template_has_sufficient_depth(self):
        """Failure: Template must be comprehensive enough for autonomous operation (>1000 chars)."""
        template = self._load_template()
        assert len(template) > 1000, (
            f"Assess prompt is too short ({len(template)} chars) for autonomous operation; "
            "needs detailed scoring criteria, hard-stop checks, and architecture instructions"
        )

    def test_template_has_guardrails(self):
        """Failure: Template must include guardrails to prevent scope creep."""
        template = self._load_template()
        assert "Do NOT" in template or "Do not" in template or "DO NOT" in template, (
            "Template should include guardrails to prevent the agent from doing work "
            "that belongs to later stages (planning, task breakdown, etc.)"
        )

    def test_template_specifies_output_dir_for_comprehensive(self):
        """Failure: Template must reference {output_dir} for writing architecture to task_context.md."""
        template = self._load_template()
        # COMPREHENSIVE tier updates task_context.md — needs output_dir or task_context_path
        assert "{output_dir}" in template or "{task_context_path}" in template


class TestAssessPromptSubstitution:
    """Tests for assess prompt variable substitution via Stage."""

    def test_substitution_replaces_all_variables(self):
        """Happy: All template variables are replaced when context is provided."""
        config = create_plan_pipeline()
        assess_config = config.stages["assess"]
        stage = Stage(config=assess_config, runner=None)

        context = {
            "task_context_path": "/tmp/plan_output/task_context.md",
            "context_files": "- `scope.md`\n- `design.md`",
            "output_dir": "/tmp/plan_output",
        }
        prompt = stage.build_prompt(context)

        assert "{task_context_path}" not in prompt
        assert "{context_files}" not in prompt
        # Substituted values should be present
        assert "/tmp/plan_output/task_context.md" in prompt
        assert "scope.md" in prompt

    def test_substitution_missing_variable_leaves_placeholder(self):
        """Failure: Missing context variables leave {placeholder} in output."""
        config = create_plan_pipeline()
        assess_config = config.stages["assess"]
        stage = Stage(config=assess_config, runner=None)

        prompt = stage.build_prompt({})
        assert "{task_context_path}" in prompt
        assert "{context_files}" in prompt
