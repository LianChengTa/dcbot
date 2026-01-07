import discord
from discord.ext import commands
from yt_dlp import YoutubeDL
import asyncio

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix='>', intents=intents)

@bot.hybrid_command()
async def play(ctx, query: str):
    await ctx.defer()
    original_link = []
    songs = await search_yt(query, original_link)
    if not songs:
        await ctx.send('未找到任何有效的音樂或播放列表。')
        return

    if not self.is_playing:
        self.music_queue = songs
        await ctx.send('已加入到播放列表，開始播放 🎶')
        await self.play_music(ctx)



    await ctx.send('pong')


async def search_yt(url: str, original_link: list):
    ydl_opts = {
        'format': 'bestaudio/best',
        'forceurl': True,
        'playlistend': '5',
        'extract_flat': 'in_playlist',
        'quiet': True,
        'noplaylist': False,
        'socket_timeout': 30,
    }

    def _extract_info_sync(url):
        ydl = YoutubeDL(ydl_opts)
        try:
            return ydl.extract_info(url, download=False)
        finally:
            ydl.close()

    try:
        # 先抓主資訊
        info = await asyncio.to_thread(_extract_info_sync, url)

        # ▶ playlist
        if 'entries' in info and info['entries'] is not None:
            playlist_videos = []
            for entry in info['entries']:
                original_link.append(entry['url'])
                list_info = await asyncio.to_thread(_extract_info_sync, entry['url'])
                playlist_videos.append({
                    'source': list_info['url'],
                    'title': list_info['title']
                })
            return playlist_videos
        
        # ▶ 單支影片
        else:
            original_link.append(f"https://www.youtube.com/watch?v={info['id']}")
            return [{
                'source': info['url'],
                'title': info['title']
            }]

    except Exception as e:
        print(f"Error downloading YouTube video: {e}")
        return []


bot.run('DISCORDBOTTOKEN')