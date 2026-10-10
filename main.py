import sys

from config import load_config
from server import State
from tray import TrayApp


def main():
    state = State(load_config())
    state.start()
    port = state.cfg["port"]
    if not state.cfg.get("access_key_id"):
        print(
            f"[deeplx-aliyun] 服务已启动 http://{state.cfg['host']}:{port}，"
            f"但尚未配置阿里云 AccessKey，请编辑 {__import__('config').config_path()}",
            file=sys.stderr,
        )
    if "--no-tray" in sys.argv:
        try:
            state.thread.join()
        except KeyboardInterrupt:
            state.stop()
        return
    TrayApp(state).run()


if __name__ == "__main__":
    main()
