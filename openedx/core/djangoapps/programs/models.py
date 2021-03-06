"""Models providing Programs support for the LMS and Studio."""
from urlparse import urljoin

from django.utils.translation import ugettext_lazy as _
from django.db import models

from config_models.models import ConfigurationModel


class ProgramsApiConfig(ConfigurationModel):
    """
    DEPRECATED. To be removed as part of ECOM-5136.

    Manages configuration for connecting to the Programs service and using its API.
    """
    OAUTH2_CLIENT_NAME = 'programs'
    CACHE_KEY = 'programs.api.data'
    API_NAME = 'programs'

    api_version_number = models.IntegerField(verbose_name=_("API Version"))

    internal_service_url = models.URLField(verbose_name=_("Internal Service URL"), blank=True)
    public_service_url = models.URLField(verbose_name=_("Public Service URL"), blank=True)

    marketing_path = models.CharField(
        max_length=255,
        blank=True,
        help_text=_(
            'Path used to construct URLs to programs marketing pages (e.g., "/foo").'
        )
    )

    authoring_app_js_path = models.CharField(
        verbose_name=_("Path to authoring app's JS"),
        max_length=255,
        blank=True,
        help_text=_(
            "This value is required in order to enable the Studio authoring interface."
        )
    )

    authoring_app_css_path = models.CharField(
        verbose_name=_("Path to authoring app's CSS"),
        max_length=255,
        blank=True,
        help_text=_(
            "This value is required in order to enable the Studio authoring interface."
        )
    )

    cache_ttl = models.PositiveIntegerField(
        verbose_name=_("Cache Time To Live"),
        default=0,
        help_text=_(
            "Specified in seconds. Enable caching by setting this to a value greater than 0."
        )
    )

    enable_student_dashboard = models.BooleanField(
        verbose_name=_("Enable Student Dashboard Displays"),
        default=False
    )

    enable_studio_tab = models.BooleanField(
        verbose_name=_("Enable Studio Authoring Interface"),
        default=False
    )

    enable_certification = models.BooleanField(
        verbose_name=_("Enable Program Certificate Generation"),
        default=False
    )

    max_retries = models.PositiveIntegerField(
        verbose_name=_("Maximum Certification Retries"),
        default=11,  # This gives about 30 minutes wait before the final attempt
        help_text=_(
            "When making requests to award certificates, make at most this many attempts "
            "to retry a failing request."
        )
    )

    xseries_ad_enabled = models.BooleanField(
        verbose_name=_("Do we want to show xseries program advertising"),
        default=False
    )

    program_listing_enabled = models.BooleanField(
        verbose_name=_("Do we want to show program listing page"),
        default=False
    )

    program_details_enabled = models.BooleanField(
        verbose_name=_("Do we want to show program details pages"),
        default=False
    )

    @property
    def internal_api_url(self):
        """
        Generate a URL based on internal service URL and API version number.
        """
        return urljoin(self.internal_service_url, '/api/v{}/'.format(self.api_version_number))

    @property
    def public_api_url(self):
        """
        Generate a URL based on public service URL and API version number.
        """
        return urljoin(self.public_service_url, '/api/v{}/'.format(self.api_version_number))

    @property
    def is_cache_enabled(self):
        """Whether responses from the Programs API will be cached."""
        return self.cache_ttl > 0

    @property
    def is_studio_tab_enabled(self):
        """
        Indicates whether Studio functionality related to Programs should
        be enabled or not.
        """
        return self.enabled and self.enable_studio_tab

    @property
    def is_certification_enabled(self):
        """
        Indicates whether background tasks should be initiated to grant
        certificates for Program completion.
        """
        return self.enabled and self.enable_certification

    @property
    def show_program_listing(self):
        """
        Indicates whether we want to show program listing page
        """
        return self.enabled and self.program_listing_enabled

    @property
    def show_program_details(self):
        """
        Indicates whether we want to show program details pages
        """
        return self.enabled and self.program_details_enabled
