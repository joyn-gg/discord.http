import re

from typing import TYPE_CHECKING, Union, Optional

from . import utils
from .asset import Asset
from .object import PartialBase, Snowflake
from .role import PartialRole

if TYPE_CHECKING:
    from .guild import PartialGuild, Guild
    from .http import DiscordAPI

MISSING = utils.MISSING

__all__ = (
    "Emoji",
    "PartialEmoji",
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

    def __repr__(self) -> str:
        if self.discord_emoji:
            return f"<PartialEmoji name='{self.name}' id={self.id} animated={self.animated}>"
        return f"<PartialEmoji name='{self.name}'>"

    def __str__(self) -> str:
        return self._original_name

    def __int__(self) -> Optional[int]:
        if self.discord_emoji:
            return self.id
        return None

    @property
    def url(self) -> Optional[str]:
        """ `str`: Returns the URL of the emoji if it's a Discord emoji """
        if self.discord_emoji:
            return f"{Asset.BASE}/emojis/{self.id}.{'gif' if self.animated else 'png'}"
        return None

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


class Emoji(PartialBase):
    def __init__(
        self,
        *,
        state: "DiscordAPI",
        guild: Union["PartialGuild", "Guild"],
        data: dict
    ):
        super().__init__(id=int(data["id"]))
        self._state = state

        self.guild: Union[PartialGuild, Guild] = guild
        self.name: str = data["name"]
        self.animated: bool = data["animated"]
        self.available: bool = data["available"]
        self.roles: list[PartialRole] = [
            PartialRole(state=state, id=r, guild_id=guild.id)
            for r in data["roles"]
        ]

    def __repr__(self) -> str:
        return f"<Emoji id={self.id} name='{self.name}' animated={self.animated}>"

    def __str__(self) -> str:
        return f"<{'a' if self.animated else ''}:{self.name}:{self.id}>"

    def __int__(self) -> int:
        return self.id

    @property
    def url(self) -> str:
        """ `str`: Returns the URL of the emoji """
        return f"{Asset.BASE}/emojis/{self.id}.{'gif' if self.animated else 'png'}"

    async def delete(
        self,
        *,
        reason: Optional[str] = None
    ) -> None:
        """
        Deletes the emoji.

        Parameters
        ----------
        reason: `Optional[str]`
            The reason for deleting the emoji.
        """
        await self._state.query(
            "DELETE",
            f"/guilds/{self.guild.id}/emojis/{self.id}",
            res_method="text",
            reason=reason
        )

    async def edit(
        self,
        *,
        name: Optional[str] = MISSING,
        roles: Optional[list[Union[PartialRole, int]]] = MISSING,
        reason: Optional[str] = None
    ):
        """
        Edits the emoji.

        Parameters
        ----------
        name: `Optional[str]`
            The new name of the emoji.
        roles: `Optional[list[Union[PartialRole, int]]]`
            Roles that are allowed to use the emoji.
        reason: `Optional[str]`
            The reason for editing the emoji.

        Returns
        -------
        `Emoji`
            The edited emoji.
        """
        payload = {}

        if name is not MISSING:
            payload["name"] = name

        if isinstance(roles, list):
            payload["roles"] = [
                int(r) for r in roles
                if isinstance(r, Snowflake)
            ]

        r = await self._state.query(
            "PATCH",
            f"/guilds/{self.guild.id}/emojis/{self.id}",
            json=payload,
            reason=reason
        )

        return Emoji(
            state=self._state,
            guild=self.guild,
            data=r.response
        )
