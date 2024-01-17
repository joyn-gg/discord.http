import asyncio
import importlib
import inspect
import logging
import re

from typing import Dict, Optional, Any, Callable, Union

from . import utils
from .backend import DiscordHTTP
from .channel import PartialChannel, BaseChannel
from .commands import Command, Interaction, Listener, Cog, SubGroup
from .context import Context
from .enums import ApplicationCommandType
from .guild import PartialGuild, Guild
from .http import DiscordAPI
from .invite import PartialInvite, Invite
from .member import PartialMember, Member
from .mentions import AllowedMentions
from .message import PartialMessage, Message
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
        self.user: Optional[User] = None
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
        self.interactions: Dict[str, Interaction] = {}
        self.listeners: list[Listener] = []

        self._ready: Optional[asyncio.Event] = asyncio.Event()
        self.backend: DiscordHTTP = DiscordHTTP(client=self)
        self._context: Callable = Context

        self._view_storage: dict[int, InteractionStorage] = {}
        self._default_allowed_mentions = allowed_mentions

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

    def is_ready(self) -> bool:
        """ `bool`: Indicates if the client is ready. """
        return (
            self._ready is not None and
            self._ready.is_set()
        )

    def set_context(
        self,
        *,
        cls: Callable
    ) -> None:
        """
        Get the context for a command, while allowing custom context as well

        Example of making one:

        .. code-block:: python

            from discord_http import commands

            class CustomContext(commands.Context):
                def __init__(self, *args, **kwargs):
                    super().__init__(*args, **kwargs)

            DiscordHTTP.set_context(cls=CustomContext)
        """
        self._context = cls

    async def _prepare_bot(self) -> None:
        """ This will run prepare_setup() before boot to make the user set up needed vars """
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
        if self._ready is not None:
            await self._ready.wait()
        else:
            raise RuntimeError(
                "Client has not been initialized yet, "
                "please use Client.start() to initialize the client."
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
    ):
        """ Schedules an event to be dispatched. """
        wrapped = self._run_event(
            listener, event_name,
            *args, **kwargs
        )

        return self.loop.create_task(
            wrapped, name=f"discord.quart: {event_name}"
        )

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
        lib = importlib.import_module(package)
        setup = getattr(lib, "setup", None)
        if not setup:
            return None
        await setup(self)

    async def add_cog(self, cog: "Cog"):
        """
        Adds a cog to the bot.

        Parameters
        ----------
        cog: `Cog`
            The cog to add to the bot.
        """
        await cog._inject(self)

    async def _prepare_me(self) -> User:
        """ Gets the bot's user data, mostly used to validate token """
        try:
            self.user = await self.state.me()
        except KeyError:
            raise RuntimeError("Invalid token")

        _log.debug(f"/users/@me verified: {self.user} ({self.user.id})")

        return self.user

    async def _prepare_commands(self) -> None:
        if self.sync:
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
                    guild_ids.extend([int(gid) for gid in cmd.guild_ids])
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
        else:
            data = await self.state.fetch_commands(guild_id=self.guild_id)
            self._update_ids(data)

    def command(
        self,
        name: Optional[str] = None,
        description: Optional[str] = None,
        guild_ids: Optional[list[Union[utils.Snowflake, int]]] = None
    ):
        """
        Used to register a command

        Parameters
        ----------
        name: `Optional[str]`
            Name of the command, if not provided, it will use the function name
        description: `Optional[str]`
            Description of the command, if not provided, it will use the function docstring
        guild_ids: `Optional[list[Union[utils.Snowflake, int]]]`
            List of guild IDs to register the command in
        """
        def decorator(func):
            command = Command(
                func,
                name=name or func.__name__,
                description=description,
                guild_ids=guild_ids,
            )
            self.add_command(command)
            return command
        return decorator

    def user_command(
        self,
        name: Optional[str] = None,
        *,
        guild_ids: Optional[list[Union[utils.Snowflake, int]]] = None,
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
        guild_ids: `Optional[list[Union[utils.Snowflake, int]]]`
            List of guild IDs to register the command in
        """
        def decorator(func):
            command = Command(
                func,
                name=name or func.__name__,
                type=ApplicationCommandType.user,
                guild_ids=guild_ids,
            )
            self.add_command(command)
            return command
        return decorator

    def message_command(
        self,
        name: Optional[str] = None,
        *,
        guild_ids: Optional[list[Union[utils.Snowflake, int]]] = None,
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
        guild_ids: `Optional[list[Union[utils.Snowflake, int]]]`
            List of guild IDs to register the command in
        """
        def decorator(func):
            command = Command(
                func,
                name=name or func.__name__,
                type=ApplicationCommandType.message,
                guild_ids=guild_ids,
            )
            self.add_command(command)
            return command
        return decorator

    def group(
        self,
        name: Optional[str] = None,
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
                func, custom_id=custom_id, regex=regex
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
        if name is not None and not isinstance(name, str):
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
            channel_id=channel_id,
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
        channel_id: int,
        message_id: int
    ) -> PartialMessage:
        """
        Creates a partial message object.

        Parameters
        ----------
        channel_id: `int`
            Channel ID to create the partial message object with.
        message_id: `int`
            Message ID to create the partial message object with.

        Returns
        -------
        `PartialMessage`
            The partial message object.
        """
        return PartialMessage(
            state=self.state,
            channel_id=channel_id,
            id=message_id
        )

    async def fetch_message(
        self,
        channel_id: int,
        message_id: int
    ) -> Message:
        """
        Fetches a message object.

        Parameters
        ----------
        channel_id: `int`
            Channel ID to fetch the message object with.
        message_id: `int`
            Message ID to fetch the message object with.

        Returns
        -------
        `Message`
            The message object
        """
        msg = self.get_partial_message(channel_id, message_id)
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
            webhook_id=webhook_id,
            webhook_token=webhook_token
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
        guild_id: int,
        user_id: int
    ) -> PartialMember:
        """
        Creates a partial member object.

        Parameters
        ----------
        guild_id: `int`
            Guild ID that the member is in.
        user_id: `int`
            User ID to create the partial member object with.

        Returns
        -------
        `PartialMember`
            The partial member object.
        """
        return PartialMember(
            state=self.state,
            guild_id=guild_id,
            user_id=user_id
        )

    async def fetch_member(
        self,
        guild_id: int,
        user_id: int
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
        member = self.get_partial_member(guild_id, user_id)
        return await member.fetch()

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
            guild_id=guild_id
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
        guild_id: int,
        role_id: int
    ) -> PartialRole:
        """
        Creates a partial role object.

        Parameters
        ----------
        guild_id: `int`
            Guild ID that the role is in.
        role_id: `int`
            Role ID to create the partial role object with.

        Returns
        -------
        `PartialRole`
            The partial role object.
        """
        return PartialRole(
            state=self.state,
            guild_id=guild_id,
            role_id=role_id
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
            Will automatically convert to regex if some interaction Custom IDs are regex.

        Returns
        -------
        `Optional[Interaction]`
            The interaction that was found if any.
        """
        for name, inter in self.interactions.items():
            if inter.is_regex and re.match(name, custom_id):
                return self.interactions[name]
            elif name == custom_id:
                return self.interactions[name]
        return None

    def add_listener(self, func: "Listener"):
        """
        Adds a listener to the bot.

        Parameters
        ----------
        func: `Listener`
            The listener to add to the bot.
        """
        self.listeners.append(func)

    def add_command(self, command: "Command"):
        """
        Adds a command to the bot.

        Parameters
        ----------
        command: `Command`
            The command to add to the bot.

        Returns
        -------
        `Command`
            The command that was added.
        """
        self.commands[command.name] = command
        return command

    def add_interaction(self, interaction: "Interaction"):
        """
        Adds an interaction to the bot.

        Parameters
        ----------
        interaction: `Interaction`
            The interaction to add to the bot.

        Returns
        -------
        `Interaction`
            The interaction that was added.
        """
        self.interactions[interaction.custom_id] = interaction
        return interaction
