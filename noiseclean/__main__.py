"""Точка входа: python -m noiseclean"""

from .singleinstance import SingleInstance


def main():
    # Не запускать второй экземпляр. Если приложение уже работает — просим его
    # показать окно и сразу выходим (тяжёлые модули даже не грузим).
    instance = SingleInstance()
    if not instance.is_primary:
        if not instance.signal_show():
            from . import settings
            lang = (settings.load() or {}).get("lang", "ru")
            instance.show_already_running_message(lang)
        return

    import tkinter as tk
    from .ui.app import NoiseCleanApp

    root = tk.Tk()
    NoiseCleanApp(root, single_instance=instance)
    root.mainloop()


if __name__ == "__main__":
    main()
