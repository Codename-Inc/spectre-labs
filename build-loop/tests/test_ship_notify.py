"""Tests for notify_ship_complete() notification function."""

from unittest.mock import patch

from build_loop.notify import notify_ship_complete


class TestNotifyShipCompleteSuccess:
    """Happy path: success=True produces correct message."""

    def test_success_message_includes_stages_and_time(self):
        """notify_ship_complete(success=True) sends correct message text."""
        with patch("build_loop.notify.notify", return_value=True) as mock_notify, \
             patch("build_loop.notify.get_git_branch", return_value="feature/ship"):
            result = notify_ship_complete(
                stages_completed=3,
                total_time="2m 30s",
                success=True,
            )
            assert result is True
            mock_notify.assert_called_once()
            call_kwargs = mock_notify.call_args[1]
            assert "Ship complete!" in call_kwargs["message"]
            assert "3 stages" in call_kwargs["message"]
            assert "2m 30s" in call_kwargs["message"]
            assert call_kwargs["title"] == "👻 | SPECTRE"

    def test_failure_message_includes_stages_and_time(self):
        """notify_ship_complete(success=False) sends failure message text."""
        with patch("build_loop.notify.notify", return_value=True) as mock_notify, \
             patch("build_loop.notify.get_git_branch", return_value="feature/ship"):
            result = notify_ship_complete(
                stages_completed=2,
                total_time="1m 15s",
                success=False,
            )
            assert result is True
            call_kwargs = mock_notify.call_args[1]
            assert "Ship failed" in call_kwargs["message"]
            assert "2 stages" in call_kwargs["message"]
            assert "1m 15s" in call_kwargs["message"]


class TestNotifyShipCompleteSubtitle:
    """Subtitle formatting with branch and project combinations."""

    def test_branch_and_project_in_subtitle(self):
        """Both project and branch appear in subtitle."""
        with patch("build_loop.notify.notify", return_value=True) as mock_notify, \
             patch("build_loop.notify.get_git_branch", return_value="feat/x"):
            notify_ship_complete(
                stages_completed=3,
                total_time="1m",
                project="my-app",
            )
            call_kwargs = mock_notify.call_args[1]
            assert call_kwargs["subtitle"] == "[my-app] feat/x"

    def test_no_branch_no_project_subtitle_is_none(self):
        """No branch and no project results in subtitle=None."""
        with patch("build_loop.notify.notify", return_value=True) as mock_notify, \
             patch("build_loop.notify.get_git_branch", return_value=None):
            notify_ship_complete(
                stages_completed=3,
                total_time="1m",
            )
            call_kwargs = mock_notify.call_args[1]
            assert call_kwargs["subtitle"] is None

    def test_branch_only_subtitle(self):
        """Branch without project is used as subtitle directly."""
        with patch("build_loop.notify.notify", return_value=True) as mock_notify, \
             patch("build_loop.notify.get_git_branch", return_value="main"):
            notify_ship_complete(
                stages_completed=3,
                total_time="1m",
            )
            call_kwargs = mock_notify.call_args[1]
            assert call_kwargs["subtitle"] == "main"

    def test_project_only_subtitle(self):
        """Project without branch uses project in brackets."""
        with patch("build_loop.notify.notify", return_value=True) as mock_notify, \
             patch("build_loop.notify.get_git_branch", return_value=None):
            notify_ship_complete(
                stages_completed=3,
                total_time="1m",
                project="my-app",
            )
            call_kwargs = mock_notify.call_args[1]
            assert call_kwargs["subtitle"] == "[my-app]"
