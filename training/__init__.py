"""Training package."""

__all__ = ["train_agent", "evaluate_agent"]


def __getattr__(name: str):
    if name == "train_agent":
        from training.train_agent import train_agent
        return train_agent
    if name == "evaluate_agent":
        from training.evaluate_agent import evaluate_agent
        return evaluate_agent
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
