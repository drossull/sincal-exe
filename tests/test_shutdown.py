import types
import unittest
from unittest.mock import Mock, patch

from sincal import app as core_sincal


class ShutdownTests(unittest.TestCase):
    def test_window_close_stops_polling_and_destroys_the_application(self):
        app = types.SimpleNamespace(
            _cerrando=False,
            cancelar_comando_vivo=False,
            _resource_poll_job="poll-job",
            after_cancel=Mock(),
            logger=Mock(),
            quit=Mock(),
            destroy=Mock(),
        )

        with patch.object(core_sincal, "record_incident") as record_incident:
            core_sincal.ActualizadorCAD.cerrar_aplicacion(app)

        self.assertTrue(app._cerrando)
        self.assertTrue(app.cancelar_comando_vivo)
        self.assertIsNone(app._resource_poll_job)
        app.after_cancel.assert_called_once_with("poll-job")
        app.quit.assert_called_once_with()
        app.destroy.assert_called_once_with()
        record_incident.assert_called_once_with("cierre_aplicacion", "ok")


if __name__ == "__main__":
    unittest.main()
