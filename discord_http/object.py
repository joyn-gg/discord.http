from . import utils

__all__ = (
    "PartialBase",
)


class PartialBase(utils.Snowflake):
    """
    A base class for partial objects.
    This class is based on the Snowflae class standard,
    but with a few extra attributes.
    """
    def __init__(self, *, id: int):
        super().__init__(id=int(id))

    def __repr__(self) -> str:
        return f"<PartialBase id={self.id}>"

    @property
    def is_partial(self) -> bool:
        """
        `bool`: Returns True if the object is partial
        This depends on the class name starting with Partial or not.
        """
        if self.__class__.__name__.startswith("Partial"):
            return True
        return False
