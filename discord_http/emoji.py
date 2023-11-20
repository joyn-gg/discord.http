import re

from datetime import datetime
from typing import TYPE_CHECKING, Union, Optional

from . import utils
from .role import PartialRole

if TYPE_CHECKING:
    from .guild import PartialGuild, Guild
    from .http import DiscordAPI

__all__ = (
    "PartialEmoji",
    "Emoji",
)


class PartialEmoji:
    def __init__(self, emoji: str):
        self._original_name: str = emoji

        self.id: Optional[int] = None
        self.animated: bool = False
        self.discord_emoji: bool = False

        is_custom: Optional[re.Match] = utils.re_emoji.search(emoji)

        if is_custom:
            _animated, _name, _id = is_custom.groups()
            self.discord_emoji = True
            self.animated = bool(_animated)
            self.name: str = _name
            self.id = int(_id)
        else:
            self.name: str = emoji

    def __str__(self) -> str:
        return self._original_name

    def __int__(self) -> Optional[int]:
        if self.discord_emoji:
            return self.id
        return None

    def __repr__(self) -> str:
        if self.discord_emoji:
            return f"<PartialEmoji name='{self.name}' id={self.id} animated={self.animated}>"
        return f"<PartialEmoji name='{self.name}'>"

    def to_dict(self) -> dict:
        """ `dict`: Returns a dict representation of the emoji """
        if self.discord_emoji:
            # Include animated if it's a Discord emoji
            return {"id": self.id, "name": self.name, "animated": self.animated}
        return {"name": self.name, "id": None}

    def to_reaction(self) -> str:
        """ `str`: Returns a string representation of the emoji """
        if self.discord_emoji:
            return f"{self.name}:{self.id}"
        return self.name


class Emoji:
    def __init__(
        self,
        *,
        state: "DiscordAPI",
        guild: Union["PartialGuild", "Guild"],
        data: dict
    ):
        self._state = state

        self.id: int = int(data["id"])
        self.guild: Union[PartialGuild, Guild] = guild
        self.created_at: datetime = utils.snowflake_time(self.id)
        self.name: str = data["name"]
        self.animated: bool = data["animated"]
        self.available: bool = data["available"]
        self.roles: list[PartialRole] = [
            PartialRole(state=state, guild_id=guild.id, role_id=r)
            for r in data["roles"]
        ]

    async def delete(self) -> None:
        await self._state.query(
            "DELETE",
            f"/guilds/{self.guild.id}/emojis/{self.id}",
            res_method="text"
        )

    def __repr__(self) -> str:
        return f"<Emoji id={self.id} name='{self.name}' animated={self.animated}>"

    def __str__(self) -> str:
        return self.name

    def __int__(self) -> int:
        return self.id
