import ast
from pathlib import Path

from app.alpha.portfolio_constructor import construct_research_weights


def _returns() -> dict[str, dict[str, float]]:
    return {
        "model_edge": {f"f-{index}": (index - 3) / 10 for index in range(8)},
        "momentum": {f"f-{index}": (3 - index) / 20 for index in range(8)},
    }


def test_constructor_returns_sane_paper_only_inverse_vol_weights():
    result = construct_research_weights(_returns())

    assert result["constructed"] is True
    assert result["paper_trading_only"] is True
    assert set(result["weights"]) == {"model_edge", "momentum"}
    assert abs(sum(result["weights"].values()) - 1.0) < 1e-6
    assert all(value > 0.0 for value in result["weights"].values())


def test_constructor_rejects_without_a_common_oos_sample():
    result = construct_research_weights({"model_edge": {"a": 0.1}, "momentum": {"b": 0.2}})

    assert result["constructed"] is False
    assert result["reason"] == "insufficient_common_oos_returns"


def test_constructor_has_no_order_path_imports():
    source = Path("app/alpha/portfolio_constructor.py").read_text(encoding="utf-8")
    imports = [node.module or "" for node in ast.walk(ast.parse(source)) if isinstance(node, ast.ImportFrom)]

    assert not any("risk" in module.lower() or "order" in module.lower() for module in imports)
