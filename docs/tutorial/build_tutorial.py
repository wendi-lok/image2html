"""构建《Image2Html 使用教程》PDF。

流程：
  1. 读取 tutorial.tpl.html
  2. 把 {{IMG:xx}} 替换成 shots/xx.png 的 base64（内嵌，避免相对路径问题）
  3. 把 {{SVG:xx}} 替换成内联 SVG 图
  4. 写出 tutorial.html
  5. 用 headless Edge --print-to-pdf 渲染成 PDF（Edge 支持 @page，A4 由 CSS 指定）

依赖：Python 标准库 + 本机装了 Edge/Chrome。不需要 pip 安装任何东西。
用法：python docs/tutorial/build_tutorial.py
截图更新后重新跑一遍即可；截图本身是 headless Edge 拍的真实界面。
"""
import base64
import os
import re
import shutil
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))          # docs/tutorial
REPO = os.path.dirname(os.path.dirname(HERE))              # 仓库根目录
SHOTS = os.path.join(HERE, "shots")
TPL = os.path.join(HERE, "tutorial.tpl.html")
OUT_HTML = os.path.join(HERE, "tutorial.html")
OUT_PDF = os.path.join(REPO, "Image2Html-使用教程.pdf")


def find_edge():
    """找一个可用的 Edge/Chrome。可用环境变量 EDGE_PATH 覆盖。"""
    env = os.environ.get("EDGE_PATH")
    if env and os.path.exists(env):
        return env
    cands = [
        r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
        r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
    ]
    for c in cands:
        if os.path.exists(c):
            return c
    for name in ("msedge", "microsoft-edge", "chrome", "chromium", "chromium-browser"):
        p = shutil.which(name)
        if p:
            return p
    sys.exit("找不到 Edge/Chrome，请用 EDGE_PATH 环境变量指定浏览器路径")


EDGE = find_edge()

FONT = "'Microsoft YaHei','PingFang SC',sans-serif"
INK = "#1b1f24"
MUTED = "#5b6774"
BLUE = "#0068d6"
BLUE_BG = "#eef5ff"
BLUE_BD = "#b9d6f5"
GREEN = "#1a8f4a"
GREEN_BG = "#edf9f0"
GREEN_BD = "#b6e0c3"
AMBER = "#b47000"
AMBER_BG = "#fff6e5"
AMBER_BD = "#f0d29a"
GREY_BG = "#f5f7f9"
GREY_BD = "#dde3e9"
RED = "#c0392b"


def svg(inner, h):
    return ('<svg viewBox="0 0 680 %d" xmlns="http://www.w3.org/2000/svg" '
            'font-family="%s">%s</svg>' % (h, FONT, inner))


def txt(x, y, s, size=11.5, fill=INK, weight="normal", anchor="start"):
    return ('<text x="%s" y="%s" font-size="%s" fill="%s" font-weight="%s" '
            'text-anchor="%s">%s</text>' % (x, y, size, fill, weight, anchor, s))


def box(x, y, w, h, fill=GREY_BG, stroke=GREY_BD, r=7, sw=1):
    return ('<rect x="%s" y="%s" width="%s" height="%s" rx="%s" fill="%s" '
            'stroke="%s" stroke-width="%s"/>' % (x, y, w, h, r, fill, stroke, sw))


def arrow_defs():
    return (
        '<defs>'
        '<marker id="ah" markerWidth="9" markerHeight="9" refX="7.5" refY="3.2" orient="auto">'
        '<path d="M0,0 L7.5,3.2 L0,6.4 z" fill="%s"/></marker>'
        '<marker id="ahg" markerWidth="9" markerHeight="9" refX="7.5" refY="3.2" orient="auto">'
        '<path d="M0,0 L7.5,3.2 L0,6.4 z" fill="%s"/></marker>'
        '</defs>' % (MUTED, GREEN)
    )


# ---------------------------------------------------------------- 解压目录结构
def svg_zip_layout():
    h = 232
    s = [arrow_defs()]
    s.append(box(24, 14, 300, 200, "#fbfcfd", GREY_BD))
    s.append(txt(40, 40, "Image2Html/", 13, INK, "bold"))
    lines = [
        ("Image2Html.exe", "双击这个启动", BLUE, "bold"),
        ("_internal/", "运行环境，不要删也不要单独拷走", MUTED, "normal"),
        ("启动.bat", "启动报错时用它，错误会留在窗口里", MUTED, "normal"),
        ("使用说明.txt", "纯文本说明", MUTED, "normal"),
        ("data/", "首次运行自动生成，存密钥与历史记录", MUTED, "normal"),
        ("uploads/  outputs/", "参考图留档与出图缓存", MUTED, "normal"),
    ]
    y = 68
    for name, desc, col, wt in lines:
        s.append(txt(44, y, name, 10.8, col, wt))
        s.append(txt(44, y + 14, desc, 9.3, MUTED))
        y += 33
    # 右侧说明
    s.append(box(344, 60, 312, 48, BLUE_BG, BLUE_BD))
    s.append(txt(360, 80, "整个文件夹是一体的", 11, "#0b4a8f", "bold"))
    s.append(txt(360, 96, "分发/搬运时请一起压缩，别只拷 exe", 9.5, "#28527d"))
    s.append(box(344, 120, 312, 48, AMBER_BG, AMBER_BD))
    s.append(txt(360, 140, "换电脑要迁移配置？", 11, AMBER, "bold"))
    s.append(txt(360, 156, "把 data/ 文件夹一起拷走即可", 9.5, "#8a5b00"))
    s.append(box(344, 180, 312, 34, GREEN_BG, GREEN_BD))
    s.append(txt(360, 201, "不需要安装 Python，不需要联网装依赖", 9.6, GREEN))
    return svg("".join(s), h)


# ---------------------------------------------------------------- 充值流程
def svg_recharge():
    h = 158
    s = [arrow_defs()]
    steps = [
        ("注册", "user/register", BLUE),
        ("登录控制台", "user/login", BLUE),
        ("订单管理\n充值", "user/order", AMBER),
        ("密钥管理\n取 Key", "user/key", BLUE),
        ("填入应用", "齿轮 → API 密钥", GREEN),
    ]
    w, gap = 116, 14
    x = 12
    for i, (title, sub, col) in enumerate(steps):
        fill = AMBER_BG if col == AMBER else (GREEN_BG if col == GREEN else BLUE_BG)
        bd = AMBER_BD if col == AMBER else (GREEN_BD if col == GREEN else BLUE_BD)
        s.append(box(x, 34, w, 62, fill, bd))
        parts = title.split("\n")
        if len(parts) == 2:
            s.append(txt(x + w / 2, 58, parts[0], 11.2, col, "bold", "middle"))
            s.append(txt(x + w / 2, 74, parts[1], 11.2, col, "bold", "middle"))
            s.append(txt(x + w / 2, 89, sub, 8.4, MUTED, "normal", "middle"))
        else:
            s.append(txt(x + w / 2, 66, title, 11.2, col, "bold", "middle"))
            s.append(txt(x + w / 2, 83, sub, 8.4, MUTED, "normal", "middle"))
        if i < len(steps) - 1:
            ax = x + w + 1
            s.append('<line x1="%s" y1="65" x2="%s" y2="65" stroke="%s" '
                     'stroke-width="1.4" marker-end="url(#ah)"/>' % (ax, ax + gap - 2, MUTED))
        x += w + gap
    # 上方的序号圆圈
    x = 12
    for i in range(len(steps)):
        cx = x + w / 2
        s.append('<circle cx="%s" cy="20" r="10" fill="%s"/>' % (cx, BLUE))
        s.append(txt(cx, 24, str(i + 1), 10.5, "#fff", "bold", "middle"))
        x += w + gap
    s.append(box(12, 108, 656, 38, "#fdeeed", "#f0c0ba"))
    s.append(txt(28, 124, "其中第 3 步是必须的：", 10.2, RED, "bold"))
    s.append(txt(158, 124, "速创 GPT-Image-2 接口的免费额度为 0，账户没有余额/点数就一定会调用失败。", 10.0, "#8f2b20"))
    s.append(txt(28, 139, "第 5 步填进 Image2Html 后，整条链路就打通了。", 10.0, "#8f2b20"))
    return svg("".join(s), h)


# ---------------------------------------------------------------- 为什么要图床
def svg_host_why():
    h = 176
    s = [arrow_defs()]
    # 左：本机
    s.append(box(12, 42, 172, 74, GREY_BG, GREY_BD))
    s.append(txt(98, 66, "你的电脑", 11.5, INK, "bold", "middle"))
    s.append(txt(98, 84, "http://127.0.0.1:5000", 8.8, RED, "normal", "middle"))
    s.append(txt(98, 100, "只有你自己能访问", 9.2, MUTED, "normal", "middle"))

    # 中：图床
    s.append(box(254, 42, 172, 74, GREEN_BG, GREEN_BD))
    s.append(txt(340, 66, "图床", 11.5, GREEN, "bold", "middle"))
    s.append(txt(340, 84, "https://uapis.cn/…", 8.8, GREEN, "normal", "middle"))
    s.append(txt(340, 100, "公网任何机器都能访问", 9.2, MUTED, "normal", "middle"))

    # 右：速创
    s.append(box(496, 42, 172, 74, BLUE_BG, BLUE_BD))
    s.append(txt(582, 66, "速创服务器", 11.5, BLUE, "bold", "middle"))
    s.append(txt(582, 84, "拿着 urls 里的地址去取图", 9.2, MUTED, "normal", "middle"))

    # 箭头
    s.append('<line x1="186" y1="79" x2="250" y2="79" stroke="%s" stroke-width="1.5" '
             'marker-end="url(#ahg)"/>' % GREEN)
    s.append(txt(218, 71, "上传", 9.2, GREEN, "bold", "middle"))
    s.append('<line x1="428" y1="79" x2="492" y2="79" stroke="%s" stroke-width="1.5" '
             'marker-end="url(#ahg)"/>' % GREEN)
    s.append(txt(460, 71, "取图", 9.2, GREEN, "bold", "middle"))

    # 直接连的红叉
    s.append('<path d="M98,120 C98,158 582,158 582,120" fill="none" stroke="%s" '
             'stroke-width="1.5" stroke-dasharray="5 4"/>' % RED)
    s.append('<line x1="330" y1="150" x2="350" y2="164" stroke="%s" stroke-width="2.2"/>' % RED)
    s.append('<line x1="350" y1="150" x2="330" y2="164" stroke="%s" stroke-width="2.2"/>' % RED)
    s.append(txt(340, 174, "速创服务器访问 127.0.0.1 访问到的是它自己，必然拿不到图", 9.3, RED, "normal", "middle"))
    return svg("".join(s), h)


# ---------------------------------------------------------------- 降级链
def svg_host_chain():
    h = 246
    s = [arrow_defs()]
    hosts = ["UAPI", "PicUI", "SM.MS", "ImgURL", "ImgBB", "Catbox", "Uguu", "Telegraph"]
    # 第一行 4 个
    y1 = 40
    w = 148
    for i, name in enumerate(hosts[:4]):
        x = 12 + i * (w + 16)
        free = name == "UAPI"
        s.append(box(x, y1, w, 36, BLUE_BG if free else GREY_BG,
                     BLUE_BD if free else GREY_BD))
        s.append(txt(x + 12, y1 + 16, name, 10.6, BLUE if free else INK, "bold"))
        s.append(txt(x + 12, y1 + 29, "免注册" if free else "需填 Token", 8.6,
                     GREEN if free else MUTED))
        if i < 3:
            s.append('<line x1="%s" y1="%s" x2="%s" y2="%s" stroke="%s" stroke-width="1.3" '
                     'marker-end="url(#ah)"/>' % (x + w + 2, y1 + 18, x + w + 13, y1 + 18, MUTED))
    # 折返箭头到第二行
    s.append('<path d="M648,%s C664,%s 664,%s 656,%s" fill="none" stroke="%s" '
             'stroke-width="1.3" marker-end="url(#ah)"/>' % (y1 + 36, y1 + 50, 86, 78, MUTED))
    y2 = 80
    for i, name in enumerate(hosts[4:]):
        x = 12 + (3 - i) * (w + 16)
        s.append(box(x, y2, w, 36, GREY_BG, GREY_BD))
        s.append(txt(x + 12, y2 + 16, name, 10.6, INK, "bold"))
        label = "免注册" if name in ("Catbox", "Uguu", "Telegraph") else "需 API Key"
        s.append(txt(x + 12, y2 + 29, label, 8.6, MUTED))
        if i < 3:
            s.append('<line x1="%s" y1="%s" x2="%s" y2="%s" stroke="%s" stroke-width="1.3" '
                     'marker-end="url(#ah)"/>' % (x - 2, y2 + 18, x - 13, y2 + 18, MUTED))

    # 结果分支
    s.append(box(12, 136, 316, 52, GREEN_BG, GREEN_BD))
    s.append(txt(28, 156, "某一个成功了", 11, GREEN, "bold"))
    s.append(txt(28, 174, "就用它，并在图片上标出图床徽标；若前面有失败，额外给出黄色提示", 9.2, "#166c3c"))
    s.append(box(352, 136, 316, 52, AMBER_BG, AMBER_BD))
    s.append(txt(368, 156, "全部失败了", 11, AMBER, "bold"))
    s.append(txt(368, 174, "回退成本地地址并警告——此时生成大概率会失败", 9.2, "#8a5b00"))
    s.append(txt(12, 208, "顺序固定：UAPI → PicUI → SM.MS → ImgURL → ImgBB → Catbox → Uguu → Telegraph", 9.6, INK, "bold"))
    s.append(txt(12, 226, "其中「需要登录」的图床若没填 Token 会被直接跳过，避免每次都白等一个超时。", 9.4, MUTED))
    s.append(txt(12, 242, "Uguu 的链接约 3 小时后失效，只适合马上要用的场景。", 9.4, RED))
    return svg("".join(s), h)


# ---------------------------------------------------------------- 生成时序
def svg_flow():
    h = 194
    s = [arrow_defs()]
    rows = [
        ("① 点「生成图片」", "前端把 提示词 / 比例 / 参考图公网链接 发给本地服务", BLUE),
        ("② 提交任务（计费一次）", "POST api.wuyinkeji.com/api/async/image_gpt → 返回 task_id", AMBER),
        ("③ 轮询等待", "每 24 秒 GET /api/async/detail 查询一次，最多 30 次（约 12 分钟）", BLUE),
        ("④ 出图", "status = 2 时拿到图片链接，展示在右侧，可保存或重新生成", GREEN),
    ]
    y = 18
    for i, (title, desc, col) in enumerate(rows):
        fill = AMBER_BG if col == AMBER else (GREEN_BG if col == GREEN else BLUE_BG)
        bd = AMBER_BD if col == AMBER else (GREEN_BD if col == GREEN else BLUE_BD)
        s.append(box(12, y, 656, 36, fill, bd))
        s.append(txt(28, y + 15, title, 10.6, col, "bold"))
        s.append(txt(28, y + 29, desc, 9.3, "#3d4956"))
        if i < len(rows) - 1:
            s.append('<line x1="340" y1="%s" x2="340" y2="%s" stroke="%s" stroke-width="1.3" '
                     'marker-end="url(#ah)"/>' % (y + 37, y + 47, MUTED))
        y += 48
    s.append(txt(12, 188, "只有第 ② 步计费；后续查询免费。所以中途关掉页面不会浪费钱，用历史记录重新查询即可。",
                 9.4, MUTED))
    return svg("".join(s), h)


SVGS = {
    "ZIP_LAYOUT": svg_zip_layout,
    "RECHARGE": svg_recharge,
    "HOST_WHY": svg_host_why,
    "HOST_CHAIN": svg_host_chain,
    "FLOW": svg_flow,
}


def main():
    with open(TPL, "r", encoding="utf-8") as f:
        html = f.read()

    # 图片 -> base64
    used = re.findall(r"\{\{IMG:([^}]+)\}\}", html)
    for name in sorted(set(used)):
        path = os.path.join(SHOTS, name + ".png")
        if not os.path.exists(path):
            sys.exit("找不到截图：" + path)
        with open(path, "rb") as f:
            b64 = base64.b64encode(f.read()).decode("ascii")
        html = html.replace("{{IMG:%s}}" % name, 'src="data:image/png;base64,%s"' % b64)
        print("  内嵌截图 %-16s %7d bytes" % (name, os.path.getsize(path)))

    # SVG
    for name, fn in SVGS.items():
        html = html.replace("{{SVG:%s}}" % name, fn())
        print("  插入图表 %s" % name)

    left = re.findall(r"\{\{[^}]+\}\}", html)
    if left:
        sys.exit("还有未替换的占位符：%s" % set(left))

    with open(OUT_HTML, "w", encoding="utf-8") as f:
        f.write(html)
    print("生成 HTML：%s" % OUT_HTML)

    if os.path.exists(OUT_PDF):
        os.remove(OUT_PDF)
    cmd = [
        EDGE, "--headless=new", "--disable-gpu", "--no-first-run",
        "--force-device-scale-factor=1",
        "--user-data-dir=" + os.path.join(HERE, "edgeprofile"),
        "--no-pdf-header-footer",
        "--print-to-pdf=" + OUT_PDF,
        "file:///" + OUT_HTML.replace("\\", "/"),
    ]
    print("渲染 PDF…")
    subprocess.run(cmd, capture_output=True, timeout=300)

    # Edge 提前返回是常态，轮询等文件落盘
    import time
    for _ in range(60):
        if os.path.exists(OUT_PDF) and os.path.getsize(OUT_PDF) > 0:
            time.sleep(1)
            break
        time.sleep(1)
    if not os.path.exists(OUT_PDF):
        sys.exit("PDF 未生成")
    print("完成：%s  (%.2f MB)" % (OUT_PDF, os.path.getsize(OUT_PDF) / 1024 / 1024))


if __name__ == "__main__":
    main()
