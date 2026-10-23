"""Mark the slow, CadQuery-heavy reference-solid sweeps so CI can run `-m "not slow"` as a fast job."""
import pytest

SLOW_MODULES = {"test_eval_tasks.py", "test_eval_tasks_dfm.py"}  # build every reference solid
SLOW_TESTS = {"test_no_errors_on_reference_solids"}  # tests/test_dfm_rules.py


def pytest_collection_modifyitems(items):
    for item in items:
        if item.path.name in SLOW_MODULES or getattr(item, "originalname", item.name) in SLOW_TESTS:
            item.add_marker(pytest.mark.slow)
