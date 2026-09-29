import tempfile
import unittest
from pathlib import Path
from sincal.ui.preferences import load_preferences, save_preferences
from sincal.ui.theme import THEME_LABELS, palette_for, mix_colors
from sincal.ui.motion import Transition


class CadencePreferencesTests(unittest.TestCase):
    def test_cadence_theme_families_and_reference_colors(self):
        self.assertEqual(len(THEME_LABELS), 16)
        self.assertEqual(palette_for('nord', True)['fondo'], '#2e3440')
        self.assertEqual(palette_for('nord', False)['texto'], '#2e3440')
        self.assertEqual(palette_for('cadence', True)['acento'], '#FFB000')
        self.assertEqual(palette_for('unknown', True), palette_for('cadence', True))
        self.assertEqual(mix_colors('#000000', '#ffffff', .5), '#808080')

    def test_preferences_roundtrip_and_invalid_values(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'ui.json'
            values = dict(family='nord', mode='system', panels_expanded=False, reduced_motion=True)
            self.assertTrue(save_preferences(values, path))
            self.assertEqual(load_preferences(path), values)
            path.write_text('{invalid', encoding='utf-8')
            self.assertEqual(load_preferences(path)['family'], 'cadence')
            save_preferences({'family':'missing', 'mode': 'bad', 'panels_expanded': 'false'}, path)
            self.assertEqual(load_preferences(path)['panels_expanded'], True)
            self.assertEqual(load_preferences(path)['mode'], 'dark')

    def test_transition_is_cancelable_and_can_be_instant(self):
        class Clock:
            def __init__(self):
                self.jobs = {}
            def winfo_exists(self):
                return True
            def after(self, delay, callback):
                self.jobs[1] = callback
                return 1
            def after_cancel(self, job):
                self.jobs.pop(job)
        owner = Clock()
        transition = Transition(owner)
        frames, completed = [], []
        transition.run(frames.append)
        self.assertEqual(len(owner.jobs), 1)
        transition.run(frames.append, lambda: completed.append(True), duration=0)
        self.assertEqual(owner.jobs, {})
        self.assertEqual(frames[-1], 1.0)
        self.assertEqual(completed, [True])


if __name__ == '__main__':
    unittest.main()
