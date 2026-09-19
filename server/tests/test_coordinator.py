from scripts.database import demo_state
from server.app.coordinator import contract_conflicts, file_conflicts, find_conflicts
from server.app.models import ApiContract, Workstream


def _ws(id: str, paths: list[str], role: str, fields: dict[str, str]) -> Workstream:
    return Workstream(
        id=id,
        objective_id="o",
        title=id,
        agent_id=f"{id}-agent",
        owned_paths=paths,
        contract=ApiContract(method="POST", path="/api/oauth", role=role, response_fields=fields),
    )


def test_seeded_scenario_is_a_contract_conflict_on_accessToken():
    conflicts = find_conflicts(demo_state().workstreams)
    assert [c.type for c in conflicts] == ["contract"]
    c = conflicts[0]
    assert c.workstream_ids == ["backend", "frontend"]
    assert c.conflicting_field == "accessToken"
    assert c.status == "open"


def test_no_file_conflict_in_seed():
    assert file_conflicts(demo_state().workstreams) == []


def test_compatible_contracts_clear_the_conflict():
    provider = _ws("backend", ["src/api/**"], "provides", {"token": "string", "user": "object"})
    consumer = _ws("frontend", ["src/ui/**"], "consumes", {"token": "string", "user": "object"})
    assert contract_conflicts([provider, consumer]) == []


def test_consumer_subset_is_fine():
    provider = _ws("backend", ["a/**"], "provides", {"token": "string", "user": "object"})
    consumer = _ws("frontend", ["b/**"], "consumes", {"token": "string"})
    assert contract_conflicts([provider, consumer]) == []


def test_two_providers_do_not_conflict():
    a = _ws("a", ["a/**"], "provides", {"x": "string"})
    b = _ws("b", ["b/**"], "provides", {"y": "string"})
    assert contract_conflicts([a, b]) == []


def test_file_overlap_glob():
    a = _ws("a", ["src/api/**"], "provides", {"x": "string"})
    b = _ws("b", ["src/api/auth/**"], "consumes", {"x": "string"})
    conflicts = file_conflicts([a, b])
    assert len(conflicts) == 1
    assert conflicts[0].type == "file"
    assert conflicts[0].workstream_ids == ["a", "b"]


def test_disjoint_files_no_conflict():
    a = _ws("a", ["src/api/**"], "provides", {"x": "string"})
    b = _ws("b", ["src/components/**"], "consumes", {"x": "string"})
    assert file_conflicts([a, b]) == []
