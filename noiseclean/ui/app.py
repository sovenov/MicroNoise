"""Главное окно MicroNoise: компоновка интерфейса и связь с движком."""

import os
import queue
import sys
import tkinter as tk
from tkinter import ttk

from .. import config, i18n, settings
from ..audio import devices as devmod
from ..audio.engine import AudioEngine
from . import assets, theme, widgets

C = config.COLORS


class NoiseCleanApp:
    WIDTH = 940
    HEIGHT = 696

    def __init__(self, root, single_instance=None):
        self.root = root
        self._single = single_instance
        self.fonts = theme.build_fonts()
        theme.setup_styles(root, self.fonts)

        self.engine = AudioEngine(on_error=self._engine_error,
                                  on_status=self._engine_status)
        self.toast = widgets.Toast(root, self.fonts)

        # сохранённые настройки; пустой dict = первый запуск
        self._settings = settings.load()

        # состояние (восстанавливается из настроек)
        self.mode = self._settings.get("mode", config.MODE_LIGHT)
        if self.mode not in (config.MODE_LIGHT, config.MODE_STRONG):
            self.mode = config.MODE_LIGHT
        try:
            self.gain_db = float(self._settings.get("gain_db", 0.0))
        except (TypeError, ValueError):
            self.gain_db = 0.0
        self.gain_db = max(config.GAIN_MIN_DB,
                           min(config.GAIN_MAX_DB, self.gain_db))
        self.power_on = bool(self._settings.get("power_on", True))
        self._alive = True

        # язык интерфейса (ru/en), запоминается в настройках
        self.lang = self._settings.get("lang", i18n.DEFAULT_LANG)
        if self.lang not in i18n.LANGS:
            self.lang = i18n.DEFAULT_LANG
        # реестр виджетов для перевода: (виджет, ключ, верхний_регистр)
        self._tr_widgets = []
        # id отложенного сохранения настроек (для ползунка усиления)
        self._save_after_id = None

        # системный трей
        self._tray = None
        self._tray_q = queue.Queue()

        # сглаженные значения индикаторов (только для отображения)
        self._disp_in = 0.0
        self._disp_out = 0.0

        self.input_devs = []
        self.output_devs = []

        self._setup_window()
        self._build_ui()
        self._load_devices()
        self._apply_engine_config()
        self._build_tray()

        # Второй экземпляр будет «будить» нас через это событие — по сигналу
        # показываем окно (через ту же очередь, что и трей: из главного потока).
        if self._single is not None:
            self._single.start_listener(lambda: self._tray_q.put("open"))

        self.root.after(120, self._post_show)
        self.root.after(33, self._tick)

        # тестовый хук: сменить язык на лету (как клик по переключателю)
        _tl = os.environ.get("NC_TEST_LANG")
        if _tl:
            self.root.after(900, lambda: self._set_language(_tl))

    # ------------------------------------------------------------------ window
    def _setup_window(self):
        root = self.root
        # Прячем окно до полной готовности: иначе Tk успевает показать пустое
        # окно с нативной рамкой (на update_idletasks) ещё до overrideredirect
        # и до построения виджетов — это и есть «прозрачное окно» при старте.
        root.withdraw()
        root.title("MicroNoise")
        self._set_window_icon()
        root.configure(bg=C["bg"])
        root.geometry("%dx%d" % (self.WIDTH, self.HEIGHT))
        root.resizable(False, False)
        # Убираем рамку ДО первого показа окна.
        try:
            root.overrideredirect(True)
        except Exception:
            pass
        # центрирование (окно скрыто — на экране ничего не появляется)
        root.update_idletasks()
        sw = root.winfo_screenwidth()
        sh = root.winfo_screenheight()
        x = (sw - self.WIDTH) // 2
        y = max(0, (sh - self.HEIGHT) // 2 - 20)
        root.geometry("+%d+%d" % (x, y))
        root.protocol("WM_DELETE_WINDOW", self._on_close)

    def _post_show(self):
        # Окно всё ещё скрыто: сначала выставляем стиль панели задач и иконку,
        # докрашиваем виджеты, и только потом показываем — единственным
        # deiconify, уже готовым, без мигания.
        self._enable_taskbar()
        self._set_taskbar_hicon()
        try:
            self.root.update_idletasks()
        except Exception:
            pass
        try:
            self.root.deiconify()
            self.root.lift()
            self.root.focus_force()
        except Exception:
            pass
        if os.environ.get("NC_TEST_TOPMOST"):
            try:
                self.root.attributes("-topmost", True)
            except Exception:
                pass

    def _enable_taskbar(self):
        if sys.platform != "win32":
            return
        try:
            import ctypes
            hwnd = ctypes.windll.user32.GetParent(self.root.winfo_id())
            GWL_STYLE = -16
            GWL_EXSTYLE = -20
            WS_MINIMIZEBOX = 0x00020000
            WS_EX_TOOLWINDOW = 0x00000080
            WS_EX_APPWINDOW = 0x00040000
            st = ctypes.windll.user32.GetWindowLongW(hwnd, GWL_STYLE)
            ctypes.windll.user32.SetWindowLongW(hwnd, GWL_STYLE,
                                                st | WS_MINIMIZEBOX)
            ex = ctypes.windll.user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
            ex = (ex & ~WS_EX_TOOLWINDOW) | WS_EX_APPWINDOW
            ctypes.windll.user32.SetWindowLongW(hwnd, GWL_EXSTYLE, ex)
        except Exception:
            pass

    def _set_window_icon(self):
        """Иконка окна на уровне Tk (alt-tab и как запасной путь для таскбара)."""
        try:
            img = assets.icon("brand")
            if img is not None:
                self._icon_img = img  # держим ссылку от сборщика мусора
                self.root.iconphoto(True, img)
        except Exception:
            pass
        if sys.platform == "win32":
            try:
                self.root.iconbitmap(default=config.APP_ICON)
            except Exception:
                pass

    def _set_taskbar_hicon(self):
        """Явно задать HICON окна из app.ico — надёжно для безрамочного окна."""
        if sys.platform != "win32":
            return
        try:
            import ctypes
            if not os.path.exists(config.APP_ICON):
                return
            u32 = ctypes.windll.user32
            u32.LoadImageW.restype = ctypes.c_void_p
            u32.LoadImageW.argtypes = [ctypes.c_void_p, ctypes.c_wchar_p,
                                       ctypes.c_uint, ctypes.c_int,
                                       ctypes.c_int, ctypes.c_uint]
            u32.SendMessageW.restype = ctypes.c_void_p
            u32.SendMessageW.argtypes = [ctypes.c_void_p, ctypes.c_uint,
                                         ctypes.c_void_p, ctypes.c_void_p]
            u32.GetSystemMetrics.restype = ctypes.c_int
            u32.GetSystemMetrics.argtypes = [ctypes.c_int]

            IMAGE_ICON = 1
            LR_LOADFROMFILE = 0x00000010
            WM_SETICON = 0x0080
            ICON_SMALL, ICON_BIG = 0, 1
            cx_big = u32.GetSystemMetrics(11) or 32   # SM_CXICON
            cy_big = u32.GetSystemMetrics(12) or 32   # SM_CYICON
            cx_sm = u32.GetSystemMetrics(49) or 16    # SM_CXSMICON
            cy_sm = u32.GetSystemMetrics(50) or 16    # SM_CYSMICON

            hwnd = u32.GetParent(self.root.winfo_id())
            big = u32.LoadImageW(None, config.APP_ICON, IMAGE_ICON,
                                 cx_big, cy_big, LR_LOADFROMFILE)
            small = u32.LoadImageW(None, config.APP_ICON, IMAGE_ICON,
                                   cx_sm, cy_sm, LR_LOADFROMFILE)
            self._hicon_big, self._hicon_small = big, small  # держим ссылки
            if big:
                u32.SendMessageW(hwnd, WM_SETICON, ICON_BIG, big)
            if small:
                u32.SendMessageW(hwnd, WM_SETICON, ICON_SMALL, small)
        except Exception:
            pass

    # ---------------------------------------------------------- window dragging
    def _start_drag(self, event):
        self._drag_x = event.x
        self._drag_y = event.y

    def _on_drag(self, event):
        x = self.root.winfo_x() + (event.x - self._drag_x)
        y = self.root.winfo_y() + (event.y - self._drag_y)
        self.root.geometry("+%d+%d" % (x, y))

    def _minimize(self):
        # Сворачиваем через Win32, не трогая overrideredirect — иначе событие
        # <Map> от смены стиля само разворачивает окно обратно.
        if sys.platform == "win32":
            try:
                import ctypes
                hwnd = ctypes.windll.user32.GetParent(self.root.winfo_id())
                ctypes.windll.user32.ShowWindow(hwnd, 6)  # SW_MINIMIZE
                return
            except Exception:
                pass
        self.root.iconify()

    def _on_close(self):
        # Крестик сворачивает в трей; полный выход — через меню трея «Завершить».
        if self._tray is not None:
            self.root.withdraw()
        else:
            self._quit()

    def _quit(self):
        self._alive = False
        # сохранить текущее состояние перед выходом (на случай несохранённого gain)
        try:
            if self._save_after_id is not None:
                self.root.after_cancel(self._save_after_id)
                self._save_after_id = None
        except Exception:
            pass
        try:
            self._save_settings()
        except Exception:
            pass
        try:
            if self._single is not None:
                self._single.stop()
        except Exception:
            pass
        try:
            if self._tray is not None:
                self._tray.stop()
        except Exception:
            pass
        try:
            self.engine.shutdown()
        except Exception:
            pass
        try:
            self.root.destroy()
        except Exception:
            pass

    def _show_window(self):
        # Универсальный показ: из трея (withdraw), из свёрнутого (minimize)
        # и просто из фона — с выводом на передний план.
        try:
            self.root.deiconify()
        except Exception:
            pass
        if sys.platform == "win32":
            try:
                import ctypes
                hwnd = ctypes.windll.user32.GetParent(self.root.winfo_id())
                ctypes.windll.user32.ShowWindow(hwnd, 9)  # SW_RESTORE
                ctypes.windll.user32.SetForegroundWindow(hwnd)
            except Exception:
                pass
        try:
            self.root.lift()
            self.root.focus_force()
        except Exception:
            pass

    # ---------------------------------------------------------------- tray
    def _build_tray(self):
        try:
            import pystray
            from PIL import Image
        except Exception:
            self._tray = None
            return
        try:
            img = Image.open(os.path.join(config.BASE_DIR, "assets", "tray.png"))
        except Exception:
            self._tray = None
            return

        def act(name):
            return lambda icon=None, item=None: self._tray_q.put(name)

        def label(key):
            # текст пункта — callable, чтобы при смене языка update_menu()
            # подхватывал актуальный перевод.
            return lambda _item: self._t(key)

        # enabled и text принимают callable (фича pystray; в его type-стабе
        # только статичные типы, поэтому # type: ignore).
        menu = pystray.Menu(
            pystray.MenuItem(label("tray_open"), act("open"),
                             default=True),  # type: ignore
            pystray.MenuItem(label("tray_on"), act("on"),
                             enabled=lambda _: not self.power_on),  # type: ignore
            pystray.MenuItem(label("tray_off"), act("off"),
                             enabled=lambda _: self.power_on),  # type: ignore
            pystray.MenuItem(label("tray_quit"), act("quit")),  # type: ignore
        )
        try:
            self._tray = pystray.Icon("micronoise", img, "MicroNoise", menu)
            self._tray.run_detached()
        except Exception:
            self._tray = None

    def _drain_tray(self):
        try:
            while True:
                action = self._tray_q.get_nowait()
                if action == "open":
                    self._show_window()
                elif action == "on":
                    self._set_power(True)
                elif action == "off":
                    self._set_power(False)
                elif action == "quit":
                    self._quit()
                    return
        except queue.Empty:
            pass

    # ---------------------------------------------------------------- i18n util
    def _t(self, key):
        return i18n.tr(self.lang, key) or key

    def _tlabel(self, parent, key, upper=False, **kw):
        """tk.Label с локализованным текстом; регистрируется для перевода."""
        txt = self._t(key)
        lbl = tk.Label(parent, text=txt.upper() if upper else txt, **kw)
        self._tr_widgets.append((lbl, key, upper))
        return lbl

    def _fmt_gain(self, value):
        return "+%.1f %s" % (value, self._t("gain_unit"))

    def _retranslate(self):
        for lbl, key, upper in self._tr_widgets:
            try:
                txt = self._t(key)
                lbl.config(text=txt.upper() if upper else txt)
            except Exception:
                pass
        # тексты, зависящие от состояния
        self._update_power_texts()
        try:
            self.mode_light.set_texts(self._t("mode_light_title"),
                                      self._t("mode_light_desc"))
            self.mode_strong.set_texts(self._t("mode_strong_title"),
                                       self._t("mode_strong_desc"))
            self.gain_val.config(text=self._fmt_gain(self.gain_db))
        except Exception:
            pass
        self._update_lang_switch()
        if self._tray is not None:
            try:
                self._tray.update_menu()
            except Exception:
                pass

    def _update_power_texts(self):
        if self.power_on:
            self.power_label.config(text=self._t("power_on"), fg=C["green"])
            self.hero_desc.config(text=self._t("hero_desc_on"))
        else:
            self.power_label.config(text=self._t("power_off"), fg=C["muted"])
            self.hero_desc.config(text=self._t("hero_desc_off"))

    def _set_language(self, lang):
        if lang == self.lang or lang not in i18n.LANGS:
            return
        self.lang = lang
        self._save_settings()
        self._retranslate()

    def _on_lang_change(self, _event):
        idx = self.lang_combo.current()
        if 0 <= idx < len(self._lang_values):
            self._set_language(self._lang_values[idx][0])
        # снять выделение текста и увести фокус, чтобы не оставалась подсветка
        try:
            self.lang_combo.selection_clear()
        except Exception:
            pass
        self.root.focus_set()

    def _update_lang_switch(self):
        try:
            for i, (code, _name) in enumerate(self._lang_values):
                if code == self.lang:
                    self.lang_combo.current(i)
                    break
        except Exception:
            pass

    def _open_url(self, url):
        try:
            import webbrowser
            webbrowser.open(url)
        except Exception:
            pass

    # ---------------------------------------------------------------- card util
    def _card(self, parent):
        return tk.Frame(parent, bg=C["panel"], highlightthickness=1,
                        highlightbackground=C["border"],
                        highlightcolor=C["border"])

    def _eyebrow(self, parent, key):
        return self._tlabel(parent, key, upper=True, bg=C["panel"],
                            fg=C["green"], font=self.fonts["eyebrow"], anchor="w")

    # -------------------------------------------------------------------- build
    def _build_ui(self):
        self._build_topbar()
        body = tk.Frame(self.root, bg=C["bg"])
        body.pack(fill="both", expand=True, padx=20, pady=(8, 18))

        self._build_hero(body)
        self._build_footer(body)

        cols = tk.Frame(body, bg=C["bg"])
        cols.pack(fill="both", expand=True, pady=(16, 0))
        cols.grid_columnconfigure(0, weight=1, uniform="col")
        cols.grid_columnconfigure(1, weight=1, uniform="col")

        left = tk.Frame(cols, bg=C["bg"])
        left.grid(row=0, column=0, sticky="nsew", padx=(0, 8))
        right = tk.Frame(cols, bg=C["bg"])
        right.grid(row=0, column=1, sticky="nsew", padx=(8, 0))

        self._build_mode_card(left)
        self._build_devices_card(left)
        self._build_meter_card(right)

    def _build_topbar(self):
        bar = tk.Frame(self.root, bg=C["panel"], height=60)
        bar.pack(fill="x")
        bar.pack_propagate(False)
        for w in (bar,):
            w.bind("<Button-1>", self._start_drag)
            w.bind("<B1-Motion>", self._on_drag)

        brand = tk.Frame(bar, bg=C["panel"])
        brand.pack(side="left", padx=16)
        brand.bind("<Button-1>", self._start_drag)
        brand.bind("<B1-Motion>", self._on_drag)

        icon_wrap = tk.Frame(brand, bg="#10271b", highlightthickness=1,
                             highlightbackground="#173a28")
        icon_wrap.pack(side="left", padx=(0, 12), pady=8)
        widgets.EqIcon(icon_wrap, bg="#10271b", size=40).pack(padx=4, pady=4)

        texts = tk.Frame(brand, bg=C["panel"])
        texts.pack(side="left")
        tk.Label(texts, text="MicroNoise", bg=C["panel"], fg=C["text"],
                 font=self.fonts["brand"]).pack(anchor="w")
        self._tlabel(texts, "topbar_subtitle", bg=C["panel"], fg=C["muted"],
                     font=self.fonts["muted"]).pack(anchor="w")
        for w in (texts,):
            w.bind("<Button-1>", self._start_drag)
            w.bind("<B1-Motion>", self._on_drag)

        actions = tk.Frame(bar, bg=C["panel"])
        actions.pack(side="right", padx=12)
        mini = widgets.make_button(actions, "—", self._minimize, bg=C["panel"],
                                   fg=C["muted"], font=self.fonts["icon"],
                                   hover_bg=C["panel_lighter"], pad=(12, 6))
        mini.pack(side="left", padx=4)
        close = widgets.make_button(actions, "✕", self._on_close, bg=C["panel"],
                                    fg=C["muted"], font=self.fonts["icon"],
                                    hover_bg="#3a1f24", pad=(12, 6))
        close.pack(side="left")
        close.bind("<Enter>", lambda e: close.config(bg="#3a1f24", fg="white"))
        close.bind("<Leave>", lambda e: close.config(bg=C["panel"], fg=C["muted"]))

    def _build_hero(self, parent):
        card = tk.Frame(parent, bg=C["panel"], highlightthickness=1,
                        highlightbackground=C["border"])
        card.pack(fill="x")
        card.grid_columnconfigure(0, weight=1)

        text = tk.Frame(card, bg=C["panel"])
        text.grid(row=0, column=0, sticky="w", padx=24, pady=(18, 18))
        self._tlabel(text, "hero_title", bg=C["panel"], fg=C["text"],
                     font=self.fonts["hero"]).pack(anchor="w")
        self.hero_desc = tk.Label(
            text, bg=C["panel"], fg=C["muted"], font=self.fonts["body"],
            justify="left", wraplength=520, text=self._t("hero_desc_on"))
        self.hero_desc.pack(anchor="w", pady=(8, 0))

        power = tk.Frame(card, bg=C["panel"])
        power.grid(row=0, column=1, padx=24, pady=12)
        self.power_btn = widgets.PowerButton(power, bg=C["panel"],
                                             command=self._toggle_power, size=78)
        self.power_btn.pack()
        self.power_label = tk.Label(power, text=self._t("power_on"), bg=C["panel"],
                                    fg=C["green"], font=self.fonts["value"])
        self.power_label.pack(pady=(6, 0))

        # восстановить вид кнопки/подписи из сохранённого состояния
        self.power_btn.set_state(self.power_on)
        self._update_power_texts()

    def _build_footer(self, parent):
        footer = tk.Frame(parent, bg=C["bg"])
        footer.pack(side="bottom", fill="x", pady=(6, 0))

        # Переключатель языка — маленький выпадающий список в самом правом углу.
        self._lang_values = [("ru", "RU"), ("en", "EN")]
        self.lang_combo = ttk.Combobox(
            footer, style="Lang.TCombobox", state="readonly",
            font=self.fonts["lang"], width=3, takefocus=0,
            values=[name for _code, name in self._lang_values])
        self.lang_combo.pack(side="right", padx=(0, 2))
        self.lang_combo.bind("<<ComboboxSelected>>", self._on_lang_change)

        # Ссылка — слева от переключателя, 10px, тёмно-серая.
        link = tk.Label(footer, text="open source · github.com/sovenov",
                        bg=C["bg"], fg="#272727", font=self.fonts["footer"],
                        cursor="hand2")
        link.pack(side="right", padx=(10, 10))
        link.bind("<Button-1>",
                  lambda e: self._open_url("https://github.com/sovenov"))

        self._update_lang_switch()

    def _build_mode_card(self, parent):
        card = self._card(parent)
        card.pack(fill="x")
        self._eyebrow(card, "mode_eyebrow").pack(anchor="w", padx=20,
                                                 pady=(18, 14))
        grid = tk.Frame(card, bg=C["panel"])
        grid.pack(fill="x", padx=16, pady=(0, 16))

        self.mode_light = widgets.ModeOption(
            grid, "light", self._t("mode_light_title"),
            self._t("mode_light_desc"), command=self._select_mode)
        self.mode_light.pack(fill="x", pady=(0, 12))
        self.mode_strong = widgets.ModeOption(
            grid, "strong", self._t("mode_strong_title"),
            self._t("mode_strong_desc"), command=self._select_mode)
        self.mode_strong.pack(fill="x")

        self._mode_options = {config.MODE_LIGHT: self.mode_light,
                              config.MODE_STRONG: self.mode_strong}
        for key, opt in self._mode_options.items():
            opt.set_selected(key == self.mode)

    def _build_devices_card(self, parent):
        card = self._card(parent)
        card.pack(fill="x", pady=(12, 0))

        self._tlabel(card, "src_mic", bg=C["panel"], fg="#d9dee7",
                     font=self.fonts["strong"]).pack(anchor="w", padx=20,
                                                     pady=(14, 6))
        in_row = tk.Frame(card, bg=C["panel"])
        in_row.pack(fill="x", padx=20)
        in_icon = tk.Canvas(in_row, width=24, height=24, bg=C["panel"],
                            highlightthickness=0, bd=0)
        _mic = assets.icon("mic")
        if _mic is not None:
            in_icon.create_image(12, 12, image=_mic)
        else:
            widgets.draw_mic(in_icon, 12, 12, C["blue"])
        in_icon.pack(side="left", padx=(0, 8))
        self.input_combo = ttk.Combobox(in_row, style="Dark.TCombobox",
                                        state="readonly", font=self.fonts["body"])
        self.input_combo.pack(side="left", fill="x", expand=True)
        self.input_combo.bind("<<ComboboxSelected>>", self._on_input_change)

        self._tlabel(card, "virt_mic", bg=C["panel"], fg="#d9dee7",
                     font=self.fonts["strong"]).pack(anchor="w", padx=20,
                                                     pady=(12, 6))
        out_row = tk.Frame(card, bg=C["panel"])
        out_row.pack(fill="x", padx=20, pady=(0, 16))
        out_icon = tk.Canvas(out_row, width=24, height=24, bg=C["panel"],
                             highlightthickness=0, bd=0)
        _mon = assets.icon("monitor")
        if _mon is not None:
            out_icon.create_image(12, 12, image=_mon)
        else:
            widgets.draw_monitor(out_icon, 12, 12, C["blue"])
        out_icon.pack(side="left", padx=(0, 8))
        self.output_combo = ttk.Combobox(out_row, style="Dark.TCombobox",
                                         state="readonly", font=self.fonts["body"])
        self.output_combo.pack(side="left", fill="x", expand=True)
        self.output_combo.bind("<<ComboboxSelected>>", self._on_output_change)

    def _build_meter_card(self, parent):
        card = self._card(parent)
        card.pack(fill="x")
        self._eyebrow(card, "signal_eyebrow").pack(anchor="w", padx=20,
                                                   pady=(18, 2))
        self._tlabel(card, "signal_title", bg=C["panel"], fg=C["text"],
                     font=self.fonts["section"]).pack(anchor="w", padx=20,
                                                      pady=(0, 14))

        # входной
        in_head = tk.Frame(card, bg=C["panel"])
        in_head.pack(fill="x", padx=20)
        self._tlabel(in_head, "in_signal", bg=C["panel"], fg="#eef2f8",
                     font=self.fonts["strong"]).pack(side="left")
        self.in_val = tk.Label(in_head, text="0%", bg=C["panel"], fg=C["green"],
                               font=self.fonts["value"])
        self.in_val.pack(side="right")
        self.in_meter = widgets.Meter(card, bg=C["panel"], kind="input")
        self.in_meter.pack(fill="x", padx=20, pady=(8, 14))

        # выходной
        out_head = tk.Frame(card, bg=C["panel"])
        out_head.pack(fill="x", padx=20)
        self._tlabel(out_head, "out_signal", bg=C["panel"], fg="#eef2f8",
                     font=self.fonts["strong"]).pack(side="left")
        self.out_val = tk.Label(out_head, text="0%", bg=C["panel"], fg=C["blue"],
                                font=self.fonts["value"])
        self.out_val.pack(side="right")
        self.out_meter = widgets.Meter(card, bg=C["panel"], kind="output")
        self.out_meter.pack(fill="x", padx=20, pady=(8, 0))

        self.meter_hint = self._tlabel(
            card, "meter_hint", bg=C["panel"], fg=C["muted"],
            font=self.fonts["small"], justify="left", wraplength=400)
        self.meter_hint.pack(anchor="w", padx=20, pady=(12, 0))

        sep = tk.Frame(card, bg=C["border"], height=1)
        sep.pack(fill="x", padx=20, pady=16)

        # усиление
        gain_head = tk.Frame(card, bg=C["panel"])
        gain_head.pack(fill="x", padx=20)
        gtext = tk.Frame(gain_head, bg=C["panel"])
        gtext.pack(anchor="w", fill="x")
        self._tlabel(gtext, "gain_title", bg=C["panel"], fg=C["text"],
                     font=self.fonts["strong"]).pack(anchor="w")
        self._tlabel(gtext, "gain_desc", bg=C["panel"], fg=C["muted"],
                     font=self.fonts["muted"]).pack(anchor="w", pady=(2, 0))
        val_row = tk.Frame(card, bg=C["panel"])
        val_row.pack(fill="x", padx=20, pady=(12, 4))
        self.gain_val = tk.Label(val_row, text=self._fmt_gain(self.gain_db),
                                 bg=C["panel"], fg=C["green"],
                                 font=self.fonts["value"])
        self.gain_val.pack(side="left")
        self.gain_reset = widgets.make_button(
            val_row, self._t("reset"), self._reset_gain, bg=C["panel_soft"],
            fg=C["muted"], font=self.fonts["muted"],
            hover_bg=C["panel_lighter"], pad=(10, 4))
        self._tr_widgets.append((self.gain_reset, "reset", False))
        self.gain_reset.pack(side="right")

        slider_row = tk.Frame(card, bg=C["panel"])
        slider_row.pack(fill="x", padx=20, pady=(0, 20))
        self._tlabel(slider_row, "db_min", bg=C["panel"], fg=C["muted"],
                     font=self.fonts["small"]).pack(side="left")
        self._tlabel(slider_row, "db_max", bg=C["panel"], fg=C["muted"],
                     font=self.fonts["small"]).pack(side="right")
        self.gain_slider = widgets.GainSlider(
            slider_row, bg=C["panel"], minimum=config.GAIN_MIN_DB,
            maximum=config.GAIN_MAX_DB, step=0.5, command=self._on_gain)
        self.gain_slider.pack(side="left", fill="x", expand=True, padx=10)
        self.gain_slider.set(self.gain_db)  # восстановить положение из настроек

    # ------------------------------------------------------------------ devices
    def _load_devices(self):
        self.input_devs = devmod.list_inputs()
        self.output_devs = devmod.list_outputs()

        self.input_combo["values"] = [d["name"] for d in self.input_devs]
        self.output_combo["values"] = [d["name"] for d in self.output_devs]

        # Вход: сохранённый выбор, иначе системный по умолчанию.
        in_target = self._resolve_saved(self.input_devs,
                                        self._settings.get("input_name"))
        if in_target is None:
            in_target = devmod.default_input_index()
        # Выход (виртуальный микрофон): сохранённый выбор, иначе — автоподбор
        # (фактически только при первом запуске, т.к. дальше выбор сохраняется).
        # CABLE Input в приоритете.
        out_target = self._resolve_saved(self.output_devs,
                                         self._settings.get("output_name"))
        if out_target is None:
            out_target = devmod.guess_virtual_output()

        self.input_idx = self._select_combo(self.input_combo, self.input_devs,
                                            in_target)
        self.output_idx = self._select_combo(self.output_combo, self.output_devs,
                                             out_target)
        self._save_settings()

    def _resolve_saved(self, devs, name):
        """Индекс устройства с сохранённым именем или None, если не найдено."""
        if name:
            for d in devs:
                if d["name"] == name:
                    return d["index"]
        return None

    def _save_settings(self):
        # запоминаем весь пользовательский выбор, чтобы восстановить при старте
        self._settings["input_name"] = devmod.device_name(self.input_idx)
        self._settings["output_name"] = devmod.device_name(self.output_idx)
        self._settings["mode"] = self.mode
        self._settings["gain_db"] = round(float(self.gain_db), 2)
        self._settings["power_on"] = bool(self.power_on)
        self._settings["lang"] = self.lang
        settings.save(self._settings)

    def _schedule_save(self):
        """Отложенное сохранение (для частых событий — перетаскивания ползунка)."""
        if self._save_after_id is not None:
            try:
                self.root.after_cancel(self._save_after_id)
            except Exception:
                pass
        self._save_after_id = self.root.after(600, self._do_scheduled_save)

    def _do_scheduled_save(self):
        self._save_after_id = None
        self._save_settings()

    def _select_combo(self, combo, devs, target_index):
        for pos, dev in enumerate(devs):
            if dev["index"] == target_index:
                combo.current(pos)
                return target_index
        if devs:
            combo.current(0)
            return devs[0]["index"]
        return None

    def _apply_engine_config(self):
        self.engine.configure(input_idx=self.input_idx, output_idx=self.output_idx,
                              mode=self.mode, gain_db=self.gain_db)
        if self.power_on:
            self.engine.start()

    # ------------------------------------------------------------------ handlers
    def _toggle_power(self, on):
        self._set_power(on)

    def _set_power(self, on):
        on = bool(on)
        self.power_on = on
        self.power_btn.set_state(on)
        self._update_power_texts()
        if on:
            self.engine.configure(input_idx=self.input_idx,
                                  output_idx=self.output_idx, mode=self.mode,
                                  gain_db=self.gain_db)
            self.engine.start()
        else:
            self.engine.stop()
        # обновить серость пунктов «Вкл/Выкл» в меню трея
        if self._tray is not None:
            try:
                self._tray.update_menu()
            except Exception:
                pass
        self._save_settings()

    def _select_mode(self, option):
        mode = config.MODE_LIGHT if option is self.mode_light else config.MODE_STRONG
        if mode == self.mode:
            return
        self.mode = mode
        for key, opt in self._mode_options.items():
            opt.set_selected(key == mode)
        self.engine.set_mode(mode)
        self._save_settings()

    def _on_input_change(self, _event):
        pos = self.input_combo.current()
        if 0 <= pos < len(self.input_devs):
            self.input_idx = self.input_devs[pos]["index"]
            self.engine.set_input_device(self.input_idx)
            self._save_settings()

    def _on_output_change(self, _event):
        pos = self.output_combo.current()
        if 0 <= pos < len(self.output_devs):
            self.output_idx = self.output_devs[pos]["index"]
            self.engine.set_output_device(self.output_idx)
            self._save_settings()

    def _on_gain(self, value):
        self.gain_db = value
        self.gain_val.config(text=self._fmt_gain(value))
        self.engine.set_gain_db(value)
        self._schedule_save()

    def _reset_gain(self):
        self.gain_slider.set(0.0, notify=True)

    # ------------------------------------------------------------------ engine cb
    def _engine_error(self, message):
        self.root.after(0, lambda: self._show_engine_error(message))

    def _show_engine_error(self, message):
        self.toast.show("Ошибка: %s" % message)

    def _engine_status(self, state):
        pass

    # ------------------------------------------------------------------ tick
    def _tick(self):
        self._drain_tray()
        if not self._alive:
            return
        try:
            il, ol, _sp = self.engine.get_levels()
            if not self.power_on:
                il = ol = 0.0
            # экспоненциальное сглаживание — плавное движение полосок
            a = config.UI_METER_SMOOTHING
            self._disp_in += (il - self._disp_in) * a
            self._disp_out += (ol - self._disp_out) * a
            self.in_meter.set_value(self._disp_in)
            self.out_meter.set_value(self._disp_out)
            self.in_val.config(text="%d%%" % round(self._disp_in))
            self.out_val.config(text="%d%%" % round(self._disp_out))
        except Exception:
            pass
        if self._alive:
            self.root.after(config.UI_TICK_MS, self._tick)
