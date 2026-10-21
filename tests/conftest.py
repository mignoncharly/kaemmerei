"""Pytest adapter for isolated, migrated test resources."""
import pytest
import os
from tests.support import environment_context


def pytest_addoption(parser):
    parser.addoption("--database", choices=("sqlite", "postgresql"), default="sqlite",
                     help="Create a NEW disposable database per application test")


def pytest_configure(config):
    config._previous_verification_backend = os.environ.get("VERIFICATION_DATABASE")
    os.environ["VERIFICATION_DATABASE"] = config.getoption("--database")


def pytest_unconfigure(config):
    previous = config._previous_verification_backend
    if previous is None:
        os.environ.pop("VERIFICATION_DATABASE", None)
    else:
        os.environ["VERIFICATION_DATABASE"] = previous


@pytest.fixture()
def environment(request):
    with environment_context(request.config.getoption("--database")) as value:
        yield value
