import asyncio
import enum
import os
import random

import discord
import dotenv
from discord import app_commands
from discord.ext import commands

from services.werewolf import (
    Game,
    Member,
    Role,
    RoleType,
    Scene,
    getRoleName,
    getRoleType,
)

dotenv.load_dotenv()


class EndType(enum.Enum):
    NOTEND = "NOTEND"
    WONWOLFS = "WONWOLF"
    WONVILAGGERS = "WONVILAGGERS"
    WONFOX = "WONFOX"


ENDCHAR = {
    EndType.WONWOLFS: "村人が全滅したため、人狼の勝利！",
    EndType.WONVILAGGERS: "人狼が全滅したため、村人の勝利！",
    EndType.WONFOX: "妖狐が生き残っていたため、妖狐の勝利！",
}


class WerewolfCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.notificationChannel: discord.VoiceChannel = None
        self.lobbyChannel: discord.VoiceChannel = None
        self.werewolfChannel: discord.VoiceChannel = None

    @commands.Cog.listener()
    async def on_ready(self):
        self.notificationChannel = self.bot.get_channel(
            os.getenv("notificationChannel")
        )
        self.lobbyChannel = self.bot.get_channel(os.getenv("lobbyChannel"))

    async def moveToRoleVoice(self):
        for member in Game.members:
            dmember = member.member
            if member.role == Role.WEREWOLF:
                await dmember.move_to(discord.utils.get(Game.channels, name="人狼"))
            else:
                await dmember.move_to(
                    discord.utils.get(Game.channels, name=str(dmember.id))
                )
            await dmember.edit(mute=False)

    async def moveToLobby(self):
        for member in Game.members:
            dmember = member.member
            await dmember.move_to(self.lobbyChannel)
            if member.dead:
                await dmember.edit(mute=True)

    def ifEnd(self):
        werewolf = len(
            [member for member in Game.members if member.role == Role.WEREWOLF]
        )
        villagers = len(
            [member for member in Game.members if member.roleType == RoleType.VILLAGER]
        )
        foxies = len([member for member in Game.members if member.role == Role.FOX])

        # 村人の勝利か・妖狐の勝利か
        if werewolf == 0:
            if foxies > 0:
                return EndType.WONFOX
            else:
                return EndType.WONVILAGGERS

        # 人狼の勝利か・妖狐の勝利か
        if villagers <= werewolf:
            if foxies > 0:
                return EndType.WONFOX
            else:
                return EndType.WONWOLFS

        return EndType.NOTEND

    async def end(self, endType: EndType):
        await self.notificationChannel.send(ENDCHAR[endType])
        await self.notificationChannel.send(
            "\n".join(
                [
                    f"{member.member.mention} - {getRoleName(member.role)}"
                    for member in Game.members
                ]
            )
        )

        for channel in Game.channels:
            await channel.delete()
        self.werewolfChannel = None

        await self.lobbyChannel.edit(
            overwrites={
                self.lobbyChannel.guild.default_role: discord.PermissionOverwrite(
                    view_channel=False
                ),
            }
        )

        Game.reset()

    async def game(self):
        match Game.scene:
            case Scene.NIGHT:
                Game.seconds = 120

                # 自分のボイスチャンネルor人狼ボイスチャンネルに移動
                await self.moveToRoleVoice()

                await self.werewolfChannel.send(
                    f"夜になりました。仲間と話し合って、村人を一人噛み殺してください。{'(初日は誰も噛み殺せません)' if Game.days == 0 else ''}"
                )
                while Game.seconds <= 0:
                    Game.seconds -= 1
                    await asyncio.sleep(1)

                # 人狼がターゲットを選択しなかった場合
                if not Game.werewolfTarget:
                    await self.werewolfChannel.send(
                        "選択されなかったため、ランダムに噛み殺します。"
                    )
                    Game.werewolfTarget = random.choice(
                        [
                            member.member
                            for member in Game.members
                            if not member.dead and member.role != Role.WEREWOLF
                        ]
                    )

                # 占い師の処理
                for teller, target in Game.tellerTarget.items():
                    if not target:
                        continue

                    if (
                        discord.utils.get(Game.members, member=target).roleType
                        == RoleType.WEREWOLF
                    ):
                        char = f"{target.mention} は人狼です"
                    else:
                        char = f"{target.mention} は人狼ではありません"

                    await discord.utils.get(
                        Game.channels,
                        name=str(teller.id),
                    ).send(char)

                # 騎士の処理(騎士が守れなかった場合は殺害処理)
                if Game.werewolfTarget in Game.knightTarget.values():
                    await self.notificationChannel.send("騎士が人狼から村人を守った！")
                else:
                    discord.utils.get(Game.members, member=Game.werewolfTarget).dead = (
                        True
                    )

                if endType := self.ifEnd() != EndType.NOTEND:
                    await self.end(endType)

                Game.scene = Scene.DAY
                await self.game()

    @commands.Cog.listener()
    async def on_voice_state_update(
        self,
        member: discord.Member,
        before: discord.VoiceState,
        after: discord.VoiceState,
    ):

        # 監視対象のボイスチャンネルへの接続
        if before.channel is None and after.channel is not None:
            if after.channel.id == os.getenv("lobbyChannel"):
                if member not in Game.entries:
                    Game.entries.append(member)

        # 監視対象のボイスチャンネルからの切断
        elif before.channel is not None and after.channel is None:
            if before.channel.id == os.getenv("lobbyChannel"):
                if member in Game.entries:
                    Game.entries.remove(member)

        # 監視対象のボイスチャンネルから別のチャンネルへの移動、またはその逆
        elif before.channel is not None and after.channel is not None:
            # 監視対象のチャンネルから別のチャンネルへ移動
            if before.channel.id == os.getenv(
                "lobbyChannel"
            ) and after.channel.id != os.getenv("lobbyChannel"):
                if member in Game.entries:
                    Game.entries.remove(member)
            # 別のチャンネルから監視対象のチャンネルへ移動
            elif before.channel.id != os.getenv(
                "lobbyChannel"
            ) and after.channel.id == os.getenv("lobbyChannel"):
                if member not in Game.entries:
                    Game.entries.append(member)

    @app_commands.command(name="cast", description="配役決めします")
    @app_commands.default_permissions(discord.Permissions(administrator=True))
    @app_commands.rename(
        knight="騎士",
        teller="占い師",
        psychic="霊能者",
        bakery="パン屋",
        werewolf="人狼",
        madman="狂人",
        fox="妖狐",
    )
    async def cast(
        self,
        interaction: discord.Interaction,
        knight: int = 0,
        teller: int = 0,
        psychic: int = 0,
        bakery: int = 0,
        werewolf: int = 0,
        madman: int = 0,
        fox: int = 0,
    ):
        if not interaction.user.guild_permissions.administrator:
            return

        Game.cast = {
            Role.KNIGHT: knight,
            Role.TELLER: teller,
            Role.PSYCHIC: psychic,
            Role.BAKERY: bakery,
            Role.WEREWOLF: werewolf,
            Role.MADMAN: madman,
            Role.FOX: fox,
        }

        await interaction.response.send_message("配役を決めました")

    @app_commands.command(name="game", description="ゲームを開始します")
    @app_commands.default_permissions(discord.Permissions(administrator=True))
    async def gameCommand(self, interaction: discord.Interaction):
        if not interaction.user.guild_permissions.administrator:
            return

        # 役職の数が多すぎたとき
        mCount = 0
        for count in Game.cast.items():
            mCount += count

        if mCount > len(Game.entries):
            return await interaction.response.send_message(
                f"メンバーが足りません (あと{mCount - Game.entries}人)"
            )

        # 役職ぎめ
        for role, count in Game.cast.items():
            members = random.sample(Game.entries, count)
            for member in members:
                Game.members.append(
                    Member(member=member, role=role, roleType=getRoleType(role))
                )
                Game.entries.remove(member)
        Game.members.sort(key=lambda m: m.roleType)

        # ロビー
        await self.lobbyChannel.edit(
            overwrites={
                interaction.guild.default_role: discord.PermissionOverwrite(
                    view_channel=False
                ),
            }
            + {
                member.member: discord.PermissionOverwrite(
                    view_channel=True, connect=True, speak=True
                )
                for member in Game.members
            },
        )

        # 人狼
        Game.channels.append(
            channel := await self.bot.get_channel(
                1381606390329507992
            ).create_voice_channel(
                name="人狼",
                overwrites={
                    interaction.guild.default_role: discord.PermissionOverwrite(
                        view_channel=False
                    ),
                }
                + {
                    member.member: discord.PermissionOverwrite(
                        view_channel=True, connect=True, speak=True
                    )
                    for member in Game.members
                    if member.role == Role.WEREWOLF
                },
            )
        )
        self.werewolfChannel = channel

        # 幽霊チャンネル
        Game.channels.append(
            await self.bot.get_channel(1381606390329507992).create_text_channel(
                name="霊界",
                overwrites={
                    interaction.guild.default_role: discord.PermissionOverwrite(
                        view_channel=False
                    ),
                },
            )
        )

        # 各ユーザーのチャンネル
        for member in Game.members:
            dmember = member.member
            Game.channels.append(
                channel := await self.bot.get_channel(
                    1381606390329507992
                ).create_voice_channel(
                    name=str(dmember.id),
                    overwrites={
                        interaction.guild.default_role: discord.PermissionOverwrite(
                            view_channel=False
                        ),
                        dmember: discord.PermissionOverwrite(
                            view_channel=True, send_messages=True
                        ),
                    },
                )
            )
            await channel.send(f"あなたは**{getRoleName(member.role)}**です！")

        await self.werewolfChannel.send(
            f"あなたは**人狼**です！あなたの仲間は {' '.join([member.member.mention for member in Game.members
                    if member.role == Role.WEREWOLF])} です。"
        )

        await self.notificationChannel.send("人狼ゲームを開始します。")
        await self.game()


async def setup(bot: commands.Bot):
    await bot.add_cog(WerewolfCog(bot))
