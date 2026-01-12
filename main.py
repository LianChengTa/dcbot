import discord
from discord.ext import commands
import os
from dcbot0 import MusicCog, MusicView

intents = discord.Intents.default()
intents.message_content = True
intents.guilds = True
intents.voice_states = True  # ⚠️ 播放音樂需要

# 使用 commands.Bot 支援 slash command
bot = commands.Bot(command_prefix='!', intents=intents)

# ----- Ping 測試指令 -----
@bot.tree.command(name="ping", description="檢查機器人延遲")
async def ping(interaction: discord.Interaction):
    await interaction.response.send_message(f"Pong! Latency: {bot.latency*1000:.0f}ms")

# ----- 顯示音樂選單 (測試用) -----
@bot.tree.command(name="選單", description="顯示音樂選單")
async def 選單(interaction: discord.Interaction):
    # 這裡傳空的 MusicView，如果你要帶 search 結果，可改傳 MusicView(results, cog, interaction)
    await interaction.response.send_message("請選擇一個選項：", view=MusicView([], None, interaction))

# ----- 載入 Cog -----
@bot.event
async def on_ready():
    print(f"✅ Logged in as {bot.user} (ID: {bot.user.id})")
    music_cog = MusicCog(bot)
    await bot.add_cog(music_cog)
    print("✅ MusicCog loaded")
    
    # 同步 slash commands (app_commands)
    try:
        synced = await bot.tree.sync()
        print(f"✅ Slash commands synced: {len(synced)} commands")
    except Exception as e:
        print(f"❌ Error syncing commands: {e}")
    
    print("✅ Bot is ready! Slash commands should be available shortly.")


# ----- 啟動 Bot -----
bot.run("DISCORDBOT_TOKEN")