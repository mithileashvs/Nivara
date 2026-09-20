def normalize(value: str | None) -> str:
    """Case/whitespace-insensitive comparison key."""
    return " ".join((value or "").lower().split())
