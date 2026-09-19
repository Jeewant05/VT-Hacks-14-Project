import argparse

from server.app.config import Settings
from server.app.models import (
    AgentPrincipal,
    ApiContract,
    Decision,
    Objective,
    WorkspaceState,
    Workstream,
)
from server.app.store import read_state, write_state


def demo_state() -> WorkspaceState:
    return WorkspaceState(
        objective=Objective(
            id="oauth-objective",
            title="Add organization-level OAuth login",
            description="Coordinate backend and frontend changes before merge.",
            acceptance_criteria=[
                "Verify participating agent identities through ANS.",
                "Align both agents on the approved authentication contract.",
                "Review changes, tests, and conflict resolution together.",
            ],
        ),
        agents=[
            AgentPrincipal(id="backend-agent", ans_name="backend.demo", role="backend"),
            AgentPrincipal(id="frontend-agent", ans_name="frontend.demo", role="frontend"),
        ],
        workstreams=[
            Workstream(
                id="backend",
                objective_id="oauth-objective",
                title="OAuth API",
                agent_id="backend-agent",
                owned_paths=["src/api/auth/**"],
                contract=ApiContract(
                    method="POST",
                    path="/api/oauth",
                    role="provides",
                    response_fields={"token": "string", "user": "object"},
                ),
            ),
            Workstream(
                id="frontend",
                objective_id="oauth-objective",
                title="Organization login",
                agent_id="frontend-agent",
                owned_paths=["src/components/login/**"],
                depends_on=["backend"],
                contract=ApiContract(
                    method="POST",
                    path="/api/oauth",
                    role="consumes",
                    response_fields={"accessToken": "string", "profile": "object"},
                ),
            ),
        ],
        decisions=[
            Decision(
                decision_id="auth-response",
                title="Authentication response contract",
                content="POST /api/oauth must return token (string) and user (object).",
                affected_component="authentication",
                created_at="2026-09-19T00:00:00Z",
            ),
            Decision(
                decision_id="scope-boundaries",
                title="Workstream ownership",
                content="Backend owns src/api/auth/**; frontend owns src/components/login/**.",
                affected_component="coordination",
                created_at="2026-09-19T00:00:00Z",
            ),
            Decision(
                decision_id="review-required",
                title="Convergence requires review",
                content="Resolve declared contract conflicts before completing the objective.",
                affected_component="review",
                created_at="2026-09-19T00:00:00Z",
            ),
        ],
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Manage local demo fixtures only.")
    parser.add_argument("action", choices=["seed", "reset"])
    args = parser.parse_args()
    path = Settings().resolved_database_path
    if args.action == "seed" and read_state(path).objective:
        print("Local workspace already seeded; left unchanged.")
        return
    write_state(path, demo_state())
    print(f"Local workspace {args.action} complete: {path}. No external data changed.")


if __name__ == "__main__":
    main()
