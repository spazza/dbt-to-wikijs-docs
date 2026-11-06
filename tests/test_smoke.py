import subprocess
import sys

import dbt_to_wikijs_docs


def test_exposes_main():
    assert callable(dbt_to_wikijs_docs.main)


def test_cli_help():
    result = subprocess.run(
        [sys.executable, "-m", "dbt_to_wikijs_docs", "--help"], capture_output=True, text=True, check=True
    )
    assert "--dry-run" in result.stdout
