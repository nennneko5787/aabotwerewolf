import asyncio
import enum
import os
import random
from collections import Counter

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
    FORCE = "FORCE"
    NOTEND = "NOTEND"
    WONWOLFS = "WONWOLF"
    WONVILAGGERS = "WONVILAGGERS"
    WONFOX = "WONFOX"


ENDCHAR = {
    EndType.FORCE: "強制終了しました",
    EndType.WONWOLFS: "村人が全滅したため、人狼の勝利！",
    EndType.WONVILAGGERS: "人狼が全滅したため、村人の勝利！",
    EndType.WONFOX: "妖狐が生き残っていたため、妖狐の勝利！",
}


async def voteCallback(interaction: discord.Interaction, to: discord.Member):
    if to == interaction.user:
        return await interaction.response.send_message(f"人狼は殺れません")
    Game.votes[interaction.user] = to
    await interaction.response.send_message(
        f"{to.mention} に投票しました。", ephemeral=True
    )


async def tellerCallback(interaction: discord.Interaction, to: discord.Member):
    if to == interaction.user:
        return await interaction.response.send_message(f"人狼は殺れません")
    Game.tellerTarget[interaction.user] = to
    await interaction.response.send_message(f"占う人を {to.mention} にしました。")


async def knightCallback(interaction: discord.Interaction, to: discord.Member):
    if to == interaction.user:
        return await interaction.response.send_message(f"人狼は殺れません")
    Game.knightTarget[interaction.user] = to
    await interaction.response.send_message(f"守る人を {to.mention} にしました。")


async def werewolfCallback(interaction: discord.Interaction, to: discord.Member):
    if discord.utils.get(Game.members, member=to).role == Role.WEREWOLF:
        return await interaction.response.send_message(f"人狼は殺れません")
    Game.werewolfTarget = to
    await interaction.response.send_message(f"{to.mention} を殺ります")


class UserSelect(discord.ui.UserSelect):
    def __init__(
        self,
        day: int,
        callback: function,
    ):
        options = [member.member for member in Game.members]
        self.day = day
        self.selectCallback = callback

        super().__init__(
            placeholder="ユーザーを選んでください。",
            min_values=1,
            max_values=1,
            options=options,
        )

    async def callback(self, interaction: discord.Interaction):
        if Game.days != self.day:
            return await interaction.response.send_message(
                "今日のパネルではありません", ephemeral=True
            )
        await self.selectCallback(interaction, self.values[0])


class UserSelectView(discord.ui.View):
    def __init__(self, day: int, callback: function = voteCallback):
        super().__init__()
        self.add_item(UserSelect(day, callback))


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
                    f"- {member.member.mention} -> {getRoleName(member.role)}"
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
                    view_channel=True
                ),
            }
        )

        Game.reset()

    async def game(self):
        match Game.scene:
            case Scene.DAY:
                Game.seconds = 240
                while Game.seconds <= 0:
                    Game.seconds -= 1
                    await asyncio.sleep(1)
                    if Game.force:
                        return await self.end(EndType.FORCE)
                Game.scene = Scene.EVENING
                await self.game()
            case Scene.EVENING:
                Game.seconds = 60

                for member in Game.members:
                    Game.votes[member] = None

                await self.notificationChannel.send(
                    "夕方になりました。投票を開始してください。",
                    view=UserSelectView(Game.days, voteCallback),
                )

                while Game.seconds <= 0:
                    Game.seconds -= 1
                    await asyncio.sleep(1)
                    if Game.force:
                        return await self.end(EndType.FORCE)

                v = Game.votes.copy()
                for m in v.keys():
                    if Game.votes[m] is None:
                        Game.votes[m] = random.choice(
                            [
                                member.member
                                for member in Game.members
                                if member.member != m
                            ]
                        )

                await self.notificationChannel.send(
                    "\n".join(
                        [
                            f"- {member.mention} -> {to.mention}"
                            for member, to in Game.votes.items()
                        ]
                    )
                    + "\n-# 選ばなかったユーザーはランダム投票になります"
                )
                valueCounts = Counter(Game.votes.values())
                voteMember, count = valueCounts.most_common(1)[0]
                await self.notificationChannel.send(
                    f"{voteMember.mention} さんが**{count}**票の投票を得たため、処刑します。"
                )
                discord.utils.get(Game.members, member=voteMember).dead = True

                for member in Game.members:
                    dmember = member.member
                    if member.role == Role.PSYCHIC:
                        await discord.utils.get(
                            Game.channels, name=str(dmember.id)
                        ).send(
                            f"{voteMember.mention} さんは**{getRoleName(discord.utils.get(Game.members, member=voteMember).role)}**",
                            view=UserSelectView(Game.days, tellerCallback),
                        )

                endType = self.ifEnd()
                if endType != EndType.NOTEND:
                    return await self.end(endType)

                self.moveToRoleVoice()
                Game.scene = Scene.NIGHT
                await self.game()
            case Scene.NIGHT:
                Game.seconds = 120

                # 自分のボイスチャンネルor人狼ボイスチャンネルに移動
                await self.moveToRoleVoice()

                for member in Game.members:
                    dmember = member.member
                    if member.role == Role.WEREWOLF:
                        continue

                    match member.role:
                        case Role.TELLER:
                            await discord.utils.get(
                                Game.channels, name=str(dmember.id)
                            ).send(
                                "占うユーザーを選択してください。",
                                view=UserSelectView(Game.days, tellerCallback),
                            )
                        case Role.KNIGHT:
                            await discord.utils.get(
                                Game.channels, name=str(dmember.id)
                            ).send(
                                "守るユーザーを選択してください。",
                                view=UserSelectView(Game.days, knightCallback),
                            )

                await self.werewolfChannel.send(
                    f"夜になりました。仲間と話し合って、村人を一人噛み殺してください。{'(初日は誰も噛み殺せません)' if Game.days == 0 else ''}",
                    view=(
                        UserSelectView(Game.days, werewolfCallback)
                        if Game.days != 0
                        else None
                    ),
                )

                while Game.seconds <= 0:
                    Game.seconds -= 1
                    await asyncio.sleep(1)
                    if Game.force:
                        return await self.end(EndType.FORCE)

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

                Game.werewolfTarget = None
                Game.knightTarget = {}
                Game.tellerTarget = {}

                endType = self.ifEnd()
                if endType != EndType.NOTEND:
                    return await self.end(endType)

                self.moveToLobby()
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
        mCount = sum(Game.cast.values())

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
