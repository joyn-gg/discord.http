import asyncio
import importlib
import inspect
import logging

from datetime import datetime
from typing import Dict, Optional, Any, Callable, Union, AsyncIterator

from . import utils
from .backend import DiscordHTTP
from .channel import PartialChannel, BaseChannel
from .commands import Command, Interaction, Listener, Cog, SubGroup
from .context import Context
from .emoji import PartialEmoji, Emoji
from .entitlements import PartialSKU, SKU, PartialEntitlements, Entitlements
from .enums import ApplicationCommandType
from .file import File
from .guild import PartialGuild, Guild, PartialScheduledEvent, ScheduledEvent
from .http import DiscordAPI
from .invite import PartialInvite, Invite
from .member import PartialMember, Member
from .mentions import AllowedMentions
from .message import PartialMessage, Message
from .object import Snowflake
from .role import PartialRole
from .sticker import PartialSticker, Sticker
from .user import User, PartialUser
from .view import InteractionStorage
from .webhook import PartialWebhook, Webhook

_log = logging.getLogger(__name__)

__all__ = (
    "Client",
)


class Client:
    def __init__(
        self,
        *,
        token: str,
        application_id: Optional[int] = None,
        public_key: Optional[str] = None,
        guild_id: Optional[int] = None,
        sync: bool = False,
        api_version: Optional[int] = None,
        loop: Optional[asyncio.AbstractEventLoop] = None,
        allowed_mentions: AllowedMentions = AllowedMentions.all(),
        logging_level: int = logging.INFO,
        disable_default_get_path: bool = False,
        disable_oauth_hint: bool = False,
        debug_events: bool = False
    ):
        """
        The main client class for discord.http

        Parameters
        ----------
        token: `str`
            Discord bot token
        application_id: `Optional[int]`
            Application ID of the bot, not the User ID
        public_key: `Optional[str]`
            Public key of the bot, used for validating interactions
        guild_id: `Optional[int]`
            Guild ID to sync commands to, if not provided, it will sync to global
        sync: `bool`
            Whether to sync commands on boot or not
        api_version: `Optional[int]`
            API version to use, if not provided, it will use the default (10)
        loop: `Optional[asyncio.AbstractEventLoop]`
            Event loop to use, if not provided, it will use `asyncio.get_running_loop()`
        allowed_mentions: `AllowedMentions`
            Allowed mentions to use, if not provided, it will use `AllowedMentions.all()`
        logging_level: `int`
            Logging level to use, if not provided, it will use `logging.INFO`
        debug_events: `bool`
            Whether to log events or not, if not provided, `on_raw_*` events will not be useable
        disable_default_get_path: `bool`
            Whether to disable the default GET path or not, if not provided, it will use `False`.
            The default GET path only provides information about the bot and when it was last rebooted.
            Usually a great tool to just validate that your bot is online.
        disable_oauth_hint: `bool`
            Whether to disable the OAuth2 hint or not on boot.
            If not provided, it will use `False`.
        """
        self.application_id: Optional[int] = application_id
        self.public_key: Optional[str] = public_key
        self.token: str = token
        self.guild_id: Optional[int] = guild_id
        self.sync: bool = sync
        self.logging_level: int = logging_level
        self.debug_events: bool = debug_events

        self.disable_oauth_hint: bool = disable_oauth_hint
        self.disable_default_get_path: bool = disable_default_get_path

        try:
            self.loop: asyncio.AbstractEventLoop = loop or asyncio.get_running_loop()
        except RuntimeError:
            self.loop: asyncio.AbstractEventLoop = asyncio.new_event_loop()
            asyncio.set_event_loop(self.loop)

        self.state: DiscordAPI = DiscordAPI(
            application_id=application_id,
            token=token,
            api_version=api_version
        )

        self.commands: Dict[str, Command] = {}
        self.listeners: list[Listener] = []
        self.interactions: Dict[str, Interaction] = {}
        self.interactions_regex: Dict[str, Interaction] = {}

        self._ready: Optional[asyncio.Event] = asyncio.Event()
        self._user_object: Optional[User] = None

        self._context: Callable = Context
        self.backend: DiscordHTTP = DiscordHTTP(client=self)

        self._view_storage: dict[int, InteractionStorage] = {}
        self._default_allowed_mentions = allowed_mentions

        self._cogs: dict[str, list[Cog]] = {}

        utils.setup_logger(level=self.logging_level)

    async def _run_event(
        self,
        listener: "Listener",
        event_name: str,
        *args: Any,
        **kwargs: Any,
    ) -> None:
        try:
            if listener.cog is not None:
                await listener.coro(listener.cog, *args, **kwargs)
            else:
                await listener.coro(*args, **kwargs)
        except asyncio.CancelledError:
            pass
        except Exception as e:
            try:
                if self.has_any_dispatch("event_error"):
                    self.dispatch("event_error", self, e)
                else:
                    _log.error(
                        f"Error in {event_name} event",
                        exc_info=e
                    )
            except asyncio.CancelledError:
                pass

    async def _prepare_bot(self) -> None:
        """
        This will run prepare_setup() before boot
        to make the user set up needed vars
        """
        client_object = await self._prepare_me()

        await self.setup_hook()
        await self._prepare_commands()

        self._ready.set()

        if self.has_any_dispatch("ready"):
            return self.dispatch("ready", client_object)

        _log.info("✅ discord.http is now ready")
        if (
            not self.disable_oauth_hint and
            self.application_id
        ):
            _log.info(
                "✨ Your bot invite URL: "
                f"{utils.oauth_url(self.application_id)}"
            )

    def _update_ids(self, data: dict) -> None:
        for g in data:
            cmd = self.commands.get(g["name"], None)
            if not cmd:
                continue
            cmd.id = int(g["id"])

    def _schedule_event(
        self,
        listener: "Listener",
        event_name: str,
        *args: Any,
        **kwargs: Any
    ) -> asyncio.Task:
        """ Schedules an event to be dispatched. """
        wrapped = self._run_event(
            listener, event_name,
            *args, **kwargs
        )

        return self.loop.create_task(
            wrapped, name=f"discord.quart: {event_name}"
        )

    async def _prepare_me(self) -> User:
        """ Gets the bot's user data, mostly used to validate token """
        try:
            self._user_object = await self.state.me()
        except KeyError:
            raise RuntimeError("Invalid token")

        _log.debug(f"/users/@me verified: {self.user} ({self.user.id})")

        return self.user

    async def _prepare_commands(self) -> None:
        """ Only used to sync commands on boot """
        if self.sync:
            await self.sync_commands()

        else:
            data = await self.state.fetch_commands(
                guild_id=self.guild_id
            )
            self._update_ids(data)

    async def sync_commands(self) -> None:
        """
        Make the bot fetch all current commands,
        to then sync them all to Discord API.
        """
        data = await self.state.update_commands(
            data=[
                v.to_dict()
                for v in self.commands.values()
                if not v.guild_ids
            ],
            guild_id=self.guild_id
        )

        guild_ids = []
        for cmd in self.commands.values():
            if cmd.guild_ids:
                guild_ids.extend([
                    int(gid) for gid in cmd.guild_ids
                ])

        guild_ids = list(set(guild_ids))

        for g in guild_ids:
            await self.state.update_commands(
                data=[
                    v.to_dict()
                    for v in self.commands.values()
                    if g in v.guild_ids
                ],
                guild_id=g
            )

        self._update_ids(data)

    @property
    def user(self) -> User:
        """
        Returns
        -------
        `User`
            The bot's user object

        Raises
        ------
        `AttributeError`
            If used before the bot is ready
        """
        if not self._user_object:
            raise AttributeError(
                "User object is not available yet "
                "(bot is not ready)"
            )

        return self._user_object

    def is_ready(self) -> bool:
        """ `bool`: Indicates if the client is ready. """
        return (
            self._ready is not None and
            self._ready.is_set()
        )

    def set_context(
        self,
        *,
        cls: Optional[Callable] = None
    ) -> None:
        """
        Get the context for a command, while allowing custom context as well

        Example of making one:

        .. code-block:: python

            from discord_http import Context

            class CustomContext(Context):
                def __init__(self, *args, **kwargs):
                    super().__init__(*args, **kwargs)

            Client.set_context(cls=CustomContext)

        Parameters
        ----------
        cls: `Optional[Callable]`
            The context to use for commands.
            Leave empty to use the default context.
        """
        if cls is None:
            cls = Context

        self._context = cls

    def set_backend(
        self,
        *,
        cls: Optional[Callable] = None
    ) -> None:
        """
        Set the backend to use for the bot

        Example of making one:

        .. code-block:: python

            from discord_http import DiscordHTTP

            class CustomBackend(DiscordHTTP):
                def __init__(self, *args, **kwargs):
                    super().__init__(*args, **kwargs)

            Client.set_backend(cls=CustomBackend)

        Parameters
        ----------
        cls: `Optional[Callable]`
            The backend to use for everything.
            Leave empty to use the default backend.
        """
        if cls is None:
            cls = DiscordHTTP

        self.backend = cls(client=self)

    async def setup_hook(self) -> None:
        """
        This will be running after the bot is ready, to get variables set up
        You can overwrite this function to do your own setup

        Example:

        .. code-block:: python

            async def setup_hook(self) -> None:
                # Making database connection available through the bot
                self.pool = SQLite.Database()
        """
        pass

    def start(
        self,
        *,
        host: str = "127.0.0.1",
        port: int = 8080
    ) -> None:
        """
        Boot up the bot and start the HTTP server

        Parameters
        ----------
        host: Optional[:class:`str`]
            Host to use, if not provided, it will use `127.0.0.1`
        port: Optional[:class:`int`]
            Port to use, if not provided, it will use `8080`
        """
        if not self.application_id or not self.public_key:
            raise RuntimeError(
                "Application ID or/and Public Key is not provided, "
                "please provide them when initializing the client server."
            )

        self.backend.before_serving(self._prepare_bot)
        self.backend.start(host=host, port=port)

    async def wait_until_ready(self) -> None:
        """ Waits until the client is ready using `asyncio.Event.wait()`. """
        if self._ready is None:
            raise RuntimeError(
                "Client has not been initialized yet, "
                "please use Client.start() to initialize the client."
            )

        await self._ready.wait()

    def dispatch(
        self,
        event_name: str,
        /,
        *args: Any,
        **kwargs: Any
    ):
        """
        Dispatches an event to all listeners of that event.

        Parameters
        ----------
        event_name: `str`
            The name of the event to dispatch.
        *args: `Any`
            The arguments to pass to the event.
        **kwargs: `Any`
            The keyword arguments to pass to the event.
        """
        for listener in self.listeners:
            if listener.name != f"on_{event_name}":
                continue

            self._schedule_event(
                listener,
                event_name,
                *args, **kwargs
            )

    def has_any_dispatch(
        self,
        event_name: str
    ) -> bool:
        """
        Checks if the bot has any listeners for the event.

        Parameters
        ----------
        event_name: `str`
            The name of the event to check for.

        Returns
        -------
        `bool`
            Whether the bot has any listeners for the event.
        """
        event = next((
            x for x in self.listeners
            if x.name == f"on_{event_name}"
        ), None)

        return event is not None

    async def load_extension(
        self,
        package: str
    ) -> None:
        """
        Loads an extension.

        Parameters
        ----------
        package: `str`
            The package to load the extension from.
        """
        if package in self._cogs:
            raise RuntimeError(f"Cog {package} is already loaded")

        lib = importlib.import_module(package)
        setup = getattr(lib, "setup", None)

        if not setup:
            raise RuntimeError(f"Cog {package} does not have a setup function")

        await setup(self)

    async def unload_extension(
        self,
        package: str
    ) -> None:
        """
        Unloads an extension.

        Parameters
        ----------
        package: `str`
            The package to unload the extension from.
        """
        if package not in self._cogs:
            raise RuntimeError(f"Cog {package} is not loaded")

        for cog in self._cogs[package]:
            await self.remove_cog(cog)

        del self._cogs[package]

    async def add_cog(self, cog: "Cog") -> None:
        """
        Adds a cog to the bot.

        Parameters
        ----------
        cog: `Cog`
            The cog to add to the bot.
        """
        await cog._inject(self)

    async def remove_cog(self, cog: "Cog") -> None:
        """
        Removes a cog from the bot.

        Parameters
        ----------
        cog: `Cog`
            The cog to remove from the bot.
        """
        await cog._eject(self)

    def command(
        self,
        name: Optional[str] = None,
        *,
        description: Optional[str] = None,
        guild_ids: Optional[list[Union[Snowflake, int]]] = None,
        guild_install: bool = True,
        user_install: bool = False,
    ):
        """
        Used to register a command

        Parameters
        ----------
        name: `Optional[str]`
            Name of the command, if not provided, it will use the function name
        description: `Optional[str]`
            Description of the command, if not provided, it will use the function docstring
        guild_ids: `Optional[list[Union[Snowflake, int]]]`
            List of guild IDs to register the command in
        user_install: `bool`
            Whether the command can be installed by users or not
        guild_install: `bool`
            Whether the command can be installed by guilds or not
        """
        def decorator(func):
            command = Command(
                func,
                name=name or func.__name__,
                description=description,
                guild_ids=guild_ids,
                guild_install=guild_install,
                user_install=user_install
            )
            self.add_command(command)
            return command

        return decorator

    def user_command(
        self,
        name: Optional[str] = None,
        *,
        guild_ids: Optional[list[Union[Snowflake, int]]] = None,
        guild_install: bool = True,
        user_install: bool = False,
    ):
        """
        Used to register a user command

        Example usage

        .. code-block:: python

            @user_command()
            async def content(ctx, user: Union[Member, User]):
                await ctx.send(f"Target: {user.name}")

        Parameters
        ----------
        name: `Optional[str]`
            Name of the command, if not provided, it will use the function name
        guild_ids: `Optional[list[Union[Snowflake, int]]]`
            List of guild IDs to register the command in
        user_install: `bool`
            Whether the command can be installed by users or not
        guild_install: `bool`
            Whether the command can be installed by guilds or not
        """
        def decorator(func):
            command = Command(
                func,
                name=name or func.__name__,
                type=ApplicationCommandType.user,
                guild_ids=guild_ids,
                guild_install=guild_install,
                user_install=user_install
            )
            self.add_command(command)
            return command

        return decorator

    def message_command(
        self,
        name: Optional[str] = None,
        *,
        guild_ids: Optional[list[Union[Snowflake, int]]] = None,
        guild_install: bool = True,
        user_install: bool = False,
    ):
        """
        Used to register a message command

        Example usage

        .. code-block:: python

            @message_command()
            async def content(ctx, msg: Message):
                await ctx.send(f"Content: {msg.content}")

        Parameters
        ----------
        name: `Optional[str]`
            Name of the command, if not provided, it will use the function name
        guild_ids: `Optional[list[Union[Snowflake, int]]]`
            List of guild IDs to register the command in
        user_install: `bool`
            Whether the command can be installed by users or not
        guild_install: `bool`
            Whether the command can be installed by guilds or not
        """
        def decorator(func):
            command = Command(
                func,
                name=name or func.__name__,
                type=ApplicationCommandType.message,
                guild_ids=guild_ids,
                guild_install=guild_install,
                user_install=user_install
            )
            self.add_command(command)
            return command

        return decorator

    def group(
        self,
        name: Optional[str] = None,
        *,
        description: Optional[str] = None
    ):
        """
        Used to register a sub-command group

        Parameters
        ----------
        name: `Optional[str]`
            Name of the group, if not provided, it will use the function name
        description: `Optional[str]`
            Description of the group, if not provided, it will use the function docstring
        """
        def decorator(func):
            subgroup = SubGroup(
                name=name or func.__name__,
                description=description
            )
            self.add_command(subgroup)
            return subgroup

        return decorator

    def add_group(self, name: str) -> SubGroup:
        """
        Used to add a sub-command group

        Parameters
        ----------
        name: `str`
            Name of the group

        Returns
        -------
        `SubGroup`
            The created group
        """
        subgroup = SubGroup(name=name)
        self.add_command(subgroup)
        return subgroup

    def interaction(
        self,
        custom_id: str,
        *,
        regex: bool = False
    ):
        """
        Used to register an interaction

        This does support regex, so you can use `r"regex here"` as the custom_id

        Parameters
        ----------
        custom_id: `str`
            Custom ID of the interaction
        regex: `bool`
            Whether the custom_id is a regex or not
        """
        def decorator(func):
            command = self.add_interaction(Interaction(
                func,
                custom_id=custom_id,
                regex=regex
            ))
            return command

        return decorator

    def listener(
        self,
        name: Optional[str] = None
    ):
        """
        Used to register a listener

        Parameters
        ----------
        name: `Optional[str]`
            Name of the listener, if not provided, it will use the function name

        Raises
        ------
        `TypeError`
            - If the listener name is not a string
            - If the listener is not a coroutine function
        """
        if not isinstance(name, (str, type(None))):
            raise TypeError(f"Listener name must be a string, not {type(name)}")

        def decorator(func):
            actual = func
            if isinstance(actual, staticmethod):
                actual = actual.__func__
            if not inspect.iscoroutinefunction(actual):
                raise TypeError("Listeners has to be coroutine functions")
            self.add_listener(Listener(
                name or actual.__name__,
                func
            ))

        return decorator

    def get_partial_channel(
        self,
        channel_id: int,
        *,
        guild_id: Optional[int] = None
    ) -> PartialChannel:
        """
        Creates a partial channel object.

        Parameters
        ----------
        channel_id: `int`
            Channel ID to create the partial channel object with.
        guild_id: `Optional[int]`
            Guild ID to create the partial channel object with.

        Returns
        -------
        `PartialChannel`
            The partial channel object.
        """
        return PartialChannel(
            state=self.state,
            id=channel_id,
            guild_id=guild_id
        )

    async def fetch_channel(
        self,
        channel_id: int,
        *,
        guild_id: Optional[int] = None
    ) -> BaseChannel:
        """
        Fetches a channel object.

        Parameters
        ----------
        channel_id: `int`
            Channel ID to fetch the channel object with.
        guild_id: `Optional[int]`
            Guild ID to fetch the channel object with.

        Returns
        -------
        `BaseChannel`
            The channel object.
        """
        c = self.get_partial_channel(channel_id, guild_id=guild_id)
        return await c.fetch()

    def get_partial_invite(
        self,
        invite_code: str
    ) -> PartialInvite:
        """
        Creates a partial invite object.

        Parameters
        ----------
        invite_code: `str`
            Invite code to create the partial invite object with.

        Returns
        -------
        `PartialInvite`
            The partial invite object.
        """
        return PartialInvite(
            state=self.state,
            code=invite_code
        )

    def get_partial_emoji(
        self,
        emoji_id: int,
        *,
        guild_id: Optional[int] = None
    ) -> PartialEmoji:
        """
        Creates a partial emoji object.

        Parameters
        ----------
        emoji_id: `int`
            Emoji ID to create the partial emoji object with.
        guild_id: `Optional[int]`
            Guild ID of where the emoji comes from.
            If None, it will get the emoji from the application.

        Returns
        -------
        `PartialEmoji`
            The partial emoji object.
        """
        return PartialEmoji(
            state=self.state,
            id=emoji_id,
            guild_id=guild_id
        )

    async def fetch_emoji(
        self,
        emoji_id: int,
        *,
        guild_id: Optional[int] = None
    ) -> Emoji:
        """
        Fetches an emoji object.

        Parameters
        ----------
        emoji_id: `int`
            The ID of the emoji in question
        guild_id: `Optional[int]`
            Guild ID of the emoji.
            If None, it will fetch the emoji from the application

        Returns
        -------
        `Emoji`
            The emoji object
        """
        e = self.get_partial_emoji(
            emoji_id,
            guild_id=guild_id
        )

        return await e.fetch()

    def get_partial_sticker(
        self,
        sticker_id: int,
        *,
        guild_id: Optional[int] = None
    ) -> PartialSticker:
        """
        Creates a partial sticker object.

        Parameters
        ----------
        sticker_id: `int`
            Sticker ID to create the partial sticker object with.
        guild_id: `Optional[int]`
            Guild ID to create the partial sticker object with.

        Returns
        -------
        `PartialSticker`
            The partial sticker object.
        """
        return PartialSticker(
            state=self.state,
            id=sticker_id,
            guild_id=guild_id
        )

    async def fetch_sticker(
        self,
        sticker_id: int,
        *,
        guild_id: Optional[int] = None
    ) -> Sticker:
        """
        Fetches a sticker object.

        Parameters
        ----------
        sticker_id: `int`
            Sticker ID to fetch the sticker object with.

        Returns
        -------
        `Sticker`
            The sticker object.
        """
        sticker = self.get_partial_sticker(
            sticker_id,
            guild_id=guild_id
        )

        return await sticker.fetch()

    async def fetch_invite(
        self,
        invite_code: str
    ) -> Invite:
        """
        Fetches an invite object.

        Parameters
        ----------
        invite_code: `str`
            Invite code to fetch the invite object with.

        Returns
        -------
        `Invite`
            The invite object.
        """
        invite = self.get_partial_invite(invite_code)
        return await invite.fetch()

    def get_partial_message(
        self,
        message_id: int,
        channel_id: int
    ) -> PartialMessage:
        """
        Creates a partial message object.

        Parameters
        ----------
        message_id: `int`
            Message ID to create the partial message object with.
        channel_id: `int`
            Channel ID to create the partial message object with.

        Returns
        -------
        `PartialMessage`
            The partial message object.
        """
        return PartialMessage(
            state=self.state,
            id=message_id,
            channel_id=channel_id,
        )

    async def fetch_message(
        self,
        message_id: int,
        channel_id: int
    ) -> Message:
        """
        Fetches a message object.

        Parameters
        ----------
        message_id: `int`
            Message ID to fetch the message object with.
        channel_id: `int`
            Channel ID to fetch the message object with.

        Returns
        -------
        `Message`
            The message object
        """
        msg = self.get_partial_message(message_id, channel_id)
        return await msg.fetch()

    def get_partial_webhook(
        self,
        webhook_id: int,
        *,
        webhook_token: Optional[str] = None
    ) -> PartialWebhook:
        """
        Creates a partial webhook object.

        Parameters
        ----------
        webhook_id: `int`
            Webhook ID to create the partial webhook object with.
        webhook_token: `Optional[str]`
            Webhook token to create the partial webhook object with.

        Returns
        -------
        `PartialWebhook`
            The partial webhook object.
        """
        return PartialWebhook(
            state=self.state,
            id=webhook_id,
            token=webhook_token
        )

    async def fetch_webhook(
        self,
        webhook_id: int,
        *,
        webhook_token: Optional[str] = None
    ) -> Webhook:
        """
        Fetches a webhook object.

        Parameters
        ----------
        webhook_id: `int`
            Webhook ID to fetch the webhook object with.
        webhook_token: `Optional[str]`
            Webhook token to fetch the webhook object with.

        Returns
        -------
        `Webhook`
            The webhook object.
        """
        webhook = self.get_partial_webhook(
            webhook_id,
            webhook_token=webhook_token
        )

        return await webhook.fetch()

    def get_partial_user(
        self,
        user_id: int
    ) -> PartialUser:
        """
        Creates a partial user object.

        Parameters
        ----------
        user_id: `int`
            User ID to create the partial user object with.

        Returns
        -------
        `PartialUser`
            The partial user object.
        """
        return PartialUser(
            state=self.state,
            id=user_id
        )

    async def fetch_user(
        self,
        user_id: int
    ) -> User:
        """
        Fetches a user object.

        Parameters
        ----------
        user_id: `int`
            User ID to fetch the user object with.

        Returns
        -------
        `User`
            The user object.
        """
        user = self.get_partial_user(user_id)
        return await user.fetch()

    def get_partial_member(
        self,
        user_id: int,
        guild_id: int
    ) -> PartialMember:
        """
        Creates a partial member object.

        Parameters
        ----------
        user_id: `int`
            User ID to create the partial member object with.
        guild_id: `int`
            Guild ID that the member is in.

        Returns
        -------
        `PartialMember`
            The partial member object.
        """
        return PartialMember(
            state=self.state,
            id=user_id,
            guild_id=guild_id,
        )

    async def fetch_member(
        self,
        user_id: int,
        guild_id: int
    ) -> Member:
        """
        Fetches a member object.

        Parameters
        ----------
        guild_id: `int`
            Guild ID that the member is in.
        user_id: `int`
            User ID to fetch the member object with.

        Returns
        -------
        `Member`
            The member object.
        """
        member = self.get_partial_member(user_id, guild_id)
        return await member.fetch()

    async def fetch_application_emojis(self) -> list[Emoji]:
        """ `list[Emoji]`: Fetches all emojis available to the application. """
        r = await self.state.query(
            "GET",
            f"/applications/{self.application_id}/emojis"
        )

        return [
            Emoji(state=self.state, data=g)
            for g in r.response
        ]

    async def create_application_emoji(
        self,
        name: str,
        *,
        image: Union[File, bytes]
    ) -> Emoji:
        """
        Creates an emoji for the application.

        Parameters
        ----------
        name: `str`
            Name of emoji
        image: `Union[File, bytes]`
            The image data to use for the emoji.

        Returns
        -------
        `Emoji`
            The created emoji object.
        """
        r = await self.state.query(
            "POST",
            f"/applications/{self.application_id}/emojis",
            json={
                "name": name,
                "image": utils.bytes_to_base64(image)
            }
        )

        return Emoji(
            state=self.state,
            data=r.response
        )

    def get_partial_sku(
        self,
        sku_id: int
    ) -> PartialSKU:
        """
        Creates a partial SKU object.

        Returns
        -------
        `PartialSKU`
            The partial SKU object.
        """
        return PartialSKU(
            state=self.state,
            id=sku_id
        )

    async def fetch_skus(self) -> list[SKU]:
        """ `list[SKU]`: Fetches all SKUs available to the bot. """
        r = await self.state.query(
            "GET",
            f"/applications/{self.application_id}/skus"
        )

        return [
            SKU(state=self.state, data=g)
            for g in r.response
        ]

    def get_partial_entitlement(
        self,
        entitlement_id: int
    ) -> PartialEntitlements:
        """
        Creates a partial entitlement object.

        Parameters
        ----------
        entitlement_id: `int`
            Entitlement ID to create the partial entitlement object with.

        Returns
        -------
        `PartialEntitlements`
            The partial entitlement object.
        """
        return PartialEntitlements(
            state=self.state,
            id=entitlement_id
        )

    async def fetch_entitlement(
        self,
        entitlement_id: int
    ) -> Entitlements:
        """
        Fetches an entitlement object.

        Parameters
        ----------
        entitlement_id: `int`
            Entitlement ID to fetch the entitlement object with.

        Returns
        -------
        `Entitlements`
            The entitlement object.
        """
        ent = self.get_partial_entitlement(entitlement_id)
        return await ent.fetch()

    async def fetch_entitlement_list(
        self,
        *,
        user_id: Optional[int] = None,
        sku_ids: Optional[list[int]] = None,
        before: Optional[int] = None,
        after: Optional[int] = None,
        limit: Optional[int] = 100,
        guild_id: Optional[int] = None,
        exclude_ended: bool = False
    ) -> AsyncIterator[Entitlements]:
        """
        Fetches a list of entitlement objects with optional filters.

        Parameters
        ----------
        user_id: `Optional[int]`
            Show entitlements for a specific user ID.
        sku_ids: `Optional[list[int]]`
            Show entitlements for a specific SKU ID.
        before: `Optional[int]`
            Only show entitlements before this entitlement ID.
        after: `Optional[int]`
            Only show entitlements after this entitlement ID.
        limit: `int`
            Limit the amount of entitlements to fetch.
            Use `None` to fetch all entitlements.
        guild_id: `Optional[int]`
            Show entitlements for a specific guild ID.
        exclude_ended: `bool`
            Whether to exclude ended entitlements or not.

        Returns
        -------
        `AsyncIterator[Entitlements]`
            The entitlement objects.
        """
        params: dict[str, Any] = {
            "exclude_ended": "true" if exclude_ended else "false"
        }

        if user_id is not None:
            params["user_id"] = int(user_id)
        if sku_ids is not None:
            params["sku_ids"] = ",".join([str(int(g)) for g in sku_ids])
        if guild_id is not None:
            params["guild_id"] = int(guild_id)

        def _resolve_id(entry) -> int:
            match entry:
                case x if isinstance(x, Snowflake):
                    return int(x)

                case x if isinstance(x, int):
                    return x

                case x if isinstance(x, str):
                    if not x.isdigit():
                        raise TypeError("Got a string that was not a Snowflake ID for before/after")
                    return int(x)

                case x if isinstance(x, datetime):
                    return utils.time_snowflake(x)

                case _:
                    raise TypeError("Got an unknown type for before/after")

        async def _get_history(limit: int, **kwargs):
            params["limit"] = min(limit, 100)
            for key, value in kwargs.items():
                if value is None:
                    continue
                params[key] = _resolve_id(value)

            return await self.state.query(
                "GET",
                f"/applications/{self.application_id}/entitlements",
                params=params
            )

        async def _after_http(
            http_limit: int,
            after_id: Optional[int],
            limit: Optional[int]
        ):
            r = await _get_history(limit=http_limit, after=after_id)

            if r.response:
                if limit is not None:
                    limit -= len(r.response)
                after_id = int(r.response[0]["id"])

            return r.response, after_id, limit

        async def _before_http(
            http_limit: int,
            before_id: Optional[int],
            limit: Optional[int]
        ):
            r = await _get_history(limit=http_limit, before=before_id)

            if r.response:
                if limit is not None:
                    limit -= len(r.response)
                before_id = int(r.response[-1]["id"])

            return r.response, before_id, limit

        if after:
            strategy, state = _after_http, _resolve_id(after)
        elif before:
            strategy, state = _before_http, _resolve_id(before)
        else:
            strategy, state = _before_http, None

        while True:
            http_limit: int = 100 if limit is None else min(limit, 100)
            if http_limit <= 0:
                break

            strategy: Callable
            messages, state, limit = await strategy(http_limit, state, limit)

            i = 0
            for i, ent in enumerate(messages, start=1):
                yield Entitlements(state=self.state, data=ent)

            if i < 100:
                break

    def get_partial_scheduled_event(
        self,
        id: int,
        guild_id: int
    ) -> PartialScheduledEvent:
        """
        Creates a partial scheduled event object.

        Parameters
        ----------
        id: `int`
            The ID of the scheduled event.
        guild_id: `int`
            The guild ID of the scheduled event.

        Returns
        -------
        `PartialScheduledEvent`
            The partial scheduled event object.
        """
        return PartialScheduledEvent(
            state=self.state,
            id=id,
            guild_id=guild_id
        )

    async def fetch_scheduled_event(
        self,
        id: int,
        guild_id: int
    ) -> ScheduledEvent:
        """
        Fetches a scheduled event object.

        Parameters
        ----------
        id: `int`
            The ID of the scheduled event.
        guild_id: `int`
            The guild ID of the scheduled event.

        Returns
        -------
        `ScheduledEvent`
            The scheduled event object.
        """
        event = self.get_partial_scheduled_event(
            id, guild_id
        )
        return await event.fetch()

    def get_partial_guild(
        self,
        guild_id: int
    ) -> PartialGuild:
        """
        Creates a partial guild object.

        Parameters
        ----------
        guild_id: `int`
            Guild ID to create the partial guild object with.

        Returns
        -------
        `PartialGuild`
            The partial guild object.
        """
        return PartialGuild(
            state=self.state,
            id=guild_id
        )

    async def fetch_guild(
        self,
        guild_id: int
    ) -> Guild:
        """
        Fetches a guild object.

        Parameters
        ----------
        guild_id: `int`
            Guild ID to fetch the guild object with.

        Returns
        -------
        `Guild`
            The guild object.
        """
        guild = self.get_partial_guild(guild_id)
        return await guild.fetch()

    def get_partial_role(
        self,
        role_id: int,
        guild_id: int
    ) -> PartialRole:
        """
        Creates a partial role object.

        Parameters
        ----------
        role_id: `int`
            Role ID to create the partial role object with.
        guild_id: `int`
            Guild ID that the role is in.

        Returns
        -------
        `PartialRole`
            The partial role object.
        """
        return PartialRole(
            state=self.state,
            id=role_id,
            guild_id=guild_id
        )

    def find_interaction(
        self,
        custom_id: str
    ) -> Optional["Interaction"]:
        """
        Finds an interaction by its Custom ID.

        Parameters
        ----------
        custom_id: `str`
            The Custom ID to find the interaction with.
            Will automatically convert to regex matching
            if some interaction Custom IDs are regex.

        Returns
        -------
        `Optional[Interaction]`
            The interaction that was found if any.
        """
        inter = self.interactions.get(custom_id, None)
        if inter:
            return inter

        for _, inter in self.interactions_regex.items():
            if inter.match(custom_id):
                return inter

        return None

    def add_listener(
        self,
        func: "Listener"
    ) -> "Listener":
        """
        Adds a listener to the bot.

        Parameters
        ----------
        func: `Listener`
            The listener to add to the bot.
        """
        self.listeners.append(func)
        return func

    def remove_listener(
        self,
        func: "Listener"
    ) -> None:
        """
        Removes a listener from the bot.

        Parameters
        ----------
        func: `Listener`
            The listener to remove from the bot.
        """
        self.listeners.remove(func)

    def add_command(
        self,
        func: "Command"
    ) -> "Command":
        """
        Adds a command to the bot.

        Parameters
        ----------
        command: `Command`
            The command to add to the bot.
        """
        self.commands[func.name] = func
        return func

    def remove_command(
        self,
        func: "Command"
    ) -> None:
        """
        Removes a command from the bot.

        Parameters
        ----------
        command: `Command`
            The command to remove from the bot.
        """
        self.commands.pop(func.name, None)

    def add_interaction(
        self,
        func: "Interaction"
    ) -> "Interaction":
        """
        Adds an interaction to the bot.

        Parameters
        ----------
        interaction: `Interaction`
            The interaction to add to the bot.
        """
        if func.regex:
            self.interactions_regex[func.custom_id] = func
        else:
            self.interactions[func.custom_id] = func

        return func

    def remove_interaction(
        self,
        func: "Interaction"
    ) -> None:
        """
        Removes an interaction from the bot.

        Parameters
        ----------
        interaction: `Interaction`
            The interaction to remove from the bot.
        """
        if func.regex:
            self.interactions_regex.pop(func.custom_id, None)
        else:
            self.interactions.pop(func.custom_id, None)
