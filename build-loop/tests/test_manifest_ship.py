"""Tests for ship field support in BuildManifest and load_manifest()."""

import os
import tempfile

import pytest

from build_loop.manifest import BuildManifest, load_manifest


class TestBuildManifestShipField:
    """Tests for the ship field on BuildManifest dataclass."""

    def test_ship_defaults_to_false(self):
        """BuildManifest ship field defaults to False when not specified."""
        manifest = BuildManifest(tasks="/path/to/tasks.md")
        assert manifest.ship is False

    def test_ship_independent_of_validate(self):
        """Ship and validate are independent boolean fields — setting one does not affect the other."""
        manifest = BuildManifest(tasks="/path/to/tasks.md", validate=True, ship=True)
        assert manifest.ship is True
        assert manifest.validate is True

        manifest2 = BuildManifest(tasks="/path/to/tasks.md", validate=True)
        assert manifest2.ship is False
        assert manifest2.validate is True


class TestLoadManifestShip:
    """Tests for load_manifest() parsing of ship field from frontmatter."""

    def test_load_manifest_reads_ship_true(self, tmp_path):
        """load_manifest() reads ship: true from YAML frontmatter."""
        manifest_file = tmp_path / "ship.md"
        manifest_file.write_text(
            "---\n"
            "tasks: tasks.md\n"
            "ship: true\n"
            "---\n"
            "\n# Ship manifest\n"
        )
        # Create the tasks file so path resolution works
        (tmp_path / "tasks.md").write_text("# Tasks\n")

        manifest = load_manifest(str(manifest_file))
        assert manifest.ship is True

    def test_load_manifest_defaults_ship_false(self, tmp_path):
        """load_manifest() defaults ship to False when not in frontmatter."""
        manifest_file = tmp_path / "build.md"
        manifest_file.write_text(
            "---\n"
            "tasks: tasks.md\n"
            "validate: true\n"
            "---\n"
            "\n# Build manifest\n"
        )
        (tmp_path / "tasks.md").write_text("# Tasks\n")

        manifest = load_manifest(str(manifest_file))
        assert manifest.ship is False

    def test_load_manifest_ship_and_validate_both_parsed(self, tmp_path):
        """load_manifest() correctly parses both ship and validate when present."""
        manifest_file = tmp_path / "full.md"
        manifest_file.write_text(
            "---\n"
            "tasks: tasks.md\n"
            "ship: true\n"
            "validate: true\n"
            "---\n"
            "\n# Full manifest\n"
        )
        (tmp_path / "tasks.md").write_text("# Tasks\n")

        manifest = load_manifest(str(manifest_file))
        assert manifest.ship is True
        assert manifest.validate is True


class TestRunManifestShipRouting:
    """Tests for run_manifest() routing when manifest.ship is True."""

    def test_ship_manifest_routes_to_run_ship_pipeline(self, tmp_path, monkeypatch):
        """run_manifest() calls run_ship_pipeline when manifest.ship is True."""
        import argparse

        manifest_file = tmp_path / "ship.md"
        manifest_file.write_text(
            "---\n"
            "tasks: tasks.md\n"
            "ship: true\n"
            "---\n"
            "\n# Ship\n"
        )
        (tmp_path / "tasks.md").write_text("# Tasks\n")

        args = argparse.Namespace(
            agent="claude",
            validate=False,
            max_iterations=10,
            notify=False,
            no_notify=True,
        )

        # Track calls
        ship_calls = []

        def mock_run_ship_pipeline(context_files, max_iterations, agent="claude", resume_context=None):
            ship_calls.append({
                "context_files": context_files,
                "max_iterations": max_iterations,
                "agent": agent,
            })
            return (0, 3)

        monkeypatch.setattr("build_loop.cli.run_ship_pipeline", mock_run_ship_pipeline)
        monkeypatch.setattr("build_loop.cli.save_session", lambda *a, **kw: None)

        from build_loop.cli import run_manifest

        with pytest.raises(SystemExit) as exc_info:
            run_manifest(str(manifest_file), args)

        assert exc_info.value.code == 0
        assert len(ship_calls) == 1

    def test_ship_check_before_validate_check(self, tmp_path, monkeypatch):
        """When both ship and validate are True, ship routing takes priority."""
        import argparse

        manifest_file = tmp_path / "both.md"
        manifest_file.write_text(
            "---\n"
            "tasks: tasks.md\n"
            "ship: true\n"
            "validate: true\n"
            "---\n"
            "\n# Both flags\n"
        )
        (tmp_path / "tasks.md").write_text("# Tasks\n")

        args = argparse.Namespace(
            agent="claude",
            validate=False,
            max_iterations=10,
            notify=False,
            no_notify=True,
        )

        ship_calls = []
        validate_calls = []

        def mock_run_ship_pipeline(context_files, max_iterations, agent="claude", resume_context=None):
            ship_calls.append(True)
            return (0, 3)

        def mock_run_default_pipeline(tasks, context, max_iter, agent="claude"):
            validate_calls.append(True)
            return (0, 5)

        monkeypatch.setattr("build_loop.cli.run_ship_pipeline", mock_run_ship_pipeline)
        monkeypatch.setattr("build_loop.cli.run_default_pipeline", mock_run_default_pipeline)
        monkeypatch.setattr("build_loop.cli.save_session", lambda *a, **kw: None)

        from build_loop.cli import run_manifest

        with pytest.raises(SystemExit):
            run_manifest(str(manifest_file), args)

        assert len(ship_calls) == 1
        assert len(validate_calls) == 0
