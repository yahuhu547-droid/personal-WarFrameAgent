from enum import Enum
from typing import List, Optional

from attrs import define

from ..common import *

__all__ = [
    "RivenItem",
    "RivenAttribute",
]


@define
class RivenItem(ModelBase):
    class Group(Enum):
        primary = "primary"
        secondary = "secondary"
        melee = "melee"
        zaw = "zaw"
        sentinel = "sentinel"
        archgun = "archgun"
        kitgun = "kitgun"

    id: str
    name: str
    slug: str
    gameRef: str
    group: Group
    rivenType: WeaponType
    icon: str
    thumb: str
    disposition: float
    reqMasteryRank: int

    @classmethod
    def from_dict(cls, data: dict) -> "RivenItem":
        return cls(
            id=data["id"],
            name=data["i18n"]["en"]["name"],
            slug=data["slug"],
            gameRef=data["gameRef"],
            group=cls.Group(data["group"]),
            rivenType=data["rivenType"],
            icon=data["i18n"]["en"]["icon"],
            thumb=data["i18n"]["en"]["thumb"],
            disposition=data["disposition"],
            reqMasteryRank=data["reqMasteryRank"],
        )


@define
class RivenAttribute(ModelBase):
    class Group(Enum):
        default = "default"
        melee = "melee"
        top = "top"

    class Unit(Enum):
        percent = "percent"
        seconds = "seconds"
        # Not know what this is
        multiply = "multiply"

    id: str
    slug: str
    name: str
    gameRef: str
    group: Group
    icon: str
    thumb: str
    unit: Optional[Unit] = None
    prefix: Optional[str] = None
    suffix: Optional[str] = None
    exclusiveTo: Optional[List[WeaponType]] = None
    positiveIsNegative: Optional[bool] = False
    positiveOnly: Optional[bool] = False
    negativeOnly: Optional[bool] = False

    @classmethod
    def from_dict(cls, data: dict) -> "RivenAttribute":
        return cls(
            id=data["id"],
            slug=data["slug"],
            name=data["i18n"]["en"]["name"],
            gameRef=data["gameRef"],
            group=cls.Group(data["group"]),
            positiveIsNegative=data.get("positiveIsNegative"),
            positiveOnly=data.get("positiveOnly"),
            negativeOnly=data.get("negativeOnly"),
            prefix=data.get("prefix"),
            suffix=data.get("suffix"),
            exclusiveTo=data.get("exclusiveTo"),
            unit=cls.Unit(data.get("unit")) if data.get("unit") else None,
            icon=data["i18n"]["en"]["icon"],
            thumb=data["i18n"]["en"]["thumb"],
        )
