"""The portable, versionable event representation used by a macro."""

from dataclasses import asdict, dataclass


@dataclass(slots=True)
class MacroEvent:
    """One captured input action using absolute virtual-screen coordinates."""

    event_type: str
    # Seconds since recording started, from a monotonic high-resolution clock.
    timestamp: float
    x: int | None = None
    y: int | None = None
    key: str | None = None
    button: str | None = None
    pressed: bool | None = None
    dx: int | None = None
    dy: int | None = None

    def to_dict(self):
        return asdict(self)
