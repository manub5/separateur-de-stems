"""Immutable values captured when a separation run starts."""

from dataclasses import dataclass

__all__ = ["RunContext"]


@dataclass(frozen=True)
class RunContext:
    """Paths and requested stems that cannot change during a run."""

    input_path: str
    output_dir: str
    model_dir: str
    stems: frozenset[str]
    workspace: str
