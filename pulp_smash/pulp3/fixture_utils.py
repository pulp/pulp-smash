from aiohttp import web
from multidict import CIMultiDict


def add_file_system_route(app, fixtures_root):
    new_routes = [web.static("/", fixtures_root.absolute(), show_index=True)]
    app.add_routes(new_routes)


def add_recording_route(app, fixtures_root):
    requests = []

    async def all_requests_handler(request):
        requests.append(request)
        path = fixtures_root / request.raw_path[1:]  # Strip off leading '/'
        if path.is_file():
            return web.FileResponse(
                path, headers=CIMultiDict({"content-type": "application/octet-stream"})
            )
        else:
            raise web.HTTPNotFound()

    app.add_routes([web.get("/{tail:.*}", all_requests_handler)])

    return requests
