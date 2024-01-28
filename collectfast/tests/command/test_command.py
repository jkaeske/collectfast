import base64

# from unittest import TestCase
from unittest import mock

import boto3
import botocore
import pytest
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.test import TestCase
from django.test import override_settings as override_django_settings
from storages.backends import gcloud

from collectfast.management.commands.collectstatic import Command
from collectfast.tests.utils import clean_static_dir
from collectfast.tests.utils import create_static_file
from collectfast.tests.utils import override_setting

from .utils import call_collectstatic

from moto import mock_aws  # isort: skip


class BaseTestCommands(TestCase):
    def basics(self) -> None:
        clean_static_dir()
        create_static_file()
        self.assertIn("1 static file copied.", call_collectstatic())
        # file state should now be cached
        self.assertIn("0 static files copied.", call_collectstatic())

    @override_setting("threads", 5)
    def threads(self) -> None:
        clean_static_dir()
        create_static_file()
        self.assertIn("1 static file copied.", call_collectstatic())
        # file state should now be cached
        self.assertIn("0 static files copied.", call_collectstatic())

    @mock.patch("collectfast.strategies.base.Strategy.post_copy_hook", autospec=True)
    def calls_post_copy_hook(self, post_copy_hook: mock.MagicMock) -> None:
        clean_static_dir()
        path = create_static_file()
        cmd = Command()
        cmd.run_from_argv(["manage.py", "collectstatic", "--noinput"])
        post_copy_hook.assert_called_once_with(mock.ANY, path.name, path.name, mock.ANY)

    @mock.patch("collectfast.strategies.base.Strategy.on_skip_hook", autospec=True)
    def calls_on_skip_hook(self, on_skip_hook: mock.MagicMock) -> None:
        clean_static_dir()
        path = create_static_file()
        cmd = Command()
        cmd.run_from_argv(["manage.py", "collectstatic", "--noinput"])
        on_skip_hook.assert_not_called()
        cmd.run_from_argv(["manage.py", "collectstatic", "--noinput"])
        on_skip_hook.assert_called_once_with(mock.ANY, path.name, path.name, mock.ANY)


@override_django_settings(
    STATICFILES_STORAGE="storages.backends.s3.S3Storage",
    COLLECTFAST_STRATEGY="collectfast.strategies.boto3.Boto3Strategy",
)
@mock_aws
class TestAWSBackends(BaseTestCommands):
    def setUp(self) -> None:
        s3 = boto3.client("s3", region_name="us-east-1")
        s3.create_bucket(Bucket="collectfast")
        # Test if bucket exist before running tests
        s3_resource = boto3.resource("s3")
        bucket_exists = True
        try:
            s3_resource.meta.client.head_bucket(Bucket="collectfast")
        except botocore.exceptions.ClientError as e:
            error_code = int(e.response["Error"]["Code"])
            if error_code == 404:
                bucket_exists = False
        self.assertTrue(bucket_exists)

    def test_basics(self) -> None:
        super().basics()

    def test_threads(self) -> None:
        super().threads()

    def test_calls_post_copy_hook(self) -> None:
        super().calls_post_copy_hook()

    def test_calls_on_skip_hook(self) -> None:
        super().calls_on_skip_hook()

    # @make_test_aws_backends
    # @override_storage_attr("gzip", True)
    # @override_setting("aws_is_gzipped", True)
    # @mock_aws
    # def test_aws_is_gzipped(case: TestCase) -> None:
    #     clean_static_dir()
    #     create_static_file()
    #     case.assertIn("1 static file copied.", call_collectstatic())
    #     # file state should now be cached
    #     case.assertIn("0 static files copied.", call_collectstatic())


@override_django_settings(
    STATICFILES_STORAGE="storages.backends.gcloud.GoogleCloudStorage",
    COLLECTFAST_STRATEGY="collectfast.strategies.gcloud.GoogleCloudStrategy",
)
class TestGCPBackends(BaseTestCommands):
    def setUp(self) -> None:
        bucket_name = "collectfast"
        gcloud.GoogleCloudStorage(bucket_name=bucket_name)
        # Start the mock for the Client
        mock_client = mock.patch("storages.backends.gcloud.Client").start()
        # Define the mocked MD5 hash
        mocked_md5_hash = base64.urlsafe_b64encode(b"mocked_md5_hash").decode()
        # Get the blob return value from the bucket
        blob_return = mock_client.return_value.bucket.return_value.get_blob.return_value
        # Get the blob properties
        properties = blob_return._properties
        # Set the return value
        properties.__getitem__.return_value = mocked_md5_hash

    def test_basics(self) -> None:
        super().basics()

    def test_threads(self) -> None:
        super().threads()

    def test_calls_post_copy_hook(self) -> None:
        super().calls_post_copy_hook()

    def test_calls_on_skip_hook(self) -> None:
        super().calls_on_skip_hook()


@override_django_settings(
    STATICFILES_STORAGE="django.core.files.storage.FileSystemStorage",
    COLLECTFAST_STRATEGY="collectfast.strategies.filesystem.FileSystemStrategy",
)
class TestLocalFileBackends(BaseTestCommands):
    def test_basics(self) -> None:
        super().basics()

    def test_threads(self) -> None:
        super().threads()

    def test_calls_post_copy_hook(self) -> None:
        super().calls_post_copy_hook()

    def test_calls_on_skip_hook(self) -> None:
        super().calls_on_skip_hook()


@override_django_settings(
    STATICFILES_STORAGE="django.core.files.storage.FileSystemStorage",
    COLLECTFAST_STRATEGY="collectfast.strategies.filesystem.CachingFileSystemStrategy",
)
class TestLocalFileCachingBackends(BaseTestCommands):
    def test_basics(self) -> None:
        super().basics()

    def test_threads(self) -> None:
        super().threads()

    def test_calls_post_copy_hook(self) -> None:
        super().calls_post_copy_hook()

    def test_calls_on_skip_hook(self) -> None:
        super().calls_on_skip_hook()


def test_dry_run():
    clean_static_dir()
    create_static_file()
    result = call_collectstatic(dry_run=True)
    assert "1 static file copied." in result
    assert "Pretending to copy" in result
    result = call_collectstatic(dry_run=True)
    assert "1 static file copied." in result
    assert "Pretending to copy" in result
    assert "Pretending to delete" in result


def test_raises_for_no_configured_strategy():
    if hasattr(settings, "STORAGES"):
        with override_django_settings(STORAGES={}, COLLECTFAST_STRATEGY=None):
            with pytest.raises(ImproperlyConfigured):
                Command._load_strategy()
    else:
        with override_django_settings(
            STATICFILES_STORAGE=None, COLLECTFAST_STRATEGY=None
        ):
            with pytest.raises(ImproperlyConfigured):
                Command._load_strategy()
