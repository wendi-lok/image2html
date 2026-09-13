# 教程构建说明

仓库根目录的 **`Image2Html-使用教程.pdf`** 就是这一套源码的产物，面向「第一次拿到这个软件的人」，
内容包含：解压启动、速创注册与充值、各图床的申请与使用方法、生成流程、排错、附录。

这里的文件只服务于**重新生成那份 PDF**，不参与程序运行。

## 文件

| 文件 | 作用 |
|------|------|
| `tutorial.tpl.html` | 教程正文模板（A4 版式、封面、目录、6 章）。图片/图表处留 `{{IMG:xx}}`、`{{SVG:xx}}` 占位 |
| `build_tutorial.py` | 把占位符换成 base64 图片与内联 SVG，再用 headless Edge `--print-to-pdf` 渲染 |
| `shots/*.png` | 界面截图，1280×800，`--force-device-scale-factor=1` |
| `tutorial.html` | 中间产物（已 gitignore，用于排查渲染问题） |

## 重新生成

```bash
python docs/tutorial/build_tutorial.py
```

只需要 Python 标准库 + 本机装了 Edge（或 Chrome）。**不需要 pip 安装任何东西。**
找不到浏览器时用 `EDGE_PATH` 指定，例如：

```bash
EDGE_PATH="D:\Program Files\Google\Chrome\Application\chrome.exe" python docs/tutorial/build_tutorial.py
```

产物直接覆盖仓库根目录的 `Image2Html-使用教程.pdf`。

## 改内容

- 改文字、改章节顺序 → 编辑 `tutorial.tpl.html`
- 改示意图（目录结构、充值链路、图床降级顺序、生成时序）→ 编辑 `build_tutorial.py` 里的 `svg_*` 函数
- 改配色 / 版心 → 编辑 `build_tutorial.py` 顶部的颜色常量与 `tutorial.tpl.html` 的 `@page`

## 截图是怎么来的

界面截图是**真实跑起来的应用**，用 headless Edge 拍的，不是拼的图：

```bash
# 1) 起一个后台实例
IMAGE2HTML_NO_BROWSER=1 IMAGE2HTML_PORT=5299 python app.py

# 2) 用 headless Edge 逐场景截图
msedge.exe --headless=new --disable-gpu --hide-scrollbars --no-first-run \
  --force-device-scale-factor=1 \
  --user-data-dir="<某个临时 profile 目录>" \
  --window-size=1280,800 --virtual-time-budget=15000 \
  --screenshot="C:\...\docs\tutorial\shots\01-home.png" \
  "http://127.0.0.1:5299/uploads/shot.html?scene=home"
```

页面上那些交互状态（拖拽遮罩、参考图徽标、降级提示）是靠一个同源 iframe 驱动页内脚本实现的：
用 `contentWindow` 拿到页面上下文，派发真实的 `DragEvent` / `DataTransfer`，
并用 `eval()` 访问脚本内 `let` 声明的变量（这些变量不会挂到 `window` 上）。

三个实际的坑：

1. **参数必须是 Windows 路径**（`C:\...`）。在 Git Bash 里传 `/c/...` 给 Edge 不会报错，但会静默不生效。
2. **`msedge.exe` 常常提前返回**（把活交给已有浏览器进程），不能靠进程退出判断完成，**必须轮询等 png 落盘**。
3. **每个场景用独立的 `--user-data-dir`**，否则 profile 被占用会失败；
   而且**复用同一个 profile 会继承上一次的 `localStorage`**（比如语言设置），截图会跟预期不一致。

第 4 张图 `04-refs.png` 里的黄色降级提示不是摆拍：当时 UAPI 的匿名额度（10 张/天）
刚好被测试用光了，应用**真的**降级到了 Uguu，提示语是它自己生成的。
