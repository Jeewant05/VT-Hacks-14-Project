import json

from pydantic import TypeAdapter

from scripts.database import demo_state
from server.app.config import ROOT
from server.app.main import app
from server.app.models import VerificationResult, WorkspaceState, WriteReceipt


def main() -> None:
    directory = ROOT / "contracts"
    directory.mkdir(exist_ok=True)
    documents = {
        "openapi.json": app.openapi(),
        "schema.json": TypeAdapter(
            WorkspaceState | VerificationResult | WriteReceipt
        ).json_schema(),
        "example-state.json": demo_state().model_dump(mode="json"),
    }
    for name, document in documents.items():
        (directory / name).write_text(json.dumps(document, indent=2) + "\n")
    print("Exported API, shared model schemas, and fixture payloads.")


if __name__ == "__main__":
    main()
