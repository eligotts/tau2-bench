from typing import Callable

import pytest

from tau2.environment.environment import Environment
from tau2.registry import registry


@pytest.fixture
def domain_name():
    return "mock"


@pytest.fixture
def get_environment() -> Callable[[], Environment]:
    return registry.get_env_constructor("mock")
