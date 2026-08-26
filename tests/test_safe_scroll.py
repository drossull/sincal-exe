import unittest

from sincal.ui.scroll import SafeScrollableFrame


class _Widget:
    def __init__(self, master=None):
        self.master = master


class _TopLevel:
    def __init__(self, mapping):
        self.mapping = mapping

    def nametowidget(self, name):
        if name not in self.mapping:
            raise KeyError(name)
        return self.mapping[name]


class SafeScrollTests(unittest.TestCase):
    def setUp(self):
        self.canvas = _Widget()
        self.child = _Widget(self.canvas)
        self.frame = object.__new__(SafeScrollableFrame)
        self.frame._parent_canvas = self.canvas
        top = _TopLevel({".!treeview": self.child})
        self.frame.winfo_toplevel = lambda: top

    def test_accepts_tk_widget_path_strings(self):
        self.assertTrue(self.frame.check_if_master_is_canvas(".!treeview"))

    def test_unknown_widget_path_is_ignored(self):
        self.assertFalse(self.frame.check_if_master_is_canvas(".!missing"))

    def test_plain_widget_without_master_is_ignored(self):
        self.assertFalse(self.frame.check_if_master_is_canvas(_Widget()))


if __name__ == "__main__":
    unittest.main()
