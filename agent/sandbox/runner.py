import os
import signal
import subprocess
import time
from dataclasses import dataclass

from sandbox.paths import PathEscapeError, is_inside

TRUNCATION_MARK = "\n[... output truncated ...]"


@dataclass
class ExecutionResult:
    exit_code: int
    stdout: str
    stderr: str
    duration: float
    timed_out: bool
    truncated: bool


def _cap(text, limit):
    if len(text) <= limit:
        return text, False
    return text[:limit] + TRUNCATION_MARK, True


def run_command(command, cwd, timeout=60, max_output=20000, env_extra=None,
                root=None, redact=None):
    if not isinstance(command, (list, tuple)) or not command:
        raise ValueError("command must be a non-empty list of arguments (no shell strings)")
    if not os.path.isdir(cwd):
        raise ValueError(f"working folder does not exist: {cwd}")
    if root is not None and not is_inside(root, cwd):
        raise PathEscapeError(f"working folder is outside the project root: {cwd}")

    env = {"PATH": os.environ.get("PATH", ""), "LANG": "C.UTF-8", "HOME": os.path.realpath(cwd)}
    env.update(env_extra or {})

    start = time.monotonic()
    timed_out = False
    try:
        proc = subprocess.Popen(
            list(command), cwd=cwd, env=env, stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
            errors="replace", start_new_session=True)
    except FileNotFoundError:
        return ExecutionResult(127, "", f"command not found: {command[0]}", 0.0, False, False)
    try:
        out, err = proc.communicate(timeout=timeout)
        code = proc.returncode
    except subprocess.TimeoutExpired:
        timed_out = True
        try:
            os.killpg(proc.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        out, err = proc.communicate()
        code = 124
    duration = time.monotonic() - start
    out, t1 = _cap(out or "", max_output)
    err, t2 = _cap(err or "", max_output)
    if redact:
        out, err = redact(out), redact(err)
    return ExecutionResult(code, out, err, duration, timed_out, t1 or t2)
