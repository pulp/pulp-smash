# coding=utf-8
"""Verify an RPM repository's ``comps.xml`` file.

Each RPM repository has a ``repodata`` directory, in which various XML files
containing metadata are present. This module houses test cases which verify the
``comps.xml`` file. For a sample ``comps.xml`` file, search through
:data:`pulp_smash.constants.RPM_FEED_URL`.
"""
import unittest
from urllib.parse import urljoin
from xml.etree import ElementTree

from packaging.version import Version

from pulp_smash import api, config, selectors, utils
from pulp_smash.constants import (
    CONTENT_UPLOAD_PATH,
    REPOSITORY_PATH,
    RPM_FEED_URL,
)
from pulp_smash.tests.rpm.api_v2.utils import (
    gen_distributor,
    gen_repo,
    get_repomd_xml,
)
from pulp_smash.tests.rpm.utils import set_up_module


def setUpModule():  # pylint:disable=invalid-name
    """Possibly skip the tests in this module.

    Skip this module of tests if Pulp suffers from `issue 2277
    <https://pulp.plan.io/issues/2277>`_.
    """
    set_up_module()
    if selectors.bug_is_untestable(2277, config.get_config().version):
        raise unittest.SkipTest('https://pulp.plan.io/issues/2277')


def _gen_realistic_group():
    """Return a realistic, typical package group.

    Most supported fields are filled in on this unit, and there are a few
    translated strings.
    """
    return {
        'id': utils.uuid4(),
        'name': 'Additional Development',
        'translated_name': {'es': 'Desarrollo adicional', 'zh_CN': '附加开发'},
        'description': (
            'Additional development headers and libraries for building '
            'open-source applications'
        ),
        'translated_description': {
            'es': (
                'Encabezados adicionales y bibliotecas para compilar '
                'aplicaciones de código abierto.'
            ),
            'zh_CN': '用于构建开源应用程序的附加开发标头及程序可。',
        },
        'default': True,
        'user_visible': True,
        'display_order': 55,
        'mandatory_package_names': ['PyQt4-devel', 'SDL-devel'],
        'default_package_names': ['perl-devel', 'polkit-devel'],
        'optional_package_names': ['binutils-devel', 'python-devel'],
        'conditional_package_names': [
            ('perl-Test-Pod', 'perl-devel'),
            ('python-setuptools', 'python-devel')
        ],
    }


def _gen_minimal_group():
    """Return a package group which is as empty as possible.

    This unit omits every non-mandatory field (which, in practice, means that
    it includes only an 'id').
    """
    return {'id': utils.uuid4()}


def _get_groups_by_id(comps_tree):
    """Return each "group" element in ``comps_tree``, keyed by ID.

    :param comps_tree: An ``xml.etree.Element`` object. This object should be
        the root element of a ``comps.xml`` file.
    :returns: A dict in the form ``{group_id: group}``.
    """
    return {
        group.find('id').text: group for group in comps_tree.findall('group')
    }


def _upload_import_package_group(server_config, repo, unit_metadata):
    """Import a unit of type ``package_group`` into a repository.

    :param repo: A dict of attributes about a repository.
    :param unit_metadata: A dict of unit metadata.
    :returns: The call report generated when importing and uploading.
    """
    client = api.Client(server_config, api.json_handler)
    malloc = client.post(CONTENT_UPLOAD_PATH)
    call_report = client.post(
        urljoin(repo['_href'], 'actions/import_upload/'),
        {
            'unit_key': {'id': unit_metadata['id'], 'repo_id': repo['id']},
            'unit_metadata': unit_metadata,
            'unit_type_id': 'package_group',
            'upload_id': malloc['upload_id'],
        },
    )
    client.delete(malloc['_href'])
    return call_report


class SyncRepoTestCase(utils.BaseAPITestCase):
    """Sync in content from another RPM repository and publish it.

    More specifically, this test case does the following:

    1. Create a repository with a feed and a distributor.
    2. Sync and publish the repository.
    3. Verify the ``comps.xml`` file available in the published repository.
    """

    @classmethod
    def setUpClass(cls):
        """Create, sync and publish a repository. Fetch its ``comps.xml``."""
        super(SyncRepoTestCase, cls).setUpClass()
        client = api.Client(cls.cfg, api.json_handler)

        # Create a repo.
        body = gen_repo()
        body['importer_config']['feed'] = RPM_FEED_URL
        body['distributors'] = [gen_distributor()]
        repo = client.post(REPOSITORY_PATH, body)
        cls.resources.add(repo['_href'])

        # Sync and publish the repo.
        repo = client.get(repo['_href'], params={'details': True})
        utils.sync_repo(cls.cfg, repo['_href'])
        client.post(
            urljoin(repo['_href'], 'actions/publish/'),
            {'id': repo['distributors'][0]['id']},
        )
        repo = client.get(repo['_href'], params={'details': True})

        # Fetch and parse comps.xml.
        dist = repo['distributors'][0]
        dist_url = urljoin('/pulp/repos/', dist['config']['relative_url'])
        cls.root_element = get_repomd_xml(cls.cfg, dist_url, 'group')
        cls.xml_as_str = ElementTree.tostring(cls.root_element)

    def test_first_level_element(self):
        """Verify the top-level element is named "comps"."""
        self.assertEqual(self.root_element.tag, 'comps')

    def test_second_level_elements(self):
        """Verify the correct second-level elements are present."""
        have = [child.tag for child in self.root_element]
        have.sort()
        want = ['category', 'group', 'group']
        if self.cfg.version >= Version('2.9'):
            want.append('langpacks')
        self.assertEqual(have, want)

    def test_langpacks_element(self):
        """Verify a ``langpacks`` element is in ``comps.xml``.

        Support for package langpacks has been added in Pulp 2.9. Consequently,
        this test is skipped on earlier versions of Pulp.
        """
        if self.cfg.version < Version('2.9'):
            self.skipTest('This test requires Pulp 2.9 or greater.')
        langpacks_elements = self.root_element.findall('langpacks')
        self.assertEqual(len(langpacks_elements), 1, self.xml_as_str)
        match_elements = langpacks_elements[0].findall('match')
        self.assertEqual(len(match_elements), 2, self.xml_as_str)


class UploadPackageGroupsTestCase(utils.BaseAPITestCase):
    """Upload custom package groups to an RPM repository and publish it.

    More specifically, this test case does the following:

    1. Create a repository without a feed.
    2. Add yum distributor to the repository.
    3. Generate several custom package groups. Upload each of them to Pulp, and
       import them into the repository.
    4. Publish the repository.
    5. Verify the ``comps.xml`` file available in the published repository.
    """

    @classmethod
    def setUpClass(cls):
        """Create an RPM repository, upload package groups, and publish."""
        super(UploadPackageGroupsTestCase, cls).setUpClass()

        # Create a repository and add a distributor to it.
        client = api.Client(cls.cfg, api.json_handler)
        repo = client.post(REPOSITORY_PATH, gen_repo())
        cls.resources.add(repo['_href'])
        distributor = client.post(
            urljoin(repo['_href'], 'distributors/'),
            gen_distributor(),
        )

        # Generate several package groups, import them into the repository, and
        # publish the repository.
        cls.package_groups = {
            'minimal': _gen_minimal_group(),
            'realistic': _gen_realistic_group(),
        }
        cls.tasks = {}
        for key, package_group in cls.package_groups.items():
            report = _upload_import_package_group(cls.cfg, repo, package_group)
            cls.tasks[key] = tuple(api.poll_spawned_tasks(cls.cfg, report))
        client.post(
            urljoin(repo['_href'], 'actions/publish/'),
            {'id': distributor['id']},
        )

        # Fetch the generated repodata of type 'group' (a.k.a. 'comps')
        cls.root_element = get_repomd_xml(
            cls.cfg,
            urljoin('/pulp/repos/', distributor['config']['relative_url']),
            'group'
        )

    def test_root(self):
        """Assert the root element of the tree has a tag of "comps"."""
        self.assertEqual(self.root_element.tag, 'comps')

    def test_count(self):
        """Assert there is one "group" element per imported group unit."""
        groups = self.root_element.findall('group')
        self.assertEqual(len(groups), len(self.package_groups))

    def test_ids_alone(self):
        """Assert each "group" element has one "id" child element."""
        for i, group in enumerate(self.root_element.findall('group')):
            with self.subTest(i=i):
                self.assertEqual(len(group.findall('id')), 1)

    def test_ids_unique(self):
        """Assert each group ID is unique."""
        ids = []
        for group in self.root_element.findall('group'):
            for group_id in group.findall('id'):
                ids.append(group_id.text)
        ids.sort()
        deduplicated_ids = list(set(ids))
        deduplicated_ids.sort()
        self.assertEqual(ids, deduplicated_ids)

    def test_one_task_per_import(self):
        """Assert only one task is spawned per package group upload."""
        for key, tasks in self.tasks.items():
            with self.subTest(key=key):
                self.assertEqual(len(tasks), 1)

    def test_tasks_state(self):
        """Assert each task's state is "finished".

        This test assumes :meth:`test_one_task_per_import` passes.
        """
        for key, tasks in self.tasks.items():
            with self.subTest(key=key):
                self.assertEqual(tasks[0]['state'], 'finished')

    def test_tasks_result(self):
        """Assert each task's result success flag (if present) is true.

        This test assumes :meth:`test_one_task_per_import` passes.
        """
        for key, tasks in self.tasks.items():
            with self.subTest(key=key):
                if 'result' not in tasks[0]:
                    continue
                result = tasks[0]['result']
                self.assertTrue(result['success_flag'], result)

    def test_has_groups(self):
        """Assert that each imported group unit appears in the XML."""
        input_ids = {pkg_grp['id'] for pkg_grp in self.package_groups.values()}
        output_ids = {
            group.find('id').text
            for group in self.root_element.findall('group')
        }
        self.assertEqual(input_ids, output_ids)

    def test_verbatim_string_fields(self):
        """Assert string fields on a unit appear unmodified in generated XML.

        This test covers fields from a group unit which are expected to be
        serialized as-is into top-level tags under a ``<group>``. For example,
        this test asserts that the 'name' attribute on a group unit will appear
        in the generated XML as::

            <group>
                <name>some-value</name>
                ...
            </group>
        """
        input_ = self.package_groups['realistic']
        output = _get_groups_by_id(self.root_element)[input_['id']]
        for key in ('id', 'name', 'description', 'display_order'):
            with self.subTest(key=key):
                input_text = type('')(input_[key])
                output_text = output.find(key).text
                self.assertEqual(input_text, output_text)

    def test_verbatim_boolean_fields(self):
        """Assert boolean fields on a unit appear correctly in generated XML.

        This test is similar to :meth:`test_verbatim_string_fields`, but
        additionally verifies that boolean values are serialized as expected in
        the XML (i.e. as text 'true' or 'false').
        """
        input_ = self.package_groups['realistic']
        output = _get_groups_by_id(self.root_element)[input_['id']]
        keys_map = (('user_visible', 'uservisible'), ('default', 'default'))
        for input_key, output_key in keys_map:
            with self.subTest(input_key=input_key, output_key=output_key):
                input_value = input_[input_key]
                self.assertIn(input_value, (True, False))
                input_value = type('')(input_value).lower()

                output_value = output.find(output_key).text
                self.assertEqual(input_value, output_value)

    def test_display_order_occurences(self):
        """Assert ``display_order`` occurs once if omitted from the unit."""
        if selectors.bug_is_untestable(1787, self.cfg.version):
            self.skipTest('https://pulp.plan.io/issues/1787')
        input_id = self.package_groups['minimal']['id']
        output = _get_groups_by_id(self.root_element)[input_id]
        self.assertEqual(len(output.findall('display_order')), 1)

    def test_display_order_value(self):
        """Assert ``display_order`` is "1024" if omitted from the unit.

        This test may be skipped if `Pulp #1787
        <https://pulp.plan.io/issues/1787>`_ is open.
        """
        if selectors.bug_is_untestable(1787, self.cfg.version):
            self.skipTest('https://pulp.plan.io/issues/1787')
        input_id = self.package_groups['minimal']['id']
        output = _get_groups_by_id(self.root_element)[input_id]
        self.assertEqual(output.find('display_order').text, '1024')

    def test_single_elements(self):
        """Assert that certain tags appear under groups exactly once."""
        for group in self.root_element.findall('group'):
            for tag in ('default', 'packagelist', 'uservisible'):
                with self.subTest((group.find('id'), tag)):
                    self.assertEqual(len(group.findall(tag)), 1)

    def test_default_default(self):
        """Assert that the default value of ``default`` tag is 'false'."""
        input_id = self.package_groups['minimal']['id']
        output = _get_groups_by_id(self.root_element)[input_id]
        self.assertEqual(output.find('default').text, 'false')

    def test_default_uservisible(self):
        """Assert that the default value of ``uservisible`` tag is 'false'."""
        input_id = self.package_groups['minimal']['id']
        output = _get_groups_by_id(self.root_element)[input_id]
        self.assertEqual(output.find('uservisible').text, 'false')

    def test_translated_string_count(self):
        """Assert that the XML has correct number of translated strings.

        Some fields (name, description) are translatable. The tags for these
        fields are expected to appear once per translation, plus once for the
        untranslated string. This test verifies that this is the case.
        """
        input_ = self.package_groups['realistic']
        output = _get_groups_by_id(self.root_element)[input_['id']]
        for key in ('description', 'name'):
            with self.subTest(key=key):
                input_values = input_['translated_' + key]
                output_values = output.findall(key)
                self.assertEqual(len(input_values) + 1, len(output_values))

    def test_translated_string_values(self):
        """Assert that the XML has correct values for translated strings.

        Some fields (name, description) are translatable. The tags for these
        fields are expected to appear once per translation, plus once for the
        untranslated string. This test verifies that each translated string
        matches exactly the string provided when the group unit was imported.
        """
        input_ = self.package_groups['realistic']
        output = _get_groups_by_id(self.root_element)[input_['id']]
        lang_attr = '{http://www.w3.org/XML/1998/namespace}lang'
        for key in ('description', 'name'):
            for value in output.findall(key):
                lang = value.get(lang_attr)
                with self.subTest(key=key, lang=lang):
                    if not lang:
                        continue  # this is the untranslated value
                    input_text = input_['translated_' + key][lang]
                    output_text = value.text
                    self.assertEqual(input_text, output_text)

    def test_packagelist_values(self):
        """Assert packagelist contains packagereq elements with correct text.

        This test verifies that, for each of the 4 possible types of package
        in a group, the packagelist in the group XML contains exactly the
        package names in the uploaded unit.
        """
        input_ = self.package_groups['realistic']
        output = _get_groups_by_id(self.root_element)[input_['id']]
        xpath = 'packagelist/packagereq[@type="{}"]'
        for pkg_type in ('mandatory', 'default', 'optional', 'conditional'):
            with self.subTest(pkg_type=pkg_type):
                input_values = input_[pkg_type + '_package_names']
                if pkg_type == 'conditional':
                    # 'conditional' is special: it maps a package name to a
                    # required package. In this test, we only test the package
                    # name part. See test_conditional_requires for testing the
                    # 'requires' attribute.
                    input_values = [key for key, _ in input_values]
                input_values = sorted(input_values)
                output_values = sorted([
                    element.text
                    for element in output.findall(xpath.format(pkg_type))
                ])
                self.assertEqual(input_values, output_values)

    def test_conditional_requires(self):
        """Assert ``requires`` attributes are correct on conditional packages.

        This test assumes :meth:`test_packagelist_values` has passed.
        """
        input_ = self.package_groups['realistic']
        output = _get_groups_by_id(self.root_element)[input_['id']]
        xpath = 'packagelist/packagereq[@type="conditional"]'
        conditional_packages_by_name = {
            elem.text: elem for elem in output.findall(xpath)
        }
        for name, requires in input_['conditional_package_names']:
            with self.subTest(name=name):
                conditional_package = conditional_packages_by_name[name]
                self.assertEqual(conditional_package.get('requires'), requires)
