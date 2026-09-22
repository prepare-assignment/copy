import os.path
import shutil
from pathlib import Path
from typing import List, Optional, Tuple

from prepare_toolbox.core import set_failed, get_input, debug, set_output, warning
from prepare_toolbox.file import get_matching_files


def main() -> None:
    try:
        source: List[str] = get_input("source", required=True)
        destination: str = str(Path(get_input("destination", required=True)))
        recursive: bool = get_input("recursive")
        force: bool = get_input("force")
        allow_outside: bool = get_input("allow-outside-working-directory")
        fail_no_match: bool = get_input("fail-no-match")
        preserve_path: bool = get_input("preserve-path")
        include_hidden: bool = get_input("include-hidden")

        # The copied paths, always with '/' (also on Windows): they are used in other steps
        copied: List[str] = []
        if not allow_outside and not Path(os.path.abspath(destination)).is_relative_to(os.getcwd()):
            set_failed(f"The destination '{Path(destination).as_posix()}' is outside the working directory, set "
                       f"'allow-outside-working-directory' to allow this")
        files = get_matching_files(source, allow_outside_working_dir=allow_outside, include_hidden=bool(include_hidden))
        if len(files) == 0:
            if fail_no_match:
                set_failed(f"Glob '{source}' doesn't match any files")
            else:
                warning(f"Glob '{source}' doesn't match any files")
                set_output("copied", copied)
                return
        debug(f"Glob '{source}', matched {files}")
        if len(files) > 1 and not preserve_path and not os.path.isdir(destination):
            # Otherwise every file is copied to the same path and only the last one remains
            set_failed(f"'{source}' matches {len(files)} files, the destination '{Path(destination).as_posix()}' must "
                       f"be an existing directory")
        # First check everything, then copy: a failing task doesn't leave half of the files copied
        plan: List[Tuple[str, str]] = []
        for path in files:
            if os.path.isfile(path):
                target = __file_target(path, destination, preserve_path)
                if os.path.exists(target) and not force:
                    set_failed(f"'{Path(target).as_posix()}' already exists, use 'force' to overwrite")
            else:
                if not recursive:
                    set_failed(f"Path '{path}' is a directory, set 'recursive' to copy")
                if os.path.isdir(destination):
                    target = os.path.join(destination, os.path.basename(os.path.normpath(path)))
                elif not os.path.exists(destination):
                    # Like cp -r: the directory is copied as the new destination
                    target = destination
                else:
                    set_failed(f"Cannot copy a directory ('{path}') to '{destination}' as it is not a directory")
                if not force:
                    existing = __first_existing_file(path, target)
                    if existing is not None:
                        set_failed(f"'{Path(existing).as_posix()}' already exists, use 'force' to overwrite")
            plan.append((path, target))

        for path, target in plan:
            if os.path.isfile(path):
                if preserve_path:
                    # Also creates the destination if it doesn't exist yet
                    os.makedirs(os.path.dirname(target) or ".", exist_ok=True)
                actual_path = shutil.copy(path, target)
            else:
                debug(f"Copying directory '{path}' to '{target}'")
                actual_path = shutil.copytree(path, target, dirs_exist_ok=True)
            copied.append(Path(actual_path).as_posix())
        debug(f"copied paths are: {copied}")
        set_output("copied", copied)
    except Exception as e:
        set_failed(e)


def __file_target(path: str, destination: str, preserve_path: bool) -> str:
    """
    The path a file is copied to: into the destination directory (with preserve-path, the directory structure
    after the common part is kept), or to the destination itself if it isn't a directory
    """
    if preserve_path:
        common_part = __preserve_path(path, destination)
        return os.path.join(destination, common_part if common_part else os.path.basename(path))
    if os.path.isdir(destination):
        return os.path.join(destination, os.path.basename(path))
    return destination


def __first_existing_file(directory: str, target: str) -> Optional[str]:
    """
    The first file of the directory that already exists in the target directory (copying would overwrite it)
    """
    for root, _, names in os.walk(directory):
        for name in names:
            existing = os.path.join(target, os.path.relpath(os.path.join(root, name), directory))
            if os.path.exists(existing):
                return existing
    return None


def __preserve_path(source: str, destination: str) -> Optional[str]:
    """
    The part of the source path after the part it has in common with the destination, e.g. source
    'a/b/c/d/e/f/g/test.txt' and destination 'x/c/d/e' give 'f/g/test.txt'.

    Starting with the deepest directory of the destination, it looks for that directory name in the source. If the
    name occurs more than once, the occurrence with the longest common sequence of directories before it is used
    (e.g. 'src/main' rather than 'images/main' for the destination 'out/src/main'), for equally long sequences the
    last occurrence.
    """
    source_parts = [x for x in os.path.abspath(source).split(os.sep) if x != '']
    dest_parts = [x for x in os.path.abspath(destination).split(os.sep) if x != '']

    for dest_index in reversed(range(len(dest_parts))):
        end: Optional[int] = None
        longest = 0
        for source_index, part in enumerate(source_parts):
            if part != dest_parts[dest_index]:
                continue
            # The number of directories (up to this one) that source and destination have in common
            length = 0
            while (length <= min(source_index, dest_index)
                   and source_parts[source_index - length] == dest_parts[dest_index - length]):
                length += 1
            if length >= longest:
                end, longest = source_index + 1, length
        if end is not None:
            debug(f"Preserving path, common: {source_parts[:end]}, preserving: {source_parts[end:]}")
            return os.sep.join(source_parts[end:])
    return None


if __name__ == "__main__":
    main()
