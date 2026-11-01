import os

from sandbox.paths import resolve_inside
from sandbox.runner import run_command


class WorkspaceError(RuntimeError):
    pass


def path_allowed(path, allowed):
    """An allowed entry is an exact file path, or a folder prefix ending with '/'."""
    path = os.path.normpath(path).replace("\\", "/")
    for entry in allowed:
        entry = entry.replace("\\", "/")
        if entry.endswith("/"):
            if path.startswith(entry):
                return True
        elif path == os.path.normpath(entry).replace("\\", "/"):
            return True
    return False


class Workspace:
    """A project folder under git: one commit per Stage, easy to revert."""

    def __init__(self, root):
        self.root = os.path.abspath(root)

    def _git(self, *args):
        result = run_command(["git", *args], cwd=self.root, timeout=30)
        if result.exit_code != 0:
            raise WorkspaceError(f"git {' '.join(args)} failed: {result.stderr.strip()}")
        return result.stdout

    def init(self):
        os.makedirs(self.root, exist_ok=True)
        self._git("init", "-q")
        self._git("config", "user.name", "Lockstep")
        self._git("config", "user.email", "lockstep@localhost")
        self._git("config", "commit.gpgsign", "false")
        self._git("commit", "--allow-empty", "-q", "-m", "workspace initialized")

    def write_file(self, rel_path, content):
        target = resolve_inside(self.root, rel_path)
        os.makedirs(os.path.dirname(target), exist_ok=True)
        with open(target, "w", encoding="utf-8") as f:
            f.write(content)
        return target

    def read_file(self, rel_path):
        with open(resolve_inside(self.root, rel_path), encoding="utf-8") as f:
            return f.read()

    def changed_files(self):
        out = self._git("status", "--porcelain", "-uall")
        paths = set()
        for line in out.splitlines():
            if len(line) > 3:
                paths.add(line[3:].strip().strip('"').replace("\\", "/"))
        return sorted(paths)

    def check_scope(self, allowed):
        return sorted(p for p in self.changed_files() if not path_allowed(p, allowed))

    def diff(self):
        self._git("add", "-N", ".")
        return self._git("diff")

    def commit_stage(self, number, message=""):
        self._git("add", "-A")
        self._git("commit", "--allow-empty", "-q", "-m", f"Stage {number}: {message}".strip())
        self._git("tag", "-f", f"stage-{number}")
        return self._git("rev-parse", "HEAD").strip()

    def revert_to_last_commit(self):
        self._git("reset", "--hard", "-q", "HEAD")
        self._git("clean", "-fdq")
