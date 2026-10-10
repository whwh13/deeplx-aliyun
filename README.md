# DeepLX-Aliyun

本地 DeepLX 协议 → 阿里云机器翻译（TranslateGeneral）的转换网关，带 Windows 托盘图标与开机自启动。

**仓库**：https://github.com/whwh13/deeplx-aliyun （打 `v*` tag 自动构建并发布 exe 到 GitHub Releases）

## 它做什么

在 `127.0.0.1:5188` 上提供标准 **DeepLX 协议**接口，把请求转发到阿里云机器翻译：

```
翻译客户端 ──DeepLX 协议──> 127.0.0.1:5188 ──TranslateGeneral(RPC/HMAC-SHA1)──> mt.aliyuncs.com
```

- 兼容 `POST /translate` 和 `POST /v2/translate`，请求/响应结构与 DeepLX 一致
- 源语言支持 `auto`（阿里云自动识别，响应里回填检测到的语种）
- 超过 5000 字符自动按段落/句子边界分片翻译后拼接
- 只监听 `127.0.0.1`，不对外网开放
- 语种代码自动映射（DeepLX 大写 `ZH`/`EN`/`JA`… → 阿里云小写 `zh`/`en`/`ja`…，未列出的按小写直传）

## 怎么用

### 运行（两种方式）

1. **打包版**：运行 `dist/DeepLXAliyun.exe`（无控制台窗口，托盘区出现蓝色"译"图标）。
2. **源码版**：项目目录内 `uv run python main.py`（托盘）或 `uv run python main.py --no-tray`（前台控制台，便于调试）。

### 配置 API（填 AccessKey 的地方）

程序目录下的 **`config.json`**（exe 版在 exe 同目录；首次运行会自动从模板生成）：

```json
{
  "host": "127.0.0.1",
  "port": 5188,
  "endpoint": "https://mt.aliyuncs.com",
  "region": "cn-hangzhou",
  "scene": "general",
  "access_key_id": "在此填写 AccessKey ID",
  "access_key_secret": "在此填写 AccessKey Secret"
}
```

AccessKey 在阿里云控制台 RAM 访问控制创建；对应 RAM 账号需有 **`alimt:TranslateGeneral`** 权限
（可授予 `AliyunMTFullAccess` 系统策略）。改完配置后托盘菜单点"重载配置"，或重启程序。

> 端口默认 5188（本机 1188 落在 Windows 保留端口段 1119-1218 内，绑定会被拒绝）；`host`/`port` 可在 config.json 里改。

### 托盘菜单

- 显示当前监听地址
- **开机自启动**（勾选开关，写 HKCU `...\CurrentVersion\Run` 注册表，当前用户级）
- 编辑配置文件（记事本打开 config.json）
- 重载配置（改完无需重启）
- 退出

### 客户端接入

任何支持 DeepLX 的客户端（沉浸式翻译、Bob、Pot 等）填：

```
自定义 API / DeepLX 地址：http://127.0.0.1:5188
```

curl 自测：

```bash
curl -X POST http://127.0.0.1:5188/translate \
  -H "Content-Type: application/json" \
  -d '{"text":"今天天气真好","source_lang":"auto","target_lang":"EN"}'
```

## 重新打包

```bash
uv run pyinstaller --onefile --noconsole --name DeepLXAliyun main.py
```

产物在 `dist/DeepLXAliyun.exe`，使用时把 `config.json` 放在 exe 同目录。

**自动构建**：推送 `v*` tag（如 `git tag v1.0.1 && git push origin v1.0.1`），GitHub Actions 会在 windows-latest 上构建 exe 并发布到 Releases（`.github/workflows/release.yml`）。

## 安全提示

- `config.json` 内含 AccessKey 明文，已列入 `.gitignore`，不要提交、不要随 exe 分发给不信任的人。
- 换正式 Key 时建议用最小权限 RAM 子账号，测试完及时禁用。

## 目录结构

```
main.py        入口（启动 HTTP 服务 + 托盘；--no-tray 前台调试）
server.py      DeepLX 协议 HTTP 服务（ThreadingHTTPServer，配置热重载）
aliyun.py      阿里云 TranslateGeneral 客户端（RPC HMAC-SHA1 签名、语种映射、长文本分片）
config.py      配置读取（config.json，缺失时自动生成模板）
tray.py        pystray 托盘（自启开关/编辑配置/重载/退出）
autostart.py   HKCU Run 注册表开机自启开关
```

## 状态

- 2026-10-10 完成：协议转换、托盘、自启、PyInstaller 打包均验证通过。
- 2026-10-10 真实翻译实测通过（auto→EN / EN→ZH / JA→ZH / 5600 字长文本分片），RAM 子账号已获 `alimt:TranslateGeneral` 授权。
