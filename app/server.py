"""Local static workbench: python -X utf8 app/server.py [--port 8767]."""
import argparse
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote, urlsplit

STATIC = Path(__file__).resolve().parent / 'static'


class WorkbenchHandler(SimpleHTTPRequestHandler):
    extensions_map = {**SimpleHTTPRequestHandler.extensions_map,
                      '.js': 'text/javascript; charset=utf-8',
                      '.css': 'text/css; charset=utf-8',
                      '.html': 'text/html; charset=utf-8',
                      '.json': 'application/json; charset=utf-8'}

    def send_head(self):
        requested = unquote(urlsplit(self.path).path)
        target = (Path(self.directory) / requested.lstrip('/')).resolve()
        if not target.is_relative_to(Path(self.directory).resolve()):
            self.send_error(403)
            return None
        return super().send_head()

    def list_directory(self, path):
        self.send_error(404)
        return None

    def end_headers(self):
        self.send_header('Cache-Control', 'no-cache')
        self.send_header('X-Content-Type-Options', 'nosniff')
        super().end_headers()


def make_server(port=8767):
    return ThreadingHTTPServer(('127.0.0.1', port), partial(WorkbenchHandler, directory=str(STATIC)))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--port', type=int, default=8767)
    args = parser.parse_args()
    with make_server(args.port) as server:
        print(f'Open-Malti: http://127.0.0.1:{server.server_port}', flush=True)
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            pass


if __name__ == '__main__':
    main()
