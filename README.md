# Image2Html — 调用速创 Image2 API 生成图片

基于 [速创 API](https://api.wuyinkeji.com/doc/53) 的 GPT-Image-2 图片生成 Web 应用。支持参考图上传、中英文切换、历史任务查询，纯 Python 标准库实现，无需安装第三方依赖。

## 功能特性

- **拖拽 / 粘贴上传参考图** — 图片直接拖进窗口、拖到参考图区域，或 Ctrl+V 粘贴截图，自动上传图床换取公网直链
- **多图床自动降级** — 默认免注册的 UAPI 开箱可用；也支持 PicUI / SM.MS / ImgURL / ImgBB，前一个失败自动换下一个，全部失败才回退本地地址
- **多参考图上传** — 支持本地上传和 URL 粘贴，最多 5 张，可拖拽排序，每张标注实际使用的图床
- **实时进度** — 24 秒轮询间隔 + 倒计时进度条，清晰显示查询次数和等待时间
- **任务 ID 持久化** — 历史记录通过 `task_id` 实时查询 API，结果不过期
- **一键保存** — 生成的图片可直接保存到本地
- **中英文切换** — 完整的中英双语界面
- **暗色模式** — 跟随系统自动切换
- **零依赖** — 仅使用 Python 标准库（`http.server`）

## 快速开始

### 方式一：一键启动（Windows，推荐）

双击 `run.bat`。它会自动找到可用的 Python、启动服务并打开浏览器。**不需要 pip 安装**（零第三方依赖），关闭窗口即停止服务。

> 如果端口 5000 被占用，会自动顺延到 5001、5002…，终端里会打印实际地址。

### 方式二：命令行

```bash
python app.py
```

浏览器自动打开 `http://127.0.0.1:5000`，首次使用点击右上角 ⚙ 设置 API 密钥。

可用的环境变量：

| 变量 | 说明 |
|------|------|
| `IMAGE2HTML_PORT` | 指定端口（默认 5000） |
| `IMAGE2HTML_NO_BROWSER=1` | 启动时不自动打开浏览器 |

### 方式三：下载 Release（无需 Python）

从 [Releases](../../releases) 下载 `Image2Html.zip`，解压后双击 `Image2Html.exe` 即可运行。

## 使用说明

1. **设置 API Key** — 点击右上角齿轮图标，输入速创 API 密钥
2. **添加参考图（可选）** — 把图片拖进窗口、拖到「参考图」区域，或 Ctrl+V 粘贴；也可以点「+」选文件、粘贴图片 URL。最多 5 张，可拖拽排序
3. **输入提示词** — 描述你想生成的图片
4. **选择比例** — 可选 auto、1:1、16:9 等
5. **点击生成** — 等待进度条倒计时和轮询，结果展示在右侧
6. **保存 / 重新生成** — 点击保存按钮下载图片，或点击重新生成

## 关于图床

速创 API 的 `urls` 参数只接受**公网 URL**，本地 `http://127.0.0.1/...` 它抓不到。
所以本地上传的参考图会先传到图床换成公网直链，再提交给 API。

**开箱即用**：默认走 [UAPI](https://uapis.cn)，免注册即可上传（匿名访客每日 10 张）。
在 ⚙ 设置里填上它免费的 API Key 即可不限量。

也可以换成别的图床（设置 → 参考图图床），按顺序自动降级：

| 图床 | 需要什么 | 备注 |
|------|----------|------|
| UAPI | 免注册 | **默认**，国内可直连 |
| PicUI | Token | 国内图床 |
| SM.MS | Token | 接口已迁移到 `s.ee` |
| ImgURL | UID + Token | |
| ImgBB | API Key | 海外 |
| Catbox / Uguu / Telegraph | 免注册 | 海外兜底；Uguu 链接约 3 小时失效 |

全部失败时会回退成本地地址，并在界面上给出提示（此时生成大概率会失败，因为速创抓不到图）。

## 项目结构

```
Image2Html/
├── app.py                # 后端（Python http.server）+ 图床适配器链
├── templates/
│   └── index.html        # 前端单页应用（HTML + CSS + JS）
├── run.bat               # Windows 一键启动
├── data/                 # API Key 配置 + 图床配置 + 历史记录（本地 JSON）
├── uploads/              # 本地上传的参考图
├── outputs/              # 保存的生成图片
└── UserDoing.py          # API 调用参考实现（命令行版）
```

## 技术栈

| 层 | 技术 |
|----|------|
| 后端 | Python 标准库 `http.server` |
| 前端 | HTML + CSS + JavaScript（单文件） |
| 存储 | 本地 JSON（`data/config.json`、`data/history.json`） |
| API | 速创 GPT-Image-2（异步提交 + 轮询查询） |
| 图床 | 可插拔适配器链，自动降级 |

## API 接口

### 提交生成任务
```
POST /api/generate
Body: {"prompt": "...", "size": "auto", "urls": ["..."]}
Response: {"success": true, "task_id": "image_xxx"}
```

### 查询任务状态
```
GET /api/task/<task_id>
Response: {"status": 2, "result_urls": [...], "message": ""}
```
- `status`: 0=排队中, 1=生成中, 2=成功

### 其他接口
- `GET /api/config` — 获取配置（API Key 已脱敏，含图床列表 `host_options`）
- `POST /api/config` — 设置 API Key 与图床（`image_host` / `host_token` / `host_uid`）
- `POST /api/upload` — 上传参考图，返回**公网直链**（附 `host` / `host_name` / `public`）
- `POST /api/save-image` — 保存生成图到本地
- `GET/POST/PUT/DELETE /api/history[/<id>]` — 历史记录 CRUD

## 打包为 EXE

```bash
pip install pyinstaller
pyinstaller --onedir --name Image2Html --add-data "templates;templates" app.py
# 输出在 dist/Image2Html/
```

## 注意事项

- **参考图 URL**：本地上传的图会先传图床。默认 UAPI 免注册可用，全部图床失败时会回退本地地址并提示。
- **API 计费**：0.1 元/张，每次生成任务仅提交一次付费 POST，后续轮询均为免费 GET
- **生成时间**：不定，前端自动轮询等待，最长约 12 分钟
- **API Key 安全**：密钥存储在本地 `data/config.json`，请勿将含密钥的 `data/` 目录上传到公开仓库

## 许可

MIT License
