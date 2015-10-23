# coding=utf-8
"""Api package contains classes for easier resource managament in pulp-smash.
"""

from __future__ import unicode_literals

import requests
import time
from requests.exceptions import HTTPError
from pulp_smash.config import get_config

# List of all paths here
CREATE_REPOSITORY_PATH = "/pulp/api/v2/repositories/"
REPOSITORY_PATH = "/pulp/api/v2/repositories/{}/"  # .format(<repo_id>)
REPOSITORY_PATH = "/pulp/api/v2/repositories/{}/"  # .format(<repo_id>)
POLL_TASK_PATH = "/pulp/api/v2/tasks/{}/"  # .format(<task_id>)

# Repository related variables
REPORT_KEYS = {
    'result',
    'error',
    'spawned_tasks',
}
ERROR_KEYS = {
    '_href',
    'error',
    'error_message',
    'exception',
    'http_status',
    'traceback',
}

# Task related variables
TASK_ERROR_STATES = {
    'error',
    'timed out',
}
TASK_FINISHED_STATES = {
    'finished',
}


class Repository:
    """Provides interface for easy manipulation with pulp repositories.
    `Create repo` accepts following kwarg parameters:
        .. _Create repo:
            http://pulp.readthedocs.org/en/latest/dev-guide/integration/rest-api/repo/cud.html

    Each time request to server is made, ie. by calling :meth:`create_repo`
    method, response is saved to last_response variable.

    :param id: System wide unique repository identifier.
    :param display_name: User-friendly name for the repository
    :param description: User-friendly text describing the repository’s contents
    :param notes: Key-value pairs to programmatically tag the repository
    :param importer_type_id: Type id of importer being associated with the
        repository
    :param importer_config: Configuration the repository will use to drive
        the behavior of the importer
    :distributors: Array of objects containing values of distributor_type_id,
        repo_plugin_config, auto_publish, and distributor_id
        """
    def __init__(self, **kwargs):
        self.data_keys = kwargs
        self.cfg = get_config()

    def create_repo(self, **kwargs):
        """Create repository on pulp server.
        After calling this method, <repo>.last_response.raise_for_status()
        should be called in order to make sure that repo was correctly created.
        :param kwargs: Additional arguments which will be passed to request,
        same as in :class:`Repository` constructor.
        """
        self.data_keys.update(kwargs)
        self.last_response = requests.post(
            self.cfg.base_url + CREATE_REPOSITORY_PATH,
            json=self.data_keys,
            **self.cfg.get_requests_kwargs()
        )

    def delete_repo(self):
        """Delete repository from pulp server.
        After calling this method, <repo>.last_response.raise_for_status()
        Taks.wait_for_tasks(<repo>.last_response) should be called in order
        to make sure repo was correctly deleted.
        """
        self.last_response = requests.delete(
            self.cfg.base_url +
            REPOSITORY_PATH.format(self.data_keys['id']),
            **self.cfg.get_requests_kwargs()
        )

    def get_repo(self):
        """Get information about repository on server.
        After calling this method, <repo>.last_response.raise_for_status()
        should be called in order to make sure that call was succesfull.
        """
        self.last_response = requests.get(
            self.cfg.base_url + REPOSITORY_PATH.format(self.data_keys['id']),
            **self.cfg.get_requests_kwargs()
        )

    def update_repo(self,
                    delta,
                    importer_config=None,
                    distributor_configs=None):
        """Update repository with keys from kwargs.
        After calling this method, <repo>.last_response.raise_for_status()
        and Task.wait_for_tasks(<repo>.last_response)
        should be called in order to make sure repo was correctly updated.
        :param delta: Object containing keys with values that should
            be updated on the repository.
        :param importer_config: Object containing keys with values that should
            be updated on the repository’s importer config.
        :param distributor_configs: object containing keys that
            are distributor ids
        """
        my_delta = {'delta': delta}
        if importer_config is not None:
            my_delta.update({'importer_config': importer_config})
        if distributor_configs is not None:
            my_delta.update({'distributor_configs': distributor_configs})
        self.last_response = requests.put(
            self.cfg.base_url + REPOSITORY_PATH.format(self.data_keys['id']),
            json=my_delta,
            **self.cfg.get_requests_kwargs()
        )


class Task:
    """Handles tasks related operations. So far only waiting for given tasks
    to immediate finish is implemented.
    """
    cfg = get_config()

    def __init__(cls):
        pass

    @classmethod
    def _wait_for_task(self, task, timeout, frequency):
        """Wait for single task to finish its execution on server.
        :param task: Dictionary containtin task_id and path to task
            on pulp server.
        :param timeout: Timeout in seconds for each task to complete.
        :param frequency: Task polling frequency in seconds.
        """
        # TODO: Handle other task states
        task_timeout = time.time() + timeout
        while time.time() <= task_timeout:
            time.sleep(frequency)
            response = requests.get(
                Task.cfg.base_url +
                POLL_TASK_PATH.format(task["task_id"]),
                **Task.cfg.get_requests_kwargs()
            )
            try:
                response.raise_for_status()
            except HTTPError:
                break
            # task finished with error
            if response.json()["state"] in TASK_ERROR_STATES:
                raise Exception("Error occured while polling task: ",
                                response.text)
            # task finished properly
            if response.json()["state"] in TASK_FINISHED_STATES:
                break
        # task probably timed out
        else:
            raise Exception("Timeout occured while waiting for task: ",
                            response.text)

    @classmethod
    def wait_for_tasks(self, report, timeout=120, frequency=0.5):
        """Wait for all populated tasks to finish.
        :param report: Call response -- report -- with list of populated tasks.
        :param timeout: Timeout in seconds for each task to complete.
        :param frequency: Task polling frequency in seconds.
        """
        if not all(key in report.json().keys() for key in REPORT_KEYS):
            raise Exception("Missing key in Call report: ", report.text)
        for task in report.json()["spawned_tasks"]:
            self._wait_for_task(task, timeout, frequency)
