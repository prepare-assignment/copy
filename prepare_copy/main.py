import os.path
import shutil
from pathlib import Path
from typing import List

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

        copied: List[str] = []
        if not allow_outside:
            # This will raise an error if the destination is outside the current working directory
            Path(os.path.abspath(destination)).relative_to(os.getcwd())
        files = get_matching_files(source, allow_outside_working_dir=allow_outside)
        if len(files) == 0:
            if fail_no_match:
                set_failed(f"Glob '{source}' doesn't match any files")
            else:
                warning(f"Glob '{source}' doesn't match any files")
                set_output("copied", copied)
                return
        debug(f"Glob '{source}', matched {files}")
        for path in files:
            if os.path.isfile(path):
                if os.path.isdir(destination):
                    new_path = os.path.join(destination, os.path.basename(path))
                else:
                    new_path = destination
                if os.path.exists(new_path) and not force:
                    set_failed(f"'{new_path}' already exists, use 'force' to overwrite")
                actual_path = shutil.copy(path, destination)
                copied.append(actual_path)
            else:
                if not recursive:
                    set_failed(f"Path '{path}' is a directory, set 'recursive' to copy")
                if not os.path.isdir(destination):
                    set_failed(f"Cannot copy a directory ('{path}') to '{destination}' as it is not a directory")
                parts = os.path.normpath(path).split(os.path.sep)
                if len(parts) > 1:
                    actual_path = shutil.copytree(path, os.path.join(destination, parts[-1]), dirs_exist_ok=True)
                else:
                    actual_path = shutil.copytree(path, os.path.join(destination, path), dirs_exist_ok=True)
                copied.append(actual_path)
        debug(f"copied paths are: {copied}")
        set_output("copied", copied)
    except Exception as e:
        set_failed(e)


if __name__ == "__main__":
    main()
