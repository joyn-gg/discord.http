import re
import numbers
import traceback
import logging
import unicodedata
import random
import enum

from base64 import b64encode
from typing import Optional, Any, Union, Iterator
from datetime import datetime, timezone
from typing import Self

from .file import File

DISCORD_EPOCH = 1420070400000

# RegEx patterns
re_channel: re.Pattern = re.compile(r"<#([0-9]{15,20})>")
re_role: re.Pattern = re.compile(r"<@&([0-9]{15,20})>")
re_mention: re.Pattern = re.compile(r"<@!?([0-9]{15,20})>")
re_emoji: re.Pattern = re.compile(r"<(a)?:([a-zA-Z0-9_]+):(\d+)>")
re_hex = re.compile(r"^(?:#)?(?:[0-9a-fA-F]{3}){1,2}$")
re_jump_url: re.Pattern = re.compile(
    r"https:\/\/(?:.*\.)?discord\.com\/channels\/([0-9]{15,20}|@me)\/([0-9]{15,20})(?:\/([0-9]{15,20}))?"
)


def traceback_maker(err: Exception, advance: bool = True) -> str:
    """
    Takes a traceback from an error and returns it as a string

    Useful if you wish to get traceback in any other forms than the console

    Parameters
    ----------
    err: `Exception`
        The error to get the traceback from
    advance: `bool`
        Whether to include the traceback or not

    Returns
    -------
    `str`
        The traceback of the error
    """
    _traceback = ''.join(traceback.format_tb(err.__traceback__))
    error = f"{_traceback}{type(err).__name__}: {err}"
    return error if advance else f"{type(err).__name__}: {err}"


def snowflake_time(id: Union[int, "Snowflake"]) -> datetime:
    """
    Get the datetime from a discord snowflake

    Parameters
    ----------
    id: `int`
        The snowflake to get the datetime from

    Returns
    -------
    `datetime`
        The datetime of the snowflake
    """
    return datetime.fromtimestamp(
        ((int(id) >> 22) + DISCORD_EPOCH) / 1000,
        tz=timezone.utc
    )


def time_snowflake(dt: datetime, *, high: bool = False) -> int:
    """
    Get a discord snowflake from a datetime

    Parameters
    ----------
    dt: `datetime`
        The datetime to get the snowflake from
    high: `bool`
        Whether to get the high snowflake or not

    Returns
    -------
    `int`
        The snowflake of the datetime

    Raises
    ------
    `TypeError`
        Wrong timestamp type provided
    """
    if not isinstance(dt, datetime):
        raise TypeError(f"dt must be a datetime object, got {type(dt)} instead")

    return (
        int(dt.timestamp() * 1000 - DISCORD_EPOCH) << 22 +
        (2 ** 22 - 1 if high else 0)
    )


def parse_time(ts: str) -> datetime:
    """
    Parse a timestamp from a string

    Parameters
    ----------
    ts: `str`
        The timestamp to parse

    Returns
    -------
    `datetime`
        The datetime of the timestamp
    """
    return datetime.fromisoformat(ts)


def unicode_name(text: str) -> str:
    """
    Get the unicode name of a string

    Parameters
    ----------
    text: `str`
        The text to get the unicode name from

    Returns
    -------
    `str`
        The unicode name of the text
    """
    try:
        output = unicodedata.name(text)
    except TypeError:
        pass
    else:
        output = output.replace(" ", "_")

    return text


def divide_chunks(array: list[Any], n: int) -> list[list[Any]]:
    """
    Divide a list into chunks

    Parameters
    ----------
    array: `list[Any]`
        The list to divide
    n: `int`
        The amount of chunks to divide the list into

    Returns
    -------
    `list[list[Any]]`
        The divided list
    """
    return [
        array[i:i + n]
        for i in range(0, len(array), n)
    ]


def mime_type_image(image: bytes) -> str:
    """
    Get the mime type of an image

    Parameters
    ----------
    image: `bytes`
        The image to get the mime type from

    Returns
    -------
    `str`
        The mime type of the image

    Raises
    ------
    `ValueError`
        The image bytes provided is not supported sadly
    """
    match image:
        case x if x.startswith(b"\xff\xd8\xff"):
            return "image/jpeg"
        case x if x.startswith(b"\x89\x50\x4E\x47\x0D\x0A\x1A\x0A"):
            return "image/png"
        case x if x.startswith((b"\x47\x49\x46\x38\x37\x61", b"\x47\x49\x46\x38\x39\x61")):
            return "image/gif"
        case x if x.startswith(b"RIFF") and x[8:12] == b"WEBP":
            return "image/webp"
        case _:
            raise ValueError("Image bytes provided is not supported sadly")


def bytes_to_base64(image: Union[File, bytes]) -> str:
    """
    Convert bytes to base64

    Parameters
    ----------
    image: `Union[File, bytes]`
        The image to convert to base64

    Returns
    -------
    `str`
        The base64 of the image

    Raises
    ------
    `ValueError`
        The image provided is not supported sadly
    """
    if isinstance(image, File):
        image = image.data.read()
    elif isinstance(image, bytes):
        pass
    else:
        raise ValueError(
            "Attempted to parse bytes, was expecting "
            f"File or bytes, got {type(image)} instead."
        )

    return (
        f"data:{mime_type_image(image)};"
        f"base64,{b64encode(image).decode('ascii')}"
    )


def get_int(data: dict, key: str, *, default: Optional[Any] = None) -> Optional[int]:
    """
    Get an integer from a dictionary, similar to `dict.get`

    Parameters
    ----------
    data: `dict`
        The dictionary to get the integer from
    key: `str`
        The key to get the integer from
    default: `Optional[Any]`
        The default value to return if the key is not found

    Returns
    -------
    `Optional[int]`
        The integer from the dictionary

    Raises
    ------
    `ValueError`
        The key returned a non-digit value
    """
    output: Optional[str] = data.get(key, None)
    if output is None:
        return default
    if isinstance(output, int):
        return output
    if not output.isdigit():
        raise ValueError(f"Key {key} returned a non-digit value")
    return int(output)


class _MissingType:
    """
    A class to represent a missing value in a dictionary
    This is used in favour of accepting None as a value

    It is also filled with a bunch of methods to make it
    more compatible with other types and make pyright happy
    """
    def __init__(self) -> None:
        self.id: int = -1

    def __str__(self) -> str:
        return ""

    def __next__(self) -> None:
        return None

    def __iter__(self) -> Iterator:
        return self

    def __dict__(self) -> dict:
        return {}

    def items(self) -> dict:
        return {}

    def __int__(self) -> int:
        return -1

    def __bytes__(self) -> bytes:
        return bytes()

    def __eq__(self, other) -> bool:
        return False

    def __bool__(self) -> bool:
        return False

    def __repr__(self) -> str:
        return "<MISSING>"


MISSING: Any = _MissingType()


class Snowflake:
    """ A class to represent a Discord Snowflake """
    def __init__(self, *, id: int):
        if not isinstance(id, int):
            raise TypeError("id must be an integer")
        self.id: int = id

    def __str__(self) -> str:
        return str(self.id)

    def __int__(self) -> int:
        return self.id

    def __repr__(self) -> str:
        return f"<Snowflake id={self.id}>"

    def __eq__(self, other) -> bool:
        match other:
            case x if isinstance(x, Snowflake):
                return self.id == other.id
            case x if isinstance(x, int):
                return self.id == other
            case _:
                return False

    def __gt__(self, other) -> bool:
        match other:
            case x if isinstance(x, Snowflake):
                return self.id > other.id
            case x if isinstance(x, int):
                return self.id > other
            case _:
                raise TypeError(
                    f"Cannot compare 'Snowflake' to '{type(other).__name__}'"
                )

    def __lt__(self, other) -> bool:
        match other:
            case x if isinstance(x, Snowflake):
                return self.id < other.id
            case x if isinstance(x, int):
                return self.id < other
            case _:
                raise TypeError(
                    f"Cannot compare 'Snowflake' to '{type(other).__name__}'"
                )

    def __ge__(self, other) -> bool:
        match other:
            case x if isinstance(x, Snowflake):
                return self.id >= other.id
            case x if isinstance(x, int):
                return self.id >= other
            case _:
                raise TypeError(
                    f"Cannot compare 'Snowflake' to '{type(other).__name__}'"
                )

    def __le__(self, other) -> bool:
        match other:
            case x if isinstance(x, Snowflake):
                return self.id <= other.id
            case x if isinstance(x, int):
                return self.id <= other
            case _:
                raise TypeError(
                    f"Cannot compare 'Snowflake' to '{type(other).__name__}'"
                )

    @property
    def created_at(self) -> datetime:
        """ `datetime`: The datetime of the snowflake """
        return snowflake_time(self.id)


class Enum(enum.Enum):
    """ Enum, but with more comparison operators to make life easier """
    @classmethod
    def random(cls) -> Self:
        """ `Enum`: Return a random enum """
        return random.choice(list(cls))

    def __str__(self) -> str:
        """ `str` Return the name of the enum """
        return self.name

    def __int__(self) -> int:
        """ `int` Return the value of the enum """
        return self.value

    def __gt__(self, other) -> bool:
        """ `bool` Greater than """
        try:
            return self.value > other.value
        except Exception:
            pass
        try:
            if isinstance(other, numbers.Real):
                return self.value > other
        except Exception:
            pass
        return NotImplemented

    def __lt__(self, other) -> bool:
        """ `bool` Less than """
        try:
            return self.value < other.value
        except Exception:
            pass
        try:
            if isinstance(other, numbers.Real):
                return self.value < other
        except Exception:
            pass
        return NotImplemented

    def __ge__(self, other) -> bool:
        """ `bool` Greater than or equal to """
        try:
            return self.value >= other.value
        except Exception:
            pass
        try:
            if isinstance(other, numbers.Real):
                return self.value >= other
            if isinstance(other, str):
                return self.name == other
        except Exception:
            pass
        return NotImplemented

    def __le__(self, other) -> bool:
        """ `bool` Less than or equal to """
        try:
            return self.value <= other.value
        except Exception:
            pass
        try:
            if isinstance(other, numbers.Real):
                return self.value <= other
            if isinstance(other, str):
                return self.name == other
        except Exception:
            pass
        return NotImplemented

    def __eq__(self, other) -> bool:
        """ `bool` Equal to """
        if self.__class__ is other.__class__:
            return self.value == other.value
        try:
            return self.value == other.value
        except Exception:
            pass
        try:
            if isinstance(other, numbers.Real):
                return self.value == other
            if isinstance(other, str):
                return self.name == other
        except Exception:
            pass
        return NotImplemented


class CustomFormatter(logging.Formatter):
    reset = "\x1b[0m"

    # Normal colours
    white = "\x1b[38;21m"
    grey = "\x1b[38;5;240m"
    blue = "\x1b[38;5;39m"
    yellow = "\x1b[38;5;226m"
    red = "\x1b[38;5;196m"
    bold_red = "\x1b[31;1m"

    # Light colours
    light_white = "\x1b[38;5;250m"
    light_grey = "\x1b[38;5;244m"
    light_blue = "\x1b[38;5;75m"
    light_yellow = "\x1b[38;5;229m"
    light_red = "\x1b[38;5;203m"
    light_bold_red = "\x1b[38;5;197m"

    def __init__(self, datefmt: Optional[str] = None):
        super().__init__()
        self._datefmt = datefmt

    def _prefix_fmt(self, name: str, primary: str, secondary: str) -> str:
        if len(name) > 5:
            name = name[:5]

        return (
            f"{secondary}[ {primary}{name.rjust(5)}{self.reset} "
            f"{secondary}]{self.reset}"
        )

    def format(self, record: logging.LogRecord) -> str:
        """ Format the log """
        match record.levelno:
            case logging.DEBUG:
                prefix = self._prefix_fmt(
                    "DEBUG", self.grey, self.light_grey
                )

            case logging.INFO:
                prefix = self._prefix_fmt(
                    "INFO", self.blue, self.light_blue
                )

            case logging.WARNING:
                prefix = self._prefix_fmt(
                    "WARN", self.yellow, self.light_yellow
                )

            case logging.ERROR:
                prefix = self._prefix_fmt(
                    "ERROR", self.red, self.light_red
                )

            case logging.CRITICAL:
                prefix = self._prefix_fmt(
                    "CRIT", self.bold_red, self.light_bold_red
                )

            case _:
                prefix = self._prefix_fmt(
                    "OTHER", self.white, self.light_white
                )

        formatter = logging.Formatter(
            f"{prefix} {self.grey}%(asctime)s{self.reset} "
            f"%(message)s{self.reset}",
            datefmt=self._datefmt
        )

        return formatter.format(record)


def setup_logger(
    *,
    level: int = logging.INFO
) -> None:
    """
    Setup the logger

    Parameters
    ----------
    level: `Optional[int]`
        The level of the logger
    """
    lib, _, _ = __name__.partition(".")
    logger = logging.getLogger(lib)

    handler = logging.StreamHandler()
    formatter = CustomFormatter(datefmt="%Y-%m-%d %H:%M:%S")

    handler.setFormatter(formatter)
    logger.setLevel(level)
    logger.addHandler(handler)
