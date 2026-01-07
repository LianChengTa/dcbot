


# ----------------- Button 按鈕 -----------------
class ButtonView(discord.ui.View):
    def __init__(self, MusicCog):
        super().__init__(timeout=None)
        self.MusicCog = MusicCog

    @discord.ui.button(label="下一個", style=discord.ButtonStyle.blurple)
    async def skip_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.MusicCog.skip(interaction)

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
        await self.MusicCog.queue(interaction)

    @discord.ui.button(label="高歌離席", style=discord.ButtonStyle.red)
    async def leave_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.MusicCog.dc(interaction)
        await self.MusicCog.send_message(interaction, "仔見~")