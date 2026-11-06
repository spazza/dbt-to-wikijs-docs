"""Tests of the command line."""

import subprocess
import sys
from pathlib import Path

import pytest

from dbt_to_wikijs_docs import main


def test_module_entry_point() -> None:
    """`python -m dbt_to_wikijs_docs` runs the command line."""
    result = subprocess.run(
        [sys.executable, "-m", "dbt_to_wikijs_docs", "--help"],
        capture_output=True,
        text=True,
        check=True,
    )
    assert "--dry-run" in result.stdout


def test_dry_run(shop_project: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """--dry-run writes the pages locally; options override the config."""
    assert main(["--dry-run", "out", "--path-prefix", "docs"]) == 0

    assert (shop_project / "out" / "docs" / "fct_sales.md").exists()
    assert "Wrote 6 pages to out/docs" in capsys.readouterr().out


@pytest.mark.usefixtures("shop_project")
def test_publish_needs_credentials(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """Publishing without URL and key fails with a hint, not a traceback."""
    monkeypatch.delenv("WIKIJS_URL", raising=False)
    monkeypatch.delenv("WIKIJS_API_KEY", raising=False)

    assert main([]) == 1
    assert "Set WIKIJS_URL" in capsys.readouterr().err


def test_missing_artifacts(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Running before `dbt docs generate` explains what to do."""
    monkeypatch.chdir(tmp_path)

    assert main(["--dry-run", "out"]) == 1
    assert "run `dbt docs generate` first" in capsys.readouterr().err


def test_delete_all_excludes_dry_run(capsys: pytest.CaptureFixture[str]) -> None:
    """--delete-all and --dry-run are different modes."""
    with pytest.raises(SystemExit):
        main(["--delete-all", "--dry-run", "out"])
    assert "not allowed with argument" in capsys.readouterr().err
