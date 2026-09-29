"""Widgets visuales reutilizables de SINCAL Suite."""

from __future__ import annotations

import customtkinter as ctk

from sincal.ui.theme import COLOR_ACENTO, COLOR_MARCO_BOTON, FAMILIA_BOTONES, FUENTE_BOTON
from sincal.ui.motion import Transition, system_reduces_motion


class ShadowButton(ctk.CTkFrame):
    """Botón CTk con una sombra corta hacia abajo y a la derecha.

    Es un contenedor compatible con ``pack`` y ``grid``. Las opciones y los
    eventos propios del botón se delegan al control interior para conservar la
    API usada por el resto de la aplicación.
    """

    _DEFAULT_WIDTH = 140
    _DEFAULT_HEIGHT = 36

    def __init__(
        self,
        master,
        *,
        shadow_size: int = 4,
        shadow_color=COLOR_ACENTO,
        flat: bool = False,
        **kwargs,
    ) -> None:
        button_width = int(kwargs.pop("width", self._DEFAULT_WIDTH))
        button_height = int(kwargs.pop("height", self._DEFAULT_HEIGHT))
        self._shadow_size = 0 if flat else max(0, shadow_size)
        self._button_width = button_width
        self._button_height = button_height
        font = kwargs.get("font", FUENTE_BOTON)
        if isinstance(font, tuple):
            kwargs["font"] = (FAMILIA_BOTONES, *font[1:])
        kwargs["corner_radius"] = 0
        if flat:
            kwargs["border_width"] = 0
        else:
            kwargs["border_width"] = 1
            kwargs["border_color"] = COLOR_MARCO_BOTON

        super().__init__(
            master,
            width=button_width + self._shadow_size,
            height=button_height + self._shadow_size,
            fg_color="transparent",
            corner_radius=0,
        )
        self.pack_propagate(False)
        self.grid_propagate(False)

        self._shadow = ctk.CTkFrame(
            self,
            fg_color=shadow_color,
            corner_radius=0,
        )
        self._button = ctk.CTkButton(
            self,
            width=button_width,
            height=button_height,
            **kwargs,
        )
        self._layout_layers()
        self._motion = Transition(self)
        self._lift = 0.0
        self._button.bind("<Enter>", lambda e: self._animate_lift(1), add="+")
        self._button.bind("<Leave>", lambda e: self._animate_lift(0), add="+")
        self._button.bind("<ButtonPress-1>", lambda e: self._animate_lift(2), add="+")
        self._button.bind("<ButtonRelease-1>", lambda e: self._animate_lift(0), add="+")
        self._button._canvas.bind("<Return>", lambda e: self.invoke(), add="+")
        self._button._canvas.bind("<space>", lambda e: self.invoke(), add="+")
        super().bind("<Configure>", self._resize_layers, add="+")

    def _animate_lift(self, target):
        if not self._shadow_size or self._button.cget("state") == "disabled":
            return
        start = self._lift
        reduced = getattr(self.winfo_toplevel(), "_reduced_motion", False) or system_reduces_motion()
        def draw(fraction):
            self._lift = start + (target - start) * fraction
            self._button.place_configure(x=round(self._lift), y=round(self._lift))
        self._motion.run(draw, duration=0 if reduced else 150)

    def destroy(self):
        if hasattr(self, "_motion"):
            self._motion.cancel()
        super().destroy()

    def _layout_layers(self) -> None:
        size = self._shadow_size
        if size:
            self._shadow.place(x=size, y=size)
            self._button.place(x=0, y=0)
        else:
            self._shadow.place_forget()
            self._button.place(x=0, y=0)
        self.after_idle(self._resize_layers)

    def _resize_layers(self, _event=None) -> None:
        if not self.winfo_exists():
            return
        width = max(1, self.winfo_width() - self._shadow_size)
        height = max(1, self.winfo_height() - self._shadow_size)
        self._shadow.configure(width=width, height=height)
        self._button.configure(width=width, height=height)

    def configure(self, require_redraw=False, **kwargs):
        """Configura el botón interior y conserva sus dimensiones externas."""
        width = kwargs.pop("width", None)
        height = kwargs.pop("height", None)
        if width is not None:
            self._button_width = int(width)
            super().configure(width=self._button_width + self._shadow_size)
            kwargs["width"] = self._button_width
        if height is not None:
            self._button_height = int(height)
            super().configure(height=self._button_height + self._shadow_size)
            kwargs["height"] = self._button_height
        if kwargs:
            return self._button.configure(require_redraw=require_redraw, **kwargs)
        return None

    config = configure

    def cget(self, attribute_name):
        if not hasattr(self, "_button"):
            return super().cget(attribute_name)
        if attribute_name == "width":
            return self._button_width
        if attribute_name == "height":
            return self._button_height
        return self._button.cget(attribute_name)

    def bind(self, sequence=None, command=None, add=None):
        result = super().bind(sequence, command, add)
        self._shadow.bind(sequence, command, add)
        self._button.bind(sequence, command, add)
        return result

    def unbind(self, sequence, funcid=None):
        super().unbind(sequence, funcid)
        self._shadow.unbind(sequence, funcid)
        self._button.unbind(sequence, funcid)

    def focus(self):
        return self.focus_set()

    def focus_set(self):
        # CTkButton.focus_set assumes a text label, absent in icon-only buttons.
        return self._button._canvas.focus_set()

    def invoke(self):
        return self._button.invoke()
