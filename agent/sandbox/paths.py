import os


class PathEscapeError(ValueError):
    pass


def resolve_inside(root, relative):
    root_real = os.path.realpath(root)
    if os.path.isabs(relative):
        raise PathEscapeError(f"absolute paths are not allowed: {relative}")
    target = os.path.realpath(os.path.join(root_real, relative))
    if os.path.commonpath([root_real, target]) != root_real:
        raise PathEscapeError(f"path escapes the project folder: {relative}")
    return target


def is_inside(root, path):
    root_real = os.path.realpath(root)
    target = os.path.realpath(path)
    return os.path.commonpath([root_real, target]) == root_real
