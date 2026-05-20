from typing import Optional

from attrs import define

from ..common import *

__all__ = [
    "LichWeapon",
    "LichEphemera",
    "LichQuirk",
]


@define
class LichWeapon(ModelBase):
    id: str
    slug: str
    gameRef: str
    reqMasteryRank: int
    name: str
    icon: str
    thumb: str

    @classmethod
    def from_dict(cls, data: dict) -> "ItemShort":
        return cls(
            id=data["id"],
            slug=data["slug"],
            gameRef=data["gameRef"],
            reqMasteryRank=data["reqMasteryRank"],
            thumb=data["i18n"]["en"]["thumb"],
            name=data["i18n"]["en"]["name"],
            icon=data["i18n"]["en"]["icon"],
        )


@define
class LichEphemera(ModelBase):
    id: str
    slug: str
    gameRef: str
    icon: str
    thumb: str
    animation: str
    element: ElementType
    name: str

    @classmethod
    def from_dict(cls, data: dict) -> "ItemShort":
        return cls(
            id=data["id"],
            slug=data["slug"],
            gameRef=data["gameRef"],
            animation=data["animation"],
            element=data["element"],
            thumb=data["i18n"]["en"]["thumb"],
            name=data["i18n"]["en"]["name"],
            icon=data["i18n"]["en"]["icon"],
        )


@define
class LichQuirk(ModelBase):
    id: str
    slug: str
    name: str
    thumb: str
    description: str
    group: str
    icon: str

    @classmethod
    def from_dict(cls, data: dict) -> "ItemShort":
        return cls(
            id=data["id"],
            slug=data["slug"],
            group=data["group"],
            thumb=data["i18n"]["en"]["thumb"],
            name=data["i18n"]["en"]["name"],
            icon=data["i18n"]["en"]["icon"],
            description=data["i18n"]["en"]["description"],
        )
