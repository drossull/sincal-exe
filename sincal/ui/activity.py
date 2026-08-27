"""Indicador global de trabajo inspirado en la animación vectorial de SINCAL.

La geometría procede del concepto ``bridge-motion``: una estructura superior
curva y barras verticales que avanzan conservando el contacto con su intradós.
Se renderiza en memoria para no distribuir DXF, GIF, ezdxf ni FFmpeg con la app.
"""

from __future__ import annotations

import math
import tkinter as tk
import time
from dataclasses import dataclass

import customtkinter as ctk
from PIL import Image, ImageDraw, ImageTk

from sincal.ui.theme import (
    COLOR_ACENTO,
    COLOR_FONDO,
    FUENTE_CARGA,
)


@dataclass
class _Activity:
    label: str
    progress: float | None
    sequence: int


class BridgeMotion:
    """Genera fotogramas transparentes y suavizados del isotipo en movimiento."""

    def __init__(self, width: int = 88, height: int = 54, frames: int = 30) -> None:
        self.width = width
        self.height = height
        self.frame_count = frames

    @staticmethod
    def _guide(x: float) -> float:
        # Curva creciente del ícono, expresada en coordenadas normalizadas.
        return 0.78 - 0.67 * math.pow(max(0.0, min(1.0, x)), 1.72)

    def render(self, color: str) -> list[Image.Image]:
        scale = 3
        width, height = self.width * scale, self.height * scale
        frames: list[Image.Image] = []
        period = 0.145
        bar_width = 0.047

        for index in range(self.frame_count):
            image = Image.new("RGBA", (width, height), (0, 0, 0, 0))
            draw = ImageDraw.Draw(image)
            phase = (index / self.frame_count) * period

            x = -period + phase
            while x <= 1.0:
                right = x + bar_width
                if x >= 0 and right <= 1:
                    draw.polygon(
                        (
                            (round(x * width), height),
                            (round(right * width), height),
                            (round(right * width), round(self._guide(right) * height)),
                            (round(x * width), round(self._guide(x) * height)),
                        ),
                        fill=color,
                    )
                x += period

            # Reproduce el logo: borde superior horizontal con aire transparente
            # encima e intradós curvo que converge hacia el extremo derecho.
            samples = 80
            deck_top = 0.18
            deck_samples = [
                x for x in range(samples + 1)
                if self._guide(x / samples) >= deck_top
            ]
            deck_end = deck_samples[-1]
            upper_edge = [
                (0, round(deck_top * height)),
                (round(deck_end / samples * width), round(deck_top * height)),
            ]
            lower_edge = [
                (round(x / samples * width), round(self._guide(x / samples) * height))
                for x in range(deck_end, -1, -1)
            ]
            draw.polygon(upper_edge + lower_edge, fill=color)
            frames.append(
                image.resize((self.width, self.height), Image.Resampling.LANCZOS)
            )
        return frames


class ActivityIndicator(ctk.CTkFrame):
    """Indicador único para todos los procesos concurrentes de la aplicación."""

    def __init__(self, master, **kwargs) -> None:
        super().__init__(
            master,
            width=170,
            height=92,
            fg_color="transparent",
            border_width=0,
            corner_radius=0,
            **kwargs,
        )
        self.pack_propagate(False)
        self.grid_propagate(False)
        self._activities: dict[str, _Activity] = {}
        self._sequence = 0
        self._frame_index = 0
        self._animation_job: str | None = None
        self._hide_job: str | None = None
        self._shown_at = 0.0
        self._hold_until = 0.0
        self._motion = BridgeMotion()
        self._images_by_mode: dict[str, list[ImageTk.PhotoImage]] = {}

        self.grid_columnconfigure(0, weight=1)
        self.animation = tk.Label(
            self,
            text="",
            borderwidth=0,
            highlightthickness=0,
            background=self._background_hex(),
        )
        self.animation.grid(row=0, column=0, padx=0, pady=(0, 4))
        self.status = ctk.CTkLabel(
            self,
            text="Procesando…",
            font=FUENTE_CARGA,
            text_color=COLOR_ACENTO,
            anchor="center",
        )
        self.status.grid(row=1, column=0, sticky="ew", padx=2, pady=(0, 2))

    @staticmethod
    def _mode() -> str:
        return "light" if ctk.get_appearance_mode().lower() == "light" else "dark"

    def _background_hex(self) -> str:
        value = COLOR_FONDO
        if isinstance(value, (tuple, list)):
            return value[0] if self._mode() == "light" else value[1]
        return value

    def _accent_hex(self) -> str:
        value = COLOR_ACENTO
        if isinstance(value, (tuple, list)):
            return value[0] if self._mode() == "light" else value[1]
        return value

    def _frames(self) -> list[ImageTk.PhotoImage]:
        mode = self._mode()
        if mode not in self._images_by_mode:
            self._images_by_mode[mode] = [
                ImageTk.PhotoImage(frame, master=self)
                for frame in self._motion.render(self._accent_hex())
            ]
        return self._images_by_mode[mode]

    def begin(self, key: str, label: str, progress: float | None = None) -> None:
        if not self._activities:
            self._shown_at = time.monotonic()
        self._hold_until = 0.0
        if self._hide_job is not None:
            self.after_cancel(self._hide_job)
            self._hide_job = None
        self._sequence += 1
        self._activities[key] = _Activity(label, self._normalize(progress), self._sequence)
        self._refresh()
        if self._animation_job is None:
            self._animate()

    def update_activity(
        self, key: str, progress: float | None = None, label: str | None = None
    ) -> None:
        current = self._activities.get(key)
        if current is None:
            self.begin(key, label or "Procesando", progress)
            return
        self._activities[key] = _Activity(
            label or current.label,
            self._normalize(progress),
            current.sequence,
        )
        self._refresh()

    def finish(self, key: str) -> None:
        self._activities.pop(key, None)
        if self._activities:
            self._refresh()
            return
        if self._hide_job is not None:
            try:
                self.after_cancel(self._hide_job)
            except Exception:
                pass
            self._hide_job = None
        remaining = max(0.0, 0.8 - (time.monotonic() - self._shown_at))
        if remaining:
            self._hold_until = time.monotonic() + remaining
            self._hide_job = self.after(round(remaining * 1000), self._hide_if_idle)
        else:
            self._hide_if_idle()

    def _hide_if_idle(self) -> None:
        self._hide_job = None
        if self._activities:
            return
        self._hold_until = 0.0
        if self._animation_job is not None:
            self.after_cancel(self._animation_job)
            self._animation_job = None
        self.place_forget()

    @staticmethod
    def _normalize(progress: float | None) -> float | None:
        if progress is None:
            return None
        return max(0.0, min(100.0, float(progress)))

    def _current(self) -> _Activity | None:
        return max(self._activities.values(), key=lambda item: item.sequence, default=None)

    def _refresh(self) -> None:
        current = self._current()
        if current is None:
            return
        progress = "" if current.progress is None else f" · {round(current.progress):d} %"
        self.status.configure(text=f"{current.label}{progress}")
        self.animation.configure(background=self._background_hex())
        self.place(relx=1.0, rely=1.0, x=-22, y=-18, anchor="se")
        self.lift()

    def _animate(self) -> None:
        holding = self._hold_until > time.monotonic()
        if (not self._activities and not holding) or not self.winfo_exists():
            self._animation_job = None
            return
        frames = self._frames()
        frame = frames[self._frame_index % len(frames)]
        self.animation.configure(image=frame)
        self.animation.image = frame
        self._frame_index += 1
        self._animation_job = self.after(50, self._animate)

    def refresh_theme(self) -> None:
        """Recrea el fotograma activo cuando cambia el tema de la aplicación."""
        self.animation.configure(background=self._background_hex())
        if self._activities:
            self._refresh()
