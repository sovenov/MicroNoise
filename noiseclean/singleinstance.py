"""Контроль единственного экземпляра MicroNoise (Windows).

Нельзя запускать второй экземпляр. Реализация на объектах ядра Windows:

* **именованный mutex** — атомарный признак «приложение уже запущено»;
* **именованное авто-сброс событие** — канал «покажи окно»: второй экземпляр
  выставляет событие и завершается, а первый (он его слушает в фоновом потоке)
  разворачивает своё окно — даже если оно свёрнуто в трей.

Имена объектов в пространстве ``Local\\`` — на текущую сессию пользователя
(достаточно для обычного запуска из проводника).
"""

import sys
import threading

_MUTEX_NAME = "Local\\MicroNoise.SingleInstance.Mutex"
_EVENT_NAME = "Local\\MicroNoise.SingleInstance.ShowEvent"
_ERROR_ALREADY_EXISTS = 183
_INFINITE = 0xFFFFFFFF
_WAIT_OBJECT_0 = 0
_ASFW_ANY = 0xFFFFFFFF  # AllowSetForegroundWindow: разрешить любому процессу


class SingleInstance:
    """Признак первого/второго экземпляра и канал «показать окно».

    Создаётся как можно раньше при старте. ``is_primary`` == False означает,
    что приложение уже запущено.
    """

    def __init__(self):
        self.is_primary = True
        self._mutex = None
        self._event = None
        self._stop = False
        if sys.platform != "win32":
            return
        try:
            import ctypes
            from ctypes import wintypes
            k32 = ctypes.windll.kernel32
            k32.CreateMutexW.restype = wintypes.HANDLE
            k32.CreateMutexW.argtypes = [wintypes.LPVOID, wintypes.BOOL,
                                         wintypes.LPCWSTR]
            k32.CreateEventW.restype = wintypes.HANDLE
            k32.CreateEventW.argtypes = [wintypes.LPVOID, wintypes.BOOL,
                                         wintypes.BOOL, wintypes.LPCWSTR]
            self._mutex = k32.CreateMutexW(None, False, _MUTEX_NAME)
            # GetLastError сразу после CreateMutexW — без промежуточных вызовов.
            if k32.GetLastError() == _ERROR_ALREADY_EXISTS:
                self.is_primary = False
            # авто-сброс событие, изначально несигнальное
            self._event = k32.CreateEventW(None, False, False, _EVENT_NAME)
        except Exception:
            # при любой ошибке не блокируем запуск — считаем себя первым
            self.is_primary = True

    # ----------------------------------------------------- вторичный экземпляр
    def signal_show(self):
        """Попросить уже запущенный экземпляр показать окно. True при успехе."""
        if sys.platform != "win32" or not self._event:
            return False
        try:
            import ctypes
            # разрешаем первому экземпляру вытащить окно на передний план
            try:
                ctypes.windll.user32.AllowSetForegroundWindow(_ASFW_ANY)
            except Exception:
                pass
            return bool(ctypes.windll.kernel32.SetEvent(self._event))
        except Exception:
            return False

    @staticmethod
    def show_already_running_message(lang="ru"):
        """Запасной вариант: сообщить, что приложение уже запущено."""
        if sys.platform != "win32":
            return
        msg = ("MicroNoise is already running." if lang == "en"
               else "MicroNoise уже запущен.")
        try:
            import ctypes
            MB_OK = 0x0
            MB_ICONINFORMATION = 0x40
            ctypes.windll.user32.MessageBoxW(
                None, msg, "MicroNoise", MB_OK | MB_ICONINFORMATION)
        except Exception:
            pass

    # ------------------------------------------------------ первичный экземпляр
    def start_listener(self, on_show):
        """Фоновое ожидание сигнала «покажи окно» (вызывать в первом экземпляре).

        ``on_show`` вызывается из фонового потока, поэтому должен быть
        потокобезопасным (класть задачу в очередь главного потока Tk).
        """
        if sys.platform != "win32" or not self._event:
            return
        threading.Thread(target=self._wait_loop, args=(on_show,),
                         daemon=True).start()

    def _wait_loop(self, on_show):
        try:
            import ctypes
            k32 = ctypes.windll.kernel32
            while not self._stop:
                r = k32.WaitForSingleObject(self._event, _INFINITE)
                if self._stop:
                    break
                if r == _WAIT_OBJECT_0:
                    try:
                        on_show()
                    except Exception:
                        pass
                else:
                    break
        except Exception:
            pass

    def stop(self):
        """Остановить фоновый поток (при выходе)."""
        self._stop = True
        if sys.platform == "win32" and self._event:
            try:
                import ctypes
                ctypes.windll.kernel32.SetEvent(self._event)  # разбудить поток
            except Exception:
                pass
