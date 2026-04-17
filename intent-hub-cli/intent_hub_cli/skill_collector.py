from __future__ import annotations

from pathlib import Path


def collect_skills(source_path: str) -> tuple[str, list[dict], list[str]]:
    root = Path(source_path).resolve()
    if not root.exists():
        raise ValueError(f"source path not found: {source_path}")
    if not root.is_dir():
        raise ValueError(f"source path must be a directory: {source_path}")

    skills: list[dict] = []
    errors: list[str] = []
    for skill_file in sorted(root.rglob("SKILL.md")):
        try:
            content = skill_file.read_text(encoding="utf-8")
        except OSError as exc:
            errors.append(f"{skill_file}: {exc}")
            continue
        if not content.strip():
            errors.append(f"{skill_file}: empty SKILL.md")
            continue
        skills.append(
            {
                "skill_name": skill_file.parent.name,
                "relative_path": skill_file.relative_to(root).as_posix(),
                "content": content,
            }
        )

    return str(root), skills, errors
