import os
import subprocess
import threading

import PIL.Image
import PIL.ImageDraw
import pystray

import autostart
from config import config_path


def make_icon_image() -> PIL.Image.Image:
    img = PIL.Image.new("RGBA", (64, 64), (24, 98, 187, 255))
    draw = PIL.ImageDraw.Draw(img)
    draw.text((20, 14), "译", fill="white")
    return img


class TrayApp:
    def __init__(self, state):
        self.state = state

    def _reload(self, icon, item):
        from config import load_config
        import server

        self.state.cfg = load_config()
        server.State.start(self.state)

    def _open_config(self, icon, item):
        subprocess.Popen(["notepad.exe", str(config_path())])

    def _toggle_autostart(self, icon, item):
        autostart.set_autostart(not autostart.is_autostart_enabled())

    def _quit(self, icon, item):
        self.state.stop()
        icon.stop()

    def run(self):
        menu = pystray.Menu(
            pystray.MenuItem(
                lambda item: f"监听 {self.state.cfg['host']}:{self.state.cfg['port']}",
                None,
                enabled=False,
            ),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem(
                "开机自启动",
                self._toggle_autostart,
                checked=lambda item: autostart.is_autostart_enabled(),
            ),
            pystray.MenuItem("编辑配置文件", self._open_config),
            pystray.MenuItem("重载配置", self._reload),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("退出", self._quit),
        )
        pystray.Icon(
            "deeplx-aliyun",
            make_icon_image(),
            "DeepLX-Aliyun（DeepLX → 阿里云机器翻译）",
            menu,
        ).run()
