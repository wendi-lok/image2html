import os
import sys
import json
import uuid
import time
import urllib.request
import urllib.parse
import urllib.error
import webbrowser
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
from io import BytesIO
import ssl

# PyInstaller: bundled read-only files are extracted to sys._MEIPASS
if getattr(sys, 'frozen', False):
    BUNDLE_DIR = sys._MEIPASS
else:
    BUNDLE_DIR = os.path.dirname(os.path.abspath(__file__))

# User-writable data lives next to the exe (or script in dev mode)
USER_DIR = os.path.dirname(os.path.abspath(sys.argv[0])) if getattr(sys, 'frozen', False) else BUNDLE_DIR

TEMPLATES_DIR = os.path.join(BUNDLE_DIR, 'templates')
UPLOADS_DIR = os.path.join(USER_DIR, 'uploads')
OUTPUTS_DIR = os.path.join(USER_DIR, 'outputs')
DATA_DIR = os.path.join(USER_DIR, 'data')
CONFIG_PATH = os.path.join(DATA_DIR, 'config.json')
HISTORY_PATH = os.path.join(DATA_DIR, 'history.json')

SUBMIT_TASK_URL = "https://api.wuyinkeji.com/api/async/image_gpt"
GET_RESULT_URL = "https://api.wuyinkeji.com/api/async/detail"
REQUEST_TIMEOUT = 30

for d in [UPLOADS_DIR, OUTPUTS_DIR, DATA_DIR]:
    os.makedirs(d, exist_ok=True)

MIME_TYPES = {
    '.html': 'text/html; charset=utf-8',
    '.css': 'text/css; charset=utf-8',
    '.js': 'application/javascript; charset=utf-8',
    '.json': 'application/json; charset=utf-8',
    '.png': 'image/png',
    '.jpg': 'image/jpeg',
    '.jpeg': 'image/jpeg',
    '.gif': 'image/gif',
    '.webp': 'image/webp',
    '.ico': 'image/x-icon',
    '.svg': 'image/svg+xml',
}


def load_json(path, default=None):
    if default is None:
        default = {}
    if not os.path.exists(path):
        return default
    try:
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception:
        return default


def save_json_file(path, data):
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def http_request(url, method='GET', data=None, headers=None, timeout=30):
    if headers is None:
        headers = {}
    if data is not None and isinstance(data, dict):
        data = json.dumps(data).encode('utf-8')
        headers['Content-Type'] = 'application/json'
    elif data is not None and isinstance(data, str):
        data = data.encode('utf-8')

    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        ctx = ssl.create_default_context()
        resp = urllib.request.urlopen(req, timeout=timeout, context=ctx)
        return resp.status, resp.read(), dict(resp.headers)
    except urllib.error.HTTPError as e:
        return e.code, e.read(), dict(e.headers)
    except Exception as e:
        raise


class AppHandler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        pass

    def send_json(self, data, status=200):
        body = json.dumps(data, ensure_ascii=False).encode('utf-8')
        self.send_response(status)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Content-Length', str(len(body)))
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        self.wfile.write(body)

    def send_html_file(self, filepath):
        if not os.path.exists(filepath):
            self.send_error(404)
            return
        with open(filepath, 'rb') as f:
            content = f.read()
        ext = os.path.splitext(filepath)[1]
        mime = MIME_TYPES.get(ext, 'application/octet-stream')
        self.send_response(200)
        self.send_header('Content-Type', mime)
        self.send_header('Content-Length', str(len(content)))
        self.end_headers()
        self.wfile.write(content)

    def send_static_file(self, filepath, base_dir):
        full = os.path.normpath(os.path.join(base_dir, filepath))
        if not full.startswith(os.path.normpath(base_dir)):
            self.send_error(403)
            return
        if not os.path.exists(full):
            self.send_error(404)
            return
        with open(full, 'rb') as f:
            content = f.read()
        ext = os.path.splitext(full)[1]
        mime = MIME_TYPES.get(ext, 'application/octet-stream')
        self.send_response(200)
        self.send_header('Content-Type', mime)
        self.send_header('Content-Length', str(len(content)))
        self.end_headers()
        self.wfile.write(content)

    def read_body(self):
        length = int(self.headers.get('Content-Length', 0))
        if length == 0:
            return b''
        return self.rfile.read(length)

    def read_json(self):
        body = self.read_body()
        if not body:
            return {}
        return json.loads(body.decode('utf-8'))

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, PUT, DELETE, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        path = urllib.parse.unquote(parsed.path)
        query = urllib.parse.parse_qs(parsed.query)

        if path == '/':
            return self.send_html_file(os.path.join(TEMPLATES_DIR, 'index.html'))

        if path.startswith('/uploads/'):
            filename = path[len('/uploads/'):]
            return self.send_static_file(filename, UPLOADS_DIR)

        if path.startswith('/outputs/'):
            filename = path[len('/outputs/'):]
            return self.send_static_file(filename, OUTPUTS_DIR)

        if path == '/api/config':
            return self.handle_get_config()

        if path == '/api/history':
            return self.handle_get_history()

        if path.startswith('/api/task/'):
            task_id = path[len('/api/task/'):]
            return self.handle_query_task(task_id)

        self.send_error(404)

    def do_POST(self):
        parsed = urllib.parse.urlparse(self.path)
        path = urllib.parse.unquote(parsed.path)

        if path == '/api/config':
            return self.handle_set_config()

        if path == '/api/upload':
            return self.handle_upload()

        if path == '/api/generate':
            return self.handle_generate()

        if path == '/api/save-image':
            return self.handle_save_image()

        if path == '/api/history':
            return self.handle_add_history()

        self.send_error(404)

    def do_PUT(self):
        parsed = urllib.parse.urlparse(self.path)
        path = urllib.parse.unquote(parsed.path)

        if path.startswith('/api/history/'):
            record_id = path[len('/api/history/'):]
            return self.handle_update_history(record_id)

        self.send_error(404)

    def do_DELETE(self):
        parsed = urllib.parse.urlparse(self.path)
        path = urllib.parse.unquote(parsed.path)

        if path.startswith('/api/history/'):
            record_id = path[len('/api/history/'):]
            return self.handle_delete_history(record_id)

        self.send_error(404)

    def handle_get_config(self):
        cfg = load_json(CONFIG_PATH, {"api_key": ""})
        key = cfg.get('api_key', '')
        if len(key) > 8:
            masked = key[:4] + '****' + key[-4:]
        elif key:
            masked = '****'
        else:
            masked = ''
        self.send_json({"api_key": key, "masked": masked})

    def handle_set_config(self):
        data = self.read_json()
        api_key = data.get('api_key', '').strip()
        if not api_key:
            return self.send_json({"error": "API key cannot be empty"}, 400)
        cfg = load_json(CONFIG_PATH, {"api_key": ""})
        cfg['api_key'] = api_key
        save_json_file(CONFIG_PATH, cfg)
        if len(api_key) > 8:
            masked = api_key[:4] + '****' + api_key[-4:]
        else:
            masked = '****'
        self.send_json({"success": True, "masked": masked})

    def parse_multipart(self):
        content_type = self.headers.get('Content-Type', '')
        if 'multipart/form-data' not in content_type:
            return None, None

        boundary = None
        for part in content_type.split(';'):
            part = part.strip()
            if part.startswith('boundary='):
                boundary = part.split('=', 1)[1].strip().strip('"')
                break

        if not boundary:
            return None, None

        length = int(self.headers.get('Content-Length', 0))
        body = self.rfile.read(length)

        boundary_bytes = boundary.encode('utf-8')
        parts = body.split(b'--' + boundary_bytes)

        filename = None
        file_data = None

        for part in parts:
            if not part or part.strip() == b'' or part.strip() == b'--':
                continue

            if b'\r\n\r\n' not in part:
                continue

            header_section, file_data = part.split(b'\r\n\r\n', 1)
            if file_data.endswith(b'\r\n'):
                file_data = file_data[:-2]

            header_str = header_section.decode('utf-8', errors='replace')
            for line in header_str.split('\r\n'):
                if 'Content-Disposition' in line and 'filename=' in line:
                    for token in line.split(';'):
                        token = token.strip()
                        if token.startswith('filename='):
                            filename = token.split('=', 1)[1].strip().strip('"')
                            break

        return filename, file_data

    def handle_upload(self):
        content_type = self.headers.get('Content-Type', '')
        if 'multipart/form-data' not in content_type:
            return self.send_json({"error": "Expected multipart/form-data"}, 400)

        filename, file_data = self.parse_multipart()

        if not filename or not file_data:
            return self.send_json({"error": "No file selected"}, 400)

        ext = os.path.splitext(filename)[1].lower()
        if ext not in ('.jpg', '.jpeg', '.png', '.gif', '.webp', '.bmp'):
            return self.send_json({"error": "Unsupported image format"}, 400)

        new_filename = f"{uuid.uuid4().hex}{ext}"
        filepath = os.path.join(UPLOADS_DIR, new_filename)
        with open(filepath, 'wb') as f:
            f.write(file_data)

        host = self.headers.get('Host', 'localhost:5000')
        url = f"http://{host}/uploads/{new_filename}"
        self.send_json({"url": url, "filename": new_filename})

    def handle_generate(self):
        cfg = load_json(CONFIG_PATH, {"api_key": ""})
        api_key = cfg.get('api_key', '').strip()
        if not api_key:
            return self.send_json({"error": "API key not set"}, 400)

        data = self.read_json()
        prompt = data.get('prompt', '').strip()
        if not prompt:
            return self.send_json({"error": "Prompt is required"}, 400)

        size = data.get('size', 'auto')
        urls = data.get('urls', [])

        headers = {
            "Authorization": api_key,
            "Content-Type": "application/json"
        }
        params = {"key": api_key}
        body = {"prompt": prompt, "size": size, "urls": urls}

        try:
            sep = '&' if '?' in SUBMIT_TASK_URL else '?'
            url = SUBMIT_TASK_URL + sep + urllib.parse.urlencode(params)
            status, resp_body, _ = http_request(url, method='POST', data=body, headers=headers, timeout=REQUEST_TIMEOUT)
            result = json.loads(resp_body.decode('utf-8'))

            if result.get('code') == 200:
                task_id = result.get('data', {}).get('id', '')
                return self.send_json({"success": True, "task_id": task_id})
            else:
                return self.send_json({
                    "error": result.get('msg', 'Unknown error'),
                    "code": result.get('code')
                }, 400)

        except urllib.error.URLError:
            return self.send_json({"error": "Network connection failed"}, 502)
        except TimeoutError:
            return self.send_json({"error": "Request timeout"}, 504)
        except Exception as e:
            return self.send_json({"error": f"Unexpected error: {str(e)}"}, 500)

    def handle_query_task(self, task_id):
        cfg = load_json(CONFIG_PATH, {"api_key": ""})
        api_key = cfg.get('api_key', '').strip()
        if not api_key:
            return self.send_json({"error": "API key not set"}, 400)

        params = {"key": api_key, "id": task_id}
        try:
            url = GET_RESULT_URL + '?' + urllib.parse.urlencode(params)
            status, resp_body, _ = http_request(url, method='GET', timeout=REQUEST_TIMEOUT)
            result = json.loads(resp_body.decode('utf-8'))

            if result.get('code') != 200:
                return self.send_json({
                    "error": result.get('msg', 'Query failed'),
                    "code": result.get('code')
                }, 400)

            task_data = result.get('data', {})
            raw_status = task_data.get('status', 1)
            try:
                status_code = int(raw_status)
            except (ValueError, TypeError):
                status_code = 1
            # status 0 = queued (treat as in-progress), 1 = generating, 2 = success, others = error
            if status_code == 0:
                status_code = 1
            return self.send_json({
                "status": status_code,
                "result_urls": task_data.get('result', []),
                "message": task_data.get('message', '')
            })

        except Exception as e:
            return self.send_json({"error": f"Query error: {str(e)}"}, 500)

    def handle_save_image(self):
        data = self.read_json()
        url = data.get('url', '')
        if not url:
            return self.send_json({"error": "URL is required"}, 400)

        try:
            status, resp_body, headers = http_request(url, method='GET', timeout=30)
            content_type = headers.get('Content-Type', '')
            ext = '.png'
            if 'jpeg' in content_type or 'jpg' in content_type:
                ext = '.jpg'
            elif 'webp' in content_type:
                ext = '.webp'
            elif 'gif' in content_type:
                ext = '.gif'

            filename = f"{uuid.uuid4().hex}{ext}"
            filepath = os.path.join(OUTPUTS_DIR, filename)
            with open(filepath, 'wb') as f:
                f.write(resp_body)

            return self.send_json({
                "success": True,
                "filename": filename,
                "local_url": f'outputs/{filename}'
            })

        except Exception as e:
            return self.send_json({"error": f"Failed to save: {str(e)}"}, 500)

    def handle_get_history(self):
        history = load_json(HISTORY_PATH, {"records": []})
        self.send_json(history)

    def handle_add_history(self):
        data = self.read_json()
        history = load_json(HISTORY_PATH, {"records": []})
        records = history.get('records', [])

        record = {
            "id": data.get('id', str(uuid.uuid4())),
            "task_id": data.get('task_id', ''),
            "prompt": data.get('prompt', ''),
            "size": data.get('size', 'auto'),
            "reference_urls": data.get('reference_urls', []),
            "result_urls": data.get('result_urls', []),
            "local_images": data.get('local_images', []),
            "created_at": data.get('created_at', time.strftime('%Y-%m-%dT%H:%M:%S')),
            "status": data.get('status', 'pending')
        }
        records.insert(0, record)
        history['records'] = records
        save_json_file(HISTORY_PATH, history)
        self.send_json({"success": True, "record": record})

    def handle_update_history(self, record_id):
        data = self.read_json()
        history = load_json(HISTORY_PATH, {"records": []})
        records = history.get('records', [])

        for i, r in enumerate(records):
            if r.get('id') == record_id or r.get('task_id') == record_id:
                records[i].update(data)
                history['records'] = records
                save_json_file(HISTORY_PATH, history)
                return self.send_json({"success": True, "record": records[i]})

        self.send_json({"error": "Record not found"}, 404)

    def handle_delete_history(self, record_id):
        history = load_json(HISTORY_PATH, {"records": []})
        records = history.get('records', [])
        history['records'] = [r for r in records if r.get('id') != record_id and r.get('task_id') != record_id]
        save_json_file(HISTORY_PATH, history)
        self.send_json({"success": True})


def open_browser(port):
    """延迟1秒后自动打开浏览器"""
    time.sleep(1)
    webbrowser.open(f'http://localhost:{port}')


def main():
    host = '0.0.0.0'
    port = 5000
    server = HTTPServer((host, port), AppHandler)
    print(f"Image2Html server running at http://localhost:{port}", flush=True)
    print("Press Ctrl+C to stop.", flush=True)
    print("Browser will open automatically. If not, visit the URL above.", flush=True)
    threading.Thread(target=open_browser, args=(port,), daemon=True).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nServer stopped.")
        server.server_close()


if __name__ == '__main__':
    main()
