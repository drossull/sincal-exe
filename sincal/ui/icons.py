"""Iconografía monocroma y escalable para la interfaz SINCAL."""
from __future__ import annotations

from functools import lru_cache
import math

import customtkinter as ctk
from PIL import Image, ImageDraw


LIGHT_ICON = "#3A2F2B"
DARK_ICON = "#F2F5F8"


def _draw_icon(name: str, size: int, color: str) -> Image.Image:
    scale = 4
    side = size * scale
    image = Image.new("RGBA", (side, side), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    width = max(5, round(side * 0.075))
    pad = round(side * 0.18)

    def line(points, **kwargs):
        draw.line(points, fill=color, width=width, joint="curve", **kwargs)

    def rect(box, radius=0):
        draw.rounded_rectangle(box, radius=radius, outline=color, width=width)

    if name == "home":
        line(((pad, side * .48), (side * .5, pad), (side - pad, side * .48)))
        line(((side * .28, side * .43), (side * .28, side - pad), (side * .72, side - pad), (side * .72, side * .43)))
    elif name == "terminal":
        rect((pad, side * .24, side - pad, side * .76), side * .05)
        line(((side * .32, side * .40), (side * .43, side * .50), (side * .32, side * .60)))
        line(((side * .50, side * .61), (side * .65, side * .61)))
    elif name == "book":
        line(((side * .18, side * .25), (side * .42, side * .20), (side * .50, side * .28), (side * .58, side * .20), (side * .82, side * .25)))
        line(((side * .18, side * .25), (side * .18, side * .76), (side * .43, side * .80), (side * .50, side * .72), (side * .57, side * .80), (side * .82, side * .76), (side * .82, side * .25)))
        line(((side * .50, side * .28), (side * .50, side * .72)))
    elif name == "rename":
        line(((side * .20, side * .35), (side * .70, side * .35)))
        line(((side * .62, side * .27), (side * .72, side * .35), (side * .62, side * .43)))
        line(((side * .80, side * .65), (side * .30, side * .65)))
        line(((side * .38, side * .57), (side * .28, side * .65), (side * .38, side * .73)))
    elif name == "pin":
        draw.ellipse((side * .31, side * .16, side * .69, side * .54), outline=color, width=width)
        draw.ellipse((side * .44, side * .29, side * .56, side * .41), fill=color)
        line(((side * .34, side * .48), (side * .50, side * .82), (side * .66, side * .48)))
    elif name == "structure":
        line(((side * .18, side * .78), (side * .18, side * .30), (side * .82, side * .30), (side * .82, side * .78)))
        line(((side * .18, side * .47), (side * .82, side * .47)))
        line(((side * .18, side * .64), (side * .82, side * .64)))
        line(((side * .38, side * .30), (side * .38, side * .78)))
        line(((side * .62, side * .30), (side * .62, side * .78)))
    elif name == "sessions":
        rect((side * .25, side * .20, side * .75, side * .76), side * .02)
        line(((side * .34, side * .36), (side * .66, side * .36)))
        line(((side * .34, side * .50), (side * .62, side * .50)))
        line(((side * .34, side * .64), (side * .56, side * .64)))
    elif name == "query":
        rect((side * .22, side * .18, side * .66, side * .76), side * .02)
        line(((side * .30, side * .34), (side * .57, side * .34)))
        line(((side * .30, side * .47), (side * .53, side * .47)))
        draw.ellipse(
            (side * .51, side * .49, side * .78, side * .76),
            outline=color, width=width)
        line(((side * .72, side * .70), (side * .84, side * .82)))
    elif name == "convert":
        line(((side * .20, side * .35), (side * .68, side * .35)))
        line(((side * .60, side * .25), (side * .72, side * .35), (side * .60, side * .45)))
        line(((side * .80, side * .65), (side * .32, side * .65)))
        line(((side * .40, side * .55), (side * .28, side * .65), (side * .40, side * .75)))
    elif name == "diagnostic":
        draw.ellipse((side * .18, side * .18, side * .70, side * .70), outline=color, width=width)
        line(((side * .62, side * .62), (side * .82, side * .82)))
        line(((side * .32, side * .46), (side * .42, side * .56), (side * .58, side * .36)))
    elif name == "menu":
        for y in (.30, .50, .70):
            line(((side * .22, side * y), (side * .78, side * y)))
    elif name == "folder":
        line(((side * .16, side * .34), (side * .42, side * .34), (side * .49, side * .42), (side * .84, side * .42), (side * .78, side * .76), (side * .16, side * .76), (side * .16, side * .34)))
    elif name == "settings":
        draw.ellipse((side * .25, side * .25, side * .75, side * .75), outline=color, width=width)
        draw.ellipse((side * .41, side * .41, side * .59, side * .59), outline=color, width=width)
        for angle in range(0, 360, 45):
            a = angle * 3.14159265 / 180
            p1 = (side * (.5 + .25 * math.cos(a)), side * (.5 + .25 * math.sin(a)))
            p2 = (side * (.5 + .37 * math.cos(a)), side * (.5 + .37 * math.sin(a)))
            line((p1, p2))
    elif name in ("refresh", "update"):
        draw.arc((side * .18, side * .18, side * .82, side * .82), 35, 315, fill=color, width=width)
        line(((side * .69, side * .18), (side * .82, side * .24), (side * .75, side * .37)))
        if name == "update":
            line(((side * .50, side * .32), (side * .50, side * .63)))
            line(((side * .39, side * .54), (side * .50, side * .65), (side * .61, side * .54)))
    elif name == "download":
        line(((side * .50, side * .18), (side * .50, side * .60)))
        line(((side * .36, side * .48), (side * .50, side * .62), (side * .64, side * .48)))
        line(((side * .24, side * .76), (side * .76, side * .76)))
    else:
        draw.ellipse((pad, pad, side - pad, side - pad), outline=color, width=width)
    return image.resize((size, size), Image.Resampling.LANCZOS)


@lru_cache(maxsize=64)
def obtener_icono(name: str, size: int = 18) -> ctk.CTkImage:
    return ctk.CTkImage(
        light_image=_draw_icon(name, size, LIGHT_ICON),
        dark_image=_draw_icon(name, size, DARK_ICON),
        size=(size, size),
    )
