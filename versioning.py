"""Версионирование бота: VERSION + CHANGELOG + тег в GitLab.

Схема: MAJOR.MINOR.PATCH (SemVer).
  PATCH  — исправления багов;
  MINOR  — новые возможности;
  MAJOR  — ломающие изменения.

Правило проекта: версия поднимается с каждым новым днём работы
и при каждом важном обновлении. Тег в GitLab — вида v0.3.0.
"""
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
VERSION_FILE = BASE_DIR / "VERSION"


def current_version() -> str:
    try:
        return VERSION_FILE.read_text(encoding="utf-8").strip()
    except FileNotFoundError:
        return "0.0.0"


def bump(part: str = "patch") -> str:
    """Поднимает версию. part: major | minor | patch."""
    major, minor, patch = (int(x) for x in current_version().split("."))
    if part == "major":
        major, minor, patch = major + 1, 0, 0
    elif part == "minor":
        minor, patch = minor + 1, 0
    else:
        patch += 1
    new = "{}.{}.{}".format(major, minor, patch)
    VERSION_FILE.write_text(new + "\n", encoding="utf-8")
    return new
