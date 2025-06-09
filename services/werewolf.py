import enum
from dataclasses import dataclass
from typing import Dict, List

import discord


# 役職
class Role(enum.Enum):
    # 村人陣営
    VILLAGER = "VILLAGER"  # 村人
    KNIGHT = "KNIGHT"  # 騎士
    TELLER = "TELLER"  # 占い師
    PSYCHIC = "PSYCHIC"  # 霊能者
    BAKERY = "BAKERY"  # パン屋
    # 人狼陣営
    WEREWOLF = "WEREWOLF"  # 人狼
    MADMAN = "MADMAN"  # 狂人
    # 第三陣営
    FOX = "FOX"  # 妖狐


# 陣営
class RoleType(enum.Enum):
    VILLAGER = "VILLAGER"  # 村人
    WEREWOLF = "WEREWOLF"  # 人狼
    OTHER = "OTHER"  # 第三陣営


# 役職 → 陣営 の対応表
ROLE_TO_TYPE = {
    # 村人陣営
    Role.VILLAGER: RoleType.VILLAGER,
    Role.KNIGHT: RoleType.VILLAGER,
    Role.TELLER: RoleType.VILLAGER,
    Role.PSYCHIC: RoleType.VILLAGER,
    Role.BAKERY: RoleType.VILLAGER,
    # 人狼陣営
    Role.WEREWOLF: RoleType.WEREWOLF,
    Role.MADMAN: RoleType.WEREWOLF,
    # 第三陣営
    Role.FOX: RoleType.OTHER,
}


def getRoleType(role: Role) -> RoleType:
    return ROLE_TO_TYPE[role]


@dataclass(slots=True, weakref_slot=True)
class Member:
    member: discord.Member
    role: Role
    roleType: RoleType
    dead: bool


class Game:
    entries: List[discord.Member] = []
    members: List[Member] = []
    channels: List[discord.VoiceChannel] = []
    cast: Dict[Role, int] = {}
    werewolfTarget: discord.Member = None
    day: int = 0
    inGame: bool = False

    @classmethod
    def reset(cls):
        cls.entries = []
        cls.members = []
        cls.channels = []
        cls.day = 0
        cls.werewolfTarget = None
        cls.inGame = False
