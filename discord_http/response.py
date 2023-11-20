from typing import TYPE_CHECKING, Union, Any, Optional

from .embeds import Embed
from .enums import ResponseType
from .view import View, Modal
from .file import File
from .multipart import MultipartData
from .flag import MessageFlags
from . import utils
from .mentions import AllowedMentions

if TYPE_CHECKING:
    from .user import User
    from .http import DiscordAPI

MISSING = utils.MISSING

__all__ = (
    "Ping",
    "DeferResponse",
    "MessageResponse",
    "AutocompleteResponse",
)


class Ping:
    def __init__(
        self,
        *,
        state: "DiscordAPI",
        data: dict
    ):
        self._state = state
        self._raw_user = data["user"]

        self.id: int = int(data["id"])
        self.application_id: int = int(data["application_id"])
        self.version: int = int(data["version"])

    def __repr__(self) -> str:
        return f"<Ping application_id={self.application_id} user='{self.user}'>"

    def __int__(self) -> int:
        return self.id

    @property
    def user(self) -> "User":
        """ `User`: Returns the user object of the bot """
        from .user import User
        return User(state=self._state, data=self._raw_user)


class BaseResponse:
    def __init__(self):
        pass

    @property
    def content_type(self) -> str:
        """ `str`: Returns the content type of the response """
        multidata = MultipartData()
        return multidata.content_type

    def to_dict(self) -> dict:
        """ Default method to convert the response to a `dict` """
        raise NotImplementedError

    def to_multipart(self) -> bytes:
        """ Default method to convert the response to a `bytes` """
        raise NotImplementedError


class DeferResponse(BaseResponse):
    def __init__(
        self,
        *,
        ephemeral: bool = False,
        thinking: bool = False
    ):
        self.ephemeral = ephemeral
        self.thinking = thinking

    def to_dict(self) -> dict:
        """ `dict`: Returns the response as a `dict` """
        return {
            "type": (
                int(ResponseType.deferred_channel_message_with_source)
                if self.thinking else int(ResponseType.deferred_update_message)
            ),
            "data": {
                "flags": (
                    MessageFlags.ephemeral.value
                    if self.ephemeral else 0
                )
            }
        }

    def to_multipart(self) -> bytes:
        """ `bytes`: Returns the response as a `bytes` """
        multidata = MultipartData()
        multidata.attach("payload_json", self.to_dict())

        return multidata.finish()


class AutocompleteResponse(BaseResponse):
    def __init__(
        self,
        choices: dict[Any, str]
    ):
        self.choices = choices

    def to_dict(self) -> dict:
        """ `dict`: Returns the response as a `dict` """
        return {
            "type": int(ResponseType.application_command_autocomplete_result),
            "data": {
                "choices": [
                    {"name": value, "value": key}
                    for key, value in self.choices.items()
                ][:25]  # Discord only allows 25 choices, so we limit it
            }
        }

    def to_multipart(self) -> bytes:
        """ `bytes`: Returns the response as a `bytes` """
        multidata = MultipartData()
        multidata.attach("payload_json", self.to_dict())

        return multidata.finish()


class ModalResponse(BaseResponse):
    def __init__(self, modal: Modal):
        self.modal = modal

    def to_dict(self) -> dict:
        """ `dict`: Returns the response as a `dict` """
        return {
            "type": int(ResponseType.modal),
            "data": self.modal.to_dict()
        }

    def to_multipart(self) -> bytes:
        """ `bytes`: Returns the response as a `bytes` """
        multidata = MultipartData()
        multidata.attach("payload_json", self.to_dict())

        return multidata.finish()


class MessageResponse(BaseResponse):
    def __init__(
        self,
        content: Optional[str] = MISSING,
        *,
        file: Optional[File] = MISSING,
        files: Optional[list[File]] = MISSING,
        embed: Optional[Embed] = MISSING,
        embeds: Optional[list[Embed]] = MISSING,
        attachment: Optional[File] = MISSING,
        attachments: Optional[list[File]] = MISSING,
        view: Optional[View] = MISSING,
        tts: Optional[bool] = False,
        allowed_mentions: Optional[AllowedMentions] = MISSING,
        type: Union[ResponseType, int] = 4,
        ephemeral: Optional[bool] = False,
    ):
        self.content = content
        self.files = files
        self.embeds = embeds
        self.attachments = attachments
        self.ephemeral = ephemeral
        self.view = view
        self.tts = tts
        self.type = type
        self.allowed_mentions = allowed_mentions

        if file is not MISSING and files is not MISSING:
            raise TypeError("Cannot pass both file and files")
        if file is not MISSING:
            self.files = [file]

        if embed is not MISSING and embeds is not MISSING:
            raise TypeError("Cannot pass both embed and embeds")
        if embed is not MISSING:
            if embed is None:
                self.embeds = []
            else:
                self.embeds = [embed]

        if attachment is not MISSING and attachments is not MISSING:
            raise TypeError("Cannot pass both attachment and attachments")
        if attachment is not MISSING:
            if attachment is None:
                self.attachments = []
            else:
                self.attachments = [attachment]

        if self.view is not MISSING and self.view is None:
            self.view = View()

        if self.attachments is not MISSING:
            self.files = (
                [a for a in self.attachments if isinstance(a, File)]
                if self.attachments is not None else None
            )

    def to_dict(self, is_request: bool = False) -> dict:
        """
        The JSON data that is sent to Discord.

        Parameters
        ----------
        is_request: `bool`
            Whether the data is being sent to Discord or not.

        Returns
        -------
        `dict`
            The JSON data that can either be sent
            to Discord or forwarded to a new parser
        """
        output: dict[str, Any] = {
            "flags": (
                MessageFlags.ephemeral.value
                if self.ephemeral else 0
            )
        }

        if self.content is not MISSING:
            output["content"] = self.content

        if self.tts:
            output["tts"] = self.tts

        if self.embeds is not MISSING:
            output["embeds"] = [
                embed.to_dict() for embed in self.embeds  # type: ignore
                if isinstance(embed, Embed)
            ]

        if self.view is not MISSING:
            output["components"] = self.view.to_dict()

        if self.allowed_mentions is not MISSING:
            output["allowed_mentions"] = self.allowed_mentions.to_dict()

        if self.attachments is not MISSING:
            if self.attachments is None:
                output["attachments"] = []
            else:
                _index = 0
                _file_payload = []
                for a in self.attachments:
                    if not isinstance(a, File):
                        continue
                    _file_payload.append(a.to_dict(_index))
                    _index += 1
                output["attachments"] = _file_payload

        if is_request:
            return output
        return {"type": int(self.type), "data": output}

    def to_multipart(self, is_request: bool = False) -> bytes:
        """
        The multipart data that is sent to Discord.

        Parameters
        ----------
        is_request: `bool`
            Whether the data is being sent to Discord or not.

        Returns
        -------
        `bytes`
            The multipart data that can either be sent
        """
        multidata = MultipartData()

        if isinstance(self.files, list):
            for i, file in enumerate(self.files):
                multidata.attach(
                    f"files[{i}]",
                    file, filename=file.filename  # type: ignore
                )

        multidata.attach(
            "payload_json",
            self.to_dict(is_request=is_request)
        )

        return multidata.finish()
