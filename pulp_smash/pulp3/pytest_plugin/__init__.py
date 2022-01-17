import asyncio
import threading
import socket
import ssl

from aiohttp import web

import pytest
import trustme

from pulp_smash.api import _get_sleep_time
from pulp_smash.config import get_config
from pulp_smash.pulp3.bindings import delete_orphans, monitor_task
from pulp_smash.pulp3.fixture_utils import add_recording_route

from pulpcore.client.pulpcore import ApiClient, TasksApi


cfg = get_config()
SLEEP_TIME = _get_sleep_time(cfg)


def pytest_configure(config):
    config.addinivalue_line(
        "markers",
        "parallel: marks tests as safe to run in parallel",
    )
    config.addinivalue_line(
        "markers",
        "serial: marks tests as required to run serially without any other tests also running",
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


@pytest.fixture(scope="session")
def pulpcore_client():
    configuration = cfg.get_bindings_config()
    return ApiClient(configuration)


@pytest.fixture(scope="session")
def tasks_api_client(pulpcore_client):
    return TasksApi(pulpcore_client)


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
        obj_hrefs.append((api_client, new_obj.pulp_href))
        return new_obj

    yield _gen_object_with_cleanup

    delete_task_hrefs = []
    for api_client, pulp_href in obj_hrefs:
        task_url = api_client.delete(pulp_href).task
        delete_task_hrefs.append(task_url)

    for deleted_task_href in delete_task_hrefs:
        monitor_task(deleted_task_href)
