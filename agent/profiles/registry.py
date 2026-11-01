from dataclasses import dataclass


@dataclass(frozen=True)
class LanguageProfile:
    name: str
    source_extensions: tuple
    config_files: tuple
    dependency_files: tuple
    test_tools: tuple
    lint_tools: tuple


PROFILES = {
    "python": LanguageProfile(
        name="python",
        source_extensions=(".py",),
        config_files=("pyproject.toml", "config.yml", "config.yaml"),
        dependency_files=("requirements.txt", "requirements-dev.txt"),
        test_tools=("pytest",),
        lint_tools=("ruff",),
    ),
    "java": LanguageProfile(
        name="java",
        source_extensions=(".java",),
        config_files=("pom.xml", "build.gradle", "build.gradle.kts",
                      "config.yml", "config.yaml"),
        dependency_files=("pom.xml", "build.gradle", "build.gradle.kts"),
        test_tools=("JUnit",),
        lint_tools=("checkstyle",),
    ),
}

# Language-agnostic project files (any profile may use them).
COMMON_PROJECT_FILES = (".md", ".txt", ".json", ".csv", ".yml", ".yaml", ".toml")


def get_profile(name: str) -> LanguageProfile:
    try:
        return PROFILES[name.lower()]
    except KeyError:
        raise ValueError(f"Unsupported language profile: {name}")


COMMANDS = {
    "python": {
        "test": ["python3", "-m", "unittest", "discover", "-s", "tests", "-t", "."],
        "lint": ["python3", "-m", "compileall", "-q", "."],
    },
    "java": {
        "test": ["mvn", "-q", "test"],
        "build": ["mvn", "-q", "compile"],
    },
}


def command_for(profile_name: str, action: str) -> list:
    profile = get_profile(profile_name)  # raises ValueError for unknown profiles
    try:
        return list(COMMANDS[profile.name][action])
    except KeyError:
        raise ValueError(f"Profile '{profile.name}' has no '{action}' command")
