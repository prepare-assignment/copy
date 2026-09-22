import json
from pathlib import Path
from typing import Any, Dict, List

import pytest
import yaml
from pytest_mock import MockerFixture

import prepare_copy.main as copy_main
from prepare_copy.main import main, __preserve_path

TASK = Path(__file__).parent.parent / "task.yml"


def set_inputs(monkeypatch: pytest.MonkeyPatch, **inputs: Any) -> None:
    """
    Pass the inputs like prepare-assignment core does: as JSON in PREPARE_<NAME> environment variables,
    including the defaults from task.yml. Use the names from task.yml, with '_' for '-'.
    """
    definition: Dict[str, Any] = yaml.safe_load(TASK.read_text(encoding="utf-8"))["inputs"]
    values = {name: spec["default"] for name, spec in definition.items() if "default" in spec}
    values.update({key.replace("_", "-"): value for key, value in inputs.items()})
    for key, value in values.items():
        if value is not None:
            monkeypatch.setenv(f"PREPARE_{key.upper()}", json.dumps(value))


@pytest.fixture
def project(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """
    project
    |- test.txt
    |- out
    |- in
    |  |- a.txt
    |  |- b.txt
    |  |- nested
    |     |- c.txt
    """
    (tmp_path / "out").mkdir()
    (tmp_path / "in" / "nested").mkdir(parents=True)
    for file in ["test.txt", "in/a.txt", "in/b.txt", "in/nested/c.txt"]:
        (tmp_path / file).write_text(file)
    monkeypatch.chdir(tmp_path)
    return tmp_path


def copied(set_output: Any) -> List[str]:
    """The copied output, as is: paths use '/' on every platform (they are used in other steps)"""
    set_output.assert_called_once()
    return list(set_output.call_args.args[1])


@pytest.mark.parametrize("source, destination, expected", [
    ("test.txt", "new.txt", {"new.txt": "test.txt"}),  # copy and rename
    ("test.txt", "out", {"out/test.txt": "test.txt"}),  # into a directory
    ("test.txt", "out/renamed.txt", {"out/renamed.txt": "test.txt"}),  # into a directory with a new name
    ("in/nested/c.txt", "out", {"out/c.txt": "in/nested/c.txt"}),  # a nested file
    ("in/*.txt", "out", {"out/a.txt": "in/a.txt", "out/b.txt": "in/b.txt"}),  # several files
    ("in/**/*.txt", "out", {"out/a.txt": "in/a.txt", "out/b.txt": "in/b.txt",
                            "out/c.txt": "in/nested/c.txt"}),  # recursive glob
    ("in/{a,b}.txt", "out", {"out/a.txt": "in/a.txt", "out/b.txt": "in/b.txt"}),  # braces
])
def test_copy_files(source: str, destination: str, expected: Dict[str, str], project: Path,
                    monkeypatch: pytest.MonkeyPatch, mocker: MockerFixture) -> None:
    """Every file contains its own path, so the content shows which file was copied"""
    set_inputs(monkeypatch, source=source, destination=destination)
    set_output = mocker.patch("prepare_copy.main.set_output")
    main()
    assert copied(set_output) == list(expected)
    for copy, original in expected.items():
        assert (project / copy).read_text() == original


def test_copy_directory(project: Path, monkeypatch: pytest.MonkeyPatch, mocker: MockerFixture) -> None:
    set_inputs(monkeypatch, source="in", destination="out")
    set_output = mocker.patch("prepare_copy.main.set_output")
    main()
    assert copied(set_output) == ["out/in"]
    assert (project / "out" / "in" / "nested" / "c.txt").read_text() == "in/nested/c.txt"


def test_overwrite_with_force(project: Path, monkeypatch: pytest.MonkeyPatch, mocker: MockerFixture) -> None:
    (project / "out" / "test.txt").write_text("old")
    set_inputs(monkeypatch, source="test.txt", destination="out", force=True)
    mocker.patch("prepare_copy.main.set_output")
    main()
    assert (project / "out" / "test.txt").read_text() == "test.txt"


def test_existing_file_without_force_fails(project: Path, monkeypatch: pytest.MonkeyPatch,
                                           mocker: MockerFixture) -> None:
    (project / "out" / "test.txt").write_text("old")
    set_inputs(monkeypatch, source="test.txt", destination="out", force=False)
    failed = mocker.spy(copy_main, "set_failed")
    with pytest.raises(SystemExit):
        main()
    assert failed.call_args.args[0] == "'out/test.txt' already exists, use 'force' to overwrite"
    assert (project / "out" / "test.txt").read_text() == "old"


def test_no_match_fails(project: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    set_inputs(monkeypatch, source="missing.txt", destination="out")
    with pytest.raises(SystemExit):
        main()


def test_no_match_allowed(project: Path, monkeypatch: pytest.MonkeyPatch, mocker: MockerFixture) -> None:
    set_inputs(monkeypatch, source="missing.txt", destination="out", fail_no_match=False)
    set_output = mocker.patch("prepare_copy.main.set_output")
    warning = mocker.patch("prepare_copy.main.warning")
    main()
    warning.assert_called_once()
    assert copied(set_output) == []


def test_directory_without_recursive_fails(project: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    set_inputs(monkeypatch, source="in", destination="out", recursive=False)
    with pytest.raises(SystemExit):
        main()
    assert not (project / "out" / "in").exists()


def test_directory_to_file_fails(project: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    set_inputs(monkeypatch, source="in", destination="test.txt")
    with pytest.raises(SystemExit):
        main()


@pytest.mark.parametrize("destination", ["..", "../outside", "ABSOLUTE"])
def test_destination_outside_working_directory_fails(destination: str, project: Path,
                                                     monkeypatch: pytest.MonkeyPatch, mocker: MockerFixture) -> None:
    """The error was pathlib's raw 'is not in the subpath of' message"""
    if destination == "ABSOLUTE":
        destination = (project.parent / "outside").as_posix()
    set_inputs(monkeypatch, source="test.txt", destination=destination)
    failed = mocker.spy(copy_main, "set_failed")
    with pytest.raises(SystemExit):
        main()
    assert failed.call_args.args[0] == (f"The destination '{destination}' is outside the working directory, set "
                                        f"'allow-outside-working-directory' to allow this")


def test_preserve_path(project: Path, monkeypatch: pytest.MonkeyPatch, mocker: MockerFixture) -> None:
    """Issue #1: the directory structure after the common part (c/d/e) is preserved"""
    (project / "a" / "b" / "c" / "d" / "e" / "f" / "g").mkdir(parents=True)
    (project / "a" / "b" / "c" / "d" / "e" / "f" / "g" / "test.txt").write_text("x")
    set_inputs(monkeypatch, source="a/b/c/d/e/f/g/test.txt", destination="x/c/d/e", preserve_path=True)
    set_output = mocker.patch("prepare_copy.main.set_output")
    main()
    assert copied(set_output) == ["x/c/d/e/f/g/test.txt"]
    assert (project / "x" / "c" / "d" / "e" / "f" / "g" / "test.txt").read_text() == "x"


def test_common_path() -> None:
    source = "/home/solution/src/main/resources/io/github/fontysvenlo/classloader/SecretClass.class.enc"
    destination = "/home/out/assignment/src/main/resources"

    common = __preserve_path(source, destination)

    assert common == str(Path("io/github/fontysvenlo/classloader/SecretClass.class.enc"))


@pytest.mark.parametrize("destination", ["new.txt", "test.txt", "missing/dir"])
def test_several_files_to_non_directory_fails(destination: str, project: Path, monkeypatch: pytest.MonkeyPatch,
                                              mocker: MockerFixture) -> None:
    """Every file was copied to the same path, only the last one survived (cp fails: target is not a directory)"""
    set_inputs(monkeypatch, source="in/*.txt", destination=destination)
    failed = mocker.spy(copy_main, "set_failed")
    with pytest.raises(SystemExit):
        main()
    assert (f"'in/*.txt' matches 2 files, the destination '{destination}' must be an existing directory"
            in failed.call_args.args[0])
    assert (project / "test.txt").read_text() == "test.txt"
    assert not (project / "new.txt").exists()


@pytest.fixture
def existing(project: Path) -> Path:
    """out/in already exists with an older copy of a.txt and a file that isn't in the source"""
    (project / "out" / "in").mkdir()
    (project / "out" / "in" / "a.txt").write_text("old")
    (project / "out" / "in" / "extra.txt").write_text("extra")
    return project


def test_directory_without_force_does_not_overwrite(existing: Path, monkeypatch: pytest.MonkeyPatch,
                                                    mocker: MockerFixture) -> None:
    """force was ignored for directories: existing files were overwritten"""
    set_inputs(monkeypatch, source="in", destination="out", force=False)
    failed = mocker.spy(copy_main, "set_failed")
    with pytest.raises(SystemExit):
        main()
    assert "'out/in/a.txt' already exists, use 'force' to overwrite" in failed.call_args.args[0].replace("\\", "/")
    assert (existing / "out" / "in" / "a.txt").read_text() == "old"
    # Nothing is copied, not even the files that don't exist yet
    assert not (existing / "out" / "in" / "b.txt").exists()


def test_directory_without_force_merges_new_files(project: Path, monkeypatch: pytest.MonkeyPatch,
                                                  mocker: MockerFixture) -> None:
    (project / "out" / "in").mkdir()
    (project / "out" / "in" / "extra.txt").write_text("extra")
    set_inputs(monkeypatch, source="in", destination="out", force=False)
    mocker.patch("prepare_copy.main.set_output")
    main()
    assert (project / "out" / "in" / "nested" / "c.txt").read_text() == "in/nested/c.txt"
    assert (project / "out" / "in" / "extra.txt").read_text() == "extra"


def test_directory_with_force_overwrites(existing: Path, monkeypatch: pytest.MonkeyPatch,
                                         mocker: MockerFixture) -> None:
    set_inputs(monkeypatch, source="in", destination="out", force=True)
    mocker.patch("prepare_copy.main.set_output")
    main()
    assert (existing / "out" / "in" / "a.txt").read_text() == "in/a.txt"
    assert (existing / "out" / "in" / "extra.txt").read_text() == "extra"


def test_nothing_copied_when_a_file_exists_without_force(project: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """The existing file was only noticed after the files before it were copied"""
    (project / "out" / "b.txt").write_text("old")
    set_inputs(monkeypatch, source="in/*.txt", destination="out", force=False)
    with pytest.raises(SystemExit):
        main()
    assert not (project / "out" / "a.txt").exists()
    assert (project / "out" / "b.txt").read_text() == "old"


def test_nothing_copied_when_a_directory_file_exists_without_force(project: Path,
                                                                    monkeypatch: pytest.MonkeyPatch) -> None:
    (project / "out" / "nested").mkdir()
    (project / "out" / "nested" / "c.txt").write_text("old")
    set_inputs(monkeypatch, source="in/*", destination="out", force=False)
    with pytest.raises(SystemExit):
        main()
    assert not (project / "out" / "a.txt").exists()
    assert (project / "out" / "nested" / "c.txt").read_text() == "old"


def test_nothing_copied_when_a_directory_is_not_allowed(project: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    set_inputs(monkeypatch, source="in/*", destination="out", recursive=False)
    with pytest.raises(SystemExit):
        main()
    assert not (project / "out" / "a.txt").exists()


def test_preserve_path_with_repeated_directory_name(project: Path, monkeypatch: pytest.MonkeyPatch,
                                                    mocker: MockerFixture) -> None:
    """'main' is both in src/main and images/main: the structure after src/main was lost"""
    (project / "solution" / "src" / "main" / "resources" / "images" / "main").mkdir(parents=True)
    (project / "solution" / "src" / "main" / "resources" / "images" / "main" / "logo.png").write_text("logo")
    set_inputs(monkeypatch, source="solution/src/main/resources/images/main/logo.png",
               destination="out/assignment/src/main", preserve_path=True)
    set_output = mocker.patch("prepare_copy.main.set_output")
    main()
    assert copied(set_output) == ["out/assignment/src/main/resources/images/main/logo.png"]
    assert (project / "out/assignment/src/main/resources/images/main/logo.png").read_text() == "logo"


@pytest.mark.parametrize("source, destination, expected", [
    # The longest common sequence wins, not the last occurrence of the name
    ("/p/solution/src/main/resources/images/main/logo.png", "/p/out/assignment/src/main",
     "resources/images/main/logo.png"),
    # Issue #1
    ("/p/a/b/c/d/e/f/g/test.txt", "/p/x/c/d/e", "f/g/test.txt"),
    # Only the deepest directory name is common
    ("/p/in/nested/c.txt", "/p/out/nested", "c.txt"),
    # Equally long: the last occurrence, as before
    ("/p/a/x/b/x/c.txt", "/p/out/x", "c.txt"),
])
def test_preserve_path_common_part(source: str, destination: str, expected: str) -> None:
    assert Path(__preserve_path(source, destination)).as_posix() == expected


@pytest.mark.parametrize("destination", ["new-dir", "out/new-dir", "deeper/new/dir"])
def test_directory_to_new_destination(destination: str, project: Path, monkeypatch: pytest.MonkeyPatch,
                                      mocker: MockerFixture) -> None:
    """Like cp -r: a directory copied to a path that doesn't exist yet is copied as that path"""
    set_inputs(monkeypatch, source="in", destination=destination)
    set_output = mocker.patch("prepare_copy.main.set_output")
    main()
    assert copied(set_output) == [destination]
    assert (project / destination / "a.txt").read_text() == "in/a.txt"
    assert (project / destination / "nested" / "c.txt").read_text() == "in/nested/c.txt"
    assert not (project / destination / "in").exists()
