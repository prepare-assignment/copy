import os
import tempfile
from pathlib import Path
from typing import List

import pytest
from _pytest.monkeypatch import MonkeyPatch
from pytest_mock import MockerFixture

from prepare_copy.main import main


def setup_temp(path: str) -> None:
    """
    Set up a temporary directory structure for testing
    path
    |- test.txt
    |- a.txt
    |- out
    |   |-
    |- in
    |  |- a.txt
    |  |- b.txt
    |  | nested
    |  |  | - c.txt
    :param path: path to the temporary root dir
    :return: None
    """
    out_dir = os.path.join(path, "out")
    os.mkdir(out_dir)
    Path(os.path.join(path, "test.txt")).touch()
    Path(os.path.join(path, "a.txt")).touch()
    in_dir = os.path.join(path, "in")
    os.mkdir(in_dir)
    Path(os.path.join(in_dir, "a.txt")).touch()
    Path(os.path.join(in_dir, "b.txt")).touch()
    nested_dir = os.path.join(in_dir, "nested")
    os.mkdir(nested_dir)
    Path(os.path.join(nested_dir, "c.txt")).touch()


@pytest.mark.parametrize(
    "source, destination, force, expected",
    [
        ("test.txt", "new.txt", False, ["new.txt"]),  # make single copy
        ("test.txt", "out", True, [os.path.join("out", "test.txt")]),  # copy to new directory
        ("test.txt", "in/a.txt", True, [os.path.join("in", "a.txt")]),  # overwrite
        ("test.txt", "out/a.txt", True, [os.path.join("out", "a.txt")]),  # copy to new directory and rename
        ("in/nested/c.txt", "out", True, [os.path.join("out", "c.txt")]),  # copy deeper nested file
        ("in/*", "out", True, [
            os.path.join("out", "a.txt"),
            os.path.join("out", "b.txt"),
            os.path.join("out/nested")
        ]),  # copy multiple files
        ("in/**/*.txt", "out", True, [
            os.path.join("out", "a.txt"),
            os.path.join("out", "b.txt"),
            os.path.join("out", "c.txt")
        ]),  # copy multiple files
        ("in", "out", True, [os.path.join("out", "in")]),  # copy directory
    ]
)
def test_copy_success(source: str,
                      destination: str,
                      force: bool,
                      expected: List[str],
                      monkeypatch: MonkeyPatch,
                      mocker: MockerFixture) -> None:
    def __get_input(key: str, required: bool = False):
        if key == "source":
            return source
        elif key == "destination":
            return destination
        else:
            return force

    mocker.patch('prepare_copy.main.get_input', side_effect=__get_input)
    spy = mocker.patch("prepare_copy.main.set_output")
    old_cwd = os.getcwd()
    with tempfile.TemporaryDirectory() as tempdir:
        monkeypatch.chdir(tempdir)
        setup_temp(tempdir)
        main()
        # We need to do this otherwise it won't work on Windows......
        monkeypatch.chdir(old_cwd)
    spy.assert_called_once_with("copied", expected)


@pytest.mark.parametrize(
    "source, destination, force, recursive, allow_outside",
    [
        ("test.txt", "a.txt", False, False, False),
        ("test.txt", "..", True, True, False),
        ("z.txt", "out", True, True, False),
        ("a.txt", "in/a.txt", False, False, False),
        ("in", "out", True, False, False),
        ("in", "a.txt", True, True, False)
    ]
)
def test_copy_failure(source: str,
                      destination: str,
                      force: bool,
                      recursive: bool,
                      allow_outside: bool,
                      monkeypatch: MonkeyPatch,
                      mocker: MockerFixture) -> None:

    def __get_input(key: str, required: bool = False):
        if key == "source":
            return source
        elif key == "destination":
            return destination
        elif key == "force":
            return force
        elif key == "recursive":
            return recursive
        elif key == "allow-outside-working-directory":
            return allow_outside

    mocker.patch('prepare_copy.main.get_input', side_effect=__get_input)
    old_cwd = os.getcwd()
    with tempfile.TemporaryDirectory() as tempdir:
        monkeypatch.chdir(tempdir)
        setup_temp(tempdir)
        with pytest.raises(SystemExit):
            main()
        # We need to do this otherwise it won't work on Windows......
        monkeypatch.chdir(old_cwd)
