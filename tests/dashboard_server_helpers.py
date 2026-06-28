import http.client
import threading
import unittest
from contextlib import contextmanager
from urllib.parse import urlencode


class DashboardServerTestCase(unittest.TestCase):
    @contextmanager
    def serving(self, server):
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            yield server.server_address
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=1)

    def request(self, host, port, method, path, form=None):
        headers = {}
        body = None
        if form is not None:
            body = urlencode(form, doseq=True)
            headers["Content-Type"] = "application/x-www-form-urlencoded"
        connection = http.client.HTTPConnection(host, port, timeout=3)
        try:
            connection.request(method, path, body=body, headers=headers)
            response = connection.getresponse()
            payload = response.read().decode("utf-8")
            return response.status, response.getheader("Location"), payload
        finally:
            connection.close()

    def multipart_request(self, host, port, path, fields, files):
        boundary = "----memex-test-boundary"
        chunks = []
        for name, value in fields.items():
            chunks.extend(
                (
                    f"--{boundary}\r\n".encode("utf-8"),
                    f'Content-Disposition: form-data; name="{name}"\r\n\r\n'.encode("utf-8"),
                    str(value).encode("utf-8"),
                    b"\r\n",
                )
            )
        for name, (filename, content_type, data) in files.items():
            chunks.extend(
                (
                    f"--{boundary}\r\n".encode("utf-8"),
                    (
                        f'Content-Disposition: form-data; name="{name}"; filename="{filename}"\r\n'
                    ).encode("utf-8"),
                    f"Content-Type: {content_type}\r\n\r\n".encode("utf-8"),
                    data,
                    b"\r\n",
                )
            )
        chunks.append(f"--{boundary}--\r\n".encode("utf-8"))
        body = b"".join(chunks)
        headers = {"Content-Type": f"multipart/form-data; boundary={boundary}"}
        connection = http.client.HTTPConnection(host, port, timeout=3)
        try:
            connection.request("POST", path, body=body, headers=headers)
            response = connection.getresponse()
            payload = response.read().decode("utf-8")
            return response.status, response.getheader("Location"), payload
        finally:
            connection.close()
