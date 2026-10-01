"""Cadence families with readable accent text on their actual background."""
from sincal.ui.cadence_palettes import FAMILIES


def rgb(value):
    return tuple(int(value[i:i+2], 16) for i in (1, 3, 5))


def luminance(color):
    values = [v / 255 for v in rgb(color)]
    values = [v / 12.92 if v <= .04045 else ((v + .055) / 1.055) ** 2.4 for v in values]
    return sum(a * b for a, b in zip(values, (.2126, .7152, .0722)))


def contrast(a, b):
    values = sorted((luminance(a), luminance(b)))
    return (values[1] + .05) / (values[0] + .05)


def readable_accent(color, background, foreground):
    source, target = rgb(color), rgb(foreground)
    for step in range(21):
        mixed = '#' + ''.join(f'{round(a + (b-a)*step/20):02x}' for a, b in zip(source, target))
        if contrast(mixed, background) >= 4.5:
            return mixed
    return foreground


def stylesheet():
    rules = []
    for name, palette in FAMILIES.items():
        for mode in ('light', 'dark'):
            bg, fg = palette[mode]
            accent = readable_accent(palette['primary'], bg, fg)
            rules.append(f':root[data-palette="{name}"][data-theme="{mode}"]' + '{' +
                         f'--bg:{bg};--text:{fg};--muted:{fg};--line:{palette["neutral"]};--accent:{accent};--field:{bg};' + '}')
    return '\n'.join(rules).encode()
