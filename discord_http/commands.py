import inspect
import itertools
import logging

from typing import get_args as get_type_args
from typing import (
    Callable, Dict, TYPE_CHECKING, Union,
    Generic, TypeVar, Optional, Coroutine, Literal
)

from . import utils
from .channel import (
    TextChannel, VoiceChannel,
    CategoryChannel, NewsThread,
    PublicThread, PrivateThread, StageChannel,
    DirectoryChannel, ForumChannel, StoreChannel,
    NewsChannel, BaseChannel
)
from .enums import ApplicationCommandType, CommandOptionType, ChannelType
from .errors import UserMissingPermissions, BotMissingPermissions, CheckFailed
from .flag import Permissions
from .member import Member
from .message import Attachment
from .object import PartialBase
from .response import BaseResponse, AutocompleteResponse
from .role import Role
from .user import User

if TYPE_CHECKING:
    from .context import Context
    from .client import Client

ChoiceT = TypeVar("ChoiceT", str, int, float, Union[str, int, float])
LocaleTypes = Literal[
    "id", "da", "de", "en-GB", "en-US", "es-ES", "fr",
    "hr", "it", "lt", "hu", "nl", "no", "pl", "pt-BR",
    "ro", "fi", "sv-SE", "vi", "tr", "cs", "el", "bg",
    "ru", "uk", "hi", "th", "zh-CN", "ja", "zh-TW", "ko"
]
ValidLocalesList = get_type_args(LocaleTypes)

channel_types = {
    BaseChannel: [g for g in ChannelType],
    TextChannel: [ChannelType.guild_text],
    VoiceChannel: [ChannelType.guild_voice],
    CategoryChannel: [ChannelType.guild_category],
    NewsChannel: [ChannelType.guild_news],
    StoreChannel: [ChannelType.guild_store],
    NewsThread: [ChannelType.guild_news_thread],
    PublicThread: [ChannelType.guild_public_thread],
    PrivateThread: [ChannelType.guild_private_thread],
    StageChannel: [ChannelType.guild_stage_voice],
    DirectoryChannel: [ChannelType.guild_directory],
    ForumChannel: [
        ChannelType.guild_news_thread,
        ChannelType.guild_public_thread,
        ChannelType.guild_private_thread
    ],
}

_log = logging.getLogger(__name__)

__all__ = (
    "Choice",
    "Cog",
    "Command",
    "Interaction",
    "Listener",
    "PartialCommand",
    "Range",
    "SubGroup",
)


class Cog:
    _cog_commands = dict()
    _cog_interactions = dict()
    _cog_listeners = dict()

    def __new__(cls, *args, **kwargs):
        commands = {}
        listeners = {}
        interactions = {}

        for base in reversed(cls.__mro__):
            for elem, value in base.__dict__.items():
                match value:
                    case x if isinstance(x, SubCommand):
                        continue  # Do not overwrite commands just in case
                    case x if isinstance(x, Command):
                        commands[value.name] = value
                    case x if isinstance(x, SubGroup):
                        commands[value.name] = value
                    case x if isinstance(x, Interaction):
                        interactions[value.custom_id] = value
                    case x if isinstance(x, Listener):
                        listeners[value.name] = value

        cls._cog_commands: dict[str, "Command"] = commands
        cls._cog_interactions: dict[str, "Interaction"] = interactions
        cls._cog_listeners: dict[str, "Listener"] = listeners

        return super().__new__(cls)

    async def _inject(self, bot: "Client"):
        await self.cog_load()

        for cmd in self._cog_commands.values():
            cmd.cog = self
            bot.add_command(cmd)

            if isinstance(cmd, SubGroup):
                for subcmd in cmd.subcommands.values():
                    subcmd.cog = self

        for listener in self._cog_listeners.values():
            listener.cog = self
            bot.add_listener(listener)

        for interaction in self._cog_interactions.values():
            interaction.cog = self
            bot.add_interaction(interaction)

    async def cog_load(self) -> None:
        pass


class PartialCommand(PartialBase):
    def __init__(self, data: dict):
        super().__init__(id=int(data["id"]))
        self.name: str = data["name"]
        self.guild_id: Optional[int] = utils.get_int(data, "guild_id")

    def __str__(self) -> str:
        return self.name

    def __repr__(self):
        return f"<PartialCommand id={self.id} name={self.name}>"


class LocaleContainer:
    def __init__(
        self,
        key: str,
        name: str,
        description: Optional[str] = None
    ):
        self.key = key
        self.name = name
        self.description = description or "..."


class Command:
    def __init__(
        self,
        command: Callable,
        name: str,
        description: Optional[str] = None,
        guild_ids: Optional[list[Union[utils.Snowflake, int]]] = None,
        type: ApplicationCommandType = ApplicationCommandType.chat_input,
    ):
        self.id: Optional[int] = None
        self.command = command
        self.cog: Optional["Cog"] = None
        self.type: int = int(type)
        self.name = name
        self.description = description
        self.options = []
        self.default_member_permissions = None

        self.name_localizations: Dict[LocaleTypes, str] = {}
        self.description_localizations: Dict[LocaleTypes, str] = {}

        self.list_autocompletes: Dict[str, Callable] = {}
        self.guild_ids: list[Union[utils.Snowflake, int]] = guild_ids or []
        self.__list_choices: list[str] = []

        if self.type == ApplicationCommandType.chat_input:
            if self.description is None:
                self.description = command.__doc__ or "No description provided."
            if self.name != self.name.lower():
                raise ValueError("Command names must be lowercase.")
            if not 1 <= len(self.description) <= 100:
                raise ValueError("Command descriptions must be between 1 and 100 characters.")
        else:
            self.description = None

        if self.type is ApplicationCommandType.chat_input.value and not self.options:
            sig = inspect.signature(self.command)
            self.options = []

            slicer = 1
            if sig.parameters.get("self"):
                slicer = 2

            for parameter in itertools.islice(sig.parameters.values(), slicer, None):
                origin = getattr(
                    parameter.annotation, "__origin__",
                    parameter.annotation
                )

                option = {}

                if (
                    origin in [Union] and
                    len(parameter.annotation.__args__) == 2
                ):
                    # Parsing Optional/Union types
                    origin = parameter.annotation.__args__[0]

                if origin in [Member, User]:
                    ptype = CommandOptionType.user
                elif origin in channel_types:
                    ptype = CommandOptionType.channel
                    option.update({
                        "channel_types": [
                            int(i) for i in channel_types[origin]
                        ]
                    })
                elif origin in [Attachment]:
                    ptype = CommandOptionType.attachment
                elif origin in [Role]:
                    ptype = CommandOptionType.role
                elif origin in [Choice]:
                    # Temporarily set to string, will be changed later
                    self.__list_choices.append(parameter.name)
                    ptype = CommandOptionType.string
                elif isinstance(origin, Range):
                    ptype = origin.type
                    if origin.type == CommandOptionType.string:
                        option.update({
                            "min_length": origin.min,
                            "max_length": origin.max
                        })
                    else:
                        option.update({
                            "min_value": origin.min,
                            "max_value": origin.max
                        })
                elif origin == int:
                    ptype = CommandOptionType.integer
                elif origin == bool:
                    ptype = CommandOptionType.boolean
                elif origin == float:
                    ptype = CommandOptionType.number
                elif origin == str:
                    ptype = CommandOptionType.string
                else:
                    ptype = CommandOptionType.string

                option.update({
                    "name": parameter.name,
                    "description": "…",
                    "type": ptype.value,
                    "required": (parameter.default == parameter.empty),
                    "autocomplete": False,
                    "name_localizations": {},
                    "description_localizations": {},
                })

                self.options.append(option)

    def __repr__(self) -> str:
        return f"<Command name='{self.name}'>"

    @property
    def mention(self) -> str:
        """ `str`: Returns a mentionable string for the command """
        if self.id:
            return f"</{self.name}:{self.id}>"
        return f"`/{self.name}`"

    def mention_sub(self, suffix: str) -> str:
        """
        Returns a mentionable string for a subcommand.

        Parameters
        ----------
        suffix: `str`
            The subcommand name.

        Returns
        -------
        `str`
            The mentionable string.
        """
        if self.id:
            return f"</{self.name} {suffix}:{self.id}>"
        return f"`/{self.name} {suffix}`"

    async def _make_context_and_run(
        self,
        context: "Context"
    ) -> BaseResponse:
        args, kwargs = context._create_args()

        for name, values in getattr(self.command, "__choices_params__", {}).items():
            if name not in kwargs:
                continue
            if name not in self.__list_choices:
                continue
            kwargs[name] = Choice(
                kwargs[name], values[kwargs[name]]
            )

        result = await self.run(context, *args, **kwargs)

        if not isinstance(result, BaseResponse):
            raise TypeError(
                f"Command {self.name} must return a "
                f"Response object, not {type(result)}."
            )

        return result

    def _has_permissions(self, ctx: "Context") -> Permissions:
        _perms: Optional[Permissions] = getattr(
            self.command, "__has_permissions__", None
        )

        if _perms is None:
            return Permissions(0)

        if (
            isinstance(ctx.user, Member) and
            Permissions.administrator in ctx.user.resolved_permissions
        ):
            return Permissions(0)

        missing = Permissions(sum([
            flag.value for flag in _perms
            if flag not in ctx.app_permissions
        ]))

        return missing

    def _bot_has_permissions(self, ctx: "Context") -> Permissions:
        _perms: Optional[Permissions] = getattr(
            self.command, "__bot_has_permissions__", None
        )

        if _perms is None:
            return Permissions(0)
        if Permissions.administrator in ctx.app_permissions:
            return Permissions(0)

        missing = Permissions(sum([
            flag.value for flag in _perms
            if flag not in ctx.app_permissions
        ]))

        return missing

    async def _command_checks(self, ctx: "Context") -> bool:
        _checks: list[Callable] = getattr(
            self.command, "__checks__", []
        )

        for g in _checks:
            if inspect.iscoroutinefunction(g):
                result = await g(ctx)
            else:
                result = g(ctx)

            if result is not True:
                raise CheckFailed(f"Check {g.__name__} failed.")

        return True

    async def run(self, context: "Context", *args, **kwargs) -> BaseResponse:
        """
        Runs the command.

        Parameters
        ----------
        context: `Context`
            The context of the command.

        Returns
        -------
        `BaseResponse`
            The return type of the command, used by backend.py (Quart)

        Raises
        ------
        `UserMissingPermissions`
            User that ran the command is missing permissions.
        `BotMissingPermissions`
            Bot is missing permissions.
        """
        # Check user permissions
        perms_user = self._has_permissions(context)
        if perms_user != Permissions(0):
            raise UserMissingPermissions(perms_user)

        # Check bot permissions
        perms_bot = self._bot_has_permissions(context)
        if perms_bot != Permissions(0):
            raise BotMissingPermissions(perms_bot)

        # Check custom checks
        await self._command_checks(context)

        if self.cog is not None:
            return await self.command(self.cog, context, *args, **kwargs)
        else:
            return await self.command(context, *args, **kwargs)

    async def run_autocomplete(
        self,
        context: "Context",
        name: str,
        current: str
    ) -> dict:
        """
        Runs the autocomplete

        Parameters
        ----------
        context: `Context`
            Context object for the command
        name: `str`
            Name of the option
        current: `str`
            Current value of the option

        Returns
        -------
        `dict`
            The return type of the command, used by backend.py (Quart)

        Raises
        ------
        `TypeError`
            Autocomplete must return an AutocompleteResponse object
        """
        if self.cog is not None:
            result = await self.list_autocompletes[name](self.cog, context, current)
        else:
            result = await self.list_autocompletes[name](context, current)

        if isinstance(result, AutocompleteResponse):
            return result.to_dict()
        raise TypeError("Autocomplete must return an AutocompleteResponse object.")

    def _find_option(self, name: str) -> Optional[dict]:
        return next((g for g in self.options if g["name"] == name), None)

    def to_dict(self) -> dict:
        """
        Converts the command to a dict.

        Returns
        -------
        `dict`
            The dict of the command.
        """
        _extra_locale = getattr(self.command, "__locales__", {})
        _extra_params = getattr(self.command, "__describe_params__", {})
        _extra_choices = getattr(self.command, "__choices_params__", {})
        _default_permissions = getattr(self.command, "__default_permissions__", None)

        # Types
        _extra_locale: dict[LocaleTypes, list[LocaleContainer]]

        data = {
            "type": self.type,
            "name": self.name,
            "description": self.description,
            "options": self.options,
            "default_permission": True,
            "dm_permission": getattr(self.command, "__dm_permission__", True),
            "nsfw": getattr(self.command, "__nsfw__", False),
            "name_localizations": {},
            "description_localizations": {},
        }

        for key, value in _extra_locale.items():
            for loc in value:
                if loc.key == "_":
                    data["name_localizations"][key] = loc.name
                    data["description_localizations"][key] = loc.description
                    continue

                opt = self._find_option(loc.key)
                if not opt:
                    _log.warn(
                        f"{self.name} -> {loc.key}: "
                        "Option not found in command, skipping..."
                    )
                    continue

                opt["name_localizations"][key] = loc.name
                opt["description_localizations"][key] = loc.description

        if _default_permissions:
            data["default_member_permissions"] = _default_permissions

        for key, value in _extra_params.items():
            opt = self._find_option(key)
            if not opt:
                continue

            opt["description"] = value

        for key, value in _extra_choices.items():
            opt = self._find_option(key)
            if not opt:
                continue

            opt["choices"] = [
                {"name": v, "value": k}
                for k, v in value.items()
            ]

        return data

    def autocomplete(self, name: str):
        """
        Decorator to set an option as an autocomplete.

        The function must at the end, return a `Response.send_autocomplete()` object.

        Parameters
        ----------
        name: `str`
            Name of the option to set as an autocomplete.
        """
        def wrapper(func):
            find_option = next((
                option for option in self.options
                if option["name"] == name
            ), None)

            if not find_option:
                raise ValueError(f"Option {name} in command {self.name} not found.")
            find_option["autocomplete"] = True
            self.list_autocompletes[name] = func
            return func

        return wrapper


class SubCommand(Command):
    def __init__(
        self,
        func: Callable,
        *,
        name: str,
        description: Optional[str] = None,
        guild_ids: Optional[list[Union[utils.Snowflake, int]]] = None
    ):
        super().__init__(
            func,
            name=name,
            description=description,
            guild_ids=guild_ids
        )

    def __repr__(self) -> str:
        return f"<SubCommand name='{self.name}'>"


class SubGroup(Command):
    def __init__(
        self,
        *,
        name: str,
        description: Optional[str] = None,
        guild_ids: Optional[list[Union[utils.Snowflake, int]]] = None
    ):
        self.name = name
        self.description = description or "..."  # Only used to make Discord happy
        self.guild_ids: list[Union[utils.Snowflake, int]] = guild_ids or []
        self.type = int(ApplicationCommandType.chat_input)
        self.cog: Optional["Cog"] = None
        self.subcommands: Dict[str, Union[SubCommand, SubGroup]] = {}

    def __repr__(self) -> str:
        _subs = [g for g in self.subcommands.values()]
        return f"<SubGroup name='{self.name}', subcommands={_subs}>"

    def command(
        self,
        name: Optional[str] = None,
        description: Optional[str] = None,
        guild_ids: Optional[list[Union[utils.Snowflake, int]]] = None,
    ):
        """
        Decorator to add a subcommand to a subcommand group

        Parameters
        ----------
        name: `Optional[str]`
            Name of the command (defaults to the function name)
        description: `Optional[str]`
            Description of the command (defaults to the function docstring)
        guild_ids: `Optional[list[Union[utils.Snowflake, int]]]`
            List of guild IDs to register the command in
        """
        def decorator(func):
            subcommand = SubCommand(
                func,
                name=name or func.__name__,
                description=description,
                guild_ids=guild_ids,
            )
            self.subcommands[subcommand.name] = subcommand
            return subcommand
        return decorator

    def group(self, name: Optional[str] = None):
        """
        Decorator to add a subcommand group to a subcommand group

        Parameters
        ----------
        name: `Optional[str]`
            Name of the subcommand group (defaults to the function name)
        """
        def decorator(func):
            subgroup = SubGroup(name=name or func.__name__)
            self.subcommands[subgroup.name] = subgroup
            return subgroup
        return decorator

    def add_group(self, name: str) -> "SubGroup":
        """
        Adds a subcommand group to a subcommand group

        Parameters
        ----------
        name: `str`
            Name of the subcommand group

        Returns
        -------
        `SubGroup`
            The subcommand group
        """
        subgroup = SubGroup(name=name)
        self.subcommands[subgroup.name] = subgroup
        return subgroup

    @property
    def options(self) -> list[dict]:
        """ `list[dict]`: Returns the options of the subcommand group """
        options = []
        for cmd in self.subcommands.values():
            data = cmd.to_dict()
            if isinstance(cmd, SubGroup):
                data["type"] = int(CommandOptionType.sub_command_group)
            else:
                data["type"] = int(CommandOptionType.sub_command)
            options.append(data)
        return options


class Interaction:
    def __init__(
        self,
        func: Callable,
        custom_id: str,
        *,
        regex: bool = False
    ):
        self.func = func
        self.custom_id = custom_id
        self.cog: Optional["Cog"] = None
        self.is_regex: bool = regex

    def __repr__(self) -> str:
        return (
            f"<Interaction custom_id='{self.custom_id}' "
            f"is_regex={self.is_regex}>"
        )

    async def run(self, context: "Context") -> BaseResponse:
        """
        Runs the interaction.

        Parameters
        ----------
        context: `Context`
            The context of the interaction.

        Returns
        -------
        `BaseResponse`
            The return type of the interaction, used by backend.py (Quart)

        Raises
        ------
        `TypeError`
            Interaction must be a Response object
        """
        if self.cog is not None:
            result = await self.func(self.cog, context)
        else:
            result = await self.func(context)

        if not isinstance(result, BaseResponse):
            raise TypeError("Interaction must be a Response object")

        return result


class Listener:
    def __init__(self, name: str, coro: Callable):
        self.name = name
        self.coro = coro
        self.cog: Optional["Cog"] = None

    def __repr__(self) -> str:
        return f"<Listener name='{self.name}'>"

    async def run(self, *args, **kwargs):
        """ Runs the listener """
        if self.cog is not None:
            await self.coro(self.cog, *args, **kwargs)
        else:
            await self.coro(*args, **kwargs)


class Choice(Generic[ChoiceT]):
    """
    Makes it possible to access both the name and value of a choice.

    Paramaters
    -----------
    key: :class:`str`
        The key of the choice from your dict.
    value: Union[:class:`int`, :class:`str`, :class:`float`]
        The value of your choice (the one that is shown to public)
    """
    def __init__(self, key: str, value: ChoiceT):
        self.key: str = key
        self.value: ChoiceT = value

    @property
    def _choice_type(self) -> CommandOptionType:
        if isinstance(self.value, str):
            return CommandOptionType.string
        elif isinstance(self.value, int):
            return CommandOptionType.integer
        elif isinstance(self.value, float):
            return CommandOptionType.number
        else:
            raise TypeError(
                "Choice value must be a str, int, or float, "
                f"not a {type(self.value)}"
            )


class Range:
    def __init__(
        self,
        opt_type: CommandOptionType,
        min: Optional[Union[int, float, str]],
        max: Optional[Union[int, float, str]]
    ):
        self.type = opt_type
        self.min = min
        self.max = max

    def __class_getitem__(cls, obj):
        if not isinstance(obj, tuple):
            raise TypeError("Range must be a tuple")

        if len(obj) == 2:
            obj = (*obj, None)
        elif len(obj) != 3:
            raise TypeError("Range must be a tuple of length 2 or 3")

        obj_type, min, max = obj

        if min is None and max is None:
            raise TypeError("Range must have a minimum or maximum value")

        if min is not None and max is not None:
            if type(min) is not type(max):
                raise TypeError("Range minimum and maximum must be the same type")

        match obj_type:
            case x if x is str:
                opt = CommandOptionType.string
            case x if x is int:
                opt = CommandOptionType.integer
            case x if x is float:
                opt = CommandOptionType.number
            case _:
                raise TypeError(
                    "Range type must be str, int, "
                    f"or float, not a {obj_type}"
                )

        if obj_type in (str, int):
            cast = int
        else:
            cast = float

        return cls(
            opt,
            cast(min) if min is not None else None,
            cast(max) if max is not None else None
        )


def command(
    name: Optional[str] = None,
    *,
    description: Optional[str] = None,
    guild_ids: Optional[list[Union[utils.Snowflake, int]]] = None,
):
    """
    Decorator to register a command.

    Parameters
    ----------
    name: `Optional[str]`
        Name of the command (defaults to the function name)
    description: `Optional[str]`
        Description of the command (defaults to the function docstring)
    guild_ids: `Optional[list[Union[utils.Snowflake, int]]]`
        List of guild IDs to register the command in
    """
    def decorator(func):
        return Command(
            func,
            name=name or func.__name__,
            description=description,
            guild_ids=guild_ids,
        )
    return decorator


def user_command(
    name: Optional[str] = None,
    *,
    guild_ids: Optional[list[Union[utils.Snowflake, int]]] = None,
):
    """
    Decorator to register a user command.

    Example usage

    .. code-block:: python

        @user_command()
        async def content(ctx, user: Union[Member, User]):
            await ctx.send(f"Target: {user.name}")

    Parameters
    ----------
    name: `Optional[str]`
        Name of the command (defaults to the function name)
    guild_ids: `Optional[list[Union[utils.Snowflake, int]]]`
        List of guild IDs to register the command in
    """
    def decorator(func):
        return Command(
            func,
            name=name or func.__name__,
            type=ApplicationCommandType.user,
            guild_ids=guild_ids,
        )
    return decorator


def message_command(
    name: Optional[str] = None,
    *,
    guild_ids: Optional[list[Union[utils.Snowflake, int]]] = None,
):
    """
    Decorator to register a message command.

    Example usage

    .. code-block:: python

        @message_command()
        async def content(ctx, msg: Message):
            await ctx.send(f"Content: {msg.content}")

    Parameters
    ----------
    name: `Optional[str]`
        Name of the command (defaults to the function name)
    guild_ids: `Optional[list[Union[utils.Snowflake, int]]]`
        List of guild IDs to register the command in
    """
    def decorator(func):
        return Command(
            func,
            name=name or func.__name__,
            type=ApplicationCommandType.message,
            guild_ids=guild_ids
        )
    return decorator


def locales(
    translations: Dict[
        LocaleTypes,
        Dict[
            str,
            Union[list[str], tuple[str], tuple[str, str]]
        ]
    ]
):
    """
    Decorator to set translations for a command.

    _ = Reserved for the root command name and description.

    Example usage:

    .. code-block:: python

        @commands.command(name="ping")
        @commands.locales({
            # Norwegian
            "no": {
                "_": ("ping", "Sender en 'pong' melding")
                "funny": ("morsomt", "Morsomt svar")
            }
        })
        async def ping(ctx, funny: str):
            await ctx.send(f"pong {funny}")

    Parameters
    ----------
    translations: `Dict[LocaleTypes, Dict[str, Union[tuple[str], tuple[str, str]]]]`
        The translations for the command name, description, and options.
    """
    def decorator(func):
        name = func.__name__
        container = {}

        for key, value in translations.items():
            temp_value: list[LocaleContainer] = []

            if not isinstance(key, str):
                _log.error(f"{name}: Translation key must be a string, not a {type(key)}")
                continue

            if key not in ValidLocalesList:
                _log.warn(f"{name}: Unsupported locale {key} skipped (might be a typo)")
                continue

            if not isinstance(value, dict):
                _log.error(f"{name} -> {key}: Translation value must be a dict, not a {type(value)}")
                continue

            for tname, tvalues in value.items():
                if not isinstance(tname, str):
                    _log.error(f"{name} -> {key}: Translation option must be a string, not a {type(tname)}")
                    continue

                if not isinstance(tvalues, (list, tuple)):
                    _log.error(f"{name} -> {key} -> {tname}: Translation values must be a list or tuple, not a {type(tvalues)}")
                    continue

                if len(tvalues) < 1:
                    _log.error(f"{name} -> {key} -> {tname}: Translation values must have a minimum of 1 value")
                    continue

                temp_value.append(
                    LocaleContainer(
                        tname,
                        *tvalues[:2]  # Only use the first 2 values, ignore the rest
                    )
                )

            if not temp_value:
                _log.warn(f"{name} -> {key}: Found an empty translation dict, skipping...")
                continue

            container[key] = temp_value

        func.__locales__ = container
        return func

    return decorator


def group(
    name: Optional[str] = None,
    description: Optional[str] = None
):
    """
    Decorator to register a command group.

    Parameters
    ----------
    name: `Optional[str]`
        Name of the command group (defaults to the function name)
    description: `Optional[str]`
        Description of the command group (defaults to the function docstring)
    """
    def decorator(func):
        return SubGroup(
            name=name or func.__name__,
            description=description
        )
    return decorator


def describe(**kwargs):
    """
    Decorator to set descriptions for a command.

    Example usage:

    .. code-block:: python

        @commands.command()
        @commands.describe(user="User to ping")
        async def ping(ctx, user: Member):
            await ctx.send(f"Pinged {user.mention}")
    """
    def decorator(func):
        func.__describe_params__ = kwargs
        return func
    return decorator


def choices(**kwargs):
    """
    Decorator to set choices for a command.

    Example usage:

    .. code-block:: python

        @commands.command()
        @commands.choices(
            options={"opt1": "Choice 1", "opt2": "Choice 2"}
        )
        async def ping(ctx, options: Choice[str]):
            await ctx.send(f"You chose {choice.value}")
    """
    def decorator(func):
        for k, v in kwargs.items():
            if not isinstance(v, dict):
                raise TypeError(
                    f"Choice {k} must be a dict, not a {type(v)}"
                )

        func.__choices_params__ = kwargs
        return func
    return decorator


def guild_only():
    """ Decorator to set a command as guild only. """
    def decorator(func):
        func.__dm_permission__ = False
        return func
    return decorator


def is_nsfw():
    """ Decorator to set a command as NSFW. """
    def decorator(func):
        func.__nsfw__ = True
        return func
    return decorator


def default_permissions(*args):
    """ Decorator to set default permissions for a command. """
    def decorator(func):
        func.__default_permissions__ = str(Permissions.from_names(*args).value)
        return func
    return decorator


def has_permissions(*args: str):
    """
    Decorator to set permissions for a command.

    Example usage:

    .. code-block:: python

        @commands.command()
        @commands.has_permissions("manage_messages")
        async def ban(ctx, user: Member):
            ...
    """
    def decorator(func):
        func.__has_permissions__ = Permissions.from_names(*args)
        return func
    return decorator


def bot_has_permissions(*args: str):
    """
    Decorator to set permissions for a command.

    Example usage:

    .. code-block:: python

        @commands.command()
        @commands.bot_has_permissions("embed_links")
        async def cat(ctx):
            ...
    """
    def decorator(func):
        func.__bot_has_permissions__ = Permissions.from_names(*args)
        return func
    return decorator


def check(predicate: Union[Callable, Coroutine]):
    """
    Decorator to set a check for a command.

    Example usage:

    .. code-block:: python

        def is_owner(ctx):
            return ctx.author.id == 123456789

        @commands.command()
        @commands.check(is_owner)
        async def foo(ctx):
            ...
    """
    def decorator(func):
        _check_list = getattr(func, "__checks__", [])
        _check_list.append(predicate)
        func.__checks__ = _check_list
        return func
    return decorator


def interaction(custom_id: str, *, regex: bool = False):
    """
    Decorator to register an interaction.

    This supports the usage of regex to match multiple custom IDs.

    Parameters
    ----------
    custom_id: `str`
        The custom ID of the interaction. (can be partial, aka. regex)
    regex: `bool`
        Whether the custom_id is a regex or not
    """
    def decorator(func):
        return Interaction(
            func, custom_id=custom_id, regex=regex
        )
    return decorator


def listener(name: Optional[str] = None):
    """
    Decorator to register a listener.

    Parameters
    ----------
    name: `Optional[str]`
        Name of the listener (defaults to the function name)

    Raises
    ------
    `TypeError`
        - If name was not a string
        - If the listener was not a coroutine function
    """
    if name is not None and not isinstance(name, str):
        raise TypeError(f"Listener name must be a string, not {type(name)}")

    def decorator(func):
        actual = func
        if isinstance(actual, staticmethod):
            actual = actual.__func__
        if not inspect.iscoroutinefunction(actual):
            raise TypeError("Listeners has to be coroutine functions")
        return Listener(
            name or actual.__name__,
            func
        )

    return decorator
