"""Transiciones cortas, cancelables y sin bloquear el bucle Tk."""
import ctypes
import os
import time


def system_reduces_motion():
    if os.name == "nt":
        enabled = ctypes.c_int(1)
        try:
            if ctypes.windll.user32.SystemParametersInfoW(0x1042, 0, ctypes.byref(enabled), 0):
                return not bool(enabled.value)
        except (AttributeError, OSError):
            pass
    return False


class Transition:
    def __init__(self, owner):
        self.owner = owner
        self.job = None

    def cancel(self):
        if self.job is not None:
            self.owner.after_cancel(self.job)
            self.job = None

    def run(self, draw, done=lambda: None, duration=180):
        self.cancel()
        if duration <= 0:
            draw(1.0)
            done()
            return
        started = time.monotonic()

        def tick():
            self.job = None
            if not self.owner.winfo_exists():
                return
            fraction = min(1.0, (time.monotonic() - started) * 1000 / duration)
            draw(1 - (1 - fraction) ** 3)
            if fraction < 1:
                self.job = self.owner.after(16, tick)
            else:
                done()
        tick()
