from discord.ext import commands
from yt_dlp import YoutubeDL
import asyncio
import discord





class ButtonView(discord.ui.View):
    def __init__(self, music_cog):
        super().__init__(timeout=None)
        self.music_cog = music_cog

    # 使用裝飾器方式創建 Button，交互函式直接寫在裝飾器底下
    @discord.ui.button(
        label = "下一個",
        style = discord.ButtonStyle.blurple
    )
    async def skip_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        # 呼叫 skip 方法
        await self.music_cog.skip(interaction)
    @discord.ui.button(
        label = "自動推薦",
        style = discord.ButtonStyle.blurple
    )
    async def rcmd_btn(self, interaction:discord.Interaction,button: discord.ui.Button):
        await interaction.response.defer()
        await self.music_cog.call_rcmd_list(interaction)
    
    @discord.ui.button(
        label = "獲取當前播放的url",
        style = discord.ButtonStyle.green
    )
    async def get_link_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message(self.music_cog.original_link[0])
    @discord.ui.button(
        label = "獲取當前播放列表",
        style = discord.ButtonStyle.green
    )
    async def get_queue_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        # await interaction.response.defer()
        await self.music_cog.queue(interaction)
    @discord.ui.button(
        label="高歌離席", 
        style=discord.ButtonStyle.red
    )
    async def leave_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message("仔見~")
        await self.music_cog.dc(interaction)
    



class music_cog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.is_playing = False
        self.is_paused = False
        self.music_queue = []
        self.FFMPEG_OPTIONS = {'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5', 'options': '-vn'}
        self.vc = None
        self.original_link=[]
        self.rcmd_or_norm=False
        self.first_time_come_in=True
    

    def search_yt(self, item):
        ydl_opts = {
            'format': 'bestaudio/best',
            'forceurl':'True',
            'playlistend': '5',
            'extract_flat':'in_playlist',
            'quiet':True,
        }


        with YoutubeDL(ydl_opts) as ydl:
            try:
                info = ydl.extract_info(item, download=False)

                if 'entries' in info:  # 表示是播放列表
                    playlist_videos = []
                    for entry in info['entries']:
                        self.original_link.append(entry['url'])
                        list_info = ydl.extract_info(entry['url'], download=False)
                        audio_url = list_info['url']  # 获取音频 URL
                        
                        title = list_info['title']    # 获取视频标题
                        # print(f'\n\n\n\nThis is audio_url:          {audio_url}')
                        playlist_videos.append({
                            'source': audio_url,
                            'title': title,
                            # 'url': audio_url  # 直接保存完整的 YouTube 链接
                        })
                        # print(playlist_videos)
                    return playlist_videos
                else:
                    # 单个视频处理
                    # print(info)
                    audio_url = info['url']
                    self.original_link.append(f"https://www.youtube.com/watch?v={info['id']}")
                    title = info['title']
                    # print(f'\n\n\n\nThis is audio_url:          {audio_url}')
                    # webpage_url = info['webpage_url']  # 直接获取视频的 YouTube 网页 URL
                    return [{'source': audio_url, 'title': title}]
            except Exception as e:
                print(f"Error downloading YouTube video: {e}")
                return []

    async def call_rcmd_list(self, ctx):
        """不再馬上啟動推薦，而是只改變自動推薦的開關狀態"""
        if not self.rcmd_or_norm:
            await ctx.followup.send("自動推薦模式......啓動！！！！")
            self.rcmd_or_norm = True

            # 如果此时队列只有一首歌，立即进行自动推荐
            if len(self.music_queue) == 1:
                await self.add_recommended_songs()

        else:
            await ctx.followup.send("自動推薦模式......關閉。。。。")
            self.rcmd_or_norm = False

    async def add_recommended_songs(self):
        """添加推薦歌曲到佇列"""
        songs = await self.get_rcmd_list()  # 获取推荐的歌曲
        if songs:
            for song in songs:
                self.music_queue.append(song)
        else:
            await self.current_ctx.followup.send("未找到推薦歌曲。")


    async def get_rcmd_list(self):
        ydl_opts = {
            'format': 'bestaudio/best',
            'forceurl': True,
            'playlistend': 5,
            'extract_flat': 'in_playlist',
            'quiet': True,
        }

        async def extract_info_async(url):
            with YoutubeDL(ydl_opts) as ydl:
                return await asyncio.to_thread(ydl.extract_info, url, download=False)

        current_link = self.original_link[0]

        try:
            info = await extract_info_async(current_link)

            current_link = f"{current_link}&list=RD{info['id']}&index=1&rv={info['id']}&ab_channel={info['channel']}"
            info = await extract_info_async(current_link)

            if 'entries' in info:  # 這是一個播放列表
                playlist_videos = []
                for cnt, entry in enumerate(info['entries']):
                    if cnt == 0:  # 跳過第一個視頻
                        continue

                    self.original_link.append(entry['url'])

                    try:
                        list_info = await extract_info_async(entry['url'])
                        audio_url = list_info['url']  # 获取音频 URL
                        title = list_info['title']  # 获取视频标题

                        playlist_videos.append({
                            'source': audio_url,
                            'title': title,
                        })
                    except Exception as e:
                        print(f"無法獲取 {entry['url']} 的信息: {e}")

                return playlist_videos

            else:  # 這裡理論上永遠進不來
                audio_url = info['url']
                title = info['title']
                return {'source': audio_url, 'title': title}

        except Exception as e:
            print(f"獲取推薦歌曲失敗: {e}")
            return False


    async def play_music(self, ctx):
        if len(self.music_queue) > 0:
            m_url = self.music_queue[0]['source']
            m_title = self.music_queue[0]['title']
            
            self.current_ctx = ctx

            try:
                view = ButtonView(self)
                if isinstance(ctx, discord.Interaction):
                    await ctx.followup.send(f"Now playing: **'{m_title}'**", view=view)
                else:
                    await ctx.send(f"Now playing: **'{m_title}'**", view=view)

                def after_playing(error):
                    if error:
                        print(f"Error in playback: {error}")
                    asyncio.run_coroutine_threadsafe(self.play_next(), self.bot.loop)  # 確保 play_next() 在 event loop 內執行

                self.is_playing = True
                self.vc.play(discord.FFmpegPCMAudio(m_url, **self.FFMPEG_OPTIONS), after=after_playing)  # 設置 after 回調函式

            except Exception as e:
                print(f"Error playing audio: {e}")
        else:
            self.is_playing = False
            if isinstance(ctx, discord.Interaction):
                await ctx.response.send_message("No music in queue")
            else:
                await ctx.send("No music in queue")


    async def play_next(self):
        if len(self.music_queue) > 0:
            # Remove the currently playing song from the queue
            self.music_queue.pop(0)
            self.original_link.pop(0)

            # If there's only one song left, check if auto-recommend mode is enabled
            if len(self.music_queue) <= 1 and self.rcmd_or_norm:
                # 异步获取推荐歌曲，不影响当前播放
                asyncio.create_task(self.async_recommend_next_song())
                # print(self.music_queue)
                if len(self.music_queue) > 0:
                    await self.play_music(self.current_ctx)
                else:
                    self.is_playing = False
            else:
                await self.play_music(self.current_ctx)
        else:
            self.is_playing = False

    async def async_recommend_next_song(self):
        """异步获取推荐歌曲，并补充到队列中"""
        songs = await self.get_rcmd_list()  # 获取推荐的歌曲
        if songs:
            for song in songs:
                self.music_queue.append(song)
            # 推荐完歌曲后，检查是否可以继续播放
            if self.music_queue and not self.is_playing:
                await self.play_music(self.current_ctx)







    @commands.hybrid_command(help="Plays a selected song from YouTube or a playlist")
    async def play(self, ctx: commands.Context, query: str):
        await ctx.defer()
        
        # 检查用户是否在语音频道
        try:
            voice_channel = ctx.author.voice.channel
        except AttributeError:
            await ctx.send('請先加入任意頻道！')
            return

        # 如果机器人未连接语音频道或当前频道与用户的频道不同
        if self.vc is None or not self.vc.is_connected():
            try:
                self.vc = await voice_channel.connect()
            except Exception as e:
                print(f'Error from joining voice channel: {e}')
                await ctx.send('無法加入語音頻道！')
                return
        else:
            # 如果机器人已连接，但不在用户当前频道
            if self.vc.channel != voice_channel:
                await self.vc.move_to(voice_channel)

        # 初次进入时发送说明
        # if self.first_time_come_in:
        #     self.first_time_come_in = False
        #     text = '''
        #         使用説明：\n
        #             **修好啦！！！但是是用之前的有存到的版本補回來的，所以可能有什麽被我漏掉/沒有修好可以再告訴我**\n
        #         '''
        #     await ctx.send(content=text)

        # 添加歌曲到播放队列
        if not self.is_playing:
            self.music_queue = self.search_yt(query)
            
            if len(self.music_queue) > 0:
                await ctx.send('已加入到播放列表')
                await self.play_music(ctx)
            else:
                await ctx.send('未找到任何有效的音樂或播放列表。')
        else:
            songs = self.search_yt(query)
            if len(songs) > 0:
                for song in songs:
                    self.music_queue.append(song)
                await ctx.send('已加入到播放列表')
            else:
                await ctx.send('未找到任何有效的音樂或播放列表。')



    def search_yt_text(self,query):
        ydl_opts = {
            'quiet': True,
            'default_search': 'ytsearch5',  # 確保是 YouTube 搜索
            'extract_flat': True,  # 只抓取信息，不下載
            'skip_download': True,
        }

        with YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(f"ytsearch5:{query}", download=False)
            # print(info)  # Debug: 看看返回的內容

            # 確保 entries 存在
            if 'entries' in info:
                return [{
                    'title': entry.get('title', 'No Title'),
                    'url': entry.get('url', ''),
                    'duration': entry.get('duration', 0)
                } for entry in info['entries']]
            else:
                return []

    @commands.hybrid_command(help="搜索 YouTube 並返回結果列表")
    async def search(self, ctx, *, query: str):
        results = self.search_yt_text(query)
        if not results:
            await ctx.send("未找到任何結果，請嘗試其他關鍵詞！")
            return
        
        embed = discord.Embed(title="YouTube 搜索結果", color=discord.Color.blue())
        for i, result in enumerate(results):
            embed.add_field(name=f"{i+1}. {result['title']}", value=result['url'], inline=False)

        await ctx.send(embed=embed)


    @commands.hybrid_command(help="Pauses the current song being played")
    async def pause(self, ctx):
        if self.is_playing:
            self.is_playing = False
            self.is_paused = True
            self.vc.pause()
        elif self.is_paused:
            self.is_paused = False
            self.is_playing = True
            self.vc.resume()

    @commands.hybrid_command(help="Resumes playing with the discord bot")
    async def resume(self, ctx):
        if self.is_paused:
            self.is_paused = False
            self.is_playing = True
            self.vc.resume()

    @commands.hybrid_command(help="Skips the current song being played")
    async def skip(self, ctx):
        if self.vc and self.vc.is_playing():
            self.vc.stop()  # 只停止播放，讓 after_playing 自己去處理 play_next()
            
            if isinstance(ctx, discord.Interaction):
                await ctx.response.send_message("Skipped the current song")
            else:
                await ctx.send("Skipped the current song")
        else:
            await ctx.send("No more songs in queue to skip.")




    @commands.hybrid_command(help="Displays the current songs in queue")
    async def queue(self, ctx):
        retval = ""
        # print(self.music_queue)
        for i in range(len(self.music_queue)):
            retval += f"#{i+1} -" + self.music_queue[i]['title'] + "\n"

        if retval:
            await ctx.response.send_message(f"```播放順序:\n{retval}```")    #這裏是因爲從interaction那裏傳進來，所以要跟著interaction的規則寫（從button那裏呼叫的）
        else:
            await ctx.response.send_message("No music in queue")

    @commands.hybrid_command(help="Stops the music and clears the queue")
    async def clear(self, ctx):
        if self.vc and self.is_playing:
            self.vc.stop()
        self.music_queue = []
        self.original_link=[]
        await ctx.send("Music queue cleared")

    @commands.hybrid_command(help="Kick the bot from VC")
    async def dc(self, ctx):
        if self.vc and self.vc.is_connected():
            await self.vc.disconnect()
            self.music_queue.clear()
            self.original_link.clear()
            self.is_playing = False
            self.is_paused = False
            # await ctx.response.send_message("機器人已離開語音頻道，播放列表已清空！")
        else:
            await ctx.response.send_message("機器人不在語音頻道！")

    @commands.hybrid_command(help="Remove the last song from the queue")
    async def re(self, ctx):
        if self.music_queue:
            self.music_queue.pop()
            self.original_link.pop()
            await ctx.send("Last song removed")
        else:
            await ctx.send("Queue is already empty")








