"""校验生成的教程 PDF：页数、页面尺寸、每页开头文字，以及关键内容要点是否都在。

需要 pypdf：pip install pypdf
用法：python docs/tutorial/verify_pdf.py
"""
import os
import sys

from pypdf import PdfReader

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))
PDF = os.path.join(REPO, "Image2Html-使用教程.pdf")

if not os.path.exists(PDF):
    sys.exit("找不到 PDF：%s，先跑 build_tutorial.py" % PDF)

r = PdfReader(PDF)
print("页数：%d   文件：%.2f MB" % (len(r.pages), os.path.getsize(PDF) / 1024 / 1024))
print("元数据：%s" % (r.metadata or {}))
print("-" * 78)
for i, p in enumerate(r.pages, 1):
    mb = p.mediabox
    w = float(mb.width) / 72 * 25.4
    h = float(mb.height) / 72 * 25.4
    text = " ".join((p.extract_text() or "").split())
    print("P%-3d %5.1f×%5.1f mm  %4d 字 | %s" % (i, w, h, len(text), text[:78]))
print("-" * 78)

# 这些是「教程必须讲到」的点：速创充值入口、每个图床、以及几个容易踩的坑
full = " ".join(" ".join((p.extract_text() or "").split()) for p in r.pages)
checks = [
    ("速创注册地址", "api.wuyinkeji.com/user/register"),
    ("订单管理页", "/user/order"),
    ("密钥管理页", "/user/key"),
    ("免费额度为0", "免费额度"),
    ("单价 0.1 元", "0.1 元/张"),
    ("计费优先级", "计费优先级"),
    ("UAPI 官网", "uapis.cn"),
    ("PicUI", "picui.cn"),
    ("SM.MS/S.EE", "s.ee"),
    ("ImgURL", "imgurl.org"),
    ("ImgBB", "imgbb.com"),
    ("Uguu 3小时", "3 小时"),
    ("轮询 24 秒", "24 秒"),
    ("降级顺序", "Telegraph"),
    ("UA 坑", "1010"),
]
print("内容核对：")
bad = 0
for label, needle in checks:
    ok = needle in full
    if not ok:
        bad += 1
    print("  %s %-14s %s" % ("[OK]" if ok else "[缺失]", label, needle))
print("\n%s" % ("全部命中" if bad == 0 else "有 %d 项缺失" % bad))
sys.exit(1 if bad else 0)
