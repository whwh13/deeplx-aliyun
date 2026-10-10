# AGENTS.md — deeplx-aliyun 项目约定

## 项目定位

本地单文件小工具：监听 `127.0.0.1:5188` 提供 DeepLX 协议，转发到阿里云机器翻译 TranslateGeneral。
打包成无控制台 Windows exe，托盘控制 + 注册表开机自启。

## 架构要点

- Python 3.12 + uv；依赖只有 pystray / pillow（托盘图标）/ requests，HTTP 服务用标准库 `ThreadingHTTPServer`。
- `aliyun.py`：RPC 签名（参数字典序排序 → percent-encode（safe=`-_.~`）→ 拼接 `GET&%2F&<query>` → HMAC-SHA1(secret+"&") → base64）。成功返回 JSON（`Code==200`，译文在 `Data.Translated`），**失败返回 XML**，错误提示解析 `<Code>/<Message>`。
- 性能（v1.1.0）：`server.py` handler 设 `protocol_version="HTTP/1.1"`（每条响应都必须带 Content-Length，否则 1.1 挂起）；`aliyun.py` 用 **thread-local `requests.Session`**（`trust_env=False` 跳过每请求的注册表代理探测）复用到 mt.aliyuncs.com 的 TLS 连接——TLS 复用只在客户端 keep-alive 复用 localhost 连接时生效（线程随连接生）；`_translate_cached` 上 `lru_cache(2000)`，缓存 key 含配置与超时，改配置自然失效，异常不入缓存。
- 语种映射在 `aliyun.py` 的 `LANG_MAP`（DeepLX 大写 → 阿里云小写）；阿里云单次请求上限 5000 字符，`split_text` 按 4800 分片。
- `server.py` 的 `State` 是托盘与 HTTP 共享的配置容器，`start()`/`stop()` 支持配置热重载。
- `config.py`：exe 冻结时配置在 **exe 同目录**，源码运行时在项目根目录；缺失时自动生成模板。

## 本机关键事实

- **GitHub**：仓库 https://github.com/whwh13/deeplx-aliyun（public），git 已配本地代理 `http.proxy http://127.0.0.1:18888`，推送用 Git Credential Manager 里的凭据；CI 打 `v*` tag 触发 windows-latest 构建并发布 Release（softprops/action-gh-release）。

- **端口必须避开 Windows 保留段**：`netsh interface ipv4 show excludedportrange protocol=tcp` 里 1119-1218 被排除，DeepLX 惯例的 1188 会绑定失败（WinError 10013），故默认 5188。
- AccessKey 是敏感凭证，只放 `config.json`（已 gitignore），测试 Key 用完由用户禁用；仓库里只保留 `config.example.json` 模板。

## 测试

```bash
# 服务（前台）
uv run python main.py --no-tray
# 自测
curl http://127.0.0.1:5188/
curl -X POST http://127.0.0.1:5188/translate -H "Content-Type: application/json" \
  -d '{"text":"你好","source_lang":"auto","target_lang":"EN"}'
# 打包
uv run pyinstaller --onefile --noconsole --name DeepLXAliyun main.py
```

打包后验证：`dist/DeepLXAliyun.exe` 同目录放好 `config.json`，`GET /` 应返回监听信息；任务管理器出现两个 DeepLXAliyun.exe 进程属正常（onefile 引导 + 主体）。

## 已知坑

- 阿里云 RPC **成功和失败都返回 XML**（成功根节点 `<TranslateGeneralResponse>`，失败 `<Error>`），不是文档示例的 JSON；解析用 ElementTree 统一处理。
- 托盘菜单 pystray 的 `checked` 回调每次渲染都会查询注册表，`autostart.py` 的读写要保持幂等。
- Git Bash 里 curl 直接传含中文的 `-d '...'` 可能出现 JSON 解析失败（编码问题），测试时用 `--data-binary @file`。
