#!/usr/bin/env python3
"""
Import a Codex/Petdex pet package into a Mythe Display theme.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
import tempfile
import zipfile
from pathlib import Path
from typing import Any


ROOT_DIR = Path(__file__).resolve().parents[1]
DEFAULT_THEME = ROOT_DIR / "public/themes/neon-dark/theme.json"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="导入 Codex/Petdex pet 包到主题资源包，并可自动启用。"
    )
    parser.add_argument(
        "package",
        help="pet 包目录、zip 文件，或 ~/.codex/pets/<id> / ~/.petdex/pets/<id> 中的 id。",
    )
    parser.add_argument(
        "--theme",
        default=str(DEFAULT_THEME),
        help="目标 theme.json，默认 public/themes/neon-dark/theme.json。",
    )
    parser.add_argument("--id", dest="pet_id", help="覆盖导入后的 pet id。")
    parser.add_argument(
        "--no-enable",
        action="store_true",
        help="只复制资源，不修改 theme.json 启用该 pet。",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="覆盖已存在的同名 pet 目录。",
    )
    return parser


def candidate_package_paths(value: str) -> list[Path]:
    raw = Path(os.path.expanduser(value))
    candidates = [raw]
    if not raw.is_absolute():
        candidates.extend(
            [
                Path.home() / ".codex/pets" / value,
                Path.home() / ".petdex/pets" / value,
                Path.home() / ".config/codex-pet/pets" / value,
            ]
        )
    return candidates


def resolve_package(value: str) -> Path:
    for candidate in candidate_package_paths(value):
        if candidate.exists():
            return candidate.resolve()
    searched = "\n".join(f"  - {path}" for path in candidate_package_paths(value))
    raise FileNotFoundError(f"找不到 pet 包：\n{searched}")


def load_pet_manifest(package_dir: Path) -> dict[str, Any]:
    manifest_path = package_dir / "pet.json"
    if not manifest_path.exists():
        raise FileNotFoundError(f"缺少 pet.json: {manifest_path}")
    with manifest_path.open("r", encoding="utf-8") as handle:
        manifest = json.load(handle)
    if not isinstance(manifest, dict):
        raise ValueError("pet.json 必须是 JSON object")
    return manifest


def find_spritesheet(package_dir: Path, manifest: dict[str, Any]) -> Path:
    configured = manifest.get("spritesheetPath") or manifest.get("spritesheet")
    candidates: list[Path] = []
    if configured:
        candidates.append(package_dir / str(configured))
    candidates.extend(
        package_dir / name
        for name in (
            "spritesheet.webp",
            "spritesheet.png",
            "spritesheet.gif",
            "spritesheet.svg",
        )
    )
    for candidate in candidates:
        if candidate.exists() and candidate.is_file():
            return candidate
    raise FileNotFoundError("找不到 spritesheet，期望 spritesheetPath、spritesheet.webp 或 spritesheet.png")


def safe_id(value: str) -> str:
    normalized = "".join(ch.lower() if ch.isalnum() else "-" for ch in value.strip())
    normalized = "-".join(part for part in normalized.split("-") if part)
    return normalized or "codex-pet"


def prepare_package(source: Path) -> tuple[Path, tempfile.TemporaryDirectory[str] | None]:
    if source.is_dir():
        return source, None
    if source.suffix.lower() != ".zip":
        raise ValueError("pet 包必须是目录或 .zip 文件")
    tmp = tempfile.TemporaryDirectory(prefix="mythe-display-pet-")
    target = Path(tmp.name)
    with zipfile.ZipFile(source) as archive:
        archive.extractall(target)
    if (target / "pet.json").exists():
        return target, tmp
    children = [child for child in target.iterdir() if child.is_dir()]
    if len(children) == 1 and (children[0] / "pet.json").exists():
        return children[0], tmp
    raise FileNotFoundError("zip 中没有找到 pet.json")


def copy_package(package_dir: Path, theme_path: Path, pet_id: str, force: bool) -> tuple[Path, Path]:
    theme_dir = theme_path.parent
    destination = theme_dir / "mascot" / "pets" / pet_id
    if destination.exists():
        if not force:
            raise FileExistsError(f"目标目录已存在: {destination}。可使用 --force 覆盖。")
        shutil.rmtree(destination)
    destination.mkdir(parents=True, exist_ok=True)

    manifest = load_pet_manifest(package_dir)
    spritesheet = find_spritesheet(package_dir, manifest)

    shutil.copy2(package_dir / "pet.json", destination / "pet.json")
    shutil.copy2(spritesheet, destination / spritesheet.name)

    for optional in ("preview.png", "preview.webp", "avatar.png", "README.md", "LICENSE", "LICENSE.md"):
        path = package_dir / optional
        if path.exists() and path.is_file():
            shutil.copy2(path, destination / optional)

    manifest_copy = load_pet_manifest(destination)
    manifest_copy["spritesheetPath"] = spritesheet.name
    with (destination / "pet.json").open("w", encoding="utf-8") as handle:
        json.dump(manifest_copy, handle, ensure_ascii=False, indent=2)
        handle.write("\n")

    return destination, destination / "pet.json"


def update_theme(theme_path: Path, manifest_path: Path) -> None:
    with theme_path.open("r", encoding="utf-8") as handle:
        theme = json.load(handle)
    theme_dir = theme_path.parent
    relative_manifest = manifest_path.relative_to(theme_dir).as_posix()
    mascot = theme.setdefault("mascot", {})
    codex_pet = mascot.setdefault("codexPet", {})
    codex_pet.update(
        {
            "enabled": True,
            "manifest": relative_manifest,
            "columns": int(codex_pet.get("columns", 8)),
            "rows": int(codex_pet.get("rows", 9)),
            "frameWidth": int(codex_pet.get("frameWidth", 192)),
            "frameHeight": int(codex_pet.get("frameHeight", 208)),
            "frames": int(codex_pet.get("frames", 8)),
            "fps": int(codex_pet.get("fps", 9)),
        }
    )
    with theme_path.open("w", encoding="utf-8") as handle:
        json.dump(theme, handle, ensure_ascii=False, indent=2)
        handle.write("\n")


def main() -> int:
    args = build_parser().parse_args()
    try:
        theme_path = Path(args.theme).expanduser().resolve()
        if not theme_path.exists():
            raise FileNotFoundError(f"找不到 theme.json: {theme_path}")

        source = resolve_package(args.package)
        package_dir, tmp = prepare_package(source)
        try:
            manifest = load_pet_manifest(package_dir)
            default_id = manifest.get("id") or manifest.get("name") or package_dir.name
            pet_id = safe_id(args.pet_id or str(default_id))
            destination, manifest_path = copy_package(package_dir, theme_path, pet_id, args.force)
            if not args.no_enable:
                update_theme(theme_path, manifest_path)
            print(f"已导入 pet: {pet_id}")
            print(f"目录: {destination}")
            if args.no_enable:
                print("未启用。可手动修改 theme.json 的 mascot.codexPet。")
            else:
                print(f"已启用: {manifest_path.relative_to(theme_path.parent).as_posix()}")
                print("刷新显示: mdp reload")
        finally:
            if tmp is not None:
                tmp.cleanup()
    except Exception as exc:  # noqa: BLE001
        print(f"导入 pet 失败: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
