import os
import discord
from discord.ext import commands
from dcbot0 import music_cog

class MyBot(commands.Bot):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    async def setup_hook(self):
        await self.add_cog(music_cog(self))
        synced = await self.tree.sync()
        # print(f"Synced commands: {synced}")


intents = discord.Intents.default()
intents.message_content = True
intents.guilds = True  # 確保這個 intents 被啟用

bot = MyBot(command_prefix="!", intents=intents)

@bot.command()
@commands.has_permissions(administrator=True)
async def synccommands(ctx):
    await bot.tree.sync()
    await ctx.send("Sync successful!")

@bot.hybrid_command(name="add", description="Add two numbers")
async def add(ctx, a: int, b: int):
    await ctx.send(a + b)

bot.run("MTI4MzM3OTkwMTAyNTc0NzAyMQ.GxX9c2.zWM8QTnw_jQohp8ic9Ve4zrRjebfIncf4i5mw8")
