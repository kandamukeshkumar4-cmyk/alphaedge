import ast
from dataclasses import fields
from pathlib import Path

from app.alpha.idea_generator import FactorHypothesis, propose_hypotheses


def test_proposes_novel_combinatorial_hypotheses():
    proposals = propose_hypotheses()

    assert proposals
    assert len({proposal.name for proposal in proposals}) == len(proposals)
    assert any(proposal.name.startswith("momentum__") for proposal in proposals)
    assert all(proposal.required_inputs for proposal in proposals)


def test_dedupes_against_seen_and_rejected_history():
    baseline = propose_hypotheses()
    seen = baseline[0].name
    rejected = baseline[1].name

    proposals = propose_hypotheses(
        {"validated_factors": {seen}, "rejected_hypotheses": {rejected}}
    )

    assert {proposal.name for proposal in proposals}.isdisjoint({seen, rejected})


def test_hypotheses_have_no_edge_or_order_authority():
    fields_by_name = {field.name for field in fields(FactorHypothesis)}
    assert fields_by_name == {"name", "description", "required_inputs", "predicted_direction"}

    source = Path("app/alpha/idea_generator.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    forbidden = {"is_edge", "stake", "side", "OrderIntent", "OrderBookService", "RiskService"}
    assert not (forbidden & {node.id for node in ast.walk(tree) if isinstance(node, ast.Name)})
