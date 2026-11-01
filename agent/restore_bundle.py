"""
Restore a bundle file (agent-core-b1b-bundle.txt) into a project folder.

Usage (from the agent/ folder):
    python3 restore_bundle.py agent-core-b1b-bundle.txt .

Safe by design:
- Every file it overwrites is first copied to backup_before_restore_<timestamp>/.
- It never touches scripts/, config.json or requirements.txt (they are not in the bundle).
- Stale test files that are not in the bundle are MOVED to the backup folder,
  so they cannot break the test run.
- Other stale .py files are only reported, never deleted.
"""
import os
import re
import shutil
import sys
import time

PACKAGES = ("core", "agents", "guardrails", "security", "profiles", "tests")


def main(bundle, target):
    text = open(bundle, encoding="utf-8").read()
    parts = re.split(r"^===== FILE: (.+?) =====\n", text, flags=re.M)
    files = [(parts[i].strip(), parts[i + 1]) for i in range(1, len(parts), 2)]
    if not files:
        sys.exit("No files found in the bundle. Is this the right file?")

    backup = os.path.join(target, "backup_before_restore_" + time.strftime("%Y%m%d_%H%M%S"))
    in_bundle = set()

    def save_backup(path):
        rel = os.path.relpath(path, target)
        dest = os.path.join(backup, rel)
        os.makedirs(os.path.dirname(dest), exist_ok=True)
        shutil.copy2(path, dest)

    for rel, body in files:
        if os.path.isabs(rel) or ".." in rel.replace("\\", "/").split("/"):
            sys.exit(f"Unsafe path in bundle: {rel}")
        if body.endswith("\n\n"):
            body = body[:-1]
        dest = os.path.join(target, rel)
        if os.path.exists(dest):
            save_backup(dest)
        os.makedirs(os.path.dirname(dest) or target, exist_ok=True)
        with open(dest, "w", encoding="utf-8") as f:
            f.write(body)
        in_bundle.add(os.path.normpath(rel))

    for pkg in PACKAGES:
        os.makedirs(os.path.join(target, pkg), exist_ok=True)
        init = os.path.join(target, pkg, "__init__.py")
        if not os.path.exists(init):
            open(init, "w").close()
        in_bundle.add(os.path.normpath(os.path.join(pkg, "__init__.py")))

    moved, stale = [], []
    for pkg in PACKAGES:
        folder = os.path.join(target, pkg)
        for name in sorted(os.listdir(folder)):
            rel = os.path.normpath(os.path.join(pkg, name))
            path = os.path.join(target, rel)
            if name == "__pycache__":
                shutil.rmtree(path, ignore_errors=True)
            elif name.endswith(".py") and rel not in in_bundle:
                if pkg == "tests" and name.startswith("test_"):
                    save_backup(path)
                    os.remove(path)
                    moved.append(rel)
                else:
                    stale.append(rel)

    print(f"Restored {len(files)} files into {os.path.abspath(target)}")
    if os.path.isdir(backup):
        print(f"Backup of replaced files: {backup}")
    for rel in moved:
        print(f"MOVED stale test to backup: {rel}")
    for rel in stale:
        print(f"NOTE stale file left in place (not in bundle): {rel}")
    print("Next: python3 -m unittest discover -s tests -t . 2>&1 | tail -8")


if __name__ == "__main__":
    if len(sys.argv) != 3:
        sys.exit("Usage: python3 restore_bundle.py <bundle.txt> <target-folder>")
    main(sys.argv[1], sys.argv[2])