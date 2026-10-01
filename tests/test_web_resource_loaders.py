from threading import Lock
from types import SimpleNamespace
from unittest.mock import Mock, patch

from sincal.web.services import Services


def test_web_update_materializes_loaders_after_download():
    service = SimpleNamespace(lock=Lock(), plans={"key": ("sync", "plan")})
    job = Mock()
    from sincal.resources import ResourceSyncResult
    with patch("sincal.resources.apply_resource_updates") as apply, patch(
        "sincal.resources.materialize_cad_resources"
    ) as materialize:
        apply.return_value = ResourceSyncResult(("lisps/PNDMAKE.lsp",), (), "revision")
        timeline = Mock()
        timeline.attach_mock(apply, "download")
        timeline.attach_mock(materialize, "loaders")
        result = Services.sync_apply(service, job, {"plan": "key"})
    assert result["updated"] == ("lisps/PNDMAKE.lsp",)
    assert [call[0] for call in timeline.mock_calls] == ["download", "loaders"]


def test_web_update_reports_loader_failure_instead_of_success():
    service = SimpleNamespace(lock=Lock(), plans={"key": ("sync", "plan")})
    import pytest
    with patch("sincal.resources.apply_resource_updates"), patch(
        "sincal.resources.materialize_cad_resources", side_effect=OSError("loader locked")
    ):
        with pytest.raises(OSError, match="loader locked"):
            Services.sync_apply(service, Mock(), {"plan": "key"})
