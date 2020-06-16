from unittest import TestCase
from time import sleep

from pulpcore.client.pulpcore import ApiClient, TasksApi

from pulp_smash.api import _get_sleep_time
from pulp_smash.config import get_config


cfg = get_config()
SLEEP_TIME = _get_sleep_time(cfg)
configuration = cfg.get_bindings_config()
pulpcore_client = ApiClient(configuration)
tasks = TasksApi(pulpcore_client)


class PulpTestCase(TestCase):
    """Pulp customized test case."""

    def doCleanups(self):
        """
        Execute all cleanup functions and waits the deletion tasks.

        Normally called for you after tearDown.
        """
        output = super().doCleanups()
        running_tasks = tasks.list(state="running", name__contains="delete")
        while running_tasks.count:
            sleep(SLEEP_TIME)
            running_tasks = tasks.list(
                state="running", name__contains="delete"
            )
        return output


class PulpTaskError(Exception):
    """Exception to describe task errors."""

    def __init__(self, task):
        """Provide task info to exception."""
        description = task.error["description"]
        super().__init__(self, f"Pulp task failed ({description})")
        self.task = task


def monitor_task(task_href):
    """Polls the Task API until the task is in a completed state.

    Prints the task details and a success or failure message. Exits on failure.

    Args:
        task_href(str): The href of the task to monitor

    Returns:
        list[str]: List of hrefs that identify resource created by the task

    """
    completed = ["completed", "failed", "canceled"]
    task = tasks.read(task_href)
    while task.state not in completed:
        sleep(SLEEP_TIME)
        task = tasks.read(task_href)

    if task.state == "completed":
        return task.created_resources

    raise PulpTaskError(task=task)
