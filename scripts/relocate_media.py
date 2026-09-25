"""Copy Homebrew media dependencies into the app and rewrite Mach-O paths."""

import argparse
import hashlib
import json
import os
import shutil
import subprocess
from pathlib import Path

from separateur_de_stems.core.bundle_manifest import PackagingError
from separateur_de_stems.core.packaging import parse_otool_dependencies, parse_otool_rpaths


def _run(command):
    try:
        return subprocess.run(
            [str(part) for part in command], check=True, capture_output=True, text=True
        ).stdout
    except (OSError, subprocess.CalledProcessError) as error:
        raise PackagingError(f"Cannot inspect or rewrite Mach-O dependencies: {error}") from error


def _formula_info(name):
    return json.loads(_run(["brew", "info", "--json=v2", name]))["formulae"][0]


def _hash_file(path):
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def relocate_media(app, brew_root, *, manifest_path, inspect=_run, rewrite=_run, formula_info=_formula_info):
    """Walk every Homebrew dependency of ffmpeg and ffprobe; fail on unknown paths."""
    app = Path(app)
    root = Path(brew_root).resolve()
    tools = app / "Contents" / "Frameworks" / "ffmpeg"
    if not tools.is_dir():
        raise PackagingError(f"Bundled media tools are absent: {tools}")
    manifest = Path(manifest_path)
    entries = json.loads(manifest.read_text(encoding="utf-8"))
    copied = {}
    pending = [(tools / name, ()) for name in ("ffmpeg", "ffprobe")]
    visited = set()
    rewrites = {}

    def resolve_dependency(reference, source, runpaths):
        if reference.startswith(("/usr/lib/", "/System/Library/")):
            return None
        if reference.startswith("@loader_path/"):
            candidate = source.parent / reference.removeprefix("@loader_path/")
        elif reference.startswith("@rpath/"):
            candidates = [directory / reference.removeprefix("@rpath/") for directory in runpaths]
            candidate = next((candidate for candidate in candidates if candidate.is_file()), None)
            if candidate is None:
                raise PackagingError(f"Unresolved @rpath in Homebrew media tool: {reference}")
        elif reference.startswith("/"):
            candidate = Path(reference)
        else:
            raise PackagingError(f"Unexpected external dependency: {reference}")
        target = candidate.resolve()
        if target == source.resolve():
            return None
        if target.is_relative_to(app.resolve()):
            return None
        if not target.is_relative_to(root) or not target.is_file():
            raise PackagingError(f"external dependency outside Homebrew: {reference}")
        relative = target.relative_to(root)
        if len(relative.parts) < 4 or relative.parts[0] != "Cellar":
            raise PackagingError(f"Unrecognised Homebrew dependency: {reference}")
        return target, relative

    while pending:
        destination, inherited = pending.pop()
        source = copied.get(destination, destination)
        own_rpaths = []
        raw_rpaths = parse_otool_rpaths(inspect(["otool", "-l", source]))
        for entry in raw_rpaths:
            if entry.startswith("@loader_path/"):
                own_rpaths.append((source.parent / entry.removeprefix("@loader_path/")).resolve())
            elif entry.startswith("/"):
                own_rpaths.append(Path(entry).resolve())
            else:
                raise PackagingError(f"Unsupported Homebrew runpath: {entry}")
        runpaths = tuple(dict.fromkeys((*own_rpaths, *inherited)))
        if (destination, runpaths) in visited:
            continue
        visited.add((destination, runpaths))
        if "arm64" not in inspect(["file", "-b", source]):
            raise PackagingError(f"Non-arm64 media dependency: {source}")
        dependencies = parse_otool_dependencies(inspect(["otool", "-L", source]))
        install_id = None
        if destination in copied:
            id_lines = inspect(["otool", "-D", source]).splitlines()
            if len(id_lines) > 1:
                install_id = id_lines[1].strip()
        for reference in dependencies:
            if reference == install_id:
                continue
            resolved = resolve_dependency(reference, source, runpaths)
            if resolved is None:
                continue
            origin, relative = resolved
            bundled = tools / "lib" / relative.relative_to("Cellar")
            if bundled not in copied:
                bundled.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(origin, bundled)
                copied[bundled] = origin
            pending.append((bundled, runpaths))
            rewritten = "@loader_path/" + os.path.relpath(bundled, destination.parent)
            previous = rewrites.get((destination, reference))
            if previous is not None and previous != rewritten:
                raise PackagingError(f"Ambiguous Homebrew runpath: {reference}")
            if previous == rewritten:
                continue
            rewrites[destination, reference] = rewritten
            rewrite(["install_name_tool", "-change", reference, rewritten, destination])
        if destination in copied:
            rewrite(["install_name_tool", "-id", "@loader_path/" + destination.name, destination])
        for entry, expanded in zip(raw_rpaths, own_rpaths):
            if expanded.is_relative_to(root):
                rewrite(["install_name_tool", "-delete_rpath", entry, destination])

    libraries = []
    for destination, origin in sorted(copied.items()):
        relative = origin.relative_to(root)
        formula = relative.parts[1]
        version = relative.parts[2]
        data = formula_info(formula)
        source_url = data["urls"]["stable"]["url"]
        licence = data["license"]
        if not all(isinstance(value, str) and value for value in (source_url, licence, version)):
            raise PackagingError(f"Missing provenance for {origin}")
        libraries.append({
            "path": destination.relative_to(tools).as_posix(),
            "source": source_url,
            "version": version,
            "licence": licence,
            "licence_status": "not-distributable",
            "architecture": "arm64",
            "size": destination.stat().st_size,
            "sha256": _hash_file(destination),
        })
    entries["libraries"] = libraries
    for entry in entries["binaries"]:
        entry["sha256"] = _hash_file(tools / entry["name"])
    manifest.write_text(json.dumps(entries, indent=2) + "\n", encoding="utf-8")
    return libraries


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("app", type=Path)
    parser.add_argument("--manifest", type=Path, default=Path("packaging/redistributed-binaries.json"))
    args = parser.parse_args()
    try:
        tools = args.app / "Contents" / "Frameworks" / "ffmpeg"
        bundled_manifest = tools / "redistributed-binaries.json"
        shutil.copy2(args.manifest, bundled_manifest)
        relocate_media(args.app, Path(_run(["brew", "--prefix"]).strip()), manifest_path=bundled_manifest)
    except (PackagingError, OSError, ValueError, KeyError) as error:
        parser.exit(1, f"Media relocation failed: {error}\n")


if __name__ == "__main__":
    main()
