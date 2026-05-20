from datetime import datetime
from typing import List, Optional

from attrs import define, field

from ..auth.models import UserShort
from ..common import *

__all__ = [
    "OrderType",
    "OrderCommon",
    "OrderRow",
    "OrderItem",
    # "OrderFull",
    "OrderNewItemBase",
    "OrderNewItem",
    "OrderUpdateItem",
]


@define
class OrderCommon(ModelBase):
    id: str
    platinum: int
    quantity: int
    type: OrderType
    visible: bool
    perTrade: Optional[int] = None
    itemId: Optional[str] = None
    platform: Optional[Platform] = None
    locale: Optional[str] = None
    createdAt: Optional[datetime] = None
    updatedAt: Optional[datetime] = None
    subtype: Optional[Subtype] = None
    mod_rank: Optional[int] = None
    ingameName: Optional[str] = None
    reputation: Optional[int] = None
    userId: Optional[str] = None

    @classmethod
    def from_dict(cls, data: dict) -> "OrderCommon":
        user_data = data.get("user")

        return cls(
            id=data.get("id"),
            platinum=data.get("platinum"),
            quantity=data.get("quantity"),
            type=data.get("type"),
            visible=data.get("visible"),
            perTrade=data.get("perTrade"),
            itemId=data.get("itemId"),
            userId=user_data.get("id"),
            ingameName=user_data.get("ingameName"),
            platform=user_data.get("platform"),
            locale=user_data.get("locale"),
            reputation=user_data.get("reputation"),
            subtype=data.get("subtype"),
            createdAt=datetime.fromisoformat((data.get("createdAt")).replace("Z", "+00:00")),
            updatedAt=datetime.fromisoformat((data.get("updatedAt").replace("Z", "+00:00"))),
        )


@define(kw_only=True)
class OrderRow(OrderCommon):
    user: UserShort

    @define
    class UserShort:
        class Status(Enum):
            ingame = "ingame"
            online = "online"
            offline = "offline"

        id: str
        status: Status
        locale: str
        reputation: int
        lastSeen: datetime
        ingameName: Optional[str] = None
        """In-game name. Only get this field when `verification=True`."""
        avatar: Optional[str] = None

    @classmethod
    def from_dict(cls, data: dict) -> "OrderRow":
        return cls(
            id=data.get("id"),
            platinum=data.get("platinum"),
            quantity=data.get("quantity"),
            type=data.get("type"),
            visible=data.get("visible"),
            user=cls.UserShort(
                data.get("user"),
                status=ProfileStatus(data.get("status")) if data.get("status") else None,
                locale=data.get("locale"),
                lastSeen=(
                    datetime.fromisoformat(data.get("lastSeen").replace("Z", "+00:00"))
                    if data.get("lastSeen")
                    else None
                ),
                reputation=data.get("reputation"),
                avatar=data.get("avatar"),
            ),
            ingameName=data.get("ingameName"),
        )


@define(kw_only=True)
class OrderItem(OrderCommon):
    @define
    class ItemInOrder(ModelBase):
        @define
        class LangInOrderItem:
            item_name: str

        id: str
        url_name: str
        icon: str
        thumb: str
        # only for relics and fishes
        tags: List[str]
        sub_icon: Optional[str] = None
        quantity_for_set: Optional[int] = None
        mod_max_rank: Optional[int] = None
        subtypes: Optional[List[str]] = None
        cyan_stars: Optional[int] = None
        amber_stars: Optional[int] = None
        ducats: Optional[int] = None
        # language items
        en: Optional[LangInOrderItem] = None
        ru: Optional[LangInOrderItem] = None
        ko: Optional[LangInOrderItem] = None
        de: Optional[LangInOrderItem] = None
        fr: Optional[LangInOrderItem] = None
        pt: Optional[LangInOrderItem] = None
        zh_hant: Optional[LangInOrderItem] = None
        zh_hans: Optional[LangInOrderItem] = None
        es: Optional[LangInOrderItem] = None
        it: Optional[LangInOrderItem] = None
        pl: Optional[LangInOrderItem] = None

    item: ItemInOrder
    user: Optional[UserShort] = None
    platform: Optional[Platform] = None


@define(kw_only=True)
class OrderFull(OrderRow):
    # TODO
    def __init__(self):
        raise NotImplementedError()


@define(kw_only=True)
class OrderNewItemBase(ModelBase):
    platinum: int
    quantity: int
    visible: bool
    rank: Optional[int] = None
    subtype: Optional[Subtype] = None


@define(kw_only=True)
class OrderNewItem(OrderNewItemBase):
    """
    Request class for ``orders.add_new_order`` and others.
    """

    item_id: str
    type: OrderType


@define(kw_only=True)
class OrderUpdateItem(OrderNewItemBase):
    """
    Request class for ``orders.update_order``
    """

    pass
