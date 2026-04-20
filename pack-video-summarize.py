from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile, ZipInfo

root = Path("skills/video-summarize")
zip_path = root / "video-summarize.zip"
include_roots = ["SKILL.md", "assets", "references", "scripts", "skillhub.manifest.json", "tests"]

files: list[Path] = []
for name in include_roots:
    path = root / name
    if path.is_dir():
        files.extend(p for p in path.rglob("*") if p.is_file())
    else:
        files.append(path)

with ZipFile(zip_path, "w", ZIP_DEFLATED) as archive:
    for file_path in sorted(files, key=lambda p: p.as_posix()):
        if "__pycache__" in file_path.parts or file_path.suffix == ".pyc":
            continue
        arcname = file_path.relative_to(root).as_posix()
        info = ZipInfo(arcname)
        info.external_attr = (0o755 if arcname.endswith(".sh") else 0o644) << 16
        with file_path.open("rb") as handle:
            archive.writestr(info, handle.read())

with ZipFile(zip_path) as archive:
    names = archive.namelist()
    if any("\\" in name for name in names):
        raise SystemExit("zip contains backslash path separator")
    if any("__pycache__" in name or name.endswith(".pyc") for name in names):
        raise SystemExit("zip contains python cache")
    print("\n".join(names))
