from datetime import timedelta, datetime
from io import BytesIO
from typing import TYPE_CHECKING, Optional, Union

from . import http, utils
from .embeds import Embed
from .emoji import EmojiParser
from .errors import HTTPException
from .file import File
from .mentions import AllowedMentions
from .object import PartialBase
from .response import MessageResponse
from .role import PartialRole
from .sticker import PartialSticker
from .user import User
from .view import View

if TYPE_CHECKING:
    from .channel import BaseChannel, PartialChannel, PublicThread
    from .guild import Guild, PartialGuild
    from .http import DiscordAPI

MISSING = utils.MISSING

__all__ = (
    "Attachment",
    "JumpURL",
    "Message",
    "MessageReference",
    "PartialMessage",
    "WebhookMessage",
)


class JumpURL:
    def __init__(
        self,
        *,
        state: "DiscordAPI",
        url: Optional[str] = None,
        guild_id: Optional[int] = None,
        channel_id: Optional[int] = None,
        message_id: Optional[int] = None
    ):
        self._state = state

        self.guild_id: Optional[int] = guild_id or None
        self.channel_id: Optional[int] = channel_id or None
        self.message_id: Optional[int] = message_id or None

        if url:
            if any([guild_id, channel_id, message_id]):
                raise ValueError("Cannot provide both a URL and a guild_id, channel_id or message_id")

            _parse_url: Optional[list[tuple[str, str, Optional[str]]]] = utils.re_jump_url.findall(url)
            if not _parse_url:
                raise ValueError("Invalid jump URL provided")

            gid, cid, mid = _parse_url[0]

            self.channel_id = int(cid)
            if gid != "@me":
                self.guild_id = int(gid)
            if mid:
                self.message_id = int(mid)

        if not self.channel_id:
            raise ValueError("Cannot create a JumpURL without a channel_id")

    def __repr__(self) -> str:
        return (
            f"<JumpURL guild_id={self.guild_id} channel_id={self.channel_id} "
            f"message_id={self.message_id}>"
        )

    def __str__(self) -> str:
        return self.url

    @property
    def guild(self) -> Optional["PartialGuild"]:
        """ `Optional[PartialGuild]`: The guild the message was sent in """
        if not self.guild_id:
            return None

        from .guild import PartialGuild
        return PartialGuild(
            state=self._state,
            id=self.guild_id
        )

    async def fetch_guild(self) -> "Guild":
        """ `Optional[Guild]`: Returns the guild the message was sent in """
        if not self.guild_id:
            raise ValueError("Cannot fetch a guild without a guild_id available")

        return await self.guild.fetch()

    @property
    def channel(self) -> Optional["PartialChannel"]:
        """ `PartialChannel`: Returns the channel the message was sent in """
        if not self.channel_id:
            return None

        from .channel import PartialChannel
        return PartialChannel(
            state=self._state,
            id=self.channel_id,
            guild_id=self.guild_id
        )

    async def fetch_channel(self) -> "BaseChannel":
        """ `BaseChannel`: Returns the channel the message was sent in """
        return await self.channel.fetch()

    @property
    def message(self) -> Optional["PartialMessage"]:
        """ `Optional[PartialMessage]`: Returns the message if a message_id is available """
        if not self.channel_id or not self.message_id:
            return None

        return PartialMessage(
            state=self._state,
            channel_id=self.channel_id,
            id=self.message_id
        )

    async def fetch_message(self) -> "Message":
        """ `Message`: Returns the message if a message_id is available """
        if not self.message_id:
            raise ValueError("Cannot fetch a message without a message_id available")

        return await self.message.fetch()

    @property
    def url(self) -> str:
        """ `Optional[str]`: Returns the jump URL """
        if self.channel_id and self.message_id:
            return f"https://discord.com/channels/{self.guild_id or '@me'}/{self.channel_id}/{self.message_id}"
        return f"https://discord.com/channels/{self.guild_id or '@me'}/{self.channel_id}"


class MessageReference:
    def __init__(self, *, state: "DiscordAPI", data: dict):
        self._state = state

        self.guild_id: Optional[int] = utils.get_int(data, "guild_id")
        self.channel_id: Optional[int] = utils.get_int(data, "channel_id")
        self.message_id: Optional[int] = utils.get_int(data, "message_id")

    def __repr__(self) -> str:
        return (
            f"<MessageReference guild_id={self.guild_id} channel_id={self.channel_id} "
            f"message_id={self.message_id}>"
        )

    @property
    def guild(self) -> Optional["PartialGuild"]:
        """ `Optional[PartialGuild]`: The guild the message was sent in """
        if not self.guild_id:
            return None

        from .guild import PartialGuild
        return PartialGuild(
            state=self._state,
            id=self.guild_id
        )

    @property
    def channel(self) -> Optional["PartialChannel"]:
        """ `Optional[PartialChannel]`: Returns the channel the message was sent in """
        if not self.channel_id:
            return None

        from .channel import PartialChannel
        return PartialChannel(
            state=self._state,
            id=self.channel_id,
            guild_id=self.guild_id
        )

    @property
    def message(self) -> Optional["PartialMessage"]:
        """ `Optional[PartialMessage]`: Returns the message if a message_id and channel_id is available """
        if not self.channel_id or not self.message_id:
            return None

        return PartialMessage(
            state=self._state,
            channel_id=self.channel_id,
            id=self.message_id
        )

    def to_dict(self) -> dict:
        """ `dict`: Returns the message reference as a dictionary """
        payload = {}

        if self.guild_id:
            payload["guild_id"] = self.guild_id
        if self.channel_id:
            payload["channel_id"] = self.channel_id
        if self.message_id:
            payload["message_id"] = self.message_id

        return payload


class Attachment:
    def __init__(self, *, state: "DiscordAPI", data: dict):
        self._state = state

        self.id: int = int(data["id"])
        self.filename: str = data["filename"]
        self.size: int = int(data["size"])
        self.url: str = data["url"]
        self.proxy_url: str = data["proxy_url"]
        self.ephemeral: bool = data.get("ephemeral", False)

        self.content_type: Optional[str] = data.get("content_type", None)
        self.description: Optional[str] = data.get("description", None)

        self.height: Optional[int] = data.get("height", None)
        self.width: Optional[int] = data.get("width", None)
        self.ephemeral: bool = data.get("ephemeral", False)

    def __str__(self) -> str:
        return self.filename or ""

    def __int__(self) -> int:
        return self.id

    def __repr__(self) -> str:
        return (
            f"<Attachment id={self.id} filename='{self.filename}' "
            f"url='{self.url}'>"
        )

    def is_spoiler(self) -> bool:
        """ `bool`: Whether the attachment is a spoiler or not """
        return self.filename.startswith("SPOILER_")

    async def fetch(self, *, use_cached: bool = False) -> bytes:
        """
        Fetches the file from the attachment URL and returns it as bytes

        Parameters
        ----------
        use_cached: `bool`
            Whether to use the cached URL or not, defaults to `False`

        Returns
        -------
        `bytes`
            The attachment as bytes

        Raises
        ------
        `HTTPException`
            If the request returned anything other than 2XX
        """
        r = await http.query(
            "GET",
            self.proxy_url if use_cached else self.url,
            res_method="read"
        )

        if r.status not in range(200, 300):
            raise HTTPException(r)

        return r.response

    async def save(
        self,
        path: str,
        *,
        use_cached: bool = False
    ) -> int:
        """
        Fetches the file from the attachment URL and saves it locally to the path

        Parameters
        ----------
        path: `str`
            Path to save the file to, which includes the filename and extension.
            Example: `./path/to/file.png`
        use_cached: `bool`
            Whether to use the cached URL or not, defaults to `False`

        Returns
        -------
        `int`
            The amount of bytes written to the file
        """
        data = await self.fetch(use_cached=use_cached)
        with open(path, "wb") as f:
            return f.write(data)

    async def to_file(
        self,
        *,
        filename: Optional[str] = MISSING,
        spoiler: bool = False
    ) -> File:
        """
        Convert the attachment to a sendable File object for Message.send()

        Parameters
        ----------
        filename: `Optional[str]`
            Filename for the file, if empty, the attachment's filename will be used
        spoiler: `bool`
            Weather the file should be marked as a spoiler or not, defaults to `False`

        Returns
        -------
        `File`
            The attachment as a File object
        """
        if filename is MISSING:
            filename = self.filename

        data = await self.fetch()

        return File(
            data=BytesIO(data),
            filename=str(filename),
            spoiler=spoiler,
            description=self.description
        )

    def to_dict(self) -> dict:
        """ `dict`: The attachment as a dictionary """
        data = {
            "id": self.id,
            "filename": self.filename,
            "size": self.size,
            "url": self.url,
            "proxy_url": self.proxy_url,
            "spoiler": self.is_spoiler(),
        }

        if self.description is not None:
            data["description"] = self.description
        if self.height:
            data["height"] = self.height
        if self.width:
            data["width"] = self.width
        if self.content_type:
            data["content_type"] = self.content_type

        return data


class PartialMessage(PartialBase):
    def __init__(
        self,
        *,
        state: "DiscordAPI",
        id: int,
        channel_id: int,
    ):
        super().__init__(id=int(id))
        self._state = state

        self.channel_id: int = int(channel_id)

    def __repr__(self) -> str:
        return f"<PartialMessage id={self.id}>"

    @property
    def channel(self) -> "PartialChannel":
        """ `PartialChannel`: Returns the channel the message was sent in """
        from .channel import PartialChannel
        return PartialChannel(state=self._state, id=self.channel_id)

    @property
    def jump_url(self) -> JumpURL:
        """ `JumpURL`: Returns the jump URL of the message, GuildID will always be @me """
        return JumpURL(
            state=self._state,
            url=f"https://discord.com/channels/@me/{self.channel_id}/{self.id}"
        )

    async def fetch(self) -> "Message":
        """ `Message`: Returns the message object """
        r = await self._state.query(
            "GET",
            f"/channels/{self.channel.id}/messages/{self.id}"
        )

        return Message(
            state=self._state,
            data=r.response,
            guild=self.channel.guild
        )

    async def delete(self, *, reason: Optional[str] = None) -> None:
        """ Delete the message """
        await self._state.query(
            "DELETE",
            f"/channels/{self.channel.id}/messages/{self.id}",
            reason=reason,
            res_method="text"
        )

    async def edit(
        self,
        *,
        content: Optional[str] = MISSING,
        embed: Optional[Embed] = MISSING,
        embeds: Optional[list[Embed]] = MISSING,
        view: Optional[View] = MISSING,
        attachment: Optional[File] = MISSING,
        attachments: Optional[list[File]] = MISSING,
        allowed_mentions: Optional[AllowedMentions] = MISSING
    ) -> "Message":
        """
        Edit the message

        Parameters
        ----------
        content: `Optional[str]`
            Content of the message
        embed: `Optional[Embed]`
            Embed of the message
        embeds: `Optional[list[Embed]]`
            Embeds of the message
        view: `Optional[View]`
            Components of the message
        attachment: `Optional[File]`
            New attachment of the message
        attachments: `Optional[list[File]]`
            New attachments of the message
        allowed_mentions: `Optional[AllowedMentions]`
            Allowed mentions of the message

        Returns
        -------
        `Message`
            The edited message
        """
        payload = MessageResponse(
            content=content,
            embed=embed,
            embeds=embeds,
            view=view,
            attachment=attachment,
            attachments=attachments,
            allowed_mentions=allowed_mentions
        )

        r = await self._state.query(
            "PATCH",
            f"/channels/{self.channel.id}/messages/{self.id}",
            headers={"Content-Type": payload.content_type},
            data=payload.to_multipart(is_request=True),
        )

        return Message(
            state=self._state,
            data=r.response,
            guild=self.channel.guild
        )

    async def publish(self) -> "Message":
        """
        Crosspost the message to another channel.
        """
        r = await self._state.query(
            "POST",
            f"/channels/{self.channel.id}/messages/{self.id}/crosspost",
            res_method="json"
        )

        return Message(
            state=self._state,
            data=r.response,
            guild=self.channel.guild
        )

    async def reply(
        self,
        content: Optional[str] = MISSING,
        *,
        embed: Optional[Embed] = MISSING,
        embeds: Optional[list[Embed]] = MISSING,
        file: Optional[File] = MISSING,
        files: Optional[list[File]] = MISSING,
        view: Optional[View] = MISSING,
        tts: Optional[bool] = False,
        allowed_mentions: Optional[AllowedMentions] = MISSING,
    ) -> "Message":
        """
        Sends a reply to a message in a channel.

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
            allowed_mentions=allowed_mentions,
            message_reference=MessageReference(
                state=self._state,
                data={
                    "channel_id": self.channel_id,
                    "message_id": self.id
                }
            )
        )

        r = await self._state.query(
            "POST",
            f"/channels/{self.channel_id}/messages",
            data=payload.to_multipart(is_request=True),
            headers={"Content-Type": payload.content_type}
        )

        return Message(
            state=self._state,
            data=r.response
        )

    async def pin(self, *, reason: Optional[str] = None) -> None:
        """
        Pin the message

        Parameters
        ----------
        reason: `Optional[str]`
            Reason for pinning the message
        """
        await self._state.query(
            "PUT",
            f"/channels/{self.channel.id}/pins/{self.id}",
            res_method="text",
            reason=reason
        )

    async def unpin(self, *, reason: Optional[str] = None) -> None:
        """
        Unpin the message

        Parameters
        ----------
        reason: `Optional[str]`
            Reason for unpinning the message
        """
        await self._state.query(
            "DELETE",
            f"/channels/{self.channel.id}/pins/{self.id}",
            res_method="text",
            reason=reason
        )

    async def add_reaction(self, emoji: str) -> None:
        """
        Add a reaction to the message

        Parameters
        ----------
        emoji: `str`
            Emoji to add to the message
        """
        _parsed = EmojiParser(emoji).to_reaction()
        await self._state.query(
            "PUT",
            f"/channels/{self.channel.id}/messages/{self.id}/reactions/{_parsed}/@me",
            res_method="text"
        )

    async def remove_reaction(
        self,
        emoji: str,
        *,
        user_id: Optional[int] = None
    ) -> None:
        """
        Remove a reaction from the message

        Parameters
        ----------
        emoji: `str`
            Emoji to remove from the message
        user_id: `Optional[int]`
            User ID to remove the reaction from
        """
        _parsed = EmojiParser(emoji).to_reaction()
        _url = (
            f"/channels/{self.channel.id}/messages/{self.id}/reactions/{_parsed}"
            f"/{user_id}" if user_id is not None else "/@me"
        )

        await self._state.query(
            "DELETE",
            _url,
            res_method="text"
        )

    async def create_public_thread(
        self,
        name: str,
        *,
        auto_archive_duration: Optional[int] = 60,
        rate_limit_per_user: Optional[Union[timedelta, int]] = None,
        reason: Optional[str] = None
    ) -> "PublicThread":
        """
        Create a public thread from the message

        Parameters
        ----------
        name: `str`
            Name of the thread
        auto_archive_duration: `Optional[int]`
            Duration in minutes to automatically archive the thread after recent activity,
        rate_limit_per_user: `Optional[Union[timedelta, int]]`
            A per-user rate limit for this thread (0-21600 seconds, default 0)
        reason: `Optional[str]`
            Reason for creating the thread

        Returns
        -------
        `PublicThread`
            The created thread

        Raises
        ------
        `ValueError`
            - If `auto_archive_duration` is not 60, 1440, 4320 or 10080
            - If `rate_limit_per_user` is not between 0 and 21600 seconds
        """
        payload = {
            "name": name,
            "auto_archive_duration": auto_archive_duration,
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
            f"/channels/{self.channel.id}/threads/messages/{self.id}/threads",
            json=payload,
            reason=reason
        )

        from .channel import PublicThread
        return PublicThread(
            state=self._state,
            data=r.response
        )


class Message(PartialMessage):
    def __init__(
        self,
        *,
        state: "DiscordAPI",
        data: dict,
        guild: Optional["PartialGuild"] = None
    ):
        super().__init__(
            state=state,
            channel_id=int(data["channel_id"]),
            id=int(data["id"])
        )

        self.guild = guild
        self.guild_id: Optional[int] = guild.id if guild is not None else None

        self.content: Optional[str] = data.get("content", None)
        self.author: User = User(state=state, data=data["author"])
        self.pinned: bool = data.get("pinned", False)
        self.mention_everyone: bool = data.get("mention_everyone", False)
        self.tts: bool = data.get("tts", False)

        self.embeds: list[Embed] = [
            Embed.from_dict(embed)
            for embed in data.get("embeds", [])
        ]

        self.attachments: list[Attachment] = [
            Attachment(state=state, data=a)
            for a in data.get("attachments", [])
        ]

        self.stickers: list[PartialSticker] = [
            PartialSticker(state=state, id=int(s["id"]), name=s["name"])
            for s in data.get("sticker_items", [])
        ]

        self.user_mentions: list[User] = [
            User(state=self._state, data=g)
            for g in data.get("mentions", [])
        ]

        self.view: Optional[View] = View.from_dict(data)
        self.edited_timestamp: Optional[datetime] = None

        self.message_reference: Optional[MessageReference] = None
        self.referenced_message: Optional[Message] = None

        self._from_data(data)

    def __repr__(self) -> str:
        return f"<Message id={self.id} author={self.author}>"

    def __str__(self) -> str:
        return self.content or ""

    def _from_data(self, data: dict):
        if data.get("message_reference", None):
            self.message_reference = MessageReference(
                state=self._state,
                data=data["message_reference"]
            )

        if data.get("referenced_message", None):
            self.referenced_message = Message(
                state=self._state,
                data=data["referenced_message"],
                guild=self.guild
            )

        if data.get("edited_timestamp", None):
            self.edited_timestamp = utils.parse_time(data["edited_timestamp"])

    @property
    def emojis(self) -> list[EmojiParser]:
        """ `list[EmojiParser]`: Returns the emojis in the message """
        return [
            EmojiParser(f"<{e[0]}:{e[1]}:{e[2]}>")
            for e in utils.re_emoji.findall(self.content)
        ]

    @property
    def jump_url(self) -> JumpURL:
        """ `JumpURL`: Returns the jump URL of the message """
        return JumpURL(
            state=self._state,
            url=f"https://discord.com/channels/{self.guild_id or '@me'}/{self.channel_id}/{self.id}"
        )

    @property
    def role_mentions(self) -> list[PartialRole]:
        """ `list[PartialRole]`: Returns the role mentions in the message """
        if not self.guild_id:
            return []

        return [
            PartialRole(
                state=self._state,
                id=int(role_id),
                guild_id=self.guild_id
            )
            for role_id in utils.re_role.findall(self.content)
        ]

    @property
    def channel_mentions(self) -> list["PartialChannel"]:
        """ `list[PartialChannel]`: Returns the channel mentions in the message """
        from .channel import PartialChannel

        return [
            PartialChannel(state=self._state, id=int(channel_id))
            for channel_id in utils.re_channel.findall(self.content)
        ]

    @property
    def jump_urls(self) -> list[JumpURL]:
        """ `list[JumpURL]`: Returns the jump URLs in the message """
        return [
            JumpURL(
                state=self._state,
                guild_id=int(gid) if gid != "@me" else None,
                channel_id=int(cid),
                message_id=int(mid) if mid else None
            )
            for gid, cid, mid in utils.re_jump_url.findall(self.content)
        ]


class WebhookMessage(Message):
    def __init__(self, *, state: "DiscordAPI", data: dict, application_id: int, token: str):
        super().__init__(state=state, data=data)
        self.application_id = int(application_id)
        self.token = token

    async def edit(
        self,
        *,
        content: Optional[str] = MISSING,
        embed: Optional[Embed] = MISSING,
        embeds: Optional[list[Embed]] = MISSING,
        attachment: Optional[File] = MISSING,
        attachments: Optional[list[File]] = MISSING,
        view: Optional[View] = MISSING,
        allowed_mentions: Optional[AllowedMentions] = MISSING
    ) -> "WebhookMessage":
        """
        Edit the webhook message

        Parameters
        ----------
        content: `Optional[str]`
            Content of the message
        embed: `Optional[Embed]`
            Embed of the message
        embeds: `Optional[list[Embed]]`
            Embeds of the message
        attachment: `Optional[File]`
            Attachment of the message
        attachments: `Optional[list[File]]`
            Attachments of the message
        view: `Optional[View]`
            Components of the message
        allowed_mentions: `Optional[AllowedMentions]`
            Allowed mentions of the message

        Returns
        -------
        `WebhookMessage`
            The edited message
        """
        payload = MessageResponse(
            content=content,
            embed=embed,
            embeds=embeds,
            view=view,
            attachment=attachment,
            attachments=attachments,
            allowed_mentions=allowed_mentions
        )

        r = await self._state.query(
            "PATCH",
            f"/webhooks/{self.application_id}/{self.token}/messages/{self.id}",
            webhook=True,
            headers={"Content-Type": payload.content_type},
            data=payload.to_multipart(is_request=True),
        )

        return WebhookMessage(
            state=self._state,
            data=r.response,
            application_id=self.application_id,
            token=self.token
        )

    async def delete(
        self,
        *,
        reason: Optional[str] = None
    ) -> None:
        """
        Delete the webhook message

        Parameters
        ----------
        reason: `Optional[str]`
            Reason for deleting the message
        """
        await self._state.query(
            "DELETE",
            f"/webhooks/{self.application_id}/{self.token}/messages/{self.id}",
            reason=reason,
            webhook=True,
            res_method="text"
        )
