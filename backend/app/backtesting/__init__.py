__all__ = ["run_backtest"]


def __getattr__(name: str):
    if name == "run_backtest":
        from app.backtesting.replay import run_backtest

        return run_backtest
    raise AttributeError(name)
