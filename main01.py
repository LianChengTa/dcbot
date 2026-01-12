import discord
from discord.ext import commands

from dcbot0 import MusicCog  # 確保 dcbot0.py 與本檔案在同一資料夾


intents = discord.Intents.default()
intents.message_content = True

# 只負責建立 Bot 實例，不在這裡定義任何指令
bot = commands.Bot(command_prefix='>', intents=intents)


@bot.event
async def setup_hook():
    """啟動時載入 Cog 並同步 application commands（slash / app_commands）。"""
    await bot.add_cog(MusicCog(bot))
    synced = await bot.tree.sync()
    print(f"✅ Synced {len(synced)} application commands")


@bot.event
async def on_ready():
    print(f"✅ Logged in as {bot.user} (ID: {bot.user.id})")


if __name__ == "__main__":
    # TODO: 把下面的 'YOUR_BOT_TOKEN_HERE' 換成你的真實 Bot Token
    bot.run("DISCORDBOT_TOKEN")
