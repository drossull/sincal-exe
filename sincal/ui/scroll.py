import customtkinter as ctk


class SafeScrollableFrame(ctk.CTkScrollableFrame):
    """Scrollable frame compatible with Tk, ttk and CustomTkinter widgets.

    CustomTkinter 5.x assumes that ``event.widget`` always is a widget object.
    Tk may instead supply its Tcl path as a string when the pointer is over a
    ttk widget.  Since every scrollable frame installs a global wheel binding,
    that assumption can produce the same exception once per frame and per
    wheel tick.  Resolve the path when possible and traverse masters safely.
    """

    def check_if_master_is_canvas(self, widget):
        if isinstance(widget, str):
            try:
                widget = self.winfo_toplevel().nametowidget(widget)
            except (KeyError, TypeError, AttributeError):
                return False

        visited = set()
        while widget is not None and id(widget) not in visited:
            if widget == self._parent_canvas:
                return True
            visited.add(id(widget))
            widget = getattr(widget, "master", None)
        return False
