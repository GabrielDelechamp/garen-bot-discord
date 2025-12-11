import aiohttp
import discord
from discord.ext import commands
from discord import app_commands
from bs4 import BeautifulSoup
import logging

logger = logging.getLogger(__name__)

PATCH_LIST_URL = "https://www.leagueoflegends.com/fr-fr/news/tags/patch-notes/"


class Patchnote(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    async def fetch(self, session, url):
        async with session.get(url) as resp:
            if resp.status != 200:
                raise Exception(f"HTTP {resp.status}")
            return await resp.text()

    async def fetch_latest_patch(self):
        async with aiohttp.ClientSession() as session:

            # ---- 1. Récupérer la liste des patchs ----
            html = await self.fetch(session, PATCH_LIST_URL)
            soup = BeautifulSoup(html, "html.parser")

            # Tous les liens vers des patch-notes LoL
            patch_links = soup.select("a[href*='/fr-fr/news/game-updates/patch-']")
            if not patch_links:
                raise Exception("Aucun patch trouvé sur la page.")

            # Premier patch
            first_patch = patch_links[0]
            patch_url = "https://www.leagueoflegends.com" + first_patch["href"]

            # ---- 2. Charger la page du patch ----
            patch_html = await self.fetch(session, patch_url)
            patch_soup = BeautifulSoup(patch_html, "html.parser")

            # ---- 3. Récupérer le titre ----
            h1 = patch_soup.select_one("h1")
            if not h1:
                raise Exception("Impossible de trouver le titre du patch.")
            title = h1.get_text(strip=True)

            # ---- 4. Récupérer l'image via TON XPATH converti ----
            img = patch_soup.select_one(
                "section:nth-of-type(3) div div div div div div:nth-of-type(2) div div span a img"
            )

            if not img:
                raise Exception("Impossible de trouver l'image via le XPATH.")

            img_url = img.get("src") or img.get("data-src")
            if img_url.startswith("//"):
                img_url = "https:" + img_url

            return title, patch_url, img_url

    @app_commands.command(
        name="garen-patchnote",
        description="Affiche le dernier patch League of Legends"
    )
    async def patch(self, interaction: discord.Interaction):
        await interaction.response.defer()

        try:
            title, url, img = await self.fetch_latest_patch()

            embed = discord.Embed(
                title=title,
                url=url,
                description="Dernier patch officiel League of Legends",
                color=0x00ADEF
            )
            embed.set_image(url=img)

            await interaction.followup.send(embed=embed)

        except Exception as e:
            logger.error(f"Erreur patchnote: {e}")
            await interaction.followup.send(f"❌ {e}", ephemeral=True)


async def setup(bot):
    await bot.add_cog(Patchnote(bot))
