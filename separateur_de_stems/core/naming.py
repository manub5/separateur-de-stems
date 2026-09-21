from pathlib import Path


FORBIDDEN_CHARACTERS = '<>:"/\\|?*'
SANITIZE_TRANSLATION = str.maketrans({character: "_" for character in FORBIDDEN_CHARACTERS})


def sanitize(name: str) -> str:
    return name.translate(SANITIZE_TRANSLATION)


def unique_path(path: str) -> str:
    candidate = Path(path)
    if not candidate.exists():
        return str(candidate)

    index = 1
    while True:
        suffixed_candidate = candidate.with_name(
            f"{candidate.stem}_{index}{candidate.suffix}"
        )
        if not suffixed_candidate.exists():
            return str(suffixed_candidate)
        index += 1


def stem_filename(source_path: str, stem: str, ext: str, output_dir: str) -> str:
    source_name = sanitize(Path(source_path).stem)
    stem_name = sanitize(stem)
    normalized_ext = ext.lstrip(".")
    path = Path(output_dir) / f"{source_name}_{stem_name}.{normalized_ext}"
    return unique_path(str(path))
