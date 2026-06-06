import discord
import os
from dotenv import load_dotenv
import traceback
import asyncio
import time
import aiohttp

load_dotenv()

ALL_MEMBERS_CHANNEL = int(os.getenv("ALL_MEMBERS_CHANNEL"))
EXECUTIVE_CHANNEL = int(os.getenv("EXECUTIVES_CHANNEL"))
VP_CHANNEL = int(os.getenv("VP_CHANNEL"))
VIP_CHANNEL = int(os.getenv("VIP_CHANNEL"))
MEMBERS_CHANNEL = int(os.getenv("MEMBERS_CHANNEL"))
BOTS_CHANNEL = int(os.getenv("BOTS_CHANNEL"))

WEBSITE_URL = "https://mcc-site-virid.vercel.app/" # Adjustable

class Client(discord.Client):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.invites = {}
        self.update_lock = asyncio.Lock()
        self.last_update = 0

    def on_error(self, event, *args, **kwargs):
        print("ERROR IN EVENT: ", event)
        traceback.print_exc()

    async def on_ready(self):
        
        for guild in self.guilds:
            await self.update_server_stats(guild)
            self.invites[guild.id] = {
                invite.code: invite.uses
                for invite in await guild.invites()
            }
                
        print(f"Logged on as {self.user}!")

    async def update_server_stats(self, guild):
        
        async with self.update_lock: 

            now = time.time()

            # prevents spam (10 second cooldown)
            if now - self.last_update < 30:
                return
            
            self.last_update = now

            executive_role = guild.get_role(int(os.getenv("EXECUTIVE_ROLE")))
            vp_role = guild.get_role(int(os.getenv("VP_ROLE")))
            vip_role = guild.get_role(int(os.getenv("VIP_ROLE")))
            member_role = guild.get_role(int(os.getenv("MEMBER_ROLE")))

            total_members = guild.member_count

            bot_count = len([mems for mems in guild.members if mems.bot])

            executive_count = sum(1 for m in guild.members if executive_role in m.roles) #len(executive_role.members)
            vp_count = sum(1 for m in guild.members if vp_role in m.roles) #len(vp_role.members)
            vip_count = sum(1 for m in guild.members if vip_role in m.roles) #len(vip_role.members)
            member_count = sum(1 for m in guild.members if member_role in m.roles) #len(member_role.members)

            channels = {
                ALL_MEMBERS_CHANNEL: f"All Members: {member_count}",
                EXECUTIVE_CHANNEL: f"Executives: {executive_count}",
                VP_CHANNEL: f"Vice Presidents: {vp_count}",
                VIP_CHANNEL: f"VIP: {vip_count}",
                BOTS_CHANNEL: f"Bots: {bot_count}"
            }

            for channel_id, name in channels.items():

                print("Updating stats for: ", guild.name)
                    
                channel = guild.get_channel(channel_id)

                print("Channel found: ", channel_id, channel)

                if channel and channel.name != name:
                    await channel.edit(name = name)

    async def on_disconnect(self):
        print(f"Bot disconnected.")

    async def on_member_update(self, before, after):
    
        if before.roles != after.roles:
            await self.update_server_stats(after.guild)

    async def get_inviter(self, member):

        guild = member.guild

        new_invites = await guild.invites()

        old_invites = self.invites.get(guild.id, {})

        inviter = None

        for invite in new_invites:

            old_uses = old_invites.get(invite.code, 0)

            if invite.uses > old_uses:
                inviter = invite.inviter
                break

        self.invites[guild.id] = {
            invite.code: invite.uses
            for invite in new_invites
        }

        return inviter
    

    async def on_member_join(self, member):

        print(f"{member} joined!")

        inviter = await self.get_inviter(member)

        log_channel = member.guild.get_channel(int(os.getenv("LOG_CHANNEL_ID")))

        if inviter:
            source = inviter.mention

            guild_lb = self.invite_leaderboard.setdefault(member.guild.id, {})

            guild_lb[inviter.id] = guild_lb.get(inviter.id, 0) + 1

        else:
            source = "Unknown / Website"

        await log_channel.send(
            f"🎉 {member.name} is member #{member.guild.member_count}!\n"
            f"Invited by: {source}"
        )

        await self.update_server_stats(member.guild)

    async def on_member_remove(self, member):

        log_channel = member.guild.get_channel(int(os.getenv("LOG_CHANNEL_ID")))

        await log_channel.send(
            f"👋 {member} left the server."
        )

        await self.update_server_stats(member.guild)

    async def on_message(self, message):

        if message.author.bot:
            return
        
        if message.content.lower() == "!status":

            url = WEBSITE_URL

            try:
                start = time.perf_counter()

                async with aiohttp.ClientSession() as session:
                    async with session.get(url) as response:

                        elapsed_ms = (time.perf_counter() - start) * 1000

                        status = response.status

                        emoji = "✅" if 200 <= status < 400 else "❌"

                        await message.channel.send(
                            f"{emoji} **Status:** {status};  "
                            f"🌐 **URL:** {url};  "
                            f"⏱️ **Response Time:** {elapsed_ms:.2f} ms"
                        )

            except Exception as e:
                await message.channel.send(
                    f"❌ Could not reach: `{url}`.  "
                    f"Error: {e}"
                )

intents = discord.Intents.default()
intents.message_content = True
intents.members = True
intents.guilds = True

client = Client(intents=intents)


if __name__ == '__main__':
    client.run(os.getenv("DISCORD_TOKEN"))