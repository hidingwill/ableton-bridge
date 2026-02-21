import hashlib
import os
import re
from pathlib import Path
from datetime import datetime
from typing import NoReturn
from rapidfuzz import fuzz


class ElevenLabsMcpError(Exception):
    pass


def make_error(error_text: str) -> NoReturn:
    raise ElevenLabsMcpError(error_text)


def is_file_writeable(path: Path) -> bool:
    """Check if path is writable. Walks up to the first existing ancestor."""
    check = path
    while not check.exists():
        parent = check.parent
        if parent == check:
            # Reached filesystem root without finding existing dir
            return False
        check = parent
    return os.access(check, os.W_OK)


def make_output_file(
    tool: str, text: str, output_path: Path, extension: str, full_id: bool = False
) -> Path:
    # Use a hash of the input text instead of raw content to avoid
    # leaking user-provided text into filenames and logs.
    digest = hashlib.sha256(text.encode("utf-8", errors="replace")).hexdigest()
    id_safe = digest if full_id else digest[:8]
    if not id_safe:
        id_safe = "unnamed"
    output_file_name = "{0}_{1}_{2}.{3}".format(
        tool, id_safe, datetime.now().strftime('%Y%m%d_%H%M%S'), extension)
    output_file = (output_path / output_file_name).resolve()
    # Ensure the file stays within the output directory
    try:
        output_file.relative_to(output_path.resolve())
    except ValueError as err:
        raise ElevenLabsMcpError(
            "Generated filename escapes output directory") from err
    return output_file


def make_output_path(
    output_directory: str | None, base_path: str | None = None
) -> Path:
    if output_directory is None:
        output_path = Path.home() / "Desktop"
    elif not os.path.isabs(output_directory) and base_path:
        resolved_base = Path(os.path.expanduser(base_path)).resolve()
        output_path = (resolved_base / Path(output_directory)).resolve()
        try:
            output_path.relative_to(resolved_base)
        except ValueError:
            make_error(
                "Output directory ({0}) escapes base path".format(
                    output_directory))
    else:
        output_path = Path(os.path.expanduser(output_directory)).resolve()
        # Enforce containment when base_path is configured
        if base_path:
            resolved_base = Path(os.path.expanduser(base_path)).resolve()
            try:
                output_path.relative_to(resolved_base)
            except ValueError:
                make_error(
                    "Output directory ({0}) is outside the configured base path".format(
                        output_directory))
    output_path.mkdir(parents=True, exist_ok=True)
    if not is_file_writeable(output_path):
        make_error("Directory ({0}) is not writeable".format(output_directory or "~/Desktop"))
    return output_path


def find_similar_filenames(
    target_file: str, directory: Path, threshold: int = 70
) -> list[tuple[Path, int]]:
    """
    Find files with names similar to the target file using fuzzy matching.

    Args:
        target_file (str): The reference filename to compare against
        directory (Path): Directory to search in (pathlib.Path)
        threshold (int): Similarity threshold (0 to 100, where 100 is identical)

    Returns:
        list[tuple[Path, int]]: List of (file_path, similarity_score) tuples
    """
    target_filename = os.path.basename(target_file)
    similar_files = []
    for root, _, files in os.walk(directory):
        for filename in files:
            if (
                filename == target_filename
                and os.path.join(root, filename) == target_file
            ):
                continue
            similarity = fuzz.token_sort_ratio(target_filename, filename)

            if similarity >= threshold:
                file_path = Path(root) / filename
                similar_files.append((file_path, similarity))

    similar_files.sort(key=lambda x: x[1], reverse=True)

    return similar_files


def try_find_similar_files(
    filename: str, directory: Path, take_n: int = 5
) -> list[Path]:
    similar_files = find_similar_filenames(filename, directory)
    if not similar_files:
        return []

    filtered_files = []

    for path, _ in similar_files[:take_n]:
        if check_audio_file(path):
            filtered_files.append(path)

    return filtered_files


def check_audio_file(path: Path) -> bool:
    audio_extensions = {
        ".wav",
        ".mp3",
        ".m4a",
        ".aac",
        ".ogg",
        ".flac",
        ".mp4",
        ".avi",
        ".mov",
        ".wmv",
    }
    return path.suffix.lower() in audio_extensions


def handle_input_file(file_path: str, audio_content_check: bool = True) -> Path:
    base_path = os.environ.get("ELEVENLABS_MCP_BASE_PATH")
    if not os.path.isabs(file_path) and not base_path:
        make_error(
            "File path must be an absolute path if ELEVENLABS_MCP_BASE_PATH is not set"
        )
    if not os.path.isabs(file_path) and base_path:
        resolved_base = Path(os.path.expanduser(base_path)).resolve()
        path = (resolved_base / Path(file_path)).resolve()
        try:
            path.relative_to(resolved_base)
        except ValueError:
            make_error(
                "File path ({0}) escapes base path".format(file_path))
    else:
        path = Path(file_path).resolve()
        # Validate absolute paths against base_path when configured
        if base_path:
            resolved_base = Path(os.path.expanduser(base_path)).resolve()
            try:
                path.relative_to(resolved_base)
            except ValueError:
                make_error(
                    "File path ({0}) is outside the configured base path".format(
                        path.name))
    if not path.exists() and path.parent.exists():
        parent_directory = path.parent
        similar_files = try_find_similar_files(path.name, parent_directory)
        similar_files_formatted = ",".join([f.name for f in similar_files])
        if similar_files:
            make_error(
                f"File ({path.name}) does not exist. Did you mean any of these files: {similar_files_formatted}?"
            )
        make_error(f"File ({path.name}) does not exist")
    elif not path.exists():
        make_error(f"File ({path.name}) does not exist")
    elif not path.is_file():
        make_error(f"File ({path.name}) is not a file")

    if audio_content_check and not check_audio_file(path):
        make_error(f"File ({path.name}) is not an audio or video file")
    return path
