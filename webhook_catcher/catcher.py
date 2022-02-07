#!/usr/bin/env python3

import http.server
import json
import os
import os.path
import re
import signal

WRITE_FREQ = 100
VERSION = "1.01"

"""
An Endpoint represents a webhook endpoint.  They may be read to and written
to.  Writing stores more data referenced by the endpoing, and reading
returns all the data at the endpoint.  They have a read_key that
acts as their id when wanting to read.  They have a write_key that acts
as their id when wanting to write to them.  The keys act as methods for
simple authentication, and this way if someone has permission to write,
they cannot necessarily read.  They correspond to a file in a directory
named the same as the read_key.  They buffer writes up to the WRITE_FREQ.
""" 
class Endpoint:
    def __init__(self, write_key, read_key, write_dir, max_file_lines):
        self.write_key = write_key
        self.read_key = read_key
        self.write_dir = write_dir
        self.write_file = os.path.join(self.write_dir, self.read_key)
        self.max_file_lines = max_file_lines
        self.count = 0
        self.read_file()

    # Read all the file data into the buffer, replacing current buffer
    def read_file(self):
        try:
            with open(self.write_file, "r") as fin:
                self.cur_lines = json.loads(fin.read())
        except FileNotFoundError:
            self.cur_lines = list()

    # Save some data, buffered
    def write(self, out_obj):
        self.cur_lines.append(out_obj)
        self.count += 1
        self.cur_lines = self.cur_lines[-self.max_file_lines:]
        
        if self.count % WRITE_FREQ == 0:
            self.safe()

        return True

    # Return all buffered data
    def read(self):
        return self.cur_lines

    # Make sure all data is written out
    def safe(self):
        with open(self.write_file, "w") as fin:
            fin.write(json.dumps(self.cur_lines))

# Endpoints keeps track of every Endpoint.
class Endpoints:
    def __init__(self, endpoint_list):
        self.endpoint_dict = {pt.write_key: pt for pt in endpoint_list}
        self.endpoint_dict_read = {pt.read_key: pt for pt in endpoint_list}

    # Write to a specific Endpoint, represented by its write_key
    def write(self, write_key, out_obj):
        if write_key in self.endpoint_dict:
            return self.endpoint_dict[write_key].write(out_obj)
        else:
            return False

    # Read from a specific Endpoint, based on read_key
    def read(self, read_key):
        if read_key in self.endpoint_dict_read:
            return self.endpoint_dict_read[read_key].read()
        else:
            return None

    # Make sure all Endpoints are written out
    def safe_all(self):
        for key, val in self.endpoint_dict.items():
            val.safe()

# Webserver for webhooks
class WebhookHandler(http.server.BaseHTTPRequestHandler):
    url_base = None
    endpoints = None

    def check_setup(self):
        if self.url_base is None or self.endpoints is None:
            raise RuntimeError("WebhookHandler properties not set...")

    # Handle a write
    def do_POST(self):
        self.check_setup()
    
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

    # Handle a read
    def do_GET(self):
        self.check_setup()

        if self.path == f"/{self.url_base}/version/":
            self.send_response(200, VERSION)
            self.end_headers()
            return
    
        pattern = f"^/{self.url_base}/get/(.*)$"
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

        read_key = path_match.groups()[0]

        out_obj = self.endpoints.read(read_key)
        
        if out_obj is None:
            self.log_error(f"Endpoint read fail: {read_key}")
            self.send_response(400, "Bad Request")
            self.end_headers()
            return

        self.send_response(200)
        self.send_header("Content-type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(json.dumps(out_obj).encode("utf-8"))

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
    def server_term_func(signum, frame):
        thr = threading.Thread(target=lambda: server.shutdown())
        thr.run()
        thr.join()
    signal.signal(signal.SIGTERM, server_term_func)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    except BaseException as exc:
        pass
    server.server_close()

    endpoints.safe_all()
