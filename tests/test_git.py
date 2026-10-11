import pytest
from unittest.mock import patch, MagicMock
from app.git.provider import GitProvider, GitError
from app.git.models import ChangeType

def test_get_current_commit():
    with patch("subprocess.run") as mock_run:
        mock_result = MagicMock()
        mock_result.stdout = "1234567890abcdef\n"
        mock_run.return_value = mock_result
        
        commit = GitProvider.get_current_commit("/fake/repo")
        assert commit == "1234567890abcdef"
        mock_run.assert_called_once()

def test_get_current_commit_error():
    with patch("subprocess.run") as mock_run:
        import subprocess
        mock_run.side_effect = subprocess.CalledProcessError(1, "git", stderr="fatal: not a git repo")
        
        with pytest.raises(GitError):
            GitProvider.get_current_commit("/fake/repo")

def test_get_changed_files_diff():
    with patch("subprocess.run") as mock_run:
        mock_result = MagicMock()
        mock_result.stdout = "M\tfile1.py\nA\tfile2.py\nD\tfile3.py\nR100\told.py\tnew.py\n"
        mock_run.return_value = mock_result
        
        changes = GitProvider.get_changed_files("/fake/repo", "HEAD~1", "HEAD")
        
        assert len(changes) == 4
        assert changes[0].change_type == ChangeType.MODIFIED
        assert changes[0].path == "file1.py"
        
        assert changes[1].change_type == ChangeType.ADDED
        assert changes[1].path == "file2.py"
        
        assert changes[2].change_type == ChangeType.DELETED
        assert changes[2].path == "file3.py"
        
        assert changes[3].change_type == ChangeType.RENAMED
        assert changes[3].path == "new.py"
        assert changes[3].old_path == "old.py"

def test_get_changed_files_working_tree():
    with patch("subprocess.run") as mock_run:
        mock_diff = MagicMock()
        mock_diff.stdout = "M\tfile1.py\n"
        
        mock_untracked = MagicMock()
        mock_untracked.stdout = "untracked.py\n"
        
        mock_run.side_effect = [mock_diff, mock_untracked]
        
        changes = GitProvider.get_changed_files("/fake/repo", "HEAD")
        
        assert len(changes) == 2
        assert changes[0].change_type == ChangeType.MODIFIED
        assert changes[0].path == "file1.py"
        assert changes[1].change_type == ChangeType.ADDED
        assert changes[1].path == "untracked.py"
