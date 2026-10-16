import subprocess
from pathlib import Path

from app.git.models import ChangeType, FileChange


class GitError(Exception):
    pass


class GitProvider:
    @staticmethod
    def is_git_repository(repo_path: str) -> bool:
        """Check if repo_path is inside a git repository."""
        try:
            result = subprocess.run(
                ["git", "rev-parse", "--is-inside-work-tree"],
                cwd=repo_path,
                capture_output=True,
                text=True,
            )
            return result.returncode == 0 and result.stdout.strip() == "true"
        except FileNotFoundError:
            raise GitError("Git executable not found")
        except Exception:
            return False

    @staticmethod
    def ref_exists(repo_path: str, ref: str) -> bool:
        """Check if a git ref (commit, branch, tag, etc.) exists in the repository."""
        if not ref or not ref.strip():
            return False
        clean_ref = ref.strip()
        try:
            result = subprocess.run(
                ["git", "rev-parse", "--verify", "--quiet", f"{clean_ref}^{{commit}}"],
                cwd=repo_path,
                capture_output=True,
                text=True,
            )
            if result.returncode == 0:
                return True
            result = subprocess.run(
                ["git", "rev-parse", "--verify", "--quiet", clean_ref],
                cwd=repo_path,
                capture_output=True,
                text=True,
            )
            return result.returncode == 0
        except FileNotFoundError:
            raise GitError("Git executable not found")
        except Exception:
            return False

    @staticmethod
    def get_current_commit(repo_path: str) -> str:
        """Get the current commit hash (HEAD)."""
        try:
            result = subprocess.run(
                ["git", "rev-parse", "HEAD"],
                cwd=repo_path,
                capture_output=True,
                text=True,
                check=True,
            )
            return result.stdout.strip()
        except subprocess.CalledProcessError as e:
            raise GitError(f"Failed to get current commit: {e.stderr}")
        except FileNotFoundError:
            raise GitError("Git executable not found")

    @staticmethod
    def get_changed_files(
        repo_path: str, base_ref: str, target_ref: str | None = None
    ) -> list[FileChange]:
        """
        Get list of changed files between base_ref and target_ref.
        If target_ref is None, compares base_ref against the working tree.
        """
        args = ["git", "diff", "--name-status", base_ref]
        if target_ref is not None:
            args.append(target_ref)

        try:
            result = subprocess.run(
                args,
                cwd=repo_path,
                capture_output=True,
                text=True,
                check=True,
            )
        except subprocess.CalledProcessError as e:
            raise GitError(f"Failed to diff git references: {e.stderr}")
        except FileNotFoundError:
            raise GitError("Git executable not found")

        changes: list[FileChange] = []
        for line in result.stdout.splitlines():
            line = line.strip()
            if not line:
                continue

            parts = line.split("\t")
            if len(parts) == 1:
                # sometimes separated by spaces instead of tabs depending on git config? 
                # git diff --name-status uses tabs, but if spaces:
                parts = line.split()

            status = parts[0]
            
            if status.startswith("M"):
                changes.append(FileChange(ChangeType.MODIFIED, parts[1]))
            elif status.startswith("A"):
                changes.append(FileChange(ChangeType.ADDED, parts[1]))
            elif status.startswith("D"):
                changes.append(FileChange(ChangeType.DELETED, parts[1]))
            elif status.startswith("R"):
                if len(parts) >= 3:
                    changes.append(FileChange(ChangeType.RENAMED, parts[2], old_path=parts[1]))
                else:
                    # fallback if R is malformed
                    changes.append(FileChange(ChangeType.RENAMED, parts[-1]))

        # Optionally, get untracked files if targeting working tree
        if target_ref is None:
            try:
                untracked_result = subprocess.run(
                    ["git", "ls-files", "--others", "--exclude-standard"],
                    cwd=repo_path,
                    capture_output=True,
                    text=True,
                    check=True,
                )
                for line in untracked_result.stdout.splitlines():
                    line = line.strip()
                    if line:
                        changes.append(FileChange(ChangeType.ADDED, line))
            except Exception:
                pass  # ignore untracked errors

        return changes
