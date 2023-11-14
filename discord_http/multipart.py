import json
import io

from typing import Union, Optional

from .file import File

__all__ = (
    "MultipartData",
)


class MultipartData:
    def __init__(self):
        self.boundary = "---------------discord.http"
        self.bufs: list[bytes] = []

    @property
    def content_type(self) -> str:
        """ `str`: The content type of the multipart data """
        return f"multipart/form-data; boundary={self.boundary}"

    def attach(
        self,
        name: str,
        data: Union[File, io.BufferedIOBase, dict, str],
        filename: Optional[str] = None,
        content_type: Optional[str] = None
    ) -> None:
        """
        Attach data to the multipart data

        Parameters
        ----------
        name: `str`
            Name of the file data
        data: `Union[File, io.BufferedIOBase, dict, str]`
            The data to attach
        filename: `Optional[str]`
            Filename to be sent on Discord
        content_type: `Optional[str]`
            The content type of the file data
        """
        if not data:
            return None

        string = f"\r\n--{self.boundary}\r\nContent-Disposition: form-data; name=\"{name}\""
        if filename:
            string += f"; filename=\"{filename}\""

        if isinstance(data, File):
            string += f"\r\nContent-Type: {content_type or 'application/octet-stream'}\r\n\r\n"
            data = data.data
        elif isinstance(data, io.BufferedIOBase):
            string += f"\r\nContent-Type: {content_type or 'application/octet-stream'}\r\n\r\n"
        elif isinstance(data, dict):
            string += "\r\nContent-Type: application/json\r\n\r\n"
            data = json.dumps(data)
        else:
            string += "\r\n\r\n"
            data = str(data)

        self.bufs.append(string.encode("utf8"))
        self.bufs.append(
            data.read()
            if isinstance(data, io.BufferedIOBase)
            else data.encode("utf8")
        )

        return None

    def finish(self) -> bytes:
        """ `bytes`: Return the multipart data to be sent to Discord """
        self.bufs.append(f"\r\n--{self.boundary}--\r\n".encode("utf8"))
        return b"".join(self.bufs)
