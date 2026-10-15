import aiohttp
import asyncio
import errno
import json
import logging
import random
import re
import sys
import time

from aiohttp.client_exceptions import ContentTypeError
from collections import deque
from urllib.parse import quote as url_quote
from typing import (
    Optional, Any, Union, Self, overload,
    Literal, TypeVar, Generic, TYPE_CHECKING
)

from . import __version__
from .errors import (
    NotFound, DiscordServerError,
    Forbidden, HTTPException, Ratelimited,
    AutomodBlock, Unauthorized
)

if TYPE_CHECKING:
    from .mentions import AllowedMentions
    from .user import User

MethodTypes = Literal["GET", "POST", "DELETE", "PUT", "HEAD", "PATCH", "OPTIONS"]
ResMethodTypes = Literal["text", "read", "json"]
ResponseT = TypeVar("ResponseT")

_log = logging.getLogger(__name__)

__all__ = (
    "DiscordAPI",
    "HTTPResponse",
)

_http_400_error_table: dict[int, type[HTTPException]] = {
    200000: AutomodBlock,
    200001: AutomodBlock,
}

_major_param_re = re.compile(r"^/(guilds|channels|webhooks|stage-instances)/(\d+)(?=/|$)")
_id_segment_re = re.compile(r"(?<=/)\d+(?=/|$)")
_token_route_re = re.compile(r"^/(interactions|webhooks)/(\d+)/([^/]+)")

# Only available in aiohttp 3.10 and newer
_connection_timeout_error: Optional[type[Exception]] = getattr(aiohttp, "ConnectionTimeoutError", None)


def _try_json(data: Any) -> Any:
    """ Try to parse the response as JSON, if it was not already """
    if isinstance(data, bytes):
        try:
            data = data.decode("utf-8")
        except UnicodeDecodeError:
            return data

    if isinstance(data, str):
        try:
            return json.loads(data)
        except json.JSONDecodeError:
            pass

    return data


def _is_retryable_error(method: str, error: OSError) -> bool:
    """ Whether a failed request can safely be sent again """
    if error.errno in (errno.ECONNRESET, errno.ECONNABORTED, 54, 10054):
        return True

    if (
        _connection_timeout_error is not None and
        isinstance(error, _connection_timeout_error)
    ):
        # Never connected, so Discord never got the request
        return True

    # Only retry read timeouts when sending the request twice is harmless
    return isinstance(error, TimeoutError) and method.upper() in ("GET", "HEAD")


class HTTPResponse(Generic[ResponseT]):
    def __init__(
        self,
        *,
        status: int,
        response: ResponseT,
        reason: str,
        res_method: ResMethodTypes,
        headers: dict[str, str],
    ):
        self.status = status
        self.response = response
        self.res_method = res_method
        self.reason = reason
        self.headers = headers

    def __repr__(self) -> str:
        return (
            f"<HTTPResponse status={self.status} "
            f"res_method='{self.res_method}'>"
        )


@overload
async def query(
    method: MethodTypes,
    url: str,
    *,
    res_method: Literal["text"],
    **kwargs
) -> HTTPResponse[str]:
    ...


@overload
async def query(
    method: MethodTypes,
    url: str,
    *,
    res_method: Literal["json"],
    **kwargs
) -> HTTPResponse[dict[Any, Any]]:
    ...


@overload
async def query(
    method: MethodTypes,
    url: str,
    *,
    res_method: Literal["read"],
    **kwargs
) -> HTTPResponse[bytes]:
    ...


async def query(
    method: MethodTypes,
    url: str,
    *,
    res_method: ResMethodTypes = "text",
    session: Optional[aiohttp.ClientSession] = None,
    **kwargs
) -> HTTPResponse:
    """
    Make a request using the aiohttp library

    Parameters
    ----------
    method: `Optional[str]`
        The HTTP method to use, defaults to GET
    url: `str`
        The URL to make the request to
    res_method: `Optional[str]`
        The method to use to get the response, defaults to text
    session: `Optional[aiohttp.ClientSession]`
        Session to make the request with, it is not closed afterwards.
        If not provided, a temporary session is used for this request only.

    Returns
    -------
    `HTTPResponse`
        The response from the request
    """
    if not res_method:
        res_method = "text"

    if res_method not in ("text", "read", "json"):
        raise ValueError(
            f"Invalid res_method: {res_method}, "
            "must be either text, read or json"
        )

    if session is not None:
        return await _request(session, method, url, res_method=res_method, **kwargs)

    async with aiohttp.ClientSession() as temp_session:
        return await _request(temp_session, method, url, res_method=res_method, **kwargs)


async def _request(
    session: aiohttp.ClientSession,
    method: MethodTypes,
    url: str,
    *,
    res_method: ResMethodTypes,
    **kwargs
) -> HTTPResponse:
    session_method = getattr(session, str(method).lower(), None)
    if not session_method:
        raise ValueError(f"Invalid HTTP method: {method}")

    async with session_method(str(url), **kwargs) as res:
        try:
            r = await getattr(res, res_method.lower())()
        except ContentTypeError:
            if res_method == "json":
                try:
                    r = json.loads(await res.text())
                except json.JSONDecodeError:
                    # Give up trying, something is really wrong...
                    r = await res.text()
                    res_method = "text"
            else:
                r = await res.text()
                res_method = "text"

        return HTTPResponse(
            status=res.status,
            response=r,
            res_method=res_method,
            reason=res.reason,
            headers=res.headers
        )


class Ratelimit:
    def __init__(self, key: str):
        self.key: str = key
        self.bucket_hash: Optional[str] = None

        self.limit: int = 1
        self.remaining: int = 1
        self.reset_after: float = 0.0
        self.expires: Optional[float] = None
        self.bucket_reset_epoch: float = 0.0
        self.in_flight: int = 0

        self._loop: asyncio.AbstractEventLoop = asyncio.get_running_loop()
        self._last_request: float = self._loop.time()
        self._pending: int = 0
        self._waiters: deque[asyncio.Future[None]] = deque()

    def __repr__(self) -> str:
        return (
            f"<Ratelimit key='{self.key}' limit={self.limit} "
            f"remaining={self.remaining} reset_after={self.reset_after:.2f} "
            f"bucket_hash={self.bucket_hash!r}>"
        )

    def is_inactive(self) -> bool:
        """ `bool`: Whether the bucket is unused and safe to remove """
        if self.in_flight > 0 or self._pending > 0:
            return False

        now = self._loop.time()
        if self.expires is not None and now < self.expires:
            # Still cooling down, removing it would let the next request
            # start from a fresh bucket and hit the ratelimit again
            return False

        return (now - self._last_request) >= 60

    def update(self, response: HTTPResponse) -> None:
        """ Update the ratelimit with the response headers """
        self._last_request = self._loop.time()
        headers = response.headers

        new_bucket_hash = headers.get("X-RateLimit-Bucket", None)
        if new_bucket_hash:
            self.bucket_hash = new_bucket_hash

        reset_epoch_str = headers.get("X-RateLimit-Reset", None)
        if not reset_epoch_str:
            return

        try:
            reset_epoch = float(reset_epoch_str)
            limit = int(headers.get("X-RateLimit-Limit", 1))
            remaining = int(headers.get("X-RateLimit-Remaining", 0))
            reset_after = float(headers.get("X-RateLimit-Reset-After", 0.0))
        except ValueError:
            return

        # Requests still in flight have taken a token locally,
        # but Discord has not counted them in this response yet
        unaccounted_in_flight = max(0, self.in_flight - 1)
        calculated_remaining = max(0, remaining - unaccounted_in_flight)

        if reset_epoch > self.bucket_reset_epoch + 0.5:
            # New bucket window
            self.bucket_reset_epoch = reset_epoch
            self.limit = max(1, limit)
            self.reset_after = reset_after
            # Never shorten a cooldown already set by a longer 429
            self.expires = max(self.expires or 0.0, self._loop.time() + reset_after)
            self.remaining = calculated_remaining

        elif abs(reset_epoch - self.bucket_reset_epoch) <= 0.5:
            # Same bucket window
            self.remaining = min(self.remaining, calculated_remaining)

    def _wake_waiters(self) -> None:
        while self._waiters:
            future = self._waiters.popleft()
            if not future.done():
                future.set_result(None)

    async def __aenter__(self) -> Self:
        self._pending += 1

        try:
            while True:
                now = self._loop.time()
                self._last_request = now

                if self.expires is not None and now >= self.expires:
                    self.remaining = self.limit
                    self.expires = None

                if self.remaining > 0:
                    self.remaining -= 1
                    self.in_flight += 1
                    return self

                if self.expires is not None:
                    wait_time = self.expires - now
                    _log.debug(f"Ratelimit bucket hit ({self.key}), waiting {wait_time:.2f}s...")
                    await asyncio.sleep(wait_time + 0.1)

                elif self.in_flight > 0:
                    # Bucket state is unknown until an in-flight request
                    # reports back, so wait for it instead of guessing
                    future = self._loop.create_future()
                    self._waiters.append(future)
                    try:
                        await future
                    finally:
                        if not future.done():
                            future.cancel()
                        try:
                            self._waiters.remove(future)
                        except ValueError:
                            pass

                else:
                    # No ratelimit info and nothing in flight to learn it from
                    # (e.g. last response had no ratelimit headers),
                    # let exactly one request through to find out
                    self.in_flight += 1
                    return self

        finally:
            self._pending -= 1

    async def __aexit__(self, type, value, traceback) -> None:
        self.in_flight -= 1
        self._wake_waiters()


class GlobalRatelimit:
    """
    Discord's global ratelimit, shared by all requests made with the same bot token.
    Interaction and webhook token routes are not part of it.
    """
    def __init__(self, *, max_requests: int = 50, per: float = 1.0):
        if max_requests < 1:
            raise ValueError("global_ratelimit must be 1 or higher")

        self.max: int = max_requests
        self.per: float = per
        self.locked_until: Optional[float] = None

        self._timestamps: deque[float] = deque()

    async def acquire(self) -> None:
        """ Wait until a request is allowed by the global ratelimit """
        loop = asyncio.get_running_loop()

        while True:
            now = loop.time()

            if self.locked_until is not None and now < self.locked_until:
                wait_time = self.locked_until - now
            else:
                self.locked_until = None

                while self._timestamps and now - self._timestamps[0] >= self.per:
                    self._timestamps.popleft()

                if len(self._timestamps) < self.max:
                    self._timestamps.append(now)
                    return

                wait_time = self.per - (now - self._timestamps[0])

            await asyncio.sleep(max(wait_time, 0.01))

    def lock_for(self, retry_after: float) -> None:
        """ Pause all requests, used when Discord reports a global ratelimit """
        locked_until = asyncio.get_running_loop().time() + retry_after
        self.locked_until = max(self.locked_until or 0.0, locked_until)


class DiscordAPI:
    def __init__(
        self,
        *,
        token: str,
        application_id: Optional[int],
        api_version: Optional[int] = None,
        global_ratelimit: int = 50
    ):
        self.token: str = token
        self.application_id: Optional[int] = application_id

        self.api_version: int = api_version or 10
        if not isinstance(self.api_version, int):
            raise TypeError("api_version must be an integer")

        self.base_url: str = "https://discord.com/api"
        self.api_url: str = f"{self.base_url}/v{self.api_version}"

        self._buckets: dict[str, Ratelimit] = {}
        self._bucket_hashes: dict[str, tuple[str, float]] = {}
        self._global_ratelimit: GlobalRatelimit = GlobalRatelimit(
            max_requests=global_ratelimit
        )
        self._last_cleanup: float = time.monotonic()
        self._session: Optional[aiohttp.ClientSession] = None

        # Set by Client, used when sending messages without allowed_mentions
        self._default_allowed_mentions: Optional["AllowedMentions"] = None

    def _get_session(self) -> aiohttp.ClientSession:
        """
        Get the session used for Discord API requests.
        It is created on first use, since it needs a running event loop.
        """
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession(
                connector=aiohttp.TCPConnector(
                    limit=0,  # Ratelimits already limit the amount of requests
                    keepalive_timeout=15
                ),
                timeout=aiohttp.ClientTimeout(
                    total=60,
                    sock_connect=10,
                    sock_read=30
                )
            )

        return self._session

    async def close(self) -> None:
        """ Close the session used for Discord API requests """
        if self._session is not None and not self._session.closed:
            await self._session.close()
        self._session = None

    def _clear_old_ratelimits(self) -> None:
        self._last_cleanup = time.monotonic()

        for key in [k for k, v in self._buckets.items() if v.is_inactive()]:
            try:
                del self._buckets[key]
            except KeyError:
                pass

        # A bucket still in use must stay reachable through its hash
        live_hashes = {v.bucket_hash for v in self._buckets.values()}
        stale_routes = [
            route for route, (bucket_hash, last_seen) in self._bucket_hashes.items()
            if self._last_cleanup - last_seen >= 60 and bucket_hash not in live_hashes
        ]

        for route in stale_routes:
            self._bucket_hashes.pop(route, None)

    @staticmethod
    def _apply_bucket_quirks(method: str, normalized: str) -> str:
        # Deleting messages has its own bucket on Discord's side
        if method == "DELETE" and normalized.endswith("/messages/:id"):
            return normalized + "-delete"
        return normalized

    def _get_bucket_key(self, method: str, path: str) -> str:
        """
        Get the bucket key guessed from the path.
        The major parameter (guild/channel/webhook ID) and
        interaction/webhook tokens are kept, every other ID is collapsed.
        """
        base_path = path.partition("?")[0]

        if token_match := _token_route_re.match(base_path):
            prefix = token_match.group(0)
            remainder = base_path[token_match.end():]
        elif major_match := _major_param_re.match(base_path):
            prefix = major_match.group(0)
            remainder = base_path[major_match.end():]
        else:
            prefix = ""
            remainder = base_path

        normalized = self._apply_bucket_quirks(
            method, prefix + _id_segment_re.sub(":id", remainder)
        )

        return f"{method} {normalized}"

    def _route_template(self, method: str, path: str) -> str:
        """ Get the route with every ID and token collapsed """
        base_path = path.partition("?")[0]
        base_path = _token_route_re.sub(r"/\1/\2/:token", base_path, count=1)
        normalized = self._apply_bucket_quirks(
            method, _id_segment_re.sub(":id", base_path)
        )
        return f"{method} {normalized}"

    @staticmethod
    def _major_param_value(path: str) -> str:
        """
        Get the major parameter of the path, or an empty string if there is none.
        Interaction/webhook tokens are included, since every token has its own bucket.
        """
        base_path = path.partition("?")[0]

        if token_match := _token_route_re.match(base_path):
            return f"{token_match.group(2)}:{token_match.group(3)}"

        if major_match := _major_param_re.match(base_path):
            return major_match.group(2)

        return ""

    def _resolve_bucket_key(self, method: str, path: str) -> tuple[str, str, str]:
        """
        Resolve which bucket a request should use.
        Once Discord has told us the bucket hash of a route, routes sharing
        that hash (and major parameter) also share the same bucket.

        Returns
        -------
        `tuple[str, str, str]`
            The route template, the bucket key and the path-guessed fallback key
        """
        route_template = self._route_template(method, path)
        fallback_key = self._get_bucket_key(method, path)

        cached = self._bucket_hashes.get(route_template, None)
        if cached:
            major_param = self._major_param_value(path)
            key = f"{method} #{cached[0]}"
            if major_param:
                key += f":{major_param}"
        else:
            key = fallback_key

        return route_template, key, fallback_key

    def get_ratelimit(
        self,
        key: str,
        *,
        migrate_from: Optional[str] = None
    ) -> Ratelimit:
        """
        Get the ratelimit bucket for the given key

        Parameters
        ----------
        key: `str`
            The bucket key
        migrate_from: `Optional[str]`
            Previous key of the bucket, its state is moved over to the new key

        Returns
        -------
        `Ratelimit`
            The ratelimit bucket
        """
        if time.monotonic() - self._last_cleanup >= 60:
            self._clear_old_ratelimits()

        try:
            return self._buckets[key]
        except KeyError:
            pass

        if migrate_from and migrate_from != key:
            old = self._buckets.pop(migrate_from, None)
            if old is not None:
                old.key = key
                self._buckets[key] = old
                return old

        self._buckets[key] = value = Ratelimit(key)
        return value

    @staticmethod
    def _retry_delay(error_tries: int) -> float:
        return 1 + (error_tries - 1) * 2 + random.random()

    @overload
    async def query(
        self,
        method: MethodTypes,
        path: str,
        *,
        res_method: Literal["json"] = "json",
        **kwargs
    ) -> HTTPResponse[dict[Any, Any]]:
        ...

    @overload
    async def query(
        self,
        method: MethodTypes,
        path: str,
        *,
        res_method: Literal["read"] = "read",
        **kwargs
    ) -> HTTPResponse[bytes]:
        ...

    @overload
    async def query(
        self,
        method: MethodTypes,
        path: str,
        *,
        res_method: Literal["text"] = "text",
        **kwargs
    ) -> HTTPResponse[str]:
        ...

    async def query(
        self,
        method: MethodTypes,
        path: str,
        *,
        res_method: ResMethodTypes = "json",
        **kwargs
    ) -> HTTPResponse:
        """
        Make a request to the Discord API

        Parameters
        ----------
        method: `str`
            Which HTTP method to use
        path: `str`
            The path to make the request to
        res_method: `str`
            The method to use to get the response

        Returns
        -------
        `HTTPResponse`
            The response from the request

        Raises
        ------
        `ValueError`
            Invalid HTTP method
        `DiscordServerError`
            Something went wrong on Discord's end
        `Forbidden`
            You are not allowed to do this
        `NotFound`
            The resource was not found
        `Unauthorized`
            The bot token is invalid or was revoked
        `Ratelimited`
            Ratelimited by CloudFlare, or by Discord too many times in a row
        `HTTPException`
            Something went wrong
        """
        if "headers" not in kwargs:
            kwargs["headers"] = {}

        if "Authorization" not in kwargs["headers"]:
            kwargs["headers"]["Authorization"] = f"Bot {self.token}"

        if res_method == "json" and "Content-Type" not in kwargs["headers"]:
            kwargs["headers"]["Content-Type"] = "application/json"

        kwargs["headers"]["User-Agent"] = "discord.http/{0} Python/{1} aiohttp/{2}".format(
            __version__,
            ".".join(str(i) for i in sys.version_info[:3]),
            aiohttp.__version__
        )

        reason = kwargs.pop("reason", None)
        if reason:
            kwargs["headers"]["X-Audit-Log-Reason"] = url_quote(str(reason))

        _api_url = self.api_url
        if kwargs.pop("webhook", False):
            _api_url = self.base_url

        # Interaction and webhook token routes are not part of the global ratelimit
        exempt_from_global = bool(_token_route_re.match(path.partition("?")[0]))

        route_template, bucket_key, fallback_key = self._resolve_bucket_key(method, path)
        ratelimit = self.get_ratelimit(bucket_key, migrate_from=fallback_key)

        error_tries = 0
        ratelimit_tries = 0

        while True:
            retry_delay = 0.0

            async with ratelimit:
                if not exempt_from_global:
                    # Acquired right before sending, so the global window
                    # counts requests when they are actually sent
                    await self._global_ratelimit.acquire()

                try:
                    r: HTTPResponse = await query(
                        method,
                        f"{_api_url}{path}",
                        res_method=res_method,
                        session=self._get_session(),
                        **kwargs
                    )

                except OSError as e:
                    # Note: TimeoutError is also an OSError
                    if error_tries >= 4 or not _is_retryable_error(method, e):
                        raise

                    error_tries += 1
                    retry_delay = self._retry_delay(error_tries)
                    _log.debug(
                        f"HTTP {method.upper()} {path} failed with {e!r}, "
                        f"retrying in {retry_delay:.2f}s (attempt {error_tries + 1}/5)"
                    )

                else:
                    ratelimit.update(r)

                    new_bucket_hash = r.headers.get("X-RateLimit-Bucket", None)
                    if new_bucket_hash:
                        self._bucket_hashes[route_template] = (new_bucket_hash, time.monotonic())

                    _log.debug(f"HTTP {method.upper()} ({r.status}): {path}")

                    match r.status:
                        case x if x >= 200 and x <= 299:
                            return r

                        case 429:
                            response = _try_json(r.response)
                            if not isinstance(response, dict):
                                # For cases where you're ratelimited by CloudFlare
                                raise Ratelimited(r)

                            ratelimit_tries += 1
                            if ratelimit_tries > 10:
                                _log.error(f"Ratelimit hit ({fallback_key}) 10 times in a row, giving up")
                                raise Ratelimited(r)

                            try:
                                retry_after = float(response.get("retry_after", 1.0))
                            except (TypeError, ValueError):
                                retry_after = 1.0

                            if response.get("global", False):
                                _log.warning(f"Global ratelimit hit, pausing all requests for {retry_after:.2f}s...")
                                self._global_ratelimit.lock_for(retry_after)
                                if exempt_from_global:
                                    retry_delay = retry_after
                            else:
                                _log.warning(f"Ratelimit hit ({fallback_key}), waiting {retry_after:.2f}s...")
                                # The longest wait must win, if several 429s arrive at once
                                ratelimit.remaining = 0
                                ratelimit.expires = max(
                                    ratelimit.expires or 0.0,
                                    ratelimit._loop.time() + retry_after
                                )

                        case x if x in (500, 502, 503, 504):
                            if error_tries >= 4:  # Give up after 5 tries
                                raise DiscordServerError(r)

                            # Try again, maybe it will work next time, surely...
                            error_tries += 1
                            retry_delay = self._retry_delay(error_tries)

                        case 400:
                            response = _try_json(r.response)
                            code = response.get("code", 0) if isinstance(response, dict) else 0
                            raise _http_400_error_table.get(code, HTTPException)(r)

                        case 401:
                            _log.error("HTTP 401: The bot token is invalid or was revoked")
                            raise Unauthorized(r)

                        case 403:
                            raise Forbidden(r)

                        case 404:
                            raise NotFound(r)

                        case _:
                            raise HTTPException(r)

            # Wait outside the bucket, so other requests are not held up
            if retry_delay > 0:
                await asyncio.sleep(retry_delay)

    async def me(self) -> "User":
        """ `User`: Fetches the bot's user information """
        r = await self.query("GET", "/users/@me")

        from .user import User
        return User(
            state=self,
            data=r.response
        )

    async def _app_command_query(
        self,
        method: MethodTypes,
        guild_id: Optional[int] = None,
        **kwargs
    ) -> HTTPResponse:
        """
        Used to query the application commands
        Mostly used internally by the library

        Parameters
        ----------
        method: `MethodTypes`
            The HTTP method to use
        guild_id: `Optional[int]`
            The guild ID to query the commands for

        Returns
        -------
        `HTTPResponse`
            The response from the request
        """
        if not self.application_id:
            raise ValueError("application_id is required to sync commands")

        url = f"/applications/{self.application_id}/commands"
        if guild_id:
            url = f"/applications/{self.application_id}/guilds/{guild_id}/commands"

        try:
            r = await self.query(method, url, res_method="json", **kwargs)
        except HTTPException as e:
            r = e.request

        return r

    async def update_commands(
        self,
        data: Union[list[dict], dict],
        guild_id: Optional[int] = None
    ) -> dict:
        """
        Updates the commands for the bot

        Parameters
        ----------
        data: `list[dict]`
            The JSON data to send to Discord API
        guild_id: `Optional[int]`
            The guild ID to update the commands for (if None, commands will be global)

        Returns
        -------
        `dict`
            The response from the request
        """
        r = await self._app_command_query(
            "PUT",
            guild_id=guild_id,
            json=data
        )

        target = f"for Guild:{guild_id}" if guild_id else "globally"

        if r.status >= 200 and r.status <= 299:
            _log.info(f"🔁 Successfully synced commands {target}")
        else:
            _log.warn(f"🔁 Failed to sync commands {target}: {r.response}")

        return r.response

    async def fetch_commands(
        self,
        guild_id: Optional[int] = None
    ) -> dict:
        """
        Fetches the commands for the bot

        Parameters
        ----------
        guild_id: `Optional[int]`
            The guild ID to fetch the commands for (if None, commands will be global)

        Returns
        -------
        `dict`
            The response from the request
        """
        r = await self._app_command_query(
            "GET",
            guild_id=guild_id
        )

        return r.response
