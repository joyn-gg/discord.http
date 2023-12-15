from .utils import Enum

__all__ = (
    "ApplicationCommandType",
    "ButtonStyles",
    "ChannelType",
    "CommandOptionType",
    "ComponentType",
    "ContentFilterLevel",
    "DefaultNotificationLevel",
    "IntegrationType",
    "InteractionType",
    "InviteType",
    "MFALevel",
    "ResponseType",
    "TextStyles",
    "VerificationLevel",
)


class IntegrationType(Enum):
    guild = 0
    user = 1


class InviteType(Enum):
    guild = 0
    group = 1
    dm = 2
    unknown = 3


class ApplicationCommandType(Enum):
    chat_input = 1
    user = 2
    message = 3


class DefaultNotificationLevel(Enum):
    all_messages = 0
    only_mentions = 1


class MFALevel(Enum):
    none = 0
    elevated = 1


class ContentFilterLevel(Enum):
    disabled = 0
    members_without_roles = 1
    all_members = 2


class VerificationLevel(Enum):
    none = 0
    low = 1
    medium = 2
    high = 3
    very_high = 4


class ChannelType(Enum):
    guild_text = 0
    dm = 1
    guild_voice = 2
    group_dm = 3
    guild_category = 4
    guild_news = 5
    guild_store = 6
    guild_news_thread = 10
    guild_public_thread = 11
    guild_private_thread = 12
    guild_stage_voice = 13
    guild_directory = 14
    guild_forum = 15


class CommandOptionType(Enum):
    sub_command = 1
    sub_command_group = 2
    string = 3
    integer = 4
    boolean = 5
    user = 6
    channel = 7
    role = 8
    mentionable = 9
    number = 10
    attachment = 11


class ResponseType(Enum):
    pong = 1
    channel_message_with_source = 4
    deferred_channel_message_with_source = 5
    deferred_update_message = 6
    update_message = 7
    application_command_autocomplete_result = 8
    modal = 9


class InteractionType(Enum):
    ping = 1
    application_command = 2
    message_component = 3
    application_command_autocomplete = 4
    modal_submit = 5


class ComponentType(Enum):
    action_row = 1
    button = 2
    string_select = 3
    text_input = 4
    user_select = 5
    role_select = 6
    mentionable_select = 7
    channel_select = 8


class ButtonStyles(Enum):
    primary = 1
    secondary = 2
    success = 3
    danger = 4
    link = 5

    blurple = 1
    grey = 2
    gray = 2
    green = 3
    red = 4
    url = 5


class TextStyles(Enum):
    short = 1
    paragraph = 2


class PermissionType(Enum):
    role = 0
    member = 1
