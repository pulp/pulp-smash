import asyncio
import threading
import socket
import ssl
import time
import uuid
import urllib3

import trustme
import proxy
import pytest

from aiohttp import web
from yarl import URL

from pulp_smash import cli
from pulp_smash.api import _get_sleep_time
from pulp_smash.config import get_config
from pulp_smash.pulp3.bindings import delete_orphans, monitor_task
from pulp_smash.pulp3.fixture_utils import add_recording_route

from pulpcore.client.pulpcore import ApiClient, StatusApi, TasksApi
from pulpcore.client.pulpcore.exceptions import ApiException


cfg = get_config()
SLEEP_TIME = _get_sleep_time(cfg)
PULP_HOST = cfg.hosts[0]
PULP_SERVICES = ("pulpcore-content", "pulpcore-api", "pulpcore-worker@1", "pulpcore-worker@2")


def pytest_configure(config):
    config.addinivalue_line(
        "markers",
        "parallel: marks tests as safe to run in parallel",
    )
    config.addinivalue_line(
        "markers",
        "serial: marks tests as required to run serially without any other tests also running",
    )
    config.addinivalue_line(
        "markers",
        "nightly: marks tests as intended to run during the nightly CI run",
    )


class ThreadedAiohttpServer(threading.Thread):
    def __init__(self, shutdown_event, app, host, port, ssl_ctx):
        super().__init__()
        self.shutdown_event = shutdown_event
        self.app = app
        self.host = host
        self.port = port
        self.ssl_ctx = ssl_ctx

    def run(self):
        loop = asyncio.new_event_loop()
        runner = web.AppRunner(self.app)
        asyncio.set_event_loop(loop)
        loop.run_until_complete(runner.setup())
        site = web.TCPSite(runner, host=self.host, port=self.port, ssl_context=self.ssl_ctx)
        loop.run_until_complete(site.start())
        while True:
            loop.run_until_complete(asyncio.sleep(1))
            if self.shutdown_event.is_set():
                break


class ThreadedAiohttpServerData:
    def __init__(
        self,
        host,
        port,
        shutdown_event,
        thread,
        ssl_ctx,
        requests_record,
    ):
        self.host = host
        self.port = port
        self.shutdown_event = shutdown_event
        self.thread = thread
        self.ssl_ctx = ssl_ctx
        self.requests_record = requests_record

    def make_url(self, path):
        if path[0] != "/":
            raise ValueError("The `path` argument should start with a '/'")

        if self.ssl_ctx is None:
            protocol_handler = "http://"
        else:
            protocol_handler = "https://"

        return f"{protocol_handler}{self.host}:{self.port}{path}"


## Webserver Fixtures


@pytest.fixture
def unused_port():
    def _unused_port():
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.bind(("127.0.0.1", 0))
            return s.getsockname()[1]

    return _unused_port


@pytest.fixture
def gen_threaded_aiohttp_server(unused_port):
    fixture_servers_data = []

    def _gen_threaded_aiohttp_server(app, ssl_ctx, call_record):
        host = cfg.aiohttp_fixtures_origin
        port = unused_port()
        shutdown_event = threading.Event()
        fixture_server = ThreadedAiohttpServer(shutdown_event, app, host, port, ssl_ctx)
        fixture_server.daemon = True
        fixture_server.start()
        fixture_server_data = ThreadedAiohttpServerData(
            host=host,
            port=port,
            shutdown_event=shutdown_event,
            thread=fixture_server,
            requests_record=call_record,
            ssl_ctx=ssl_ctx,
        )
        fixture_servers_data.append(fixture_server_data)
        return fixture_server_data

    yield _gen_threaded_aiohttp_server

    for fixture_server_data in fixture_servers_data:
        fixture_server_data.shutdown_event.set()

    for fixture_server_data in fixture_servers_data:
        fixture_server_data.thread.join()


@pytest.fixture
def gen_fixture_server(gen_threaded_aiohttp_server):
    def _gen_fixture_server(fixtures_root, ssl_ctx):
        app = web.Application()
        call_record = add_recording_route(app, fixtures_root)
        return gen_threaded_aiohttp_server(app, ssl_ctx, call_record)

    yield _gen_fixture_server


## Proxy Fixtures


@pytest.fixture
def http_proxy(unused_port):
    host = cfg.aiohttp_fixtures_origin
    port = unused_port()
    proxypy_args = [
        "--num-workers",
        "4",
        "--hostname",
        host,
        "--port",
        str(port),
    ]

    proxy_data = ProxyData(host=host, port=port)

    with proxy.Proxy(input_args=proxypy_args):
        yield proxy_data


@pytest.fixture
def http_proxy_with_auth(unused_port):
    host = cfg.aiohttp_fixtures_origin
    port = unused_port()

    username = str(uuid.uuid4())
    password = str(uuid.uuid4())

    proxypy_args = [
        "--num-workers",
        "4",
        "--hostname",
        host,
        "--port",
        str(port),
        "--basic-auth",
        f"{username}:{password}",
    ]

    proxy_data = ProxyData(host=host, port=port, username=username, password=password)

    with proxy.Proxy(input_args=proxypy_args):
        yield proxy_data


@pytest.fixture
def https_proxy(unused_port, proxy_tls_certificate_pem_path):
    host = cfg.aiohttp_fixtures_origin
    port = unused_port()

    proxypy_args = [
        "--num-workers",
        "4",
        "--hostname",
        host,
        "--port",
        str(port),
        "--cert-file",
        proxy_tls_certificate_pem_path,  # contains both key and cert
        "--key-file",
        proxy_tls_certificate_pem_path,  # contains both key and cert
    ]

    proxy_data = ProxyData(host=host, port=port, ssl=True)  # TODO update me

    with proxy.Proxy(input_args=proxypy_args):
        yield proxy_data


class ProxyData:
    def __init__(self, *, host, port, username=None, password=None, ssl=False):
        self.host = host
        self.port = port

        self.username = username
        self.password = password

        self.ssl = ssl

        if ssl:
            scheme = "https"
        else:
            scheme = "http"

        self.proxy_url = str(
            URL.build(
                scheme=scheme,
                host=self.host,
                port=self.port,
            )
        )


# Infrastructure Fixtures


@pytest.fixture(scope="session")
def pulp_cfg():
    return cfg


@pytest.fixture(scope="session")
def bindings_cfg(pulp_cfg):
    return pulp_cfg.get_bindings_config()


@pytest.fixture(scope="session")
def cli_client(pulp_cfg):
    return cli.Client(pulp_cfg)


@pytest.fixture(scope="session")
def svc_mgr(pulp_cfg):
    return cli.ServiceManager(pulp_cfg, PULP_HOST)


@pytest.fixture
def stop_and_check_services(status_api_client, svc_mgr):
    """Stop services and wait up to 30 seconds to check if services have stopped."""

    def _stop_and_check_services(pulp_services=None):
        svc_mgr.stop(pulp_services or PULP_SERVICES)
        for i in range(10):
            time.sleep(3)
            try:
                status_api_client.status_read()
            except (urllib3.exceptions.MaxRetryError, ApiException):
                return True
        return False

    yield _stop_and_check_services


@pytest.fixture
def start_and_check_services(status_api_client, svc_mgr):
    """Start services and wait up to 30 seconds to check if services have started."""

    def _start_and_check_services(pulp_services=None):
        svc_mgr.start(pulp_services or PULP_SERVICES)
        for i in range(10):
            time.sleep(3)
            try:
                status, http_code, _ = status_api_client.status_read_with_http_info()
            except (urllib3.exceptions.MaxRetryError, ApiException):
                # API is not responding
                continue
            else:
                if (
                    http_code == 200
                    and len(status.online_workers) > 0
                    and len(status.online_content_apps) > 0
                    and status.database_connection.connected
                ):
                    return True
                else:
                    # sometimes it takes longer for the content app to start
                    continue
        return False

    yield _start_and_check_services


## Pulpcore Bindings Fixtures


@pytest.fixture(scope="session")
def pulpcore_client(bindings_cfg):
    return ApiClient(bindings_cfg)


@pytest.fixture(scope="session")
def tasks_api_client(pulpcore_client):
    return TasksApi(pulpcore_client)


try:
    from pulpcore.client.pulpcore import TaskSchedulesApi
except ImportError:

    @pytest.fixture(scope="session")
    def task_schedules_api_client():
        pytest.fail("`TaskSchedulesApi` is not available in the bindings.")

else:

    @pytest.fixture(scope="session")
    def task_schedules_api_client(pulpcore_client):
        return TaskSchedulesApi(pulpcore_client)


@pytest.fixture
def status_api_client(pulpcore_client):
    return StatusApi(pulpcore_client)


## Orphan Handling Fixtures


@pytest.fixture
def delete_orphans_pre():
    delete_orphans()
    yield


## Server Side TLS Fixtures


@pytest.fixture(scope="session")
def tls_certificate_authority():
    return trustme.CA()


@pytest.fixture
def tls_certificate_authority_cert(tls_certificate_authority):
    return tls_certificate_authority.cert_pem.bytes().decode()


@pytest.fixture
def tls_certificate(tls_certificate_authority):
    return tls_certificate_authority.issue_cert(
        cfg.aiohttp_fixtures_origin,
    )


## Proxy TLS Fixtures


@pytest.fixture(scope="session")
def proxy_tls_certificate_authority():
    return trustme.CA()


@pytest.fixture
def proxy_tls_certificate(client_tls_certificate_authority):
    return client_tls_certificate_authority.issue_cert(
        cfg.aiohttp_fixtures_origin,
    )


@pytest.fixture
def proxy_tls_certificate_pem_path(proxy_tls_certificate):
    with proxy_tls_certificate.private_key_and_cert_chain_pem.tempfile() as cert_pem:
        yield cert_pem


## Client Side TLS Fixtures


@pytest.fixture(scope="session")
def client_tls_certificate_authority():
    return trustme.CA()


@pytest.fixture
def client_tls_certificate_authority_pem_path(client_tls_certificate_authority):
    with client_tls_certificate_authority.cert_pem.tempfile() as client_ca_pem:
        yield client_ca_pem


@pytest.fixture
def client_tls_certificate(client_tls_certificate_authority):
    return client_tls_certificate_authority.issue_cert(
        cfg.aiohttp_fixtures_origin,
    )


@pytest.fixture
def client_tls_certificate_cert_pem(client_tls_certificate):
    return client_tls_certificate.cert_chain_pems[0].bytes().decode()


@pytest.fixture
def client_tls_certificate_key_pem(client_tls_certificate):
    return client_tls_certificate.private_key_pem.bytes().decode()


## SSL Context Fixtures


@pytest.fixture
def ssl_ctx(tls_certificate):
    ssl_ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    tls_certificate.configure_cert(ssl_ctx)
    return ssl_ctx


@pytest.fixture
def ssl_ctx_req_client_auth(
    tls_certificate, client_tls_certificate, client_tls_certificate_authority_pem_path
):
    ssl_ctx = ssl.create_default_context(
        purpose=ssl.Purpose.CLIENT_AUTH, cafile=client_tls_certificate_authority_pem_path
    )
    ssl_ctx.verify_mode = ssl.CERT_REQUIRED
    tls_certificate.configure_cert(ssl_ctx)
    return ssl_ctx


## Object Cleanup fixtures


@pytest.fixture
def gen_object_with_cleanup():
    obj_hrefs = []

    def _gen_object_with_cleanup(api_client, data):
        new_obj = api_client.create(data)
        try:
            obj_hrefs.append((api_client, new_obj.pulp_href))
        except AttributeError:
            # This is a task and the real object href comes from monitoring it
            task_data = monitor_task(new_obj.task)

            num_created_resources = len(task_data.created_resources)
            if num_created_resources != 1:
                msg = (
                    f"gen_object_with_cleanup can only handle tasks with exactly 1 "
                    f"created_resource. this task has f{num_created_resources}"
                )
                raise NotImplementedError(msg)

            new_obj = api_client.read(task_data.created_resources[0])
            obj_hrefs.append((api_client, new_obj.pulp_href))

        return new_obj

    yield _gen_object_with_cleanup

    delete_task_hrefs = []
    for api_client, pulp_href in obj_hrefs:
        task_url = api_client.delete(pulp_href).task
        delete_task_hrefs.append(task_url)

    for deleted_task_href in delete_task_hrefs:
        monitor_task(deleted_task_href)
