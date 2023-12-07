from typing import Union, TYPE_CHECKING, Optional, AsyncIterator, Callable, Self
from datetime import datetime, timedelta

from .enums import ChannelType, PermissionType, ResponseType
from .member import PartialMember, Member, ThreadMember
from .role import PartialRole, Role
from .response import MessageResponse
from .flag import Permissions
from .object import PartialBase
from .embeds import Embed
from .file import File
from .view import View
from .mentions import AllowedMentions
from .webhook import Webhook
from . import utils

if TYPE_CHECKING:
    from .message import PartialMessage, Message
    from .guild import PartialGuild
    from .user import PartialUser, User
    from .invite import Invite
    from .http import DiscordAPI

MISSING = utils.MISSING

__all__ = (
    "PartialChannel",
    "BaseChannel",
    "TextChannel",
    "DMChannel",
    "StoreChannel",
    "GroupDMChannel",
    "DirectoryChannel",
    "CategoryChannel",
    "NewsChannel",
    "PublicThread",
    "ForumChannel",
    "NewsThread",
    "PrivateThread",
    "VoiceChannel",
    "StageChannel",
    "PermissionOverwrite",
)


class PermissionOverwrite:
    def __init__(
        self,
        allow: Optional[Permissions] = None,
        deny: Optional[Permissions] = None
    ):
        self.allow: Permissions = allow or Permissions(0)
        self.deny: Permissions = deny or Permissions(0)


class PartialChannel(PartialBase):
    def __init__(
        self,
        *,
        state: "DiscordAPI",
        channel_id: int,
        guild_id: Optional[int] = None
    ):
        super().__init__(id=int(channel_id))
        self._state = state
        self.guild_id: Optional[int] = guild_id

    def __repr__(self) -> str:
        return f"<PartialChannel id={self.id}>"

    @property
    def guild(self) -> Optional["PartialGuild"]:
        """ `Optional[PartialGuild]`: The guild the channel belongs to (if available) """
        from .guild import PartialGuild

        if self.guild_id:
            return PartialGuild(state=self._state, guild_id=self.guild_id)
        return None

    def get_partial_message(self, message_id: int) -> "PartialMessage":
        """
        Get a partial message object from the channel

        Parameters
        ----------
        message_id: `int`
            The message ID to get the partial message from

        Returns
        -------
        `PartialMessage`
            The partial message object
        """
        from .message import PartialMessage
        return PartialMessage(
            state=self._state,
            channel_id=self.id,
            id=message_id
        )

    async def fetch_message(self, message_id: int) -> "Message":
        """
        Fetch a message from the channel

        Parameters
        ----------
        message_id: `int`
            The message ID to fetch

        Returns
        -------
        `Message`
            The message object
        """
        r = await self._state.query(
            "GET",
            f"/channels/{self.id}/messages/{message_id}"
        )

        from .message import Message
        return Message(
            state=self._state,
            data=r.response,
            guild=self.guild
        )

    async def fetch_pins(self) -> list["Message"]:
        """
        Fetch all pinned messages for the channel in question

        Returns
        -------
        `list[Message]`
            The list of pinned messages
        """
        r = await self._state.query(
            "GET",
            f"/channels/{self.id}/pins"
        )

        from .message import Message
        return [
            Message(
                state=self._state,
                data=data,
                guild=self.guild
            )
            for data in r.response
        ]

    async def follow_announcement_channel(
        self,
        source_channel_id: Union[utils.Snowflake, int]
    ) -> None:
        """
        Follow an announcement channel to send messages to the webhook

        Parameters
        ----------
        source_channel_id: `int`
            The channel ID to follow
        """
        await self._state.query(
            "POST",
            f"/channels/{source_channel_id}/followers",
            json={"webhook_channel_id": self.id},
            res_method="text"
        )

    async def create_invite(
        self,
        *,
        max_age: Union[timedelta, int] = 86400,  # 24 hours
        max_uses: Optional[int] = 0,
        temporary: bool = False,
        unique: bool = False,
    ) -> "Invite":
        """
        Create an invite for the channel

        Parameters
        ----------
        max_age: `Union[timedelta, int]`
            How long the invite should last
        temporary: `bool`
            If the invite should be temporary
        unique: `bool`
            If the invite should be unique

        Returns
        -------
        `Invite`
            The invite object
        """
        if isinstance(max_age, timedelta):
            max_age = int(max_age.total_seconds())

        r = await self._state.query(
            "POST",
            f"/channels/{self.id}/invites",
            json={
                "max_age": max_age,
                "max_uses": max_uses,
                "temporary": temporary,
                "unique": unique
            }
        )

        from .invite import Invite
        return Invite(
            state=self._state,
            data=r.response
        )

    async def send(
        self,
        content: Optional[str] = MISSING,
        *,
        embed: Optional[Embed] = MISSING,
        embeds: Optional[list[Embed]] = MISSING,
        file: Optional[File] = MISSING,
        files: Optional[list[File]] = MISSING,
        view: Optional[View] = MISSING,
        tts: Optional[bool] = False,
        type: Union[ResponseType, int] = 4,
        allowed_mentions: Optional[AllowedMentions] = MISSING,
    ) -> "Message":
        """
        Send a message to the channel

        Parameters
        ----------
        content: `Optional[str]`
            Cotnent of the message
        embed: `Optional[Embed]`
            Includes an embed object
        embeds: `Optional[list[Embed]]`
            List of embed objects
        file: `Optional[File]`
            A file object
        files: `Union[list[File], File]`
            A list of file objects
        view: `View`
            Send components to the message
        tts: `bool`
            If the message should be sent as a TTS message
        type: `Optional[ResponseType]`
            The type of response to the message
        allowed_mentions: `Optional[AllowedMentions]`
            The allowed mentions for the message

        Returns
        -------
        `Message`
            The message object
        """
        payload = MessageResponse(
            content,
            embed=embed,
            embeds=embeds,
            file=file,
            files=files,
            view=view,
            tts=tts,
            type=type,
            allowed_mentions=allowed_mentions,
        )

        r = await self._state.query(
            "POST",
            f"/channels/{self.id}/messages",
            data=payload.to_multipart(is_request=True),
            headers={"Content-Type": payload.content_type}
        )

        from .message import Message
        return Message(
            state=self._state,
            data=r.response
        )

    def _class_to_return(
        self,
        data: dict,
        *,
        state: Optional["DiscordAPI"] = None
    ) -> "BaseChannel":
        match data["type"]:
            case x if x in (ChannelType.guild_text, ChannelType.guild_news):
                _class = TextChannel
            case ChannelType.guild_voice:
                _class = VoiceChannel
            case ChannelType.guild_category:
                _class = CategoryChannel
            case ChannelType.guild_news_thread:
                _class = NewsThread
            case ChannelType.guild_public_thread:
                _class = PublicThread
            case ChannelType.guild_private_thread:
                _class = PrivateThread
            case ChannelType.guild_stage_voice:
                _class = StageChannel
            case _:
                _class = BaseChannel

        _class: type["BaseChannel"]

        return _class(
            state=state or self._state,
            data=data
        )

    @classmethod
    def from_dict(cls, *, state: "DiscordAPI", data: dict) -> Self:
        """
        Create a channel object from a dictionary
        Requires the state to be set

        Parameters
        ----------
        state: `DiscordAPI`
            The state to use
        data: `dict`
            Data provided by Discord API

        Returns
        -------
        `BaseChannel`
            The channel object
        """
        temp_class = cls(
            state=state,
            channel_id=int(data["id"]),
            guild_id=utils.get_int(data, "guild_id")
        )

        return temp_class._class_to_return(data=data, state=state)

    async def fetch(self) -> "BaseChannel":
        """ `BaseChannel`: Fetches the channel and returns the channel object """
        r = await self._state.query(
            "GET",
            f"/channels/{self.id}"
        )

        return self._class_to_return(
            data=r.response
        )

    async def edit(
        self,
        *,
        name: Optional[str] = MISSING,
        category: Union["CategoryChannel", utils.Snowflake, None] = MISSING,
        position: Optional[int] = MISSING,
        nsfw: Optional[bool] = MISSING,
        overwrites: Union[
            dict[Union[PartialRole, PartialMember, utils.Snowflake], PermissionOverwrite],
            None
        ] = MISSING,
        reason: Optional[str] = None,
        **kwargs
    ) -> Self:
        """
        Edit the channel

        Parameters
        ----------
        name: `Optional[str]`
            New name of the channel
        category: `Optional[Union[CategoryChannel, utils.Snowflake]]`
            Which category the channel should be in
        position: `Optional[int]`
            The position of the channel
        nsfw: `Optional[bool]`
            If the channel should be NSFW
        overwrites: `Optional[dict[Union[PartialRole, PartialMember, utils.Snowflake], PermissionOverwrite]]`
            The permission overwrites for the channel
        reason: `Optional[str]`
            The reason for editing the channel

        Returns
        -------
        `BaseChannel`
            The channel object

        Raises
        ------
        `TypeError`
            If the overwrite key is not a PartialRole, Role, PartialMember, Member or Snowflake
        """
        payload = {}

        if overwrites is not MISSING:
            _overwrites = []
            for obj, perm in overwrites.items():
                if not isinstance(perm, PermissionOverwrite):
                    raise TypeError(
                        f"overwrite {obj}:value must be a PermissionOverwrite"
                    )

                _type = None
                if isinstance(obj, (PartialRole, Role)):
                    _type = PermissionType.role
                elif isinstance(obj, (PartialMember, Member, utils.Snowflake)):
                    _type = PermissionType.member
                else:
                    raise TypeError(
                        f"overwrite {obj}:key must be a PartialRole, "
                        "Role, PartialMember, Member or Snowflake"
                    )

                _overwrites.append({
                    "id": str(obj.id),
                    "type": int(_type),
                    "allow": perm.allow,
                    "deny": perm.deny
                })

            payload["permission_overwrites"] = _overwrites

        if name is not MISSING:
            payload["name"] = str(name)
        if category is not MISSING:
            payload["parent_id"] = str(category.id)
        if position is not MISSING:
            payload["position"] = int(position or 0)
        if nsfw is not MISSING:
            payload["nsfw"] = bool(nsfw)

        payload.update(kwargs)

        r = await self._state.query(
            "PATCH",
            f"/channels/{self.id}",
            json=payload,
            reason=reason
        )

        return self._class_to_return(
            data=r.response
        )

    async def delete(
        self,
        *,
        reason: Optional[str] = None
    ) -> None:
        """
        Delete the channel

        Parameters
        ----------
        reason: `Optional[str]`
            The reason for deleting the channel
        """
        await self._state.query(
            "DELETE",
            f"/channels/{self.id}",
            reason=reason,
            res_method="text"
        )

    async def delete_messages(
        self,
        message_ids: list[int],
        *,
        reason: Optional[str] = None
    ) -> None:
        """
        _summary_

        Parameters
        ----------
        message_ids: `list[int]`
            List of message IDs to delete
        reason: `Optional[str]`
            The reason of why you are deleting them (appears in audit log)

        Raises
        ------
        `ValueError`
            If you provide >100 IDs to delete
        """
        if len(message_ids) <= 0:
            return None

        if len(message_ids) == 1:
            msg = self.get_partial_message(message_ids[0])
            return await msg.delete(reason=reason)
        if len(message_ids) > 100:
            raise ValueError("message_ids must be less than or equal to 100")

        await self._state.query(
            "POST",
            f"/channels/{self.id}/messages/bulk-delete",
            json={"messages": message_ids},
            reason=reason,
            res_method="text"
        )

    async def create_webhook(
        self,
        name: str,
        *,
        avatar: Optional[Union[File, bytes]] = None,
        reason: Optional[str] = None
    ) -> Webhook:
        """
        Create a webhook for the channel

        Parameters
        ----------
        name: `str`
            The name of the webhook
        avatar: `Optional[File]`
            The avatar of the webhook
        reason: `Optional[str]`
            The reason for creating the webhook that appears in audit logs

        Returns
        -------
        `Webhook`
            The webhook object
        """
        payload = {"name": name}

        if avatar is not None:
            payload["avatar"] = utils.bytes_to_base64(avatar)

        r = await self._state.query(
            "POST",
            f"/channels/{self.id}/webhooks",
            json=payload,
            reason=reason,
        )

        return Webhook(state=self._state, data=r.response)

    async def create_thread(
        self,
        name: str,
        *,
        type: Union[ChannelType, int] = ChannelType.guild_private_thread,
        auto_archive_duration: Optional[int] = 60,
        invitable: bool = True,
        rate_limit_per_user: Optional[Union[timedelta, int]] = None,
        reason: Optional[str] = None
    ) -> Union["PublicThread", "PrivateThread", "NewsThread"]:
        """
        Creates a thread in the channel

        Parameters
        ----------
        name: `str`
            The name of the thread
        type: `Optional[Union[ChannelType, int]]`
            The type of thread to create
        auto_archive_duration: `Optional[int]`
            The duration in minutes to automatically archive the thread after recent activity
        invitable: `bool`
            If the thread is invitable
        rate_limit_per_user: `Optional[Union[timedelta, int]]`
            How long the slowdown should be
        reason: `Optional[str]`
            The reason for creating the thread

        Returns
        -------
        `Union[PublicThread, PrivateThread, NewsThread]`
            The thread object

        Raises
        ------
        `ValueError`
            - If the auto_archive_duration is not 60, 1440, 4320 or 10080
            - If the rate_limit_per_user is not between 0 and 21600 seconds
        """
        payload = {
            "name": name,
            "type": int(type),
            "invitable": invitable,
        }

        if auto_archive_duration not in (60, 1440, 4320, 10080):
            raise ValueError("auto_archive_duration must be 60, 1440, 4320 or 10080")

        if rate_limit_per_user is not None:
            if isinstance(rate_limit_per_user, timedelta):
                rate_limit_per_user = int(rate_limit_per_user.total_seconds())

            if rate_limit_per_user not in range(0, 21601):
                raise ValueError("rate_limit_per_user must be between 0 and 21600 seconds")

            payload["rate_limit_per_user"] = rate_limit_per_user

        r = await self._state.query(
            "POST",
            f"/channels/{self.id}/threads",
            json=payload,
            reason=reason
        )

        match r.response["type"]:
            case ChannelType.guild_public_thread:
                _class = PublicThread
            case ChannelType.guild_private_thread:
                _class = PrivateThread
            case ChannelType.guild_news_thread:
                _class = NewsThread
            case _:
                raise ValueError("Invalid thread type")

        return _class(
            state=self._state,
            data=r.response
        )

    async def fetch_history(
        self,
        *,
        before: Optional[Union[datetime, "Message", utils.Snowflake, int]] = None,
        after: Optional[Union[datetime, "Message", utils.Snowflake, int]] = None,
        around: Optional[Union[datetime, "Message", utils.Snowflake, int]] = None,
        limit: Optional[int] = 100,
    ) -> AsyncIterator["Message"]:
        """
        Fetch the channel's message history

        Parameters
        ----------
        before: `Optional[Union[datetime, Message, utils.Snowflake, int]]`
            Get messages before this message
        after: `Optional[Union[datetime, Message, utils.Snowflake, int]]`
            Get messages after this message
        around: `Optional[Union[datetime, Message, utils.Snowflake, int]]`
            Get messages around this message
        limit: `int`
            The maximum amount of messages to fetch

        Yields
        ------
        `Message`
            The message object
        """
        def _resolve_id(entry) -> int:
            match entry:
                case x if isinstance(x, Message):
                    return x.id
                case x if isinstance(x, utils.Snowflake):
                    return int(x)
                case x if isinstance(x, int):
                    return x
                case x if isinstance(x, str):
                    if not x.isdigit():
                        raise TypeError("Got a string that was not a Snowflake ID for before/after/around")
                    return int(x)
                case x if isinstance(x, datetime):
                    return utils.time_snowflake(x)
                case _:
                    raise TypeError("Got an unknown type for before/after/around")

        async def _get_history(limit: int, **kwargs):
            params = {"limit": limit}
            for key, value in kwargs.items():
                if value is None:
                    continue
                params[key] = _resolve_id(value)

            return await self._state.query(
                "GET",
                f"/channels/{self.id}/messages",
                params=params
            )

        async def _around_http(http_limit: int, around_id: int, limit: int):
            r = await _get_history(limit=http_limit, around=around_id)
            return r.response, None, limit

        async def _after_http(http_limit: int, after_id: int, limit: int):
            r = await _get_history(limit=http_limit, after=after_id)

            if r.response:
                if limit is not None:
                    limit -= len(r.response)
                after_id = int(r.response[0]["id"])

            return r.response, after_id, limit

        async def _before_http(http_limit: int, before_id: int, limit: int):
            r = await _get_history(limit=http_limit, before=before_id)

            if r.response:
                if limit is not None:
                    limit -= len(r.response)
                before_id = int(r.response[-1]["id"])

            return r.response, before_id, limit

        if around:
            if limit is None:
                raise ValueError("limit must be specified when using around")
            if limit > 100:
                raise ValueError("limit must be less than or equal to 100 when using around")

            strategy, state = _around_http, _resolve_id(around)
        elif after:
            strategy, state = _after_http, _resolve_id(after)
        elif before:
            strategy, state = _before_http, _resolve_id(before)
        else:
            strategy, state = _before_http, None

        # Must be imported here to avoid circular import
        # From the top of the file
        from .message import Message

        while True:
            http_limit = 100 if limit is None else min(limit, 100)
            if http_limit <= 0:
                break

            strategy: Callable
            messages, state, limit = await strategy(http_limit, state, limit)

            i = 0
            for i, msg in enumerate(messages, start=1):
                yield Message(
                    state=self._state,
                    data=msg,
                    guild=self.guild
                )

            if i < 100:
                break

    async def join_thread(self) -> None:
        """ Make the bot join a thread """
        await self._state.query(
            "PUT",
            f"/channels/{self.id}/thread-members/@me",
            res_method="text"
        )

    async def leave_thread(self) -> None:
        """ Make the bot leave a thread """
        await self._state.query(
            "DELETE",
            f"/channels/{self.id}/thread-members/@me",
            res_method="text"
        )

    async def add_thread_member(
        self,
        user_id: int
    ) -> None:
        """
        Add a thread member

        Parameters
        ----------
        user_id: `int`
            The user ID to add
        """
        await self._state.query(
            "PUT",
            f"/channels/{self.id}/thread-members/{user_id}",
            res_method="text"
        )

    async def remove_thread_member(
        self,
        user_id: int
    ) -> None:
        """
        Remove a thread member

        Parameters
        ----------
        user_id: `int`
            The user ID to remove
        """
        await self._state.query(
            "DELETE",
            f"/channels/{self.id}/thread-members/{user_id}",
            res_method="text"
        )

    async def fetch_thread_member(
        self,
        user_id: int
    ) -> ThreadMember:
        """
        Fetch a thread member

        Parameters
        ----------
        user_id: `int`
            The user ID to fetch

        Returns
        -------
        `ThreadMember`
            The thread member object
        """
        r = await self._state.query(
            "GET",
            f"/channels/{self.id}/thread-members/{user_id}",
            params={"with_member": "true"}
        )

        return ThreadMember(
            state=self._state,
            data=r.response,
        )

    async def fetch_thread_members(self) -> list[ThreadMember]:
        """
        Fetch all thread members

        Returns
        -------
        `list[ThreadMember]`
            The list of thread members
        """
        r = await self._state.query(
            "GET",
            f"/channels/{self.id}/thread-members",
            params={"with_member": "true"},
        )

        return [
            ThreadMember(
                state=self._state,
                data=data
            )
            for data in r.response
        ]


class BaseChannel(PartialChannel):
    def __init__(self, state: "DiscordAPI", data: dict):
        super().__init__(
            state=state,
            channel_id=int(data["id"]),
            guild_id=utils.get_int(data, "guild_id")
        )

        self.id: int = int(data["id"])
        self.name: Optional[str] = data.get("name", None)
        self._raw_type: ChannelType = ChannelType(data["type"])
        self.nsfw: bool = data.get("nsfw", False)
        self.topic: Optional[str] = data.get("topic", None)
        self.position: Optional[int] = utils.get_int(data, "position")

        self._from_data(data)

    def _from_data(self, data: dict):
        self.permission_overwrites: Optional[int] = None
        if data.get("permissions", None):
            self.permissions = int(data["permissions"])

        self.parent_id: Optional[int] = None
        if data.get("parent_id", None):
            self.parent_id = int(data["parent_id"])

        self.last_message_id: Optional[int] = None
        if data.get("last_message_id", None):
            self.last_message_id = int(data["last_message_id"])

    def __repr__(self) -> str:
        return f"<Channel id={self.id} name='{self.name}'>"

    def __str__(self) -> str:
        return self.name or ""

    @property
    def mention(self) -> str:
        """ `str`: The channel's mention """
        return f"<#{self.id}>"

    @property
    def type(self) -> ChannelType:
        """ `ChannelType`: Returns the channel's type """
        return ChannelType.guild_text


class TextChannel(BaseChannel):
    def __init__(self, *, state: "DiscordAPI", data: dict):
        super().__init__(state=state, data=data)

    def __repr__(self) -> str:
        return f"<TextChannel id={self.id} name='{self.name}'>"

    async def edit(
        self,
        *,
        name: Optional[str] = MISSING,
        type: Optional[ChannelType] = MISSING,
        topic: Optional[str] = MISSING,
        position: Optional[int] = MISSING,
        nsfw: Optional[bool] = MISSING,
        parent_id: Optional[int] = MISSING,
    ) -> Self:
        """
        Edit the channel

        Parameters
        ----------
        name: `str`
            Name of the channel
        type: `ChannelType`
            Which type the channel should be
        topic: `str`
            Topic of the channel
        position: `int`
            Position of the channel
        nsfw: `Optional[bool]`
            If the channel should be NSFW
        parent_id: `int`
            The parent ID of the channel

        Returns
        -------
        `TextChannel`
            The channel object

        Raises
        ------
        `ValueError`
            If the type is not guild_text or guild_news
        """
        payload = {}

        if name is not MISSING:
            payload["name"] = name
        if topic is not MISSING:
            payload["topic"] = topic
        if position is not MISSING:
            payload["position"] = position
        if nsfw is not MISSING:
            payload["nsfw"] = nsfw
        if parent_id is not MISSING:
            payload["parent_id"] = parent_id
        if type is not MISSING:
            if type not in (ChannelType.guild_text, ChannelType.guild_news):
                raise ValueError("Invalid channel type, must be text or news.")
            payload["type"] = type.value

        return await super().edit(**payload)

    @property
    def type(self) -> ChannelType:
        """ `ChannelType`: Returns the channel's type """
        if self._raw_type == 0:
            return ChannelType.guild_text
        return ChannelType.guild_news


class DMChannel(BaseChannel):
    def __init__(self, *, state: "DiscordAPI", data: dict):
        super().__init__(state=state, data=data)

        self.name: Optional[str] = None
        self.user: Optional["User"] = None
        self.last_message: Optional["PartialMessage"] = None

        self._from_data(data)

    def __repr__(self) -> str:
        return f"<DMChannel id={self.id} name='{self.user}'>"

    def _from_data(self, data: dict):
        if data.get("recipients", None):
            from .user import User
            self.user = User(state=self._state, data=data["recipients"][0])
            self.name = self.user.name

        if data.get("last_message_id", None):
            from .message import PartialMessage
            self.last_message = PartialMessage(
                state=self._state,
                channel_id=self.id,
                id=int(data["last_message_id"])
            )

        if data.get("last_pin_timestamp", None):
            self.last_pin_timestamp = utils.parse_time(data["last_pin_timestamp"])

    @property
    def type(self) -> ChannelType:
        """ `ChannelType`: Returns the channel's type """
        return ChannelType.dm

    @property
    def mention(self) -> str:
        """ `str`: The channel's mention """
        return f"<@{self.id}>"

    async def edit(self, *args, **kwargs) -> None:
        """
        Only here to prevent errors

        Raises
        ------
        `TypeError`
            If you try to edit a DM channel
        """
        raise TypeError("Cannot edit a DM channel")


class StoreChannel(BaseChannel):
    def __init__(self, *, state: "DiscordAPI", data: dict):
        super().__init__(state=state, data=data)

    def __repr__(self) -> str:
        return f"<StoreChannel id={self.id} name='{self.name}'>"

    @property
    def type(self) -> ChannelType:
        """ `ChannelType`: Returns the channel's type """
        return ChannelType.guild_store


class GroupDMChannel(BaseChannel):
    def __init__(self, *, state: "DiscordAPI", data: dict):
        super().__init__(state=state, data=data)

    def __repr__(self) -> str:
        return f"<GroupDMChannel id={self.id} name='{self.name}'>"

    @property
    def type(self) -> ChannelType:
        """ `ChannelType`: Returns the channel's type """
        return ChannelType.group_dm


class DirectoryChannel(BaseChannel):
    def __init__(self, *, state: "DiscordAPI", data: dict):
        super().__init__(state=state, data=data)

    def __repr__(self) -> str:
        return f"<DirectoryChannel id={self.id} name='{self.name}'>"

    @property
    def type(self) -> ChannelType:
        """ `ChannelType`: Returns the channel's type """
        return ChannelType.guild_directory


class CategoryChannel(BaseChannel):
    def __init__(self, *, state: "DiscordAPI", data: dict):
        super().__init__(state=state, data=data)

    def __repr__(self) -> str:
        return f"<CategoryChannel id={self.id} name='{self.name}'>"

    @property
    def type(self) -> ChannelType:
        """ `ChannelType`: Returns the channel's type """
        return ChannelType.guild_category


class NewsChannel(BaseChannel):
    def __init__(self, state: "DiscordAPI", data: dict):
        super().__init__(state, data)

    def __repr__(self) -> str:
        return f"<NewsChannel id={self.id} name='{self.name}'>"

    @property
    def type(self) -> ChannelType:
        """ `ChannelType`: Returns the channel's type """
        return ChannelType.guild_news


# Thread channels
class PublicThread(BaseChannel):
    def __init__(self, *, state: "DiscordAPI", data: dict):
        super().__init__(state=state, data=data)

        self.name: str = data["name"]

        self.message_count: int = int(data["message_count"])
        self.member_count: int = int(data["member_count"])
        self.rate_limit_per_user: int = int(data["rate_limit_per_user"])
        self.total_message_sent: int = int(data["total_message_sent"])

        self._metadata: dict = data.get("thread_metadata", {})

        self.locked: bool = self._metadata.get("locked", False)
        self.auto_archive_duration: int = self._metadata.get("auto_archive_duration", 60)

        self.channel_id: int = int(data["id"])
        self.guild_id: int = int(data["guild_id"])
        self.owner_id: int = int(data["owner_id"])
        self.last_message_id: Optional[int] = utils.get_int(data, "last_message_id")
        self.parent_id: Optional[int] = utils.get_int(data, "parent_id")

    def __repr__(self) -> str:
        return f"<PublicThread id={self.id} name='{self.name}'>"

    @property
    def channel(self) -> "PartialChannel":
        """ `PartialChannel`: Returns a partial channel object """
        from .channel import PartialChannel
        return PartialChannel(state=self._state, channel_id=self.channel_id)

    @property
    def guild(self) -> "PartialGuild":
        """ `PartialGuild`: Returns a partial guild object """
        from .guild import PartialGuild
        return PartialGuild(state=self._state, guild_id=self.guild_id)

    @property
    def owner(self) -> "PartialUser":
        """ `PartialUser`: Returns a partial user object """
        from .user import PartialUser
        return PartialUser(state=self._state, id=self.owner_id)

    @property
    def last_message(self) -> Optional["PartialMessage"]:
        """ `Optional[PartialMessage]`: Returns a partial message object if the last message ID is available """
        if not self.last_message_id:
            return None

        from .message import PartialMessage
        return PartialMessage(
            state=self._state,
            channel_id=self.channel_id,
            id=self.last_message_id
        )


class ForumChannel(PublicThread):
    def __init__(self, state: "DiscordAPI", data: dict):
        super().__init__(state=state, data=data)
        self.default_reaction_emoji: str = data["default_auto_archive_duration"]

    def __repr__(self) -> str:
        return f"<ForumChannel id={self.id} name='{self.name}'>"


class NewsThread(PublicThread):
    def __init__(self, state: "DiscordAPI", data: dict):
        super().__init__(state=state, data=data)

    def __repr__(self) -> str:
        return f"<NewsThread id={self.id} name='{self.name}'>"


class PrivateThread(PublicThread):
    def __init__(self, *, state: "DiscordAPI", data: dict):
        super().__init__(state=state, data=data)

    @property
    def type(self) -> ChannelType:
        """ `ChannelType`: Returns the channel's type """
        return ChannelType.guild_private_thread


# Voice channels
class VoiceChannel(BaseChannel):
    def __init__(self, *, state: "DiscordAPI", data: dict):
        super().__init__(state=state, data=data)
        self.bitrate: int = int(data["bitrate"])
        self.user_limit: int = int(data["user_limit"])
        self.rtc_region: Optional[str] = data.get("rtc_region", None)

    def __repr__(self) -> str:
        return f"<VoiceChannel id={self.id} name='{self.name}'>"

    @property
    def type(self) -> ChannelType:
        """ `ChannelType`: Returns the channel's type """
        return ChannelType.guild_voice


class StageChannel(VoiceChannel):
    def __init__(self, *, state: "DiscordAPI", data: dict):
        super().__init__(state=state, data=data)

    def __repr__(self) -> str:
        return f"<StageChannel id={self.id} name='{self.name}'>"

    @property
    def type(self) -> ChannelType:
        """ `ChannelType`: Returns the channel's type """
        return ChannelType.guild_stage_voice
