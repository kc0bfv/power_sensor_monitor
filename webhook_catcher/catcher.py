#!/usr/bin/env python3

import http.server
import json
import os
import os.path
import re

class Endpoint:
    def __init__(self, write_key, read_key, write_dir, max_file_lines):
        self.write_key = write_key
        self.read_key = read_key
        self.write_dir = write_dir
        self.write_file = os.path.join(self.write_dir, self.read_key)
        self.max_file_lines = max_file_lines
        self.cur_lines = None
    def write(self, out_obj):
        if self.cur_lines is None:
            try:
                with open(self.write_file, "r") as fin:
                    self.cur_lines = json.loads(fin.read())
            except FileNotFoundError:
                self.cur_lines = list()
        self.cur_lines.append(out_obj)
        self.cur_lines = self.cur_lines[-self.max_file_lines:]
        with open(self.write_file, "w") as fin:
            fin.write(json.dumps(self.cur_lines))
        return True

class Endpoints:
    def __init__(self, endpoint_list):
        self.endpoint_dict = {pt.write_key: pt for pt in endpoint_list}

    def write(self, write_key, out_obj):
        if write_key in self.endpoint_dict:
            return self.endpoint_dict[write_key].write(out_obj)
        else:
            return False

class WebhookHandler(http.server.BaseHTTPRequestHandler):
    url_base = None
    endpoints = None

    def do_POST(self):
        if self.url_base is None or self.endpoints is None:
            raise RuntimeError("WebhookHandler properties not set...")

        pattern = f"^/{self.url_base}/(.*)$"
        path_match = re.fullmatch(pattern, self.path)

        if path_match is None:
            self.log_error(f"Path match failed: {self.path}")
            self.send_response(400, "Bad Request")
            self.end_headers()
            return

        if len(path_match.groups()) != 1:
            self.log_error(f"No groups matched: {self.path}")
            self.send_response(400, "Bad Request")
            self.end_headers()
            return

        write_key = path_match.groups()[0]

        content_length = int(self.headers['Content-Length'])
        content = self.rfile.read(content_length)

        try:
            in_data = json.loads(content)
        except json.decoder.JSONDecodeError as exc:
            self.log_error(f"Bad JSON decode: {content}")
            self.send_response(400, "Bad Request")
            self.end_headers()
            return
        except BaseException as exc:
            self.log_error(f"JSON loads exc: {exc}")
            self.send_response(400, "Bad Request")
            self.end_headers()
            return

        try:
            out_obj = {"published_at": in_data["published_at"], "data": in_data["data"]}
        except KeyError as exc:
            self.log_error(f"Wrong data format: {in_data}")
            self.send_response(400, "Bad Request")
            self.end_headers()
            return
        except BaseException as exc:
            self.log_error(f"Data format exc: {exc}")
            self.send_response(400, "Bad Request")
            self.end_headers()
            return

        write_ret = self.endpoints.write(write_key, out_obj)

        if not write_ret:
            self.log_error(f"Endpoint write fail: {write_key}")
            self.send_response(400, "Bad Request")
            self.end_headers()
            return

        self.send_response(200, "Success")
        self.end_headers()

if __name__ == "__main__":
    port = int(os.environ.get("PORT","8080"))
    host = os.environ.get("HOST","")
    url_base = os.environ.get("URL_BASE","webhook")
    write_key = os.environ.get("WRITE_KEY","itH9FLjtECHsxYWXJ7gi")
    read_key = os.environ.get("READ_KEY","uXXa2TtQavZWApSj3amg")
    write_dir = os.environ.get("WRITE_DIR","temp_dir")
    hist_len = int(os.environ.get("HIST_LEN","1000"))

    endpoint_list = [
        Endpoint(write_key, read_key, write_dir, hist_len)
    ]
    endpoints = Endpoints(endpoint_list)

    WebhookHandler.url_base = url_base
    WebhookHandler.endpoints = endpoints

    server = http.server.ThreadingHTTPServer((host, port), WebhookHandler)
    server.serve_forever()
