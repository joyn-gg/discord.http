__all__ = (
    "VoiceRegion",
)


class VoiceRegion:
    def __init__(self, *, data: dict):
        self.id: str = data["id"]
        self.name: str = data["name"]
        self.custom: bool = data["custom"]
        self.deprecated: bool = data["deprecated"]
        self.optimal: bool = data["optimal"]

    def __str__(self) -> str:
        return self.name

    def __repr__(self) -> str:
        return f"<VoiceRegion id='{self.id}' name='{self.name}'>"
