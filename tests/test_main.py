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
    "source, destination, force, expected, fail_no_match",
    [
        ("test.txt", "new.txt", False, ["new.txt"], True),  # make single copy
        ("test.txt", "out", True, [os.path.join("out", "test.txt")], True),  # copy to new directory
        ("test.txt", "in/a.txt", True, [os.path.join("in", "a.txt")], True),  # overwrite
        ("test.txt", "out/a.txt", True, [os.path.join("out", "a.txt")], True),  # copy to new directory and rename
        ("in/nested/c.txt", "out", True, [os.path.join("out", "c.txt")], True),  # copy deeper nested file
        ("in/*", "out", True, [
            os.path.join("out", "a.txt"),
            os.path.join("out", "b.txt"),
            os.path.join("out", "nested")
        ], True),  # copy multiple files
        ("in/**/*.txt", "out", True, [
            os.path.join("out", "a.txt"),
            os.path.join("out", "b.txt"),
            os.path.join("out", "c.txt")
        ], True),  # copy multiple files
        ("in", "out", True, [os.path.join("out", "in")], True),  # copy directory
        ("asdasdasd", "out", True, [], False),  # copy non-existing
    ]
)
def test_copy_success(source: str,
                      destination: str,
                      force: bool,
                      expected: List[str],
                      fail_no_match: bool,
                      monkeypatch: MonkeyPatch,
                      mocker: MockerFixture) -> None:
    def __get_input(key: str, required: bool = False):
        if key == "source":
            return source
        elif key == "destination":
            return destination
        elif key == "fail-no-match":
            return fail_no_match
        elif key == "preserve-path":
            return False
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
    "source, destination, force, recursive, allow_outside, fail_no_match",
    [
        ("test.txt", "a.txt", False, False, False, True),
        ("test.txt", "..", True, True, False, True),
        ("z.txt", "out", True, True, False, True),
        ("a.txt", "in/a.txt", False, False, False, True),
        ("in", "out", True, False, False, True),
        ("in", "a.txt", True, True, False, True)
    ]
)
def test_copy_failure(source: str,
                      destination: str,
                      force: bool,
                      recursive: bool,
                      allow_outside: bool,
                      fail_no_match: bool,
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
        elif key == "fail-no-match":
            return fail_no_match

    mocker.patch('prepare_copy.main.get_input', side_effect=__get_input)
    old_cwd = os.getcwd()
    with tempfile.TemporaryDirectory() as tempdir:
        monkeypatch.chdir(tempdir)
        setup_temp(tempdir)
        with pytest.raises(SystemExit):
            main()
        # We need to do this otherwise it won't work on Windows......
        monkeypatch.chdir(old_cwd)


def test_preserve_path(monkeypatch: MonkeyPatch, mocker: MockerFixture):
    def __get_input(key: str, required: bool = False):
        if key == "source":
            return "in/nested/deeper/d.txt"
        elif key == "destination":
            return "out/nested"
        elif key == "force":
            return False
        elif key == "recursive":
            return False
        elif key == "allow-outside-working-directory":
            return False
        elif key == "fail-no-match":
            return False
        elif key == "preserve-path":
            return True

    mocker.patch('prepare_copy.main.get_input', side_effect=__get_input)
    spy = mocker.patch("prepare_copy.main.set_output")
    old_cwd = os.getcwd()
    with tempfile.TemporaryDirectory() as tempdir:
        monkeypatch.chdir(tempdir)
        setup_temp(tempdir)
        os.mkdir("in/nested/deeper")
        os.mkdir("out/nested")
        Path(os.path.join("in/nested/deeper", "d.txt")).touch()
        main()
        monkeypatch.chdir(old_cwd)
    spy.assert_called_once_with("copied", [os.path.join("out", "nested", "deeper", "d.txt")])