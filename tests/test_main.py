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
    set_output.assert_called_once()
    return [Path(path).as_posix() for path in set_output.call_args.args[1]]


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
    assert "already exists, use 'force' to overwrite" in failed.call_args.args[0]
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


def test_destination_outside_working_directory_fails(project: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    set_inputs(monkeypatch, source="test.txt", destination="..")
    with pytest.raises(SystemExit):
        main()


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
