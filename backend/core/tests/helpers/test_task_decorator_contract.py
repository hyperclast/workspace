from importlib import import_module

from django.apps import apps
from django.test import SimpleTestCase


def _collect_task_decorated_callables():
    """Yield (module, name, fn) for every @task-decorated function across
    `<app>.tasks` modules in ``INSTALLED_APPS``.

    The @task decorator from ``core.helpers.tasks`` attaches a callable
    ``.enqueue`` attribute to its wrapper. That attribute is the marker we
    use for discovery — any object missing it is filtered out.
    """
    seen_ids = set()
    for config in apps.get_app_configs():
        try:
            module = import_module(f"{config.name}.tasks")
        except ModuleNotFoundError:
            continue

        for attr_name in dir(module):
            if attr_name.startswith("_"):
                continue
            obj = getattr(module, attr_name)
            if not callable(obj):
                continue
            if not callable(getattr(obj, "enqueue", None)):
                continue

            obj_id = id(obj)
            if obj_id in seen_ids:
                continue
            seen_ids.add(obj_id)

            yield module, attr_name, obj


class TestTaskDecoratorContract(SimpleTestCase):
    """Project-wide regression guard for the @task decorator contract.

    Generalizes the per-task ``.delay``-vs-``.enqueue`` assertion: any future
    Celery-style call site (``.delay(...)``, ``.apply_async(...)``) is caught
    by a single test instead of needing a per-task sentinel.
    """

    def test_discovery_finds_task_decorated_functions(self):
        """Sanity-check that discovery isn't silently empty.

        Without this, the contract test below could pass vacuously if app
        discovery breaks or ``<app>.tasks`` modules are missed.
        """
        found = list(_collect_task_decorated_callables())
        self.assertGreater(
            len(found),
            0,
            "Expected to discover @task-decorated functions across INSTALLED_APPS",
        )

    def test_decorated_functions_expose_enqueue_only(self):
        offenders = []
        for module, name, fn in _collect_task_decorated_callables():
            qualname = f"{module.__name__}.{name}"
            if not callable(getattr(fn, "enqueue", None)):
                offenders.append(f"{qualname}: .enqueue is not callable")
            if hasattr(fn, "delay"):
                offenders.append(f"{qualname}: exposes .delay (Celery API)")
            if hasattr(fn, "apply_async"):
                offenders.append(f"{qualname}: exposes .apply_async (Celery API)")

        self.assertEqual(offenders, [], "\n".join(offenders))
