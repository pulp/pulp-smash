# coding=utf-8
# pylint: disable=super-on-old-class,wrong-import-order

"""Test rwr sanity of content generated by pulp."""

from __future__ import unicode_literals
import json
import requests

import pulp_smash.tests.rpm.content.xmlparser as xmlparser

from pulp_smash import api, utils
from pulp_smash.compat import urljoin
from pulp_smash.constants import (REPOSITORY_PATH, RPM_FEED_URL)

from pulp_smash.tests.rpm.api_v2.utils import (
    gen_distributor,
    gen_repo,
)
from pulp_smash.tests.rpm.utils import set_up_module as setUpModule  # noqa pylint:disable=unused-import
from pulp_smash.tests.rpm.content.utils import dict_cmp, open_gzipped

try:
    import StringIO
except ImportError:
    import io as StringIO


CONTENT = {'advisory1': 'content/dummy_adv1.json',
           'comps1': 'content/fedora_comps-small.json',
           'test_iso': 'content/test_iso.iso',
           'test_productid': 'content/test_productid'}


def get_repo_md_type_url(server_config, distributor, _type):
    """Return relative url of metadata type in repomd file."""
    client = api.Client(server_config)
    path = urljoin('/pulp/repos/', distributor['config']['relative_url'])
    path = urljoin(path, 'repodata/repomd.xml')
    metadata_f = client.get(path)
    parsed = parse_repomd(StringIO.StringIO(metadata_f.content))
    return parsed[_type]['location']


def get_metadata(server_config, distributor, metadata_url):
    """Download metadata from pulp repo."""
    client = api.Client(server_config)
    path = urljoin('/pulp/repos/', distributor['config']['relative_url'])
    path = urljoin(path, metadata_url)
    metadata_f = StringIO.StringIO(client.get(path).content)
    return metadata_f


def _cdata_to_text(obj):
    """convert .cdata attribute to text."""
    stack = [(None, '', obj)]
    while stack:
        parent, key, obj = stack.pop(0)
        if isinstance(obj, dict):
            if len(obj) == 1 and '.cdata' in obj:
                parent[key] = obj.values()[0]
            else:
                for key in obj.keys():
                    if key == '.cdata':
                        obj.pop(key)
                        continue
                    stack.insert(0, (obj, key, obj[key]))
        elif isinstance(obj, list):
            for index, _ in enumerate(obj):
                stack.insert(0, (obj, index, obj[index]))
    return obj


def force_list(obj, unexpected_type):
    """Return list for of obj."""
    if isinstance(obj, unexpected_type):
        return [obj]


def strbool_convert(value):
    """Convert string to bool."""
    if value.lower() == 'false':
        return False
    elif value.lower() == 'true':
        return True


def _updateinfo_transform(updateinfos):
    """transform parsed updateinfo into pulp acceptable format."""
    updates = updateinfos['updates']
    updates = force_list(updates['update'], dict)

    for update in updateinfos['updates']['update']:
        updateinfo = update

        reboot_suggested = updateinfo.get('reboot_suggested',
                                          {'.cdata': 'False'})
        strbool = strbool_convert(reboot_suggested)
        updateinfo['reboot_suggested'] = strbool
        if 'pushcount' in updateinfo:
            updateinfo['pushcount'] = int(updateinfo['pushcount']['.cdata'])
        updateinfo['updated'] = updateinfo['updated']['date']
        updateinfo['issued'] = updateinfo['issued']['date']
        updateinfo['references'] = updateinfo.get('references',
                                                  {}).get('reference', {})

        for reference in updateinfo['references']:
            if reference['id'] == '':
                reference['id'] = None
            if 'title' not in reference:
                reference['title'] = None

        collections = updateinfo['pkglist']
        collections = force_list(collections, dict)

        new_collections = []
        for collection in collections:
            new_collections.append(collection['collection'])

        updateinfo['pkglist'] = new_collections

        for collection in new_collections:
            if 'package' not in collection:
                break
            packages = collection.pop('package')
            collection['packages'] = packages
            for package in collection['packages']:
                _sums = []
                if 'sum' not in package:
                    continue
                package['sum'] = force_list(package['sum'], dict)
                for _sum in package['sum']:
                    _sums.append(_sum['type'])
                    _sums.append(_sum['.cdata'])
                package['sum'] = _sums


def parse_repomd(repomd_fp):
    """Parse repomd xml file and return result as dict."""
    parser = xmlparser.Parser()
    parsed = parser.parse_file(repomd_fp)
    repomd = {}
    for entry in parsed['repomd']['data']:
        repomd[entry['type']] = {}
        repomd[entry['type']]['checksum'] = entry['checksum']['.cdata']
        repomd[entry['type']]['checksum_type'] = entry['checksum']['type']
        ochecksum = entry.get('open-checksum', {})
        repomd[entry['type']]['open_checksum'] = ochecksum.get('.cdata')
        repomd[entry['type']]['open_checksum_type'] = ochecksum.get('type')
        repomd[entry['type']]['size'] = entry['size']['.cdata']
        osize = entry.get('open-size', {})
        repomd[entry['type']]['open_size'] = osize.get('.cdata')
        repomd[entry['type']]['location'] = entry['location']['href']
        repomd[entry['type']]['timestamp'] = entry['timestamp']['.cdata']
    return repomd


class ErratumContentSWRTest(utils.BaseAPITestCase):
    """Test ability to generate erratum equal to synced data."""

    @classmethod
    def setUpClass(cls):
        """Create repo, sync, publish, compare.

        More specifically:

        1. Create a repository.
        2. Add yum distributor to it.
        3. Sync repository.
        4. Publish repository.
        5. Fetch and parse generated ``comps.xml``.
        6. Fetch and parse generated ``updateinfo.xml``.
        """
        super(ErratumContentSWRTest, cls).setUpClass()

        # Create a repository and add a distributor to it.
        client = api.Client(cls.cfg, api.json_handler)
        body = gen_repo()
        body['importer_config']['feed'] = RPM_FEED_URL
        repo = client.post(REPOSITORY_PATH, body)
        cls.resources.add(repo['_href'])
        distributor = client.post(
            urljoin(repo['_href'], 'distributors/'),
            gen_distributor(),
        )

        cls.tasks = {}  # {'import_no_pkglist': (…), 'import_typical': (…)}

        cls.report = utils.sync_repo(cls.cfg, repo['_href'])

        client.post(
            urljoin(repo['_href'], 'actions/publish/'),
            {'id': distributor['id']},
        )

        updateinfo_fpath = get_repo_md_type_url(cls.cfg, distributor,
                                                'updateinfo')
        updateinfo_f = get_metadata(cls.cfg, distributor, updateinfo_fpath)

        cls.parsed = None
        with open_gzipped(updateinfo_f) as gz_file:
            parser = xmlparser.Parser()
            cls.parsed = parser.parse_file(gz_file)

        _updateinfo_transform(cls.parsed)
        _cdata_to_text(cls.parsed)
        cls.parsed['updates']['update'] = sorted(
            cls.parsed['updates']['update'],
            key=lambda x: x['id']
        )

        feed_url = urljoin(RPM_FEED_URL, 'repodata/repomd.xml')
        feed_repomd = StringIO.StringIO(requests.get(feed_url).content)
        feed_repomd.decode_content = True
        repomd = parse_repomd(feed_repomd)
        updateinfo_f = requests.get(urljoin(RPM_FEED_URL,
                                            repomd['updateinfo']['location']),
                                    stream=True).raw
        updateinfo_f.decode_content = True
        with open_gzipped(updateinfo_f) as gz_file:
            parser = xmlparser.Parser()
            cls.parsed2 = parser.parse_file(gz_file)

        _updateinfo_transform(cls.parsed2)
        _cdata_to_text(cls.parsed2)
        cls.parsed2['updates']['update'] = sorted(
            cls.parsed2['updates']['update'],
            key=lambda x: x['id']
        )

    def test_01_content_equal(self):
        """test if content is equal."""
        diff = dict_cmp(self.parsed2, self.parsed, 'SYNCED', 'PUBLISHED',
                        required_fields={'updates.update': 'id'})
        self.assertTrue(not diff, json.dumps(diff, indent=4, sort_keys=True))
