import discord
from discord import app_commands
from discord.ext import commands

from services.werewolf import Game, Role, getRoleType


class WerewolfEntryView(discord.ui.View):
    @discord.ui.button(label="参加", style=discord.ButtonStyle.blurple)
    async def entry(
        self, interaction: discord.Interaction, button: discord.Button
    ) -> None:
        if not interaction.user in Game.entries:
            Game.entries.append(interaction.user)
            await interaction.response.send_message(
                "エントリーしました", ephemeral=True
            )
        else:
            Game.entries.remove(interaction.user)
            await interaction.response.send_message(
                "エントリーを解除しました", ephemeral=True
            )


class WerewolfCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(
        name="joinpanel", description="ゲームに参加するためのパネルを設置します"
    )
    @app_commands.default_permissions(discord.Permissions(administrator=True))
    async def joinPanelCommand(self, interaction: discord.Interaction):
        if not interaction.user.guild_permissions.administrator:
            return
        await interaction.response.send_message(view=WerewolfEntryView(timeout=None))

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
        await interaction.response.send_message("開発中です！ｗ")


async def setup(bot: commands.Bot):
    await bot.add_cog(WerewolfCog(bot))
