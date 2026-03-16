import pytest

from tau2.run import (
    get_options,
    get_tasks,
    load_tasks,
)


def test_get_options():
    """Test that we can get available options from the registry"""
    options = get_options()
    assert options.domains is not None


def test_load_tasks():
    """Test that we can load tasks from the domain"""
    tasks = load_tasks("mock")
    assert len(tasks) > 0


def test_get_tasks():
    """Test that we can load tasks from the domain by id"""
    tasks = get_tasks("mock", task_ids=["create_task_1"])
    assert len(tasks) == 1
    assert tasks[0].id == "create_task_1"
