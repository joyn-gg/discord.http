from typing import TYPE_CHECKING, Union, Optional

from . import utils
from .asset import Asset
from .object import PartialBase

if TYPE_CHECKING:
    from .guild import PartialGuild, Guild
    from .http import DiscordAPI

MISSING = utils.MISSING

__all__ = (
    "PartialSticker",
    "Sticker",
)


class PartialSticker(PartialBase):
    def __init__(
        self,
        *,
        state: "DiscordAPI",
        id: int,
        name: Optional[str] = None,
        guild_id: Optional[int] = None
    ):
        super().__init__(id=int(id))
        self._state = state

        self.name: Optional[str] = name
        self.guild_id: Optional[int] = guild_id

    def __repr__(self) -> str:
        return f"<PartialSticker id={self.id}>"

    async def fetch(self) -> "Sticker":
        """ `Sticker`: Returns the sticker data """
        r = await self._state.query(
            "GET",
            f"/stickers/{self.id}"
        )

        self.guild_id = int(r.response["guild_id"])

        return Sticker(
            state=self._state,
            guild=self.partial_guild,
            data=r.response,
        )

    @property
    def partial_guild(self) -> "PartialGuild":
        """
        Returns the guild this sticker is in

        Returns
        -------
        `PartialGuild`
            The guild this sticker is in

        Raises
        ------
        `ValueError`
            guild_id is not defined, unable to create PartialGuild
        """
        if not self.guild_id:
            raise ValueError("guild_id is not defined, unable to create PartialGuild")

        from .guild import PartialGuild
        return PartialGuild(state=self._state, guild_id=self.guild_id)

    async def edit(
        self,
        *,
        name: Optional[str] = MISSING,
        description: Optional[str] = MISSING,
        tags: Optional[str] = MISSING,
        guild_id: Optional[int] = None,
    ) -> "Sticker":
        """
        Edits the sticker

        Parameters
        ----------
        guild_id: `Optional[int]`
            Guild ID to edit the sticker from
        name: `Optional[str]`
            Replacement name for the sticker
        description: `Optional[str]`
            Replacement description for the sticker
        tags: `Optional[str]`
            Replacement tags for the sticker

        Returns
        -------
        `Sticker`
            The edited sticker

        Raises
        ------
        `ValueError`
            No guild_id was passed
        """
        guild_id = guild_id or self.guild_id
        if guild_id is None:
            raise ValueError("guild_id is a required argument")

        payload = {}

        if name is not MISSING:
            payload["name"] = name
        if description is not MISSING:
            payload["description"] = description
        if tags is not MISSING:
            payload["tags"] = utils.unicode_name(str(tags))

        r = await self._state.query(
            "PATCH",
            f"/guilds/{guild_id}/stickers/{self.id}",
            json=payload
        )

        self.guild_id = int(r.response["guild_id"])

        return Sticker(
            state=self._state,
            data=r.response,
            guild=self.partial_guild,
        )

    async def delete(self, *, guild_id: Optional[int] = None) -> None:
        """
        Deletes the sticker

        Parameters
        ----------
        guild_id: `int`
            Guild ID to delete the sticker from

        Raises
        ------
        `ValueError`
            No guild_id was passed or guild_id is not defined
        """
        guild_id = guild_id or self.guild_id
        if guild_id is None:
            raise ValueError("guild_id is a required argument")

        await self._state.query(
            "DELETE",
            f"/guilds/{guild_id}/stickers/{self.id}",
            res_method="text"
        )

    @property
    def url(self) -> str:
        """ `str`: Returns the sticker's URL """
        return f"{Asset.BASE}/stickers/{self.id}.png"


class Sticker(PartialSticker):
    def __init__(
        self,
        *,
        state: "DiscordAPI",
        data: dict,
        guild: Union["PartialGuild", "Guild"],
    ):
        super().__init__(
            state=state,
            id=data["id"],
            name=data["name"],
            guild_id=guild.id
        )

        self.guild: Union["PartialGuild", "Guild"] = guild
        self.description: str = data["description"]
        self.tags: str = data["tags"]
        self.available: bool = data["available"]

        # Re-define types
        self.name: str

    def __str__(self) -> str:
        return self.name

    def __repr__(self) -> str:
        return f"<Sticker id={self.id} name='{self.name}'>"

    async def edit(
        self,
        *,
        name: Optional[str] = MISSING,
        description: Optional[str] = MISSING,
        tags: Optional[str] = MISSING
    ) -> "Sticker":
        """
        Edits the sticker

        Parameters
        ----------
        name: `Optional[str]`
            Name of the sticker
        description: `Optional[str]`
            Description of the sticker
        tags: `Optional[str]`
            Tags of the sticker

        Returns
        -------
        `Sticker`
            The edited sticker
        """
        return await super().edit(
            guild_id=self.guild.id,
            name=name,
            description=description,
            tags=tags
        )

    async def delete(self) -> None:
        """ Deletes the sticker """
        await super().delete(guild_id=self.guild.id)
