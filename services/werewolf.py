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

# 役職 → 名前 の対応表
ROLE_TO_NAME = {
    # 村人陣営
    Role.VILLAGER: "村人",
    Role.KNIGHT: "騎士",
    Role.TELLER: "占い師",
    Role.PSYCHIC: "霊能者",
    Role.BAKERY: "パン屋",
    # 人狼陣営
    Role.WEREWOLF: "人狼",
    Role.MADMAN: "狂人",
    # 第三陣営
    Role.FOX: "妖狐",
}


def getRoleType(role: Role) -> RoleType:
    return ROLE_TO_TYPE[role]


def getRoleName(role: Role) -> str:
    return ROLE_TO_NAME[role]


@dataclass(slots=True, weakref_slot=True)
class Member:
    member: discord.Member
    role: Role
    roleType: RoleType
    dead: bool


class Scene(enum.Enum):
    NIGHT = "NIGHT"
    DAY = "DAY"
    EVENING = "EVENING"


class Game:
    entries: List[discord.Member] = []
    members: List[Member] = []
    channels: List[discord.VoiceChannel] = []
    cast: Dict[Role, int] = {}
    days: int = 0
    inGame: bool = False
    scene: Scene = Scene.NIGHT
    seconds = 0
    werewolfTarget: discord.Member = None
    tellerTarget: Dict[discord.Member, discord.Member] = None
    knightTarget: Dict[discord.Member, discord.Member] = None

    @classmethod
    def reset(cls):
        cls.entries = []
        cls.members = []
        cls.channels = []
        cls.days = 0
        cls.inGame = False
        cls.scene = Scene.NIGHT
        cls.seconds = 0
        cls.werewolfTarget = None
        cls.tellerTarget = None
        cls.knightTarget = None
