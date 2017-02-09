"""Tests covering utilities for integrating with the catalog service."""
# pylint: disable=missing-docstring
import uuid
import copy

from django.contrib.auth import get_user_model
from django.test import TestCase
import mock
from opaque_keys.edx.keys import CourseKey

from openedx.core.djangoapps.catalog.models import CatalogIntegration
from openedx.core.djangoapps.catalog.tests.factories import ProgramFactory, ProgramTypeFactory
from openedx.core.djangoapps.catalog.tests.mixins import CatalogIntegrationMixin
from openedx.core.djangoapps.catalog.utils import (
    get_programs,
    munge_catalog_program,
    get_program_types,
    get_program_type,
    get_programs_with_type,
    get_program_with_type_and_instructors,
)
from openedx.core.djangolib.testing.utils import skip_unless_lms
from student.tests.factories import UserFactory


UTILS_MODULE = 'openedx.core.djangoapps.catalog.utils'
User = get_user_model()  # pylint: disable=invalid-name


@skip_unless_lms
@mock.patch(UTILS_MODULE + '.get_edx_api_data')
class TestGetPrograms(CatalogIntegrationMixin, TestCase):
    """Tests covering retrieval of programs from the catalog service."""
    def setUp(self):
        super(TestGetPrograms, self).setUp()

        self.uuid = str(uuid.uuid4())
        self.marketing_slug = 'foo_bar_program'
        self.type = 'FooBar'
        self.catalog_integration = self.create_catalog_integration(cache_ttl=1)

        UserFactory(username=self.catalog_integration.service_username)

    def assert_contract(self, call_args, program_uuid=None, marketing_slug=None, type=None):  # pylint: disable=redefined-builtin
        """Verify that API data retrieval utility is used correctly."""
        args, kwargs = call_args

        for arg in (self.catalog_integration, 'programs'):
            self.assertIn(arg, args)

        self.assertEqual(kwargs['resource_id'], program_uuid)

        cache_key = '{base}.programs{marketing_slug}{type}'.format(
            base=self.catalog_integration.CACHE_KEY,
            marketing_slug='.' + marketing_slug if marketing_slug else '',
            type='.' + type if type else ''
        )
        self.assertEqual(
            kwargs['cache_key'],
            cache_key if self.catalog_integration.is_cache_enabled else None
        )

        self.assertEqual(kwargs['api']._store['base_url'], self.catalog_integration.internal_api_url)  # pylint: disable=protected-access

        querystring = {
            'marketable': 1,
            'exclude_utm': 1,
        }
        if marketing_slug:
            querystring['marketing_slug'] = marketing_slug
            querystring['use_full_course_serializer'] = 1
        if type:
            querystring['type'] = type
        self.assertEqual(kwargs['querystring'], querystring)

        return args, kwargs

    def test_get_programs(self, mock_get_edx_api_data):
        programs = [ProgramFactory() for __ in range(3)]
        mock_get_edx_api_data.return_value = programs

        data = get_programs()

        self.assert_contract(mock_get_edx_api_data.call_args)
        self.assertEqual(data, programs)

    def test_get_one_program(self, mock_get_edx_api_data):
        program = ProgramFactory()
        mock_get_edx_api_data.return_value = program

        data = get_programs(uuid=self.uuid)

        self.assert_contract(mock_get_edx_api_data.call_args, program_uuid=self.uuid)
        self.assertEqual(data, program)

    def test_get_one_program_by_marketing_slug(self, mock_get_edx_api_data):
        program = ProgramFactory()
        mock_get_edx_api_data.return_value = program

        data = get_programs(marketing_slug=self.marketing_slug)

        self.assert_contract(mock_get_edx_api_data.call_args, marketing_slug=self.marketing_slug)
        self.assertEqual(data, program)

    def test_get_programs_by_type(self, mock_get_edx_api_data):
        programs = ProgramFactory.create_batch(2)
        mock_get_edx_api_data.return_value = programs

        data = get_programs(type=self.type)

        self.assert_contract(mock_get_edx_api_data.call_args, type=self.type)
        self.assertEqual(data, programs)

    def test_programs_unavailable(self, mock_get_edx_api_data):
        mock_get_edx_api_data.return_value = []

        data = get_programs()

        self.assert_contract(mock_get_edx_api_data.call_args)
        self.assertEqual(data, [])

    def test_cache_disabled(self, mock_get_edx_api_data):
        self.catalog_integration = self.create_catalog_integration(cache_ttl=0)
        get_programs()
        self.assert_contract(mock_get_edx_api_data.call_args)

    def test_config_missing(self, _mock_get_edx_api_data):
        """
        Verify that no errors occur if this method is called when catalog config
        is missing.
        """
        CatalogIntegration.objects.all().delete()

        data = get_programs()
        self.assertEqual(data, [])

    def test_service_user_missing(self, _mock_get_edx_api_data):
        """
        Verify that no errors occur if this method is called when the catalog
        service user is missing.
        """
        # Note: Deleting the service user would be ideal, but causes mysterious
        # errors on Jenkins.
        self.create_catalog_integration(service_username='nonexistent-user')

        data = get_programs()
        self.assertEqual(data, [])


class TestMungeCatalogProgram(TestCase):
    def setUp(self):
        super(TestMungeCatalogProgram, self).setUp()

        self.catalog_program = ProgramFactory()

    def assert_munged(self, program):
        munged = munge_catalog_program(program)
        expected = {
            'id': program['uuid'],
            'name': program['title'],
            'subtitle': program['subtitle'],
            'category': program['type'],
            'marketing_slug': program['marketing_slug'],
            'organizations': [
                {
                    'display_name': organization['name'],
                    'key': organization['key']
                } for organization in program['authoring_organizations']
            ],
            'course_codes': [
                {
                    'display_name': course['title'],
                    'key': course['key'],
                    'organization': {
                        'display_name': course['owners'][0]['name'],
                        'key': course['owners'][0]['key']
                    },
                    'run_modes': [
                        {
                            'course_key': course_run['key'],
                            'run_key': CourseKey.from_string(course_run['key']).run,
                            'mode_slug': course_run['type'],
                            'marketing_url': course_run['marketing_url'],
                        } for course_run in course['course_runs']
                    ],
                } for course in program['courses']
            ],
            'banner_image_urls': {
                'w1440h480': program['banner_image']['large']['url'],
                'w726h242': program['banner_image']['medium']['url'],
                'w435h145': program['banner_image']['small']['url'],
                'w348h116': program['banner_image']['x-small']['url'],
            },
            'detail_url': program.get('detail_url'),
        }

        self.assertEqual(munged, expected)

    def test_munge_catalog_program(self):
        self.assert_munged(self.catalog_program)

    def test_munge_with_detail_url(self):
        self.catalog_program['detail_url'] = 'foo'
        self.assert_munged(self.catalog_program)


@skip_unless_lms
@mock.patch(UTILS_MODULE + '.get_edx_api_data')
class TestGetProgramTypes(CatalogIntegrationMixin, TestCase):
    """Tests covering retrieval of program types from the catalog service."""
    def setUp(self):
        super(TestGetProgramTypes, self).setUp()

        self.catalog_program = ProgramFactory()
    def test_get_program_types(self, mock_get_edx_api_data):
        """Verify get_program_types returns the expected list of program types."""
        program_types = ProgramTypeFactory.create_batch(3)
        mock_get_edx_api_data.return_value = program_types

        # Catalog integration is disabled.
        data = get_program_types()
        self.assertEqual(data, [])

        catalog_integration = self.create_catalog_integration()
        UserFactory(username=catalog_integration.service_username)
        data = get_program_types()
        self.assertEqual(data, program_types)

    def test_get_program_type(self, mock_get_edx_api_data):
        """Verify get_program_type returns the expected program type."""
        program_types = ProgramTypeFactory.create_batch(3)
        mock_get_edx_api_data.return_value = program_types

        catalog_integration = self.create_catalog_integration()
        UserFactory(username=catalog_integration.service_username)

        program_type = program_types[0]
        actual = get_program_type(program_type['name'])
        self.assertDictEqual(actual, program_type)

    def test_get_programs_with_type(self, _mock_get_edx_api_data):
        """Verify get_programs_with_type returns the expected list of programs."""
        programs = []
        program_types = []
        programs_with_program_type = []
        type_name_template = 'type_name_{postfix}'

        for index in range(3):
            # Creating the Programs and their corresponding program types.
            type_name = type_name_template.format(postfix=index)
            program = ProgramFactory(type=type_name)
            program_type = ProgramTypeFactory(name=type_name)

            programs.append(program)
            program_types.append(program_type)

            program_with_type = copy.deepcopy(program)
            program_with_type['type'] = program_type
            programs_with_program_type.append(program_with_type)

        with mock.patch(UTILS_MODULE + '.get_programs') as patched_get_programs:
            with mock.patch(UTILS_MODULE + '.get_program_types') as patched_get_program_types:
                patched_get_programs.return_value = programs
                patched_get_program_types.return_value = program_types

                # Test that we get all active programs without the type filter
                actual = get_programs_with_type()
                self.assertEqual(actual, programs_with_program_type)

                # Test that we get just the active programs of the given type
                actual = get_programs_with_type([type_name_template.format(postfix=0)])
                self.assertEqual(actual, [programs_with_program_type[0]])

    def test_get_program_with_type_and_instructors(self, _mock_get_edx_api_data):
        """Verify get_program_with_type_and_instructors returns the expected program data."""
        program = ProgramFactory()
        program_type = ProgramTypeFactory(name=program['type'])

        program_detail = copy.deepcopy(program)
        program_detail['type'] = program_type
        program_detail['instructors'] = {}

        with mock.patch(UTILS_MODULE + '.get_programs') as patched_get_programs:
            with mock.patch(UTILS_MODULE + '.get_program_types') as patched_get_program_types:
                with mock.patch(UTILS_MODULE + '._get_program_instructors') as patched_get_program_instructors:
                    patched_get_programs.return_value = [program]
                    patched_get_program_types.return_value = [program_type]
                    patched_get_program_instructors.return_value = {}

                    actual = get_program_with_type_and_instructors(program['marketing_slug'])
                    self.assertEqual(actual, program_detail)

