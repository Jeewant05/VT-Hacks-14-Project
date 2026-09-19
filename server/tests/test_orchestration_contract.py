"""Keep the frontend-facing orchestration response contract stable during the demo."""

import json

from server.app.config import ROOT
from server.app.main import app


def test_orchestration_api_v1_snapshot_is_unchanged():
    snapshot = json.loads((ROOT / "contracts" / "orchestration-api-v1.json").read_text())
    current = {
        path: operation for path, operation in app.openapi()["paths"].items()
        if path.startswith("/api/")
    }
    assert snapshot == {"version": "v1", "paths": current}
