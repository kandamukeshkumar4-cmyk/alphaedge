import ast
from pathlib import Path


def test_alpha_scheduler_is_wall_clock_aligned_and_dual_wired():
    main_source = Path("app/main.py").read_text(encoding="utf-8")
    task_source = Path("app/workers/tasks.py").read_text(encoding="utf-8")
    tree = ast.parse(main_source)
    loop = next(node for node in tree.body if isinstance(node, ast.AsyncFunctionDef) and node.name == "_alpha_model_loop")
    first_await = next(node for node in ast.walk(loop) if isinstance(node, ast.Await))

    assert isinstance(first_await.value, ast.Call)
    assert getattr(first_await.value.func, "id", "") == "alpha_model_task"
    assert "_seconds_until_next_utc_hour(datetime.now(timezone.utc), hour=7)" in main_source
    assert "asyncio.create_task(_alpha_model_loop())" in main_source
    assert "cron(alpha_model_task, hour={7}, minute={0})" in task_source


def test_alpha_modules_have_no_order_or_llm_execution_path_imports():
    forbidden = (
        "app.services.risk_service",
        "app.services.order_book_service",
        "app.services.order",
        "app.llm",
    )
    for path in Path("app/alpha").glob("*.py"):
        imports = [
            node.module or ""
            for node in ast.walk(ast.parse(path.read_text(encoding="utf-8")))
            if isinstance(node, ast.ImportFrom)
        ]
        assert not any(part in module.lower() for module in imports for part in forbidden), path
