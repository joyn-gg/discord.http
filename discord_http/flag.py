import sys

from enum import Flag, CONFORM
from typing import Union, Self

__all__ = (
    "BaseFlag",
    "MessageFlags",
    "Permissions",
    "PublicFlags",
    "SKUFlags",
    "SystemChannelFlags",
)

if sys.version_info >= (3, 11, 0):
    class _FlagPyMeta(Flag, boundary=CONFORM):
        pass
else:
    class _FlagPyMeta(Flag):
        pass


class BaseFlag(_FlagPyMeta):
    def to_names(self) -> list[str]:
        """ `list[str]`: Returns the current names of the flag """
        return [
            name for name, member in self.__class__.__members__.items()
            if member in self
        ]

    def __int__(self) -> int:
        return self.value

    @classmethod
    def all(cls) -> Self:
        """ `BaseFlag`: Returns a flag with all the flags """
        return cls(sum([int(g) for g in cls.__members__.values()]))

    @property
    def list_names(self) -> list[str]:
        """ `list[str]`: Returns a list of all the names of the flag """
        return [
            g.name or "UNKNOWN"
            for g in self
        ]

    def add_flag(
        self,
        flag_name: Union[Self, str]
    ) -> Self:
        """
        Add a flag by name

        Parameters
        ----------
        flag_name: `Union[BaseFlag, str]`
            The flag to add

        Returns
        -------
        `BaseFlag`
            The flag with the added flag

        Raises
        ------
        `ValueError`
            The flag name is not a valid flag
        """
        if isinstance(flag_name, BaseFlag):
            self |= flag_name
            return self
        else:
            if flag_name in self.list_names:
                return self

            try:
                self |= self.__class__[flag_name]
            except KeyError:
                raise ValueError(
                    f"{flag_name} is not a valid "
                    f"{self.__class__.__name__} flag value"
                )

            return self

    def remove_flag(self, flag_name: Union[Self, str]) -> Self:
        """
        Remove a flag by name

        Parameters
        ----------
        flag_name: `Union[BaseFlag, str]`
            The flag to remove

        Returns
        -------
        `BaseFlag`
            The flag with the removed flag

        Raises
        ------
        `ValueError`
            The flag name is not a valid flag
        """
        if isinstance(flag_name, BaseFlag):
            self &= ~flag_name
            return self
        else:
            if flag_name not in self.list_names:
                return self

            try:
                self &= ~self.__class__[flag_name]
            except KeyError:
                raise ValueError(
                    f"{flag_name} is not a valid "
                    f"{self.__class__.__name__} flag value"
                )

            return self

    @classmethod
    def from_names(cls, *args: str) -> Self:
        """
        Create a flag from names

        Parameters
        ----------
        *args: `str`
            The names of the flags to create

        Returns
        -------
        `BaseFlag`
            The flag with the added flags

        Raises
        ------
        `TypeError`
            The argument is not a `str`
        `ValueError`
            The flag name is not a valid flag
        """
        _value = 0
        for i, arg in enumerate(args, start=1):
            if not isinstance(arg, str):
                raise TypeError(f"Expected str, received {type(arg)} instead (arg:{i})")
            try:
                _value |= cls[arg].value
            except KeyError:
                raise ValueError(f"{arg} is not a valid {cls.__name__} argument")
        return cls(_value)


class MessageFlags(BaseFlag):
    crossposted = 1 << 0
    is_crosspost = 1 << 1
    suppress_embeds = 1 << 2
    source_message_deleted = 1 << 3
    urgent = 1 << 4
    has_thread = 1 << 5
    ephemeral = 1 << 6
    loading = 1 << 7
    failed_to_mention_some_roles_in_thread = 1 << 8
    suppress_notifications = 1 << 12
    is_voice_message = 1 << 13


class SKUFlags(BaseFlag):
    available = 1 << 2
    guild_subscription = 1 << 7
    user_subscription = 1 << 8


class PublicFlags(BaseFlag):
    staff = 1 << 0
    partner = 1 << 1
    hypesquad = 1 << 2
    bug_hunter_level_1 = 1 << 3
    hypesquad_online_house_1 = 1 << 6
    hypesquad_online_house_2 = 1 << 7
    hypesquad_online_house_3 = 1 << 8
    premium_early_supporter = 1 << 9
    team_pseudo_user = 1 << 10
    bug_hunter_level_2 = 1 << 14
    verified_bot = 1 << 16
    verified_developer = 1 << 17
    certified_moderator = 1 << 18
    bot_http_interactions = 1 << 19
    active_developer = 1 << 22


class SystemChannelFlags(BaseFlag):
    suppress_join_notifications = 1 << 0
    suppress_premium_subscriptions = 1 << 1
    suppress_guild_reminder_notifications = 1 << 2
    suppress_join_notification_replies = 1 << 3
    suppress_role_subscription_purchase_notifications = 1 << 4
    suppress_role_subscription_purchase_notifications_replies = 1 << 5


class Permissions(BaseFlag):
    create_instant_invite = 1 << 0
    kick_members = 1 << 1
    ban_members = 1 << 2
    administrator = 1 << 3
    manage_channels = 1 << 4
    manage_guild = 1 << 5
    add_reactions = 1 << 6
    view_audit_log = 1 << 7
    priority_speaker = 1 << 8
    stream = 1 << 9
    view_channel = 1 << 10
    send_messages = 1 << 11
    send_tts_messages = 1 << 12
    manage_messages = 1 << 13
    embed_links = 1 << 14
    attach_files = 1 << 15
    read_message_history = 1 << 16
    mention_everyone = 1 << 17
    use_external_emojis = 1 << 18
    view_guild_insights = 1 << 19
    connect = 1 << 20
    speak = 1 << 21
    mute_members = 1 << 22
    deafen_members = 1 << 23
    move_members = 1 << 24
    use_vad = 1 << 25
    change_nickname = 1 << 26
    manage_nicknames = 1 << 27
    manage_roles = 1 << 28
    manage_webhooks = 1 << 29
    manage_guild_expressions = 1 << 30
    use_application_commands = 1 << 31
    request_to_speak = 1 << 32
    manage_events = 1 << 33
    manage_threads = 1 << 34
    create_public_threads = 1 << 35
    create_private_threads = 1 << 36
    use_external_stickers = 1 << 37
    send_messages_in_threads = 1 << 38
    use_embedded_activities = 1 << 39
    moderate_members = 1 << 40
    view_creator_monetization_analytics = 1 << 41
    use_soundboard = 1 << 42
    use_external_sounds = 1 << 45
    send_voice_messages = 1 << 46
