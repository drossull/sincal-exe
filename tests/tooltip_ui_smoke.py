"""Real Tk regression checks, run in an isolated interpreter by pytest."""
import time
import tkinter as tk
import unittest
from unittest.mock import patch

import customtkinter as ctk

from sincal.ui.theme import Tooltip


class TooltipLifecycleTests(unittest.TestCase):
    def setUp(self):
        self.root = ctk.CTk()
        self.root.withdraw()
        self.errors = []
        self.root.report_callback_exception = lambda *args: self.errors.append(args)
        self.button = ctk.CTkButton(self.root, text="Tema")
        self.tooltip = Tooltip(self.button, "Cambiar tema")

    def tearDown(self):
        self.tooltip.hide()
        self.root.destroy()

    def drain_events(self):
        deadline = time.monotonic() + .08
        while time.monotonic() < deadline:
            self.root.update()
            time.sleep(.005)

    def test_tooltip_has_no_native_titlebar_retheme_callbacks(self):
        with patch.object(ctk.CTkToplevel, "_windows_set_titlebar_color") as titlebar:
            self.tooltip._show_now()
            self.assertIsNotNone(self.tooltip.window)
            titlebar.assert_not_called()

    def test_theme_switch_and_expiring_tooltip_do_not_raise(self):
        for mode in ("light", "dark", "light", "dark"):
            self.tooltip._show_now()
            self.root.after(0, self.tooltip.hide)
            ctk.set_appearance_mode(mode)
            self.drain_events()
            self.assertIsNone(self.tooltip.window)
        self.assertEqual(self.errors, [])

    def test_destroying_owner_cancels_pending_help(self):
        self.tooltip.show()
        job = self.tooltip.show_job
        self.button.destroy()
        self.assertIsNone(self.tooltip.show_job)
        with self.assertRaises(tk.TclError):
            self.root.tk.call("after", "info", job)

    def test_destroying_owner_closes_visible_help_and_cancels_expiration(self):
        self.tooltip._show_now()
        window = self.tooltip.window
        job = self.tooltip.hide_job
        self.button.destroy()
        self.assertIsNone(self.tooltip.window)
        self.assertIsNone(self.tooltip.hide_job)
        self.assertFalse(window.winfo_exists())
        with self.assertRaises(tk.TclError):
            self.root.tk.call("after", "info", job)


if __name__ == "__main__":
    unittest.main()
