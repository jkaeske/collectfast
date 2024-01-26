from unittest import TestCase
from unittest import mock

import boto3
from django.test import override_settings as override_django_settings

from collectfast.tests.utils import clean_static_dir
from collectfast.tests.utils import create_static_file
from collectfast.tests.utils import make_test
from collectfast.tests.utils import override_setting

from moto import mock_s3

from .utils import call_collectstatic


@make_test
@override_django_settings(
    STATICFILES_STORAGE="django.contrib.staticfiles.storage.StaticFilesStorage"
)
def test_disable_collectfast_with_default_storage(case: TestCase) -> None:
    clean_static_dir()
    create_static_file()
    case.assertIn("1 static file copied", call_collectstatic(disable_collectfast=True))


@make_test
@mock_s3
def test_disable_collectfast(case: TestCase) -> None:
    conn = boto3.resource('s3', region_name='us-east-1')
    # Create bucket
    conn.create_bucket(Bucket='collectfast')

    clean_static_dir()
    create_static_file()
    case.assertIn("1 static file copied.", call_collectstatic(disable_collectfast=True))


@override_setting("enabled", False)
@mock.patch("collectfast.management.commands.collectstatic.Command._load_strategy")
def test_no_load_with_disable_setting(mocked_load_strategy: mock.MagicMock) -> None:
    clean_static_dir()
    call_collectstatic()
    mocked_load_strategy.assert_not_called()


@mock.patch("collectfast.management.commands.collectstatic.Command._load_strategy")
def test_no_load_with_disable_flag(mocked_load_strategy: mock.MagicMock) -> None:
    clean_static_dir()
    call_collectstatic(disable_collectfast=True)
    mocked_load_strategy.assert_not_called()
