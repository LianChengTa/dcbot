from discord.ext import commands
from yt_dlp import YoutubeDL
import asyncio
import discord
from discord import app_commands

# ----------------- Button 按鈕 -----------------
class ButtonView(discord.ui.View):
    def __init__(self, MusicCog):
        super().__init__(timeout=None)
        self.MusicCog = MusicCog

    @discord.ui.button(label="下一個", style=discord.ButtonStyle.blurple)
    async def skip_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.MusicCog._skip(interaction)

    @discord.ui.button(label="自動推薦", style=discord.ButtonStyle.blurple)
    async def rcmd_btn(self, ctx, button: discord.ui.Button):
        # 確保傳入 interaction
        await ctx.response.defer()
        await self.MusicCog.call_rcmd_list(ctx)

    @discord.ui.button(label="獲取當前播放的url", style=discord.ButtonStyle.green)
    async def get_link_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        msg = self.MusicCog.original_link[0] if self.MusicCog.original_link else "目前沒有播放歌曲"
        await self.MusicCog.send_message(interaction, msg)

    @discord.ui.button(label="獲取當前播放列表", style=discord.ButtonStyle.green)
    async def get_queue_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.MusicCog._queue(interaction)

    @discord.ui.button(label="高歌離席", style=discord.ButtonStyle.red)
    async def leave_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.MusicCog._dc(interaction)
        await self.MusicCog.send_message(interaction, "仔見~")


class MusicSelect(discord.ui.Select):
    def __init__(self, results, cog, interaction):
        self.results = results
        self.MusicCog = cog
        self.interaction = interaction
        options = [
            discord.SelectOption(
                label=result["title"][:100],
                description=f"{result.get('duration', '未知時長')}",
                value=result["url"]
            )
            for result in results
        ]
        super().__init__(placeholder="請選擇一個搜索結果...", options=options)

    async def callback(self, interaction: discord.Interaction):
        selected_url = self.values[0]
        selected_title = next((r['title'] for r in self.results if r["url"] == selected_url), "未知影片")
        self.disabled = True
        await interaction.message.edit(view=self.view)
        await interaction.response.send_message(f"🎵 你選擇了 **{selected_title}**\n🔗 {selected_url}", ephemeral=True)
        # 修复：调用内部方法而不是 slash command
        await self.MusicCog._play(interaction, query=selected_url)


class MusicView(discord.ui.View):
    def __init__(self, results, cog, interaction):
        super().__init__(timeout=None)
        self.add_item(MusicSelect(results, cog, interaction))

class MusicCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.is_playing = False
        self.is_paused = False
        self.music_queue = []
        self.FFMPEG_OPTIONS = {
            'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5',
            'options': '-vn'
        }
        self.vc = None
        self.original_link = []
        self.rcmd_or_norm = False
        self.force_stop = False
        self.current_interaction = None

    # ----------------- send_message -----------------
    async def send_message(self, interaction, content=None, embed=None, view=None, ephemeral=False):
        try:
            # 如果是 Interaction
            if isinstance(interaction, discord.Interaction):
                if not getattr(interaction.response, "is_done", lambda: False)():
                    # 只在 view 不为 None 时才传递 view 参数
                    if view is not None:
                        await interaction.response.send_message(content=content, embed=embed, view=view, ephemeral=ephemeral)
                    else:
                        await interaction.response.send_message(content=content, embed=embed, ephemeral=ephemeral)
                else:
                    # 使用 followup.send
                    if view is not None:
                        await interaction.followup.send(content=content, embed=embed, view=view, ephemeral=ephemeral)
                    else:
                        await interaction.followup.send(content=content, embed=embed, ephemeral=ephemeral)
            # 如果是 Context / 其他物件
            else:
                channel = getattr(interaction, "channel", None)
                if channel:
                    if view is not None:
                        await channel.send(content=content, embed=embed, view=view)
                    else:
                        await channel.send(content=content, embed=embed)
                else:
                    print("⚠️ 無法送出訊息，連 channel 都沒有")
        except (discord.errors.InteractionResponded, discord.errors.NotFound):
            # fallback: 用 channel.send
            channel = getattr(interaction, "channel", None)
            if channel:
                if view is not None:
                    await channel.send(content=content, embed=embed, view=view)
                else:
                    await channel.send(content=content, embed=embed)
            else:
                print("⚠️ 無法送出訊息，連 channel 都沒有")

    # ----------------- YouTube 搜索 -----------------
    async def search_yt(self, item):
        ydl_opts = {
            'format': 'bestaudio/best',
            'forceurl': True,
            'playlistend': '5',
            'extract_flat': 'in_playlist',
            'quiet': True,
            'noplaylist': False,
            'socket_timeout': 30,
            'cookies': 'cookies.txt',
        }
        
        def _extract_info_sync(url):
            ydl = YoutubeDL(ydl_opts)
            try:
                return ydl.extract_info(url, download=False)
            finally:
                ydl.close()
        
        try:
            info = await asyncio.to_thread(_extract_info_sync, item)
            # 修复：创建临时列表存储新的链接，避免直接修改 original_link
            new_links = []
            if 'entries' in info:
                playlist_videos = []
                for entry in info['entries']:
                    new_links.append(entry['url'])
                    list_info = await asyncio.to_thread(_extract_info_sync, entry['url'])
                    playlist_videos.append({'source': list_info['url'], 'title': list_info['title']})
                # 如果当前没有在播放，清空旧链接并添加新链接
                if not self.is_playing:
                    self.original_link = new_links
                else:
                    self.original_link.extend(new_links)
                return playlist_videos
            else:
                new_link = f"https://www.youtube.com/watch?v={info['id']}"
                # 如果当前没有在播放，清空旧链接并添加新链接
                if not self.is_playing:
                    self.original_link = [new_link]
                else:
                    self.original_link.append(new_link)
                return [{'source': info['url'], 'title': info['title']}]
        except Exception as e:
            print(f"Error downloading YouTube video: {e}")
            return []

    # 添加搜索文本的方法（searchlink命令需要使用）
    async def search_yt_text(self, query):
        ydl_opts = {
            'format': 'bestaudio/best',
            'quiet': True,
            'no_warnings': True,
            'default_search': 'ytsearch5:',  # 搜索前5个结果
            'socket_timeout': 30,
            'cookies': 'cookies.txt',
        }
        
        def _search_sync(search_query):
            ydl = YoutubeDL(ydl_opts)
            try:
                return ydl.extract_info(search_query, download=False)
            finally:
                ydl.close()
        
        try:
            search_results = await asyncio.to_thread(_search_sync, query)
            results = []
            for entry in search_results['entries']:
                results.append({
                    'title': entry['title'],
                    'url': f"https://www.youtube.com/watch?v={entry['id']}",
                    'duration': entry.get('duration_string', '未知時長')
                })
            return results
        except Exception as e:
            print(f"Search error: {e}")
            return []

    # ----------------- 播放控制 -----------------
    async def play_music(self, interaction: discord.Interaction):
        if not self.music_queue:
            self.is_playing = False
            await self.send_message(interaction, "空空如也~")
            return

        # 检查并确保语音连接正常
        # 首先尝试从 bot 的 voice_clients 中获取现有连接
        existing_vc = None
        for voice_client in self.bot.voice_clients:
            if voice_client.guild == interaction.guild:
                existing_vc = voice_client
                break
        
        # 如果找到现有连接，使用它
        if existing_vc:
            self.vc = existing_vc
            # 如果机器人在不同的频道，移动到用户所在的频道
            if interaction.user.voice and interaction.user.voice.channel and self.vc.channel != interaction.user.voice.channel:
                try:
                    await self.vc.move_to(interaction.user.voice.channel)
                except Exception as e:
                    print(f"Error moving to channel: {e}")
        # 如果没有现有连接，尝试新建连接
        elif not self.vc or not self.vc.is_connected():
            if interaction.user.voice and interaction.user.voice.channel:
                try:
                    self.vc = await interaction.user.voice.channel.connect()
                except discord.errors.ClientException as e:
                    # 如果连接失败（可能已经连接），再次尝试获取现有连接
                    for voice_client in self.bot.voice_clients:
                        if voice_client.guild == interaction.guild:
                            self.vc = voice_client
                            break
                    if not self.vc:
                        await self.send_message(interaction, f"無法連接到語音頻道: {e}")
                        return
            else:
                await self.send_message(interaction, "無法連接到語音頻道！")
                return

        self.current_interaction = interaction
        song = self.music_queue[0]
        
        # 在开始播放前检查：如果队列只剩1首（包括当前这首），且自动推荐模式开启，提前添加推荐歌曲
        if len(self.music_queue) == 1 and self.rcmd_or_norm:
            print(f"[DEBUG] play_music: 队列只剩1首，提前添加推荐歌曲...")
            # 等待推荐歌曲添加完成，确保在播放完当前歌曲前推荐歌曲已经在队列中
            await self.async_recommend_next_song()
            print(f"[DEBUG] play_music: 推荐歌曲添加完成，当前队列长度={len(self.music_queue)}")
        
        view = ButtonView(self)
        await self.send_message(interaction, f"Now playing: **'{song['title']}'**", view=view)

        def after_playing(error):
            if self.force_stop:
                self.force_stop = False
                return
            if error:
                print(f"Error in playback: {error}")
            asyncio.run_coroutine_threadsafe(self.play_next(), self.bot.loop)

        self.is_playing = True
        try:
            # 在播放时重新获取 URL，避免 URL 过期和 403 错误
            yt_url = self.original_link[0] if self.original_link else song.get('url', song['source'])
            
            # 重新获取最新的 URL
            ytdl_opts = {
                'format': 'bestaudio/best',
                'quiet': True,
                'no_warnings': True,
            }
            ytdl = YoutubeDL(ytdl_opts)
            try:
                info = ytdl.extract_info(yt_url, download=False)
                # 获取最新的流 URL
                if 'url' in info:
                    play_url = info['url']
                elif 'formats' in info:
                    # 从格式中选择最佳音频流
                    for fmt in info['formats']:
                        if fmt.get('acodec') != 'none' and fmt.get('vcodec') == 'none':
                            play_url = fmt['url']
                            break
                    else:
                        play_url = song['source']
                else:
                    play_url = song['source']
                
                # 使用新获取的 URL 播放
                self.vc.play(discord.FFmpegPCMAudio(play_url, **self.FFMPEG_OPTIONS), after=after_playing)
            finally:
                ytdl.close()
        except Exception as e:
            print(f"Error playing audio: {e}")
            # 如果重新获取失败，尝试使用原始 URL
            try:
                self.vc.play(discord.FFmpegPCMAudio(song['source'], **self.FFMPEG_OPTIONS), after=after_playing)
            except Exception as e2:
                print(f"Final retry error: {e2}")
                await self.send_message(interaction, f"播放時發生錯誤: {e}")
                self.is_playing = False

    async def play_next(self):
        if self.music_queue:
            # 在pop之前检查队列长度，判断是否只剩1首
            was_only_one_song = len(self.music_queue) == 1
            print(f"[DEBUG] play_next: 队列长度={len(self.music_queue)}, was_only_one_song={was_only_one_song}, rcmd_or_norm={self.rcmd_or_norm}")
            
            self.music_queue.pop(0)
            # 如果只剩1首且需要推荐，先不pop original_link，因为get_rcmd_list需要它
            if was_only_one_song and self.rcmd_or_norm:
                # 保留 original_link[0] 用于推荐，稍后再pop
                pass
            elif self.original_link:
                self.original_link.pop(0)
            
            # 如果原来只剩1首，且自动推荐模式开启，则自动添加推荐歌曲
            if was_only_one_song and self.rcmd_or_norm:
                print(f"[DEBUG] 开始执行自动推荐...")
                # 等待推荐任务完成（此时 original_link[0] 还在，get_rcmd_list 可以使用它）
                await self.async_recommend_next_song()
                # 推荐完成后，pop掉 original_link[0]
                if self.original_link:
                    self.original_link.pop(0)
                print(f"[DEBUG] 推荐完成，队列长度={len(self.music_queue)}")
                if self.music_queue:
                    await self.play_music(self.current_interaction)
                else:
                    self.is_playing = False
            elif self.music_queue:
                # 如果还有歌曲，继续播放
                await self.play_music(self.current_interaction)
            else:
                # 队列为空，停止播放
                self.is_playing = False
                self.original_link.clear()
        else:
            self.is_playing = False
            self.original_link.clear()

    async def async_recommend_next_song(self):
        """获取推荐歌曲并添加到队列（不负责播放，由 play_next 处理）"""
        print(f"[DEBUG] async_recommend_next_song: 开始获取推荐歌曲...")
        songs = await self.get_rcmd_list()
        print(f"[DEBUG] async_recommend_next_song: 获取到 {len(songs) if songs else 0} 首推荐歌曲")
        if songs:
            self.music_queue.extend(songs)
            print(f"[DEBUG] async_recommend_next_song: 已添加推荐歌曲，当前队列长度={len(self.music_queue)}")
            # 注意：original_link 已经在 get_rcmd_list 中更新了
        else:
            print(f"[DEBUG] async_recommend_next_song: 未获取到推荐歌曲")

    # ----------------- 自動推薦功能 -----------------
    async def call_rcmd_list(self, interaction: discord.Interaction):
        """非馬上啟動推薦，而是切換自動推薦模式"""
        # defer 如果還沒 defer
        if not interaction.response.is_done():
            await interaction.response.defer()

        if not self.rcmd_or_norm:
            self.rcmd_or_norm = True
            await interaction.followup.send("自動推薦模式......啟動！！！！")
            # 如果此時隊列只有一首歌，立即進行自動推薦
            if len(self.music_queue) == 1:
                await self.add_recommended_songs(interaction)
        else:
            self.rcmd_or_norm = False
            await interaction.followup.send("自動推薦模式......關閉。。。。")

    async def add_recommended_songs(self, interaction: discord.Interaction):
        """添加推薦歌曲到佇列"""
        songs = await self.get_rcmd_list()
        if songs:
            for song in songs:
                self.music_queue.append(song)
            await self.send_message(interaction, f"已添加 {len(songs)} 首推薦歌曲到播放列表")
        else:
            await self.send_message(interaction, "未找到推薦歌曲。")

    async def get_rcmd_list(self):
        """取得推薦歌曲列表"""
        ydl_opts = {
            'format': 'bestaudio/best',
            'forceurl': True,
            'playlistend': 5,
            'extract_flat': 'in_playlist',
            'quiet': True,
            'socket_timeout': 30,
            'cookies': 'cookies.txt',
        }

        async def extract_info_async(url):
            ydl = YoutubeDL(ydl_opts)
            try:
                return await asyncio.to_thread(ydl.extract_info, url, download=False)
            finally:
                ydl.close()

        if not self.original_link:
            return []

        current_link = self.original_link[0]
        try:
            info = await extract_info_async(current_link)
            # 修复：使用 get 方法避免 KeyError
            channel = info.get('channel', info.get('uploader', ''))
            current_link = f"{current_link}&list=RD{info['id']}&index=1&rv={info['id']}&ab_channel={channel}"
            info = await extract_info_async(current_link)

            if 'entries' in info:  # 播放列表
                playlist_videos = []
                for cnt, entry in enumerate(info['entries']):
                    if cnt == 0:  # 跳過第一個
                        continue
                    self.original_link.append(entry['url'])
                    try:
                        list_info = await extract_info_async(entry['url'])
                        playlist_videos.append({
                            'source': list_info['url'],
                            'title': list_info['title'],
                        })
                    except Exception as e:
                        print(f"無法獲取 {entry['url']} 的信息: {e}")
                return playlist_videos
            else:
                # 單曲理論上不會來這裡
                return [{'source': info['url'], 'title': info['title']}]
        except Exception as e:
            print(f"獲取推薦歌曲失敗: {e}")
            return []




    # ----------------- Slash Commands -----------------
    @app_commands.command(name="search", description="搜索 YouTube 並返回結果列表")
    @app_commands.describe(query="搜索關鍵字")
    async def search(self, interaction: discord.Interaction, query: str):
        await interaction.response.defer()
        
        results = await self.search_yt_text(query)  # 使用文本搜索方法
        if not results:
            await self.send_message(interaction, "未找到任何結果，請嘗試其他關鍵字！")
            return

        view = MusicView(results, self, interaction)
        await self.send_message(interaction, "🔎 搜索結果：", view=view)

    @app_commands.command(name="searchlink", description="搜索 YouTube 並返回結果列表（以嵌入訊息展示）")
    @app_commands.describe(query="搜索關鍵字")
    async def searchlink(self, interaction: discord.Interaction, query: str):
        await interaction.response.defer()
        
        results = await self.search_yt_text(query)
        if not results:
            await self.send_message(interaction, "未找到任何結果，請嘗試其他關鍵字！")
            return

        embed = discord.Embed(title="YouTube 搜索結果", color=discord.Color.blue())
        for i, result in enumerate(results):
            embed.add_field(name=f"{i+1}. {result['title']}", value=result['url'], inline=False)

        await self.send_message(interaction, embed=embed)

    # ----------------- play 指令 -----------------
    @app_commands.command(name="play", description="使用YouTube鏈接播放")
    @app_commands.describe(query="YouTube 鏈接或搜索關鍵字")
    async def play(self, interaction: discord.Interaction, query: str):
        # defer
        await interaction.response.defer(ephemeral=False)
        await self._play(interaction, query)
    
    async def _play(self, interaction: discord.Interaction, query: str):
        """內部方法：處理播放邏輯（可被 slash command 和 callback 調用）"""
        member = interaction.user
        voice_state = getattr(member, "voice", None)
        voice_channel = getattr(voice_state, "channel", None)
        if not voice_channel:
            # 檢查是否已經 defer，如果沒有則使用 followup
            if interaction.response.is_done():
                await interaction.followup.send("請先加入語音頻道！", ephemeral=True)
            else:
                await interaction.response.send_message("請先加入語音頻道！", ephemeral=True)
            return

        # 連線或移動
        try:
            if not self.vc or not self.vc.is_connected():
                self.vc = await voice_channel.connect()
            elif self.vc.channel != voice_channel:
                await self.vc.move_to(voice_channel)
        except Exception as e:
            print(f"Error joining voice channel: {e}")
            if interaction.response.is_done():
                await interaction.followup.send("無法加入語音頻道！", ephemeral=True)
            else:
                await interaction.response.send_message("無法加入語音頻道！", ephemeral=True)
            return

        # 搜尋
        songs = await self.search_yt(query)
        if not songs:
            if interaction.response.is_done():
                await interaction.followup.send("未找到任何有效的音樂或播放列表。", ephemeral=True)
            else:
                await interaction.response.send_message("未找到任何有效的音樂或播放列表。", ephemeral=True)
            return

        # 播放
        if not self.is_playing:
            # 修复：清空旧的队列和链接，避免残留
            self.music_queue = songs
            if interaction.response.is_done():
                await interaction.followup.send("已加入到播放列表，開始播放 🎶")
            else:
                await interaction.response.send_message("已加入到播放列表，開始播放 🎶")
            await self.play_music(interaction)  # 注意這裡傳 interaction
        else:
            self.music_queue.extend(songs)
            if interaction.response.is_done():
                await interaction.followup.send("已加入到播放列表 🎶")
            else:
                await interaction.response.send_message("已加入到播放列表 🎶")



    @app_commands.command(name="skip", description="跳過當前播放歌曲")
    async def skip(self, interaction: discord.Interaction):
        await self._skip(interaction)
    
    async def _skip(self, interaction: discord.Interaction):
        """內部方法：跳過當前播放歌曲"""
        if self.vc and self.vc.is_playing():
            self.vc.stop()
            await self.send_message(interaction, "下面一位")
        else:
            await self.send_message(interaction, "空空如也~")


    @app_commands.command(name="pause", description="暫停或恢復播放")
    async def pause(self, interaction: discord.Interaction):
        if self.is_playing:
            self.vc.pause()
            self.is_playing = False
            self.is_paused = True
            await self.send_message(interaction, "已暫停播放")
        elif self.is_paused:
            self.vc.resume()
            self.is_paused = False
            self.is_playing = True
            await self.send_message(interaction, "已恢復播放")

    @app_commands.command(name="queue", description="顯示播放列表")
    async def queue(self, interaction: discord.Interaction):
        await self._queue(interaction)
    
    async def _queue(self, interaction: discord.Interaction):
        """內部方法：顯示播放列表"""
        if not self.music_queue:
            await self.send_message(interaction, "No music in queue")
            return
        msg = "\n".join(f"#{i+1} - {song['title']}" for i, song in enumerate(self.music_queue))
        await self.send_message(interaction, f"```播放順序:\n{msg}```")

    @app_commands.command(name="clear", description="停止播放並清空播放列表")
    async def clear(self, interaction: discord.Interaction):
        if self.vc and self.is_playing:
            self.vc.stop()
        self.music_queue.clear()
        self.original_link.clear()
        await self.send_message(interaction, "Music queue cleared")

    @app_commands.command(name="dc", description="讓機器人離開語音頻道")
    async def dc(self, interaction: discord.Interaction):
        await self._dc(interaction)
    
    async def _dc(self, interaction: discord.Interaction):
        """內部方法：讓機器人離開語音頻道"""
        if self.vc and self.vc.is_connected():
            self.force_stop = True
            self.vc.stop()
            await self.vc.disconnect()
            self.vc = None
            self.music_queue.clear()
            self.original_link.clear()
            self.is_playing = False
            self.is_paused = False
            await self.send_message(interaction, "已離開語音頻道")
        else:
            await self.send_message(interaction, "機器人不在語音頻道！")

    @app_commands.command(name="re", description="移除播放列表最後一首歌曲")
    async def re(self, interaction: discord.Interaction):
        if self.music_queue:
            self.music_queue.pop()
            self.original_link.pop()
            await self.send_message(interaction, "Last song removed")
        else:
            await self.send_message(interaction, "Queue is already empty")
