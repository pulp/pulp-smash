# coding=utf-8
"""Utility functions for Python API tests."""
import io
from urllib.parse import urljoin

from pulp_smash import api, constants, utils


def gen_repo():
    """Return a semi-random dict for use in creating a Python repository."""
    return {
        'id': utils.uuid4(),
        'importer_config': {},
        'importer_type_id': 'python_importer',
        'notes': {'_repo-type': 'PYTHON'},
    }


def gen_distributor():
    """Return a semi-random dict for use in creating a Python distributor."""
    return {
        'distributor_id': utils.uuid4(),
        'distributor_type_id': 'python_distributor',
    }


def upload_import_unit(cfg, unit, import_params, repo):
    """Upload a content unit to a Pulp server and import it into a repository.

    This procedure only works for some unit types, such as ``rpm`` or
    ``python_package``. Others, like ``package_group``, require an alternate
    procedure. The procedure encapsulated by this function is as follows:

    1. Create an upload request.
    2. Upload the content unit to Pulp, in small chunks.
    3. Import the uploaded content unit into a repository.
    4. Delete the upload request.

    The default set of parameters sent to Pulp during step 3 are::

        {'unit_key': {}, 'upload_id': '…'}

    The actual parameters required by Pulp depending on the circumstances, and
    the parameters sent to Pulp may be customized via the ``import_params``
    argument. For example, if uploading a Python content unit,
    ``import_params`` should be the following::

        {'unit_key': {'filename': '…'}, 'unit_type_id': 'python_package'}

    This would result in the following upload parameters being used::

        {
            'unit_key': {'filename': '…'},
            'unit_type_id': 'python_package',
            'upload_id': '…',
        }

    :param pulp_smash.config.ServerConfig cfg: Information about a Pulp host.
    :param unit: The unit to be uploaded and imported, as a binary blob.
    :param import_params: A dict of parameters to be merged into the default
        set of import parameters during step 3.
    :param repo: A dict of information about the target repository.
    :returns: The call report returned when importing the unit.
    """
    client = api.Client(cfg, api.json_handler)
    malloc = client.post(constants.CONTENT_UPLOAD_PATH)

    # 200,000 bytes ~= 200 kB
    chunk_size = 200000
    offset = 0
    with io.BytesIO(unit) as handle:
        while True:
            chunk = handle.read(chunk_size)
            if not chunk:  # if chunk == b'':
                break  # we've reached EOF
            path = urljoin(malloc['_href'], '{}/'.format(offset))
            client.put(path, data=chunk)
            offset += chunk_size

    path = urljoin(repo['_href'], 'actions/import_upload/')
    body = {'unit_key': {}, 'upload_id': malloc['upload_id']}
    body.update(import_params)
    call_report = client.post(path, body)
    client.delete(malloc['_href'])
    return call_report
