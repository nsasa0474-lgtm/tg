from __future__ import annotations

import logging

from kivy.app import App
from kivy.clock import Clock
from kivy.lang import Builder
from kivy.properties import BooleanProperty, StringProperty

from tg_bridge.mobile import MobileBridge
from tg_bridge.telegram_setup import apply_telegram_proxy

log = logging.getLogger("tg_bridge")

KV = """
BoxLayout:
    orientation: 'vertical'
    padding: '16dp'
    spacing: '12dp'

    Label:
        text: 'TG Tunnel'
        font_size: '26sp'
        bold: True
        size_hint_y: None
        height: self.texture_size[1] + '12dp'

    Label:
        text: root.status_text
        font_size: '15sp'
        text_size: self.width, None
        halign: 'left'
        valign: 'top'
        size_hint_y: None
        height: self.texture_size[1] + '8dp'

    Button:
        text: 'Остановить' if root.running else 'Запустить туннель'
        size_hint_y: None
        height: '52dp'
        on_release: root.toggle_tunnel()

    Button:
        text: 'Настроить Telegram (Подключить)'
        size_hint_y: None
        height: '52dp'
        disabled: not root.running
        on_release: root.open_telegram()

    Label:
        text: 'SOCKS5: 127.0.0.1:1080\\nОставьте приложение включённым или в фоне.'
        font_size: '13sp'
        color: 0.7, 0.7, 0.7, 1
"""


class TGTunnelApp(App):
    status_text = StringProperty("Нажмите «Запустить туннель».")
    running = BooleanProperty(False)

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._bridge = MobileBridge(on_ready=self._on_bridge_ready)

    def build(self):
        return Builder.load_string(KV)

    def toggle_tunnel(self):
        if self.running:
            self._bridge.stop()
            self.running = False
            self.status_text = "Остановлено."
            return
        self.status_text = "Запуск SOCKS5…"
        self._bridge.start()

    def _on_bridge_ready(self):
        Clock.schedule_once(lambda *_: self._set_running(), 0)

    def _set_running(self):
        self.running = True
        self.status_text = (
            "Туннель работает.\n"
            "Нажмите «Настроить Telegram» и подтвердите «Подключить»."
        )

    def open_telegram(self):
        apply_telegram_proxy("127.0.0.1", 1080)

    def on_stop(self):
        if self._bridge.running:
            self._bridge.stop()


def run_app():
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    TGTunnelApp().run()
