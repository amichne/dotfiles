import subprocess

import pytest

from tests.test_main import SOURCE


@pytest.mark.parametrize(
    ("message", "expected"),
    [
        ("summary\n\ndetails\n", "summary\n\ndetails\n"),
        ("null\n", ""),
        ("", ""),
    ],
)
def test_generator_output_without_terminal(message: str, expected: str) -> None:
    result = subprocess.run(
        [str(SOURCE / ".local/bin/worktrunk-commit-message")],
        input=message,
        capture_output=True,
        text=True,
        start_new_session=True,
        check=False,
    )
    assert result.stdout == expected
    if expected:
        assert result.returncode == 0
    else:
        assert result.returncode != 0
        assert "no terminal" in result.stderr
