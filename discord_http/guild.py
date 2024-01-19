from dataclasses import dataclass
from typing import TYPE_CHECKING, Union, Optional, AsyncIterator

from . import utils
from .asset import Asset
from .colour import Colour, Color
from .enums import (
    ChannelType, VerificationLevel,
    DefaultNotificationLevel, ContentFilterLevel
)
from .emoji import Emoji
from .file import File
from .flag import Permissions, SystemChannelFlags
from .multipart import MultipartData
from .object import PartialBase
from .role import Role, PartialRole
from .sticker import Sticker
from .voice import VoiceRegion

if TYPE_CHECKING:
    from .channel import (
        TextChannel, VoiceChannel,
        PartialChannel, BaseChannel
    )
    from .http import DiscordAPI
    from .invite import Invite
    from .member import PartialMember, Member

MISSING = utils.MISSING

__all__ = (
    "Guild",
    "PartialGuild",
)


@dataclass
class _GuildLimits:
    bitrate: int
    emojis: int
    filesize: int
    soundboards: int
    stickers: int


class PartialGuild(PartialBase):
    def __init__(self, *, state: "DiscordAPI", id: int):
        super().__init__(id=int(id))
        self._state = state

    def __repr__(self) -> str:
        return f"<PartialGuild id={self.id}>"

    async def fetch(self) -> "Guild":
        """ `Guild`: Fetches more information about the guild """
        r = await self._state.query(
            "GET",
            f"/guilds/{self.id}"
        )

        return Guild(
            state=self._state,
            data=r.response
        )

    async def fetch_roles(self) -> list[Role]:
        """ `list[Role]`: Fetches all the roles in the guild """
        r = await self._state.query(
            "GET",
            f"/guilds/{self.id}/roles"
        )

        return [
            Role(
                state=self._state,
                guild=self,
                data=data
            )
            for data in r.response
        ]

    async def fetch_stickers(self) -> list[Sticker]:
        """ `list[Sticker]`: Fetches all the stickers in the guild """
        r = await self._state.query(
            "GET",
            f"/guilds/{self.id}/stickers"
        )

        return [
            Sticker(
                state=self._state,
                guild=self,
                data=data
            )
            for data in r.response
        ]

    async def fetch_emojis(self) -> list[Emoji]:
        """ `list[Emoji]`: Fetches all the emojis in the guild """
        r = await self._state.query(
            "GET",
            f"/guilds/{self.id}/emojis"
        )

        return [
            Emoji(
                state=self._state,
                guild=self,
                data=data
            )
            for data in r.response
        ]

    async def create_guild(
        self,
        *,
        name: str,
        icon: Optional[Union[File, bytes]] = None,
        reason: Optional[str] = None
    ) -> "Guild":
        """
        Create a guild

        Note that the bot must be in less than 10 guilds to use this endpoint

        Parameters
        ----------
        name: `str`
            The name of the guild
        icon: `Optional[File]`
            The icon of the guild
        reason: `Optional[str]`
            The reason for creating the guild

        Returns
        -------
        `Guild`
            The created guild
        """
        payload = {"name": name}

        if icon is not None:
            payload["icon"] = utils.bytes_to_base64(icon)

        r = await self._state.query(
            "POST",
            "/guilds",
            json=payload,
            reason=reason
        )

        return Guild(
            state=self._state,
            data=r.response
        )

    async def create_role(
        self,
        *,
        name: str,
        permissions: Optional[Union[Permissions, int]] = 0,
        color: Optional[Union[Colour, Color, int]] = None,
        colour: Optional[Union[Colour, Color, int]] = None,
        unicode_emoji: Optional[str] = None,
        icon: Optional[Union[File, bytes]] = None,
        hoist: bool = False,
        mentionable: bool = False,
        reason: Optional[str] = None
    ) -> Role:
        """
        Create a role

        Parameters
        ----------
        name: `str`
            The name of the role
        permissions: `Optional[Union[Permissions, int]]`
            The permissions of the role
        color: `Optional[Union[Colour, Color, int]]`
            The colour of the role
        colour: `Optional[Union[Colour, Color, int]]`
            The colour of the role
        hoist: `bool`
            Whether the role should be hoisted
        mentionable: `bool`
            Whether the role should be mentionable
        unicode_emoji: `Optional[str]`
            The unicode emoji of the role
        icon: `Optional[File]`
            The icon of the role
        reason: `Optional[str]`
            The reason for creating the role

        Returns
        -------
        `Role`
            The created role
        """
        payload = {
            "name": name,
            "hoist": hoist,
            "mentionable": mentionable
        }

        if colour is not None:
            payload["color"] = int(colour)
        if color is not None:
            payload["color"] = int(color)

        if unicode_emoji is not None:
            payload["unicode_emoji"] = unicode_emoji
        if icon is not None:
            payload["icon"] = utils.bytes_to_base64(icon)

        if unicode_emoji and icon:
            raise ValueError("Cannot set both unicode_emoji and icon")

        if permissions:
            payload["permissions"] = int(permissions)

        r = await self._state.query(
            "POST",
            f"/guilds/{self.id}/roles",
            json=payload,
            reason=reason
        )

        return Role(
            state=self._state,
            guild=self,
            data=r.response
        )

    async def create_text_channel(
        self,
        *,
        name: str,
        topic: Optional[str] = MISSING,
        rate_limit_per_user: Optional[int] = MISSING,
        parent_id: Union[utils.Snowflake, int] = MISSING,
        nsfw: Optional[bool] = MISSING,
        reason: Optional[str] = None
    ) -> "TextChannel":
        """
        Create a text channel

        Parameters
        ----------
        name: `str`
            The name of the channel
        topic: `Optional[str]`
            The topic of the channel
        rate_limit_per_user: `Optional[int]`
            The rate limit per user of the channel
        parent_id: `Optional[Union[utils.Snowflake, int]]`
            The Category ID where the channel will be placed
        nsfw: `Optional[bool]`
            Whether the channel is NSFW or not
        reason: `Optional[str]`
            The reason for creating the text channel

        Returns
        -------
        `TextChannel`
            The created channel
        """
        payload = {
            "name": name,
            "type": int(ChannelType.guild_text)
        }

        if topic is not MISSING:
            payload["topic"] = topic
        if rate_limit_per_user is not MISSING:
            payload["rate_limit_per_user"] = (
                int(rate_limit_per_user)
                if isinstance(rate_limit_per_user, int)
                else None
            )
        if parent_id is not MISSING:
            payload["parent_id"] = str(int(parent_id))
        if nsfw is not MISSING:
            payload["nsfw"] = bool(nsfw)

        r = await self._state.query(
            "POST",
            f"/guilds/{self.id}/channels",
            json=payload,
            reason=reason
        )

        from .channel import TextChannel
        return TextChannel(
            state=self._state,
            data=r.response
        )

    async def create_voice_channel(
        self,
        *,
        name: str,
        bitrate: Optional[int] = None,
        user_limit: Optional[int] = None,
        rate_limit_per_user: Optional[int] = None,
        position: Optional[int] = None,
        parent_id: Union[utils.Snowflake, int, None] = None,
        nsfw: Optional[bool] = None,
        reason: Optional[str] = None
    ) -> "VoiceChannel":
        """
        Create a voice channel

        Parameters
        ----------
        name: `str`
            The name of the channel

        Returns
        -------
        `VoiceChannel`
            The created channel
        """
        payload = {
            "name": name,
            "type": int(ChannelType.guild_voice)
        }

        if bitrate is not None:
            payload["bitrate"] = int(bitrate)
        if user_limit is not None:
            payload["user_limit"] = int(user_limit)
        if rate_limit_per_user is not None:
            payload["rate_limit_per_user"] = int(rate_limit_per_user)
        if position is not None:
            payload["position"] = int(position)
        if parent_id is not None:
            payload["parent_id"] = str(int(parent_id))
        if nsfw is not None:
            payload["nsfw"] = bool(nsfw)

        r = await self._state.query(
            "POST",
            f"/guilds/{self.id}/channels",
            json=payload,
            reason=reason
        )

        from .channel import VoiceChannel
        return VoiceChannel(
            state=self._state,
            data=r.response
        )

    async def create_emoji(
        self,
        *,
        name: str,
        image: Union[File, bytes],
        reason: Optional[str] = None
    ) -> Emoji:
        """
        Create an emoji

        Parameters
        ----------
        name: `str`
            Name of the emoji
        image: `File`
            File object to create an emoji from
        reason: `Optional[str]`
            The reason for creating the emoji

        Returns
        -------
        `Emoji`
            The created emoji
        """
        r = await self._state.query(
            "POST",
            f"/guilds/{self.id}/emojis",
            reason=reason,
            json={
                "name": name,
                "image": utils.bytes_to_base64(image)
            }
        )

        return Emoji(
            state=self._state,
            guild=self,
            data=r.response
        )

    async def create_sticker(
        self,
        *,
        name: str,
        description: str,
        emoji: str,
        file: File,
        reason: Optional[str] = None
    ) -> Sticker:
        """
        Create a sticker

        Parameters
        ----------
        name: `str`
            Name of the sticker
        description: `str`
            Description of the sticker
        emoji: `str`
            Emoji that represents the sticker
        file: `File`
            File object to create a sticker from
        reason: `Optional[str]`
            The reason for creating the sticker

        Returns
        -------
        `Sticker`
            The created sticker
        """
        _bytes = file.data.read(16)
        try:
            mime_type = utils.mime_type_image(_bytes)
        except ValueError:
            mime_type = "application/octet-stream"
        finally:
            file.reset()

        multidata = MultipartData()

        multidata.attach("name", str(name))
        multidata.attach("description", str(description))
        multidata.attach("tags", utils.unicode_name(emoji))

        multidata.attach(
            "file",
            file,
            filename=file.filename,
            content_type=mime_type
        )

        r = await self._state.query(
            "POST",
            f"/guilds/{self.id}/stickers",
            headers={"Content-Type": multidata.content_type},
            data=multidata.finish(),
            reason=reason
        )

        return Sticker(
            state=self._state,
            guild=self,
            data=r.response
        )

    async def fetch_guild_prune_count(
        self,
        *,
        days: Optional[int] = 7,
        include_roles: Optional[list[Union[Role, PartialRole, int]]] = None
    ) -> int:
        """
        Fetch the amount of members that would be pruned

        Parameters
        ----------
        days: `Optional[int]`
            How many days of inactivity to prune for
        include_roles: `Optional[list[Union[Role, PartialRole, int]]]`
            Which roles to include in the prune

        Returns
        -------
        `int`
            The amount of members that would be pruned
        """
        _roles = []

        for r in include_roles or []:
            if isinstance(r, int):
                _roles.append(str(r))
            else:
                _roles.append(str(r.id))

        r = await self._state.query(
            "GET",
            f"/guilds/{self.id}/prune",
            params={
                "days": days,
                "include_roles": ",".join(_roles)
            }
        )

        return int(r.response["pruned"])

    async def begin_guild_prune(
        self,
        *,
        days: Optional[int] = 7,
        compute_prune_count: bool = True,
        include_roles: Optional[list[Union[Role, PartialRole, int]]] = None,
        reason: Optional[str] = None
    ) -> Optional[int]:
        """
        Begin a guild prune

        Parameters
        ----------
        days: `Optional[int]`
            How many days of inactivity to prune for
        compute_prune_count: `bool`
            Whether to return the amount of members that would be pruned
        include_roles: `Optional[list[Union[Role, PartialRole, int]]]`
            Which roles to include in the prune
        reason: `Optional[str]`
            The reason for beginning the prune

        Returns
        -------
        `Optional[int]`
            The amount of members that were pruned
        """
        payload = {
            "days": days,
            "compute_prune_count": compute_prune_count
        }

        _roles = []

        for r in include_roles or []:
            if isinstance(r, int):
                _roles.append(str(r))
            else:
                _roles.append(str(r.id))

        payload["include_roles"] = _roles or None

        r = await self._state.query(
            "POST",
            f"/guilds/{self.id}/prune",
            json=payload,
            reason=reason
        )

        try:
            return int(r.response["pruned"])
        except (KeyError, TypeError):
            return None

    async def fetch_member(self, member_id: int) -> "Member":
        r = await self._state.query(
            "GET",
            f"/guilds/{self.id}/members/{member_id}"
        )

        from .member import Member

        return Member(
            state=self._state,
            guild=self,
            data=r.response
        )

    async def fetch_members(
        self,
        *,
        limit: Optional[int] = 1000,
        after: Optional[Union[utils.Snowflake, int]] = None
    ) -> AsyncIterator["Member"]:
        from .member import Member

        while True:
            http_limit = 1000 if limit is None else min(limit, 1000)
            if http_limit <= 0:
                break

            after_id = after or 0
            if isinstance(after, utils.Snowflake):
                after_id = after.id

            data = await self._state.query(
                "GET",
                f"/guilds/{self.id}/members?limit={http_limit}&after={after_id}",
            )

            if not data.response:
                return

            if len(data.response) < 1000:
                limit = 0

            after = int(data.response[-1]["user"]["id"])

            for member_data in data.response:
                yield Member(
                    state=self._state,
                    guild=self,
                    data=member_data
                )

    async def fetch_regions(self) -> list[VoiceRegion]:
        """ `list[VoiceRegion]`: Fetches all the voice regions for the guild """
        r = await self._state.query(
            "GET",
            f"/guilds/{self.id}/regions"
        )

        return [
            VoiceRegion(
                data=data
            )
            for data in r.response
        ]

    async def fetch_invites(self) -> list["Invite"]:
        """ `list[Invite]`: Fetches all the invites for the guild """
        r = await self._state.query(
            "GET",
            f"/guilds/{self.id}/invites"
        )

        from .invite import Invite
        return [
            Invite(
                state=self._state,
                data=data
            )
            for data in r.response
        ]

    async def ban(
        self,
        member: Union["Member", "PartialMember", int],
        *,
        reason: Optional[str] = None,
        delete_message_days: Optional[int] = 0,
        delete_message_seconds: Optional[int] = 0,
    ) -> None:
        """
        Ban a member from the server

        Parameters
        ----------
        member: `Union[Member, PartialMember, int]`
            The member to ban
        reason: `Optional[str]`
            The reason for banning the member
        delete_message_days: `Optional[int]`
            How many days of messages to delete
        delete_message_seconds: `Optional[int]`
            How many seconds of messages to delete
        """
        if isinstance(member, int):
            from .member import PartialMember
            member = PartialMember(state=self._state, id=member, guild_id=self.id)

        await member.ban(
            reason=reason,
            delete_message_days=delete_message_days,
            delete_message_seconds=delete_message_seconds
        )

    async def unban(
        self,
        member: Union["Member", "PartialMember", int],
        *,
        reason: Optional[str] = None
    ) -> None:
        """
        Unban a member from the server

        Parameters
        ----------
        member: `Union[Member, PartialMember, int]`
            The member to unban
        reason: `Optional[str]`
            The reason for unbanning the member
        """
        if isinstance(member, int):
            from .member import PartialMember
            member = PartialMember(state=self._state, id=member, guild_id=self.id)

        await member.unban(reason=reason)

    async def kick(
        self,
        member: Union["Member", "PartialMember", int],
        *,
        reason: Optional[str] = None
    ) -> None:
        """
        Kick a member from the server

        Parameters
        ----------
        member: `Union[Member, PartialMember, int]`
            The member to kick
        reason: `Optional[str]`
            The reason for kicking the member
        """
        if isinstance(member, int):
            from .member import PartialMember
            member = PartialMember(state=self._state, id=member, guild_id=self.id)

        await member.kick(reason=reason)

    async def fetch_channels(self) -> list[type["BaseChannel"]]:
        """ `list[BaseChannel]`: Fetches all the channels in the guild """
        r = await self._state.query(
            "GET",
            f"/guilds/{self.id}/channels"
        )

        from .channel import PartialChannel
        return [
            PartialChannel.from_dict(
                state=self._state,
                data=data  # type: ignore
            )
            for data in r.response
        ]

    async def search_members(
        self,
        query: str,
        *,
        limit: Optional[int] = 100
    ) -> list["Member"]:
        """
        Search for members in the guild

        Parameters
        ----------
        query: `str`
            The query to search for
        limit: `Optional[int]`
            The maximum amount of members to return

        Returns
        -------
        `list[Member]`
            The members that matched the query

        Raises
        ------
        `ValueError`
            If the limit is not between 1 and 1000
        """
        if limit not in range(1, 1001):
            raise ValueError("Limit must be between 1 and 1000")

        r = await self._state.query(
            "GET",
            f"/guilds/{self.id}/members/search",
            params={
                "query": query,
                "limit": limit
            }
        )

        from .member import Member
        return [
            Member(
                state=self._state,
                guild=self,
                data=m
            )
            for m in r.response
        ]

    async def delete(self) -> None:
        """ Delete the guild (the bot must own the server) """
        await self._state.query(
            "DELETE",
            f"/guilds/{self.id}"
        )

    async def edit(
        self,
        *,
        name: Optional[str] = MISSING,
        verification_level: Optional[VerificationLevel] = MISSING,
        default_message_notifications: Optional[DefaultNotificationLevel] = MISSING,
        explicit_content_filter: Optional[ContentFilterLevel] = MISSING,
        afk_channel_id: Union["VoiceChannel", "PartialChannel", int, None] = MISSING,
        afk_timeout: Optional[int] = MISSING,
        icon: Optional[Union[File, bytes]] = MISSING,
        owner_id: Union["Member", "PartialMember", int, None] = MISSING,
        splash: Optional[Union[File, bytes]] = MISSING,
        discovery_splash: Optional[File] = MISSING,
        banner: Optional[Union[File, bytes]] = MISSING,
        system_channel_id: Union["TextChannel", "PartialChannel", int, None] = MISSING,
        system_channel_flags: Optional[SystemChannelFlags] = MISSING,
        rules_channel_id: Union["TextChannel", "PartialChannel", int, None] = MISSING,
        public_updates_channel_id: Union["TextChannel", "PartialChannel", int, None] = MISSING,
        preferred_locale: Optional[str] = MISSING,
        description: Optional[str] = MISSING,
        features: Optional[list[str]] = MISSING,
        premium_progress_bar_enabled: Optional[bool] = MISSING,
        safety_alerts_channel_id: Union["TextChannel", "PartialChannel", int, None] = MISSING,
        reason: Optional[str] = None
    ) -> "PartialGuild":
        """
        Edit the guild

        Parameters
        ----------
        name: `Optional[str]`
            New name of the guild
        verification_level: `Optional[VerificationLevel]`
            Verification level of the guild
        default_message_notifications: `Optional[DefaultNotificationLevel]`
            Default message notification level of the guild
        explicit_content_filter: `Optional[ContentFilterLevel]`
            Explicit content filter level of the guild
        afk_channel_id: `Optional[Union[VoiceChannel, PartialChannel, int]]`
            AFK channel of the guild
        afk_timeout: `Optional[int]`
            AFK timeout of the guild
        icon: `Optional[File]`
            Icon of the guild
        owner_id: `Optional[Union[Member, PartialMember, int]]`
            Owner of the guild
        splash: `Optional[File]`
            Splash of the guild
        discovery_splash: `Optional[File]`
            Discovery splash of the guild
        banner: `Optional[File]`
            Banner of the guild
        system_channel_id: `Optional[Union[TextChannel, PartialChannel, int]]`
            System channel of the guild
        system_channel_flags: `Optional[SystemChannelFlags]`
            System channel flags of the guild
        rules_channel_id: `Optional[Union[TextChannel, PartialChannel, int]]`
            Rules channel of the guild
        public_updates_channel_id: `Optional[Union[TextChannel, PartialChannel, int]]`
            Public updates channel of the guild
        preferred_locale: `Optional[str]`
            Preferred locale of the guild
        description: `Optional[str]`
            Description of the guild
        features: `Optional[list[str]]`
            Features of the guild
        premium_progress_bar_enabled: `Optional[bool]`
            Whether the premium progress bar is enabled
        safety_alerts_channel_id: `Optional[Union[TextChannel, PartialChannel, int]]`
            Safety alerts channel of the guild
        reason: `Optional[str]`
            The reason for editing the guild

        Returns
        -------
        `PartialGuild`
            The edited guild
        """
        payload = {}

        if name is not MISSING:
            payload["name"] = name
        if verification_level is not MISSING:
            payload["verification_level"] = int(verification_level or 0)
        if default_message_notifications is not MISSING:
            payload["default_message_notifications"] = int(default_message_notifications or 0)
        if explicit_content_filter is not MISSING:
            payload["explicit_content_filter"] = int(explicit_content_filter or 0)
        if afk_channel_id is not MISSING:
            payload["afk_channel_id"] = str(int(afk_channel_id)) if afk_channel_id else None
        if afk_timeout is not MISSING:
            payload["afk_timeout"] = int(afk_timeout or 0)
        if icon is not MISSING:
            payload["icon"] = utils.bytes_to_base64(icon) if icon else None
        if owner_id is not MISSING:
            payload["owner_id"] = str(int(owner_id)) if owner_id else None
        if splash is not MISSING:
            payload["splash"] = (
                utils.bytes_to_base64(splash)
                if splash else None
            )
        if discovery_splash is not MISSING:
            payload["discovery_splash"] = (
                utils.bytes_to_base64(discovery_splash)
                if discovery_splash else None
            )
        if banner is not MISSING:
            payload["banner"] = (
                utils.bytes_to_base64(banner)
                if banner else None
            )
        if system_channel_id is not MISSING:
            payload["system_channel_id"] = (
                str(int(system_channel_id))
                if system_channel_id else None
            )
        if system_channel_flags is not MISSING:
            payload["system_channel_flags"] = (
                int(system_channel_flags)
                if system_channel_flags else None
            )
        if rules_channel_id is not MISSING:
            payload["rules_channel_id"] = (
                str(int(rules_channel_id))
                if rules_channel_id else None
            )
        if public_updates_channel_id is not MISSING:
            payload["public_updates_channel_id"] = (
                str(int(public_updates_channel_id))
                if public_updates_channel_id else None
            )
        if preferred_locale is not MISSING:
            payload["preferred_locale"] = str(preferred_locale)
        if description is not MISSING:
            payload["description"] = str(description)
        if features is not MISSING:
            payload["features"] = features
        if premium_progress_bar_enabled is not MISSING:
            payload["premium_progress_bar_enabled"] = bool(premium_progress_bar_enabled)
        if safety_alerts_channel_id is not MISSING:
            payload["safety_alerts_channel_id"] = (
                str(int(safety_alerts_channel_id))
                if safety_alerts_channel_id else None
            )

        r = await self._state.query(
            "PATCH",
            f"/guilds/{self.id}",
            json=payload,
            reason=reason
        )

        return Guild(
            state=self._state,
            data=r.response
        )


class Guild(PartialGuild):
    _GUILD_LIMITS: dict[int, _GuildLimits] = {
        0: _GuildLimits(emojis=50, stickers=5, bitrate=96_000, filesize=26_214_400, soundboards=8),
        1: _GuildLimits(emojis=100, stickers=15, bitrate=128_000, filesize=26_214_400, soundboards=24),
        2: _GuildLimits(emojis=150, stickers=30, bitrate=256_000, filesize=52_428_800, soundboards=36),
        3: _GuildLimits(emojis=250, stickers=60, bitrate=384_000, filesize=104_857_600, soundboards=48),
    }

    def __init__(self, *, state: "DiscordAPI", data: dict):
        super().__init__(state=state, id=int(data["id"]))
        self.afk_channel_id: Optional[int] = utils.get_int(data, "afk_channel_id")
        self.afk_timeout: int = data.get("afk_timeout", 0)
        self.default_message_notifications: int = data.get("default_message_notifications", 0)
        self.description: Optional[str] = data.get("description", None)
        self.emojis: list[Emoji] = [
            Emoji(state=self._state, guild=self, data=e)
            for e in data.get("emojis", [])
        ]
        self.stickers: list[Sticker] = [
            Sticker(state=self._state, guild=self, data=s)
            for s in data.get("stickers", [])
        ]

        self._icon = data.get("icon", None)
        self._banner = data.get("banner", None)

        self.explicit_content_filter: int = data.get("explicit_content_filter", 0)
        self.features: list[str] = data.get("features", [])
        self.latest_onboarding_question_id: Optional[int] = utils.get_int(data, "latest_onboarding_question_id")
        self.max_members: int = data.get("max_members", 0)
        self.max_stage_video_channel_users: int = data.get("max_stage_video_channel_users", 0)
        self.max_video_channel_users: int = data.get("max_video_channel_users", 0)
        self.mfa_level: Optional[int] = utils.get_int(data, "mfa_level")
        self.name: str = data["name"]
        self.nsfw: bool = data.get("nsfw", False)
        self.nsfw_level: int = data.get("nsfw_level", 0)
        self.owner_id: Optional[int] = utils.get_int(data, "owner_id")
        self.preferred_locale: Optional[str] = data.get("preferred_locale", None)
        self.premium_progress_bar_enabled: bool = data.get("premium_progress_bar_enabled", False)
        self.premium_subscription_count: int = data.get("premium_subscription_count", 0)
        self.premium_tier: int = data.get("premium_tier", 0)
        self.public_updates_channel_id: Optional[int] = utils.get_int(data, "public_updates_channel_id")
        self.region: Optional[str] = data.get("region", None)
        self.roles: list[Role] = [
            Role(state=self._state, guild=self, data=r)
            for r in data.get("roles", [])
        ]
        self.safety_alerts_channel_id: Optional[int] = utils.get_int(data, "safety_alerts_channel_id")
        self.system_channel_flags: int = data.get("system_channel_flags", 0)
        self.system_channel_id: Optional[int] = utils.get_int(data, "system_channel_id")
        self.vanity_url_code: Optional[str] = data.get("vanity_url_code", None)
        self.verification_level: int = data.get("verification_level", 0)
        self.widget_channel_id: Optional[int] = utils.get_int(data, "widget_channel_id")
        self.widget_enabled: bool = data.get("widget_enabled", False)

    def __str__(self) -> str:
        return self.name

    def __repr__(self) -> str:
        return f"<Guild id={self.id} name='{self.name}'>"

    @property
    def emojis_limit(self) -> int:
        """ `int`: The maximum amount of emojis the guild can have """
        return max(
            200 if "MORE_EMOJI" in self.features else 50,
            self._GUILD_LIMITS[self.premium_tier].emojis
        )

    @property
    def stickers_limit(self) -> int:
        """ `int`: The maximum amount of stickers the guild can have """
        return max(
            60 if "MORE_STICKERS" in self.features else 0,
            self._GUILD_LIMITS[self.premium_tier].stickers
        )

    @property
    def bitrate_limit(self) -> int:
        """ `float`: The maximum bitrate the guild can have """
        return max(
            self._GUILD_LIMITS[1].bitrate if "VIP_REGIONS" in self.features else 96_000,
            self._GUILD_LIMITS[self.premium_tier].bitrate
        )

    @property
    def filesize_limit(self) -> int:
        """ `int`: The maximum filesize the guild can have """
        return self._GUILD_LIMITS[self.premium_tier].filesize

    @property
    def icon(self) -> Optional[Asset]:
        """ `Optional[Asset]`: The guild's icon """
        if self._icon is None:
            return None
        return Asset._from_guild_icon(self.id, self._icon)

    @property
    def banner(self) -> Optional[Asset]:
        """ `Optional[Asset]`: The guild's banner """
        if self._banner is None:
            return None
        return Asset._from_guild_banner(self.id, self._banner)

    @property
    def default_role(self) -> Role:
        """ `Role`: The guild's default role, which is always provided """
        role = self.get_role(self.id)
        if not role:
            raise ValueError("The default Guild role was somehow not found...?")
        return role

    @property
    def premium_subscriber_role(self) -> Optional[Role]:
        """ `Optional[Role]`: The guild's premium subscriber role if available """
        return next(
            (r for r in self.roles if r.is_premium_subscriber()),
            None
        )

    @property
    def self_role(self) -> Optional[Role]:
        """ `Optional[Role]`: The guild's bot role if available """
        return next(
            (
                r for r in self.roles
                if r.bot_id and
                r.bot_id == self._state.application_id
            ),
            None
        )

    def get_role(self, role_id: int) -> Optional[Role]:
        """
        Get a role from the guild

        This simply returns the role from the role list in this object if it exists

        Parameters
        ----------
        role_id: `int`
            The ID of the role to get

        Returns
        -------
        `Optional[Role]`
            The role if it exists, else `None`
        """
        return next((
            r for r in self.roles
            if r.id == role_id
        ), None)

    def get_role_by_name(self, role_name: str) -> Optional[Role]:
        """
        Gets the first role with the specified name

        Parameters
        ----------
        role_name: `str`
            The name of the role to get (case sensitive)

        Returns
        -------
        `Optional[Role]`
            The role if it exists, else `None`
        """
        return next((
            r for r in self.roles
            if r.name == role_name
        ), None)
