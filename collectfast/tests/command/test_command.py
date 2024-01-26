import base64
import os
from unittest import TestCase
from unittest import mock

import botocore
from django.core.exceptions import ImproperlyConfigured
from django.test import override_settings as override_django_settings
from django.conf import settings

from collectfast.management.commands.collectstatic import Command
from collectfast.tests.utils import clean_static_dir
from collectfast.tests.utils import create_static_file
from collectfast.tests.utils import make_test
from collectfast.tests.utils import override_setting
from collectfast.tests.utils import override_storage_attr
from collectfast.tests.utils import test_many
from storages.backends import gcloud

import boto3

from .utils import call_collectstatic

from moto import mock_s3

aws_backend_confs = {
    "boto3": override_django_settings(
        STATICFILES_STORAGE="storages.backends.s3.S3Storage",
        COLLECTFAST_STRATEGY="collectfast.strategies.boto3.Boto3Strategy",
    ),
}
gcp_backends_confs = {
    "gcloud": override_django_settings(
        STATICFILES_STORAGE="storages.backends.gcloud.GoogleCloudStorage",
        COLLECTFAST_STRATEGY="collectfast.strategies.gcloud.GoogleCloudStrategy",
    ),
}
local_backend_confs = {
    "filesystem": override_django_settings(
        STATICFILES_STORAGE="django.core.files.storage.FileSystemStorage",
        COLLECTFAST_STRATEGY="collectfast.strategies.filesystem.FileSystemStrategy",
    ),
    "cachingfilesystem": override_django_settings(
        STATICFILES_STORAGE="django.core.files.storage.FileSystemStorage",
        COLLECTFAST_STRATEGY=(
            "collectfast.strategies.filesystem.CachingFileSystemStrategy"
        ),
    ),
}
all_backend_confs = {
    **aws_backend_confs,
    **gcp_backends_confs,
    **local_backend_confs
}

make_test_aws_backends = test_many(**aws_backend_confs)
make_test_gcp_backends = test_many(**gcp_backends_confs)
make_test_local_backends = test_many(**local_backend_confs)
make_test_all_backends = test_many(**all_backend_confs)


def check_bucket_exists(bucket_name):
    s3 = boto3.resource('s3')
    bucket_exists = True
    try:
        s3.meta.client.head_bucket(Bucket=bucket_name)
    except botocore.exceptions.ClientError as e:
        # If a client error is thrown, then check that it was a 404 error.
        # If it was a 404 error, then the bucket does not exist.
        error_code = int(e.response['Error']['Code'])
        if error_code == 404:
            bucket_exists = False
    return bucket_exists


@make_test_aws_backends
@mock_s3
def test_basics_aws(case: TestCase) -> None:
    bucket_name = 'collectfast'
    conn = boto3.resource('s3', region_name='us-east-1')
    # Create bucket
    conn.create_bucket(Bucket=bucket_name)
    case.assertTrue(
        expr=check_bucket_exists(bucket_name),
        msg=f"Bucket {bucket_name} does not exist."
    )
    clean_static_dir()
    create_static_file()
    case.assertIn("1 static file copied.", call_collectstatic())
    # file state should now be cached
    case.assertIn("0 static files copied.", call_collectstatic())


@make_test_gcp_backends
def test_basics_gcp(case: TestCase) -> None:
    bucket_name = "collectfast"
    storage = gcloud.GoogleCloudStorage(bucket_name=bucket_name)
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

    clean_static_dir()
    create_static_file()
    case.assertIn("1 static file copied.", call_collectstatic())
    # file state should now be cached
    case.assertIn("0 static files copied.", call_collectstatic())


@make_test_local_backends
@mock_s3
def test_basics_local(case: TestCase) -> None:
    clean_static_dir()
    create_static_file()
    case.assertIn("1 static file copied.", call_collectstatic())
    # file state should now be cached
    case.assertIn("0 static files copied.", call_collectstatic())


@make_test_aws_backends
@override_setting("threads", 5)
def test_threads_aws(case: TestCase) -> None:
    conn = boto3.resource('s3', region_name='us-east-1')
    # Create bucket
    conn.create_bucket(Bucket='collectfast')

    clean_static_dir()
    create_static_file()
    case.assertIn("1 static file copied.", call_collectstatic())
    # file state should now be cached
    case.assertIn("0 static files copied.", call_collectstatic())


@make_test_gcp_backends
@override_setting("threads", 5)
def test_threads_gcp(case: TestCase) -> None:
    bucket_name = "collectfast"
    storage = gcloud.GoogleCloudStorage(bucket_name=bucket_name)
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

    clean_static_dir()
    create_static_file()
    case.assertIn("1 static file copied.", call_collectstatic())
    # file state should now be cached
    case.assertIn("0 static files copied.", call_collectstatic())


@make_test_local_backends
@override_setting("threads", 5)
def test_threads_local(case: TestCase) -> None:
    clean_static_dir()
    create_static_file()
    case.assertIn("1 static file copied.", call_collectstatic())
    # file state should now be cached
    case.assertIn("0 static files copied.", call_collectstatic())


@make_test
def test_dry_run(case: TestCase) -> None:
    clean_static_dir()
    create_static_file()
    result = call_collectstatic(dry_run=True)
    case.assertIn("1 static file copied.", result)
    case.assertTrue("Pretending to copy", result)
    result = call_collectstatic(dry_run=True)
    case.assertIn("1 static file copied.", result)
    case.assertTrue("Pretending to copy", result)
    case.assertTrue("Pretending to delete", result)


@make_test_aws_backends
@override_storage_attr("gzip", True)
@override_setting("aws_is_gzipped", True)
@mock_s3
def test_aws_is_gzipped(case: TestCase) -> None:
    conn = boto3.resource('s3', region_name='us-east-1')
    # Create bucket
    conn.create_bucket(Bucket='collectfast')
    clean_static_dir()
    create_static_file()
    case.assertIn("1 static file copied.", call_collectstatic())
    # file state should now be cached
    case.assertIn("0 static files copied.", call_collectstatic())


@make_test
def test_raises_for_no_configured_strategy(case: TestCase) -> None:
    if hasattr(settings, 'STORAGES'):
        with override_django_settings(STORAGES={}, COLLECTFAST_STRATEGY=None):
            with case.assertRaises(ImproperlyConfigured):
                Command._load_strategy()
    else:
        with override_django_settings(STATICFILES_STORAGE=None, COLLECTFAST_STRATEGY=None):
            with case.assertRaises(ImproperlyConfigured):
                Command._load_strategy()


@make_test_aws_backends
@mock.patch("collectfast.strategies.base.Strategy.post_copy_hook", autospec=True)
def test_calls_post_copy_hook_aws(_case: TestCase,
                                  post_copy_hook: mock.MagicMock) -> None:
    conn = boto3.resource('s3', region_name='us-east-1')
    # Create bucket
    conn.create_bucket(Bucket='collectfast')
    clean_static_dir()
    path = create_static_file()
    cmd = Command()
    cmd.run_from_argv(["manage.py", "collectstatic", "--noinput"])
    post_copy_hook.assert_called_once_with(mock.ANY, path.name, path.name, mock.ANY)


@make_test_gcp_backends
@mock.patch("collectfast.strategies.base.Strategy.post_copy_hook", autospec=True)
def test_calls_post_copy_hook_gcp(_case: TestCase,
                                  post_copy_hook: mock.MagicMock) -> None:
    bucket_name = "collectfast"
    storage = gcloud.GoogleCloudStorage(bucket_name=bucket_name)
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

    clean_static_dir()
    path = create_static_file()
    cmd = Command()
    cmd.run_from_argv(["manage.py", "collectstatic", "--noinput"])
    post_copy_hook.assert_called_once_with(mock.ANY, path.name, path.name, mock.ANY)


@make_test_local_backends
@mock.patch("collectfast.strategies.base.Strategy.post_copy_hook", autospec=True)
def test_calls_post_copy_hook_local(_case: TestCase,
                                    post_copy_hook: mock.MagicMock) -> None:
    clean_static_dir()
    path = create_static_file()
    cmd = Command()
    cmd.run_from_argv(["manage.py", "collectstatic", "--noinput"])
    post_copy_hook.assert_called_once_with(mock.ANY, path.name, path.name, mock.ANY)


@make_test_aws_backends
@mock_s3
@mock.patch("collectfast.strategies.base.Strategy.on_skip_hook", autospec=True)
def test_calls_on_skip_hook_aws(_case: TestCase, on_skip_hook: mock.MagicMock) -> None:
    conn = boto3.resource('s3', region_name='us-east-1')
    # Create bucket
    conn.create_bucket(Bucket='collectfast')
    clean_static_dir()
    path = create_static_file()
    cmd = Command()
    cmd.run_from_argv(["manage.py", "collectstatic", "--noinput"])
    on_skip_hook.assert_not_called()
    cmd.run_from_argv(["manage.py", "collectstatic", "--noinput"])
    on_skip_hook.assert_called_once_with(mock.ANY, path.name, path.name, mock.ANY)


@make_test_gcp_backends
@mock_s3
@mock.patch("collectfast.strategies.base.Strategy.on_skip_hook", autospec=True)
def test_calls_on_skip_hook_gcp(_case: TestCase, on_skip_hook: mock.MagicMock) -> None:
    bucket_name = "collectfast"
    storage = gcloud.GoogleCloudStorage(bucket_name=bucket_name)
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

    clean_static_dir()
    path = create_static_file()
    cmd = Command()
    cmd.run_from_argv(["manage.py", "collectstatic", "--noinput"])
    on_skip_hook.assert_not_called()
    cmd.run_from_argv(["manage.py", "collectstatic", "--noinput"])
    on_skip_hook.assert_called_once_with(mock.ANY, path.name, path.name, mock.ANY)


@make_test_local_backends
@mock.patch("collectfast.strategies.base.Strategy.on_skip_hook", autospec=True)
def test_calls_on_skip_hook_local(_case: TestCase,
                                  on_skip_hook: mock.MagicMock) -> None:
    clean_static_dir()
    path = create_static_file()
    cmd = Command()
    cmd.run_from_argv(["manage.py", "collectstatic", "--noinput"])
    on_skip_hook.assert_not_called()
    cmd.run_from_argv(["manage.py", "collectstatic", "--noinput"])
    on_skip_hook.assert_called_once_with(mock.ANY, path.name, path.name, mock.ANY)
