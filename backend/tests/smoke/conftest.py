import os

import pytest


def pytest_addoption(parser: pytest.Parser) -> None:
    parser.addoption(
        "--base-url",
        action="store",
        default=None,
        help="Base URL for E2E smoke tests (e.g. http://localhost:8000)",
    )


@pytest.fixture(scope="session")
def base_url(request: pytest.FixtureRequest) -> str:
    url = request.config.getoption("--base-url") or os.environ.get("BASE_URL")
    if not url:
        pytest.skip("Smoke tests require --base-url or BASE_URL")
    return url.rstrip("/")
