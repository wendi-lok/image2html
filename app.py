import os
import sys
import json
import uuid
import time
import base64
import socket
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
if getattr(sys, 'frozen', False):
    # sys.executable is always the real .exe path when frozen
    USER_DIR = os.path.dirname(os.path.abspath(sys.executable))
else:
    USER_DIR = BUNDLE_DIR

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


# =====================================================================
# 图床模块 —— 把本地参考图转成公网可访问 URL
#
# 速创 API 的 urls 参数只接受公网 URL，本地 http://localhost/... 它抓不到，
# 所以本地上传的图片必须先传到图床。免费的匿名图床 API 这两年基本都关掉了
# （sm.ms 需 token、ImgURL 需 uid+token、cdnjson 需 key、0x0.st 已停服），
# 因此这里做成「适配器链」：按顺序逐个尝试，谁先成功就用谁，
# 全部失败再回退成原来的本地 URL，保证功能不会整体挂掉。
# =====================================================================

# 适配器：key -> 元信息
# need     需要用户额外配置什么（none = 免注册直接可用）
# timeout  单次请求超时（免注册的兜底图床给短一点，避免整体太慢）
IMAGE_HOSTS = {
    'uapis':     {'name': 'UAPI',      'need': 'none',      'tip': 'uapis.cn 国内图床，免注册即可用（访客每日 10 张；填 Key 可不限量）',
                  'timeout': 30},
    'picui':     {'name': 'PicUI',     'need': 'token',     'tip': 'https://picui.cn 注册后在「个人设置」取 Token（国内图床，更稳定）',
                  'timeout': 60},
    'smms':      {'name': 'SM.MS',     'need': 'token',     'tip': 'https://sm.ms 注册后在 Dashboard 取 API Token（接口已迁移到 s.ee）',
                  'timeout': 60},
    'imgurl':    {'name': 'ImgURL',    'need': 'uid+token', 'tip': 'https://www.imgurl.org 注册后在个人中心取 UID 与 Token',
                  'timeout': 60},
    'imgbb':     {'name': 'ImgBB',     'need': 'token',     'tip': 'https://api.imgbb.com 免费申请 API Key',
                  'timeout': 60},
    'catbox':    {'name': 'Catbox',    'need': 'none',      'tip': '免注册，永久保存（海外）',
                  'timeout': 20},
    'uguu':      {'name': 'Uguu',      'need': 'none',      'tip': '免注册，但链接仅保留约 3 小时（海外）',
                  'timeout': 20, 'expire': '该图床链接仅保留约 3 小时，生成前若已过期会抓不到图'},
    'telegraph': {'name': 'Telegraph', 'need': 'none',      'tip': '免注册（海外，部分国内网络不可达）',
                  'timeout': 20},
}

# 自动模式下的尝试顺序：先试免注册的国内图床，再试已配置凭据的，
# 最后才用海外兜底（海外图床国内直连不稳，速创服务器也可能抓不到）
AUTO_ORDER = ['uapis', 'picui', 'smms', 'imgurl', 'imgbb', 'catbox', 'uguu', 'telegraph']

HOST_CHOICES = ['auto', 'local'] + AUTO_ORDER

AUTO_TIP = ('自动模式：按顺序尝试可用图床，第一张成功即用。免注册的 UAPI 默认可用；'
            '填了 Token 的图床会被优先尝试。全部失败才退回本地地址。')
LOCAL_TIP = '仅本地：不上传图床。参考图会以本地地址提交，速创服务器通常抓不到，只建议在调试时使用。'


def host_ready(key, cfg):
    """当前配置是否满足调用该图床的条件（免注册图床恒为 True）"""
    need = IMAGE_HOSTS.get(key, {}).get('need')
    if need == 'none':
        return True
    token = (cfg.get('host_token') or '').strip()
    if need == 'token':
        return bool(token)
    if need == 'uid+token':
        return bool(token)
    return False


def encode_multipart(fields, files, boundary=None):
    """构造 multipart/form-data 请求体。标准库没有现成实现，自己拼。

    fields: dict[str, str]
    files:  list[tuple[name, filename, bytes]]
    返回 (body_bytes, content_type)
    """
    if boundary is None:
        boundary = '----Image2HtmlBoundary' + uuid.uuid4().hex
    bb = boundary.encode('ascii')
    out = []
    for key, val in (fields or {}).items():
        out.append(b'--' + bb)
        out.append(('Content-Disposition: form-data; name="%s"' % key).encode('utf-8'))
        out.append(b'')
        out.append(str(val).encode('utf-8'))
    for fname_field, fname, content in (files or []):
        out.append(b'--' + bb)
        out.append(('Content-Disposition: form-data; name="%s"; filename="%s"'
                    % (fname_field, fname)).encode('utf-8'))
        out.append(b'Content-Type: application/octet-stream')
        out.append(b'')
        out.append(content)
    out.append(b'--' + bb + b'--')
    out.append(b'')
    return b'\r\n'.join(out), 'multipart/form-data; boundary=' + boundary


def _json_or_text(body):
    text = body.decode('utf-8', errors='replace').strip()
    try:
        return json.loads(text), text
    except Exception:
        return None, text


def _pick(obj, path):
    """按 'a.b.c' 取嵌套字段，取不到返回 None"""
    cur = obj
    for part in path.split('.'):
        if isinstance(cur, dict):
            cur = cur.get(part)
        elif isinstance(cur, list) and part.isdigit() and int(part) < len(cur):
            cur = cur[int(part)]
        else:
            return None
    return cur if isinstance(cur, str) and cur.startswith('http') else None


def upload_to_host(host_key, filename, data, cfg):
    """调用单个图床，返回 (url, error_msg)"""
    token = (cfg.get('host_token') or '').strip()
    uid = (cfg.get('host_uid') or '').strip()
    timeout = IMAGE_HOSTS.get(host_key, {}).get('timeout', 60)

    if host_key == 'uapis':
        # 国内免注册图床，POST 一个 multipart 就返回直链
        # 匿名访客每日限 10 次；填了 Key 则不限（Key 走 Authorization: Bearer）
        body, ctype = encode_multipart({}, [('file', filename, data)])
        headers = {'Content-Type': ctype, 'Accept': 'application/json'}
        if token:
            headers['Authorization'] = 'Bearer ' + token
        st, resp, _ = http_request('https://uapis.cn/api/v1/image/upload', 'POST',
                                   body, headers, timeout)
        js, text = _json_or_text(resp)
        if isinstance(js, dict):
            url = _pick(js, 'url') or _pick(js, 'data.url')
            if url:
                return url, None
            return None, js.get('message') or js.get('msg') or ('HTTP %s' % st)
        return None, 'HTTP %s' % st

    if host_key == 'smms':
        if not token:
            return None, 'SM.MS 需要 token'
        headers = {'Authorization': token}
        body, ctype = encode_multipart({}, [('smfile', filename, data)])
        headers['Content-Type'] = ctype
        # 2024 年起 sm.ms 的上传接口迁移到了 s.ee，这里两个都试
        last_err = None
        for endpoint in ('https://s.ee/api/v1/file/upload',
                         'https://sm.ms/api/v2/upload'):
            try:
                st, resp, _ = http_request(endpoint, 'POST', body, dict(headers), timeout)
            except Exception as e:
                last_err = '%s: %s' % (type(e).__name__, e)
                continue
            js, text = _json_or_text(resp)
            if isinstance(js, dict):
                url = _pick(js, 'data.url') or _pick(js, 'data.links.url')
                if js.get('code') == 200 and url:
                    return url, None
                if js.get('success') and url:
                    return url, None
                # 同一张图重复上传时直接返回已有的 URL
                if js.get('code') == 'image_repeated' and js.get('images'):
                    return js['images'], None
                last_err = js.get('message') or js.get('msg') or ('HTTP %s' % st)
            else:
                last_err = 'HTTP %s' % st
        return None, last_err

    if host_key == 'imgurl':
        if not token:
            return None, 'ImgURL 需要 uid 和 token'
        body, ctype = encode_multipart({'uid': uid, 'token': token},
                                       [('file', filename, data)])
        st, resp, _ = http_request('https://www.imgurl.org/api/v2/upload', 'POST',
                                   body, {'Content-Type': ctype}, timeout)
        js, text = _json_or_text(resp)
        if isinstance(js, dict):
            url = _pick(js, 'data.url') or _pick(js, 'data.links.url')
            if js.get('code') == 200 and url:
                return url, None
            return None, js.get('msg') or ('HTTP %s' % st)
        return None, 'HTTP %s' % st

    if host_key == 'picui':
        if not token:
            return None, 'PicUI 需要 token'
        body, ctype = encode_multipart({}, [('file', filename, data)])
        headers = {'Content-Type': ctype, 'Authorization': 'Bearer ' + token,
                   'Accept': 'application/json'}
        st, resp, _ = http_request('https://picui.cn/api/v1/upload', 'POST', body, headers, timeout)
        js, text = _json_or_text(resp)
        if isinstance(js, dict):
            url = _pick(js, 'data.links.url') or _pick(js, 'data.url')
            if js.get('status') and url:
                return url, None
            return None, js.get('message') or js.get('msg') or ('HTTP %s' % st)
        return None, 'HTTP %s' % st

    if host_key == 'imgbb':
        if not token:
            return None, 'ImgBB 需要 API Key'
        b64 = base64.b64encode(data).decode('ascii')
        body, ctype = encode_multipart({'image': b64}, [])
        st, resp, _ = http_request('https://api.imgbb.com/1/upload?key=' + urllib.parse.quote(token),
                                   'POST', body, {'Content-Type': ctype}, timeout)
        js, text = _json_or_text(resp)
        if isinstance(js, dict):
            url = _pick(js, 'data.url') or _pick(js, 'data.image.url')
            if url and js.get('success', True):
                return url, None
            return None, _pick(js, 'error.message') or js.get('message') or ('HTTP %s' % st)
        return None, 'HTTP %s' % st

    if host_key == 'catbox':
        body, ctype = encode_multipart({'reqtype': 'fileupload'},
                                       [('fileToUpload', filename, data)])
        st, resp, _ = http_request('https://catbox.moe/user/api.php', 'POST',
                                   body, {'Content-Type': ctype}, timeout)
        text = resp.decode('utf-8', errors='replace').strip()
        if text.startswith('http'):
            return text, None
        return None, text[:120] or ('HTTP %s' % st)

    if host_key == 'uguu':
        body, ctype = encode_multipart({}, [('files[]', filename, data)])
        st, resp, _ = http_request('https://uguu.se/upload', 'POST',
                                   body, {'Content-Type': ctype}, timeout)
        js, text = _json_or_text(resp)
        url = _pick(js, 'files.0.url') if isinstance(js, dict) else None
        if url:
            return url, None
        return None, 'HTTP %s' % st

    if host_key == 'telegraph':
        body, ctype = encode_multipart({}, [('file', filename, data)])
        st, resp, _ = http_request('https://telegra.ph/upload', 'POST',
                                   body, {'Content-Type': ctype}, timeout)
        js, text = _json_or_text(resp)
        if isinstance(js, list) and js:
            src = (js[0] or {}).get('src')
            if src:
                return 'https://telegra.ph' + src, None
            return None, (js[0] or {}).get('error') or 'telegraph 返回异常'
        return None, 'HTTP %s' % st

    return None, '未知图床：%s' % host_key


def upload_reference_image(filename, data, cfg):
    """按配置把图片传到图床。

    返回 (url, host_used, public, errors)
      public=False 表示没传上图床，url 由调用方回退成本地地址
    """
    mode = (cfg.get('image_host') or 'auto').strip().lower()
    if mode not in HOST_CHOICES:
        mode = 'auto'

    if mode == 'local':
        return None, 'local', False, []

    if mode == 'auto':
        # 未配置凭据的图床直接跳过（否则必然 401，白白等一个超时）
        candidates = [k for k in AUTO_ORDER if host_ready(k, cfg)]
    else:
        candidates = [mode]

    errors = []
    for key in candidates:
        try:
            url, err = upload_to_host(key, filename, data, cfg)
        except Exception as e:
            url, err = None, '%s: %s' % (type(e).__name__, e)
        if url:
            return url, key, True, errors
        if err:
            errors.append('%s: %s' % (IMAGE_HOSTS.get(key, {}).get('name', key), err))
    return None, None, False, errors


def host_display_name(key):
    if not key:
        return 'local'
    return IMAGE_HOSTS.get(key, {}).get('name', key)


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

    @staticmethod
    def _mask(value):
        if len(value) > 8:
            return value[:4] + '****' + value[-4:]
        if value:
            return '****'
        return ''

    def handle_get_config(self):
        cfg = load_json(CONFIG_PATH, {"api_key": ""})
        key = cfg.get('api_key', '')
        token = (cfg.get('host_token') or '').strip()
        self.send_json({
            "api_key": key,
            "masked": self._mask(key),
            # 图床配置（新增）
            "image_host": (cfg.get('image_host') or 'auto').strip(),
            "host_uid": (cfg.get('host_uid') or '').strip(),
            "host_token_masked": self._mask(token),
            "host_saved": bool(token) or cfg.get('image_host') in ('catbox', 'telegraph', 'local'),
            "host_options": [
                {
                    "key": k,
                    "name": ('自动选择（推荐）' if k == 'auto' else
                             '仅本地（不上传）' if k == 'local' else
                             IMAGE_HOSTS[k]['name']),
                    "need": 'none' if k in ('auto', 'local') else IMAGE_HOSTS[k]['need'],
                    "tip": (AUTO_TIP if k == 'auto' else
                            LOCAL_TIP if k == 'local' else
                            IMAGE_HOSTS[k]['tip']),
                }
                for k in HOST_CHOICES
            ],
        })

    def handle_set_config(self):
        data = self.read_json()
        cfg = load_json(CONFIG_PATH, {"api_key": ""})

        if 'api_key' in data:
            api_key = (data.get('api_key') or '').strip()
            if not api_key:
                return self.send_json({"error": "API key cannot be empty"}, 400)
            cfg['api_key'] = api_key

        for field in ('image_host', 'host_token', 'host_uid'):
            if field in data:
                cfg[field] = (data.get(field) or '').strip()

        save_json_file(CONFIG_PATH, cfg)

        token = (cfg.get('host_token') or '').strip()
        self.send_json({
            "success": True,
            "masked": self._mask(cfg.get('api_key', '')),
            "image_host": (cfg.get('image_host') or 'auto').strip(),
            "host_token_masked": self._mask(token),
        })

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

        # 1) 本地留档（保持原有行为：uploads/ 里始终有一份，便于本地预览与历史回溯）
        new_filename = f"{uuid.uuid4().hex}{ext}"
        filepath = os.path.join(UPLOADS_DIR, new_filename)
        with open(filepath, 'wb') as f:
            f.write(file_data)

        host = self.headers.get('Host', 'localhost:5000')
        local_url = f"http://{host}/uploads/{new_filename}"

        # 2) 上传图床，拿到速创服务器能抓到的公网 URL
        cfg = load_json(CONFIG_PATH, {"api_key": ""})
        url, host_used, is_public, errors = upload_reference_image(new_filename, file_data, cfg)

        if is_public:
            resp = {
                "url": url,
                "filename": new_filename,
                "host": host_used,
                "host_name": host_display_name(host_used),
                "public": True,
                "local_url": local_url,
            }
            # 降级是有代价的：默认图床失败后换用的备用图床可能限时失效，
            # 必须让用户知道，否则生成时图挂了会一脸茫然。
            if errors:
                resp["warning"] = (
                    "默认图床不可用，已自动换用「%s」。%s"
                    % (host_display_name(host_used),
                       IMAGE_HOSTS.get(host_used, {}).get('expire', '该图床可能不如默认图床稳定'))
                )
                resp["errors"] = errors
            elif IMAGE_HOSTS.get(host_used, {}).get('expire'):
                resp["warning"] = "当前使用「%s」。%s" % (
                    host_display_name(host_used), IMAGE_HOSTS[host_used]['expire'])
            return self.send_json(resp)

        # 3) 图床全部失败 → 回退本地 URL，并如实告知原因
        resp = {
            "url": local_url,
            "filename": new_filename,
            "host": "local",
            "host_name": "local",
            "public": False,
            "local_url": local_url,
        }
        if errors:
            resp["warning"] = "图床均不可用，已回退为本地地址（速创服务器可能无法访问）"
            resp["errors"] = errors
        elif (cfg.get('image_host') or 'auto').strip().lower() != 'local':
            resp["warning"] = "未配置可用的图床，已回退为本地地址（速创服务器可能无法访问）"
        return self.send_json(resp)

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


def probe_port(port):
    """判断端口状态：'ours' 本程序已在运行 / 'other' 被别的程序占用 / 'free' 空闲"""
    # 先发一个 HTTP 请求，看是不是本程序（只看端口占用会把别的程序误判成自己）
    try:
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
        req = urllib.request.Request(f'http://127.0.0.1:{port}/api/config',
                                     headers={'User-Agent': 'Image2Html'})
        with opener.open(req, timeout=2) as resp:
            data = json.loads(resp.read().decode('utf-8', 'replace'))
            if isinstance(data, dict) and 'host_options' in data:
                return 'ours'
            return 'other'
    except urllib.error.HTTPError:
        return 'other'
    except Exception:
        pass

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(0.6)
        if s.connect_ex(('127.0.0.1', port)) == 0:
            return 'other'
    return 'free'


def find_free_port(preferred=5000, limit=20):
    """从 preferred 开始找一个能绑上的端口，避免端口占用直接崩掉。

    这里刻意不设 SO_REUSEADDR：Windows 上它会让两个进程绑到同一端口，
    结果谁收到连接完全看运气，反而比直接失败更难排查。
    """
    for port in range(preferred, preferred + limit):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            try:
                s.bind(('0.0.0.0', port))
                return port
            except OSError:
                continue
    return preferred


class AppServer(HTTPServer):
    """同理：Windows 下关掉 allow_reuse_address，端口冲突要能被发现"""
    allow_reuse_address = (os.name != 'nt')


def open_browser(port):
    """延迟1秒后自动打开浏览器。

    注意用 127.0.0.1 而不是 localhost：Windows 上 localhost 可能优先解析到
    IPv6 的 ::1，而服务只监听了 IPv4，浏览器就会打不开页面。
    设置环境变量 IMAGE2HTML_NO_BROWSER=1 可跳过自动打开（调试时用）。
    """
    if os.environ.get('IMAGE2HTML_NO_BROWSER'):
        return
    time.sleep(1)
    url = f'http://127.0.0.1:{port}'
    try:
        webbrowser.open(url)
    except Exception:
        print(f"未能自动打开浏览器，请手动访问：{url}", flush=True)


def main():
    host = '0.0.0.0'
    preferred = int(os.environ.get('IMAGE2HTML_PORT', '5000') or 5000)

    # 本程序已经在跑 → 不重复起服务，直接把页面打开（双击两次 run.bat 不会报错）
    if probe_port(preferred) == 'ours':
        url = f'http://127.0.0.1:{preferred}'
        print(f"检测到服务已在运行，直接打开页面：{url}", flush=True)
        if not os.environ.get('IMAGE2HTML_NO_BROWSER'):
            try:
                webbrowser.open(url)
            except Exception:
                pass
        return

    port = find_free_port(preferred)
    if port != preferred:
        print(f"端口 {preferred} 被占用，自动改用 {port}", flush=True)

    try:
        server = AppServer((host, port), AppHandler)
    except OSError as e:
        print(f"启动失败：无法监听端口 {port} —— {e}", flush=True)
        print("可以换个端口再试，例如：set IMAGE2HTML_PORT=5050 && python app.py", flush=True)
        return

    url = f'http://127.0.0.1:{port}'
    print("=" * 46, flush=True)
    print("  Image2Html 已启动", flush=True)
    print(f"  页面地址：{url}", flush=True)
    print("  浏览器会自动打开；关闭本窗口或按 Ctrl+C 停止服务", flush=True)
    print("=" * 46, flush=True)

    threading.Thread(target=open_browser, args=(port,), daemon=True).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n服务已停止。", flush=True)
    finally:
        server.server_close()


if __name__ == '__main__':
    main()
