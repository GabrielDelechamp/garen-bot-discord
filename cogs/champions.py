import discord
from discord.ext import commands
from discord import app_commands
import logging
import aiohttp
from io import BytesIO
from PIL import Image
from typing import Optional
import json

from utils.riot_api import RiotAPIClient, RiotAPIError
from utils.embed_builder import EmbedBuilder
from utils.constants import normalize_champion_name
from config import Config

logger = logging.getLogger(__name__)

class ChampionsCog(commands.Cog):
    """Commandes liées aux champions League of Legends"""
    
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.riot_api: Optional[RiotAPIClient] = None
        self.champion_map: dict = {}
    
    async def cog_load(self):
        """Initialise le client API et charge les données champions"""
        self.riot_api = RiotAPIClient(
            api_key=Config.RIOT_API_KEY,
            region=Config.REGION,
            routing=Config.get_routing()
        )
        await self.riot_api.__aenter__()
        
        # Charger le mapping champions
        try:
            with open("data/champions.json", "r", encoding="utf-8") as f:
                self.champion_map = json.load(f)
            logger.info(f"Mapping champions chargé: {len(self.champion_map)} champions")
        except FileNotFoundError:
            logger.warning("Fichier champions.json non trouvé")
        
        logger.info("Client Riot API initialisé pour ChampionsCog")
    
    async def cog_unload(self):
        """Nettoie le client API"""
        if self.riot_api and self.riot_api.session:
            await self.riot_api.__aexit__(None, None, None)
            logger.info("Client Riot API fermé pour ChampionsCog")
    
    async def fetch_champion_icon(
        self,
        champion_name: str,
        size: int = 64
    ) -> Optional[Image.Image]:
        """
        Récupère l'icône d'un champion depuis Data Dragon
        
        Args:
            champion_name: Nom du champion
            size: Taille de l'image (défaut: 64x64)
        
        Returns:
            Image PIL ou None si échec
        """
        try:
            safe_name = normalize_champion_name(champion_name)
            url = (
                f"{Config.DDRAGON_BASE_URL}/{Config.DDRAGON_VERSION}/"
                f"img/champion/{safe_name}.png"
            )
            
            if not self.riot_api.session:
                return None
            
            async with self.riot_api.session.get(url) as response:
                if response.status != 200:
                    logger.warning(f"Impossible de récupérer l'icône pour {champion_name}")
                    return None
                
                image_data = await response.read()
                img = Image.open(BytesIO(image_data))
                img = img.convert("RGBA").resize((size, size), Image.Resampling.LANCZOS)
                return img
        
        except Exception as e:
            logger.error(f"Erreur lors de la récupération de l'icône {champion_name}: {e}")
            return None
    
    def create_champion_grid(
        self,
        images: list[Image.Image],
        cols: int = 5
    ) -> BytesIO:
        """
        Crée une grille d'images de champions
        
        Args:
            images: Liste des images PIL
            cols: Nombre de colonnes
        
        Returns:
            Buffer contenant l'image PNG
        """
        if not images:
            raise ValueError("Liste d'images vide")
        
        img_size = 64
        rows = (len(images) + cols - 1) // cols
        
        # Créer l'image combinée
        grid = Image.new(
            "RGBA",
            (cols * img_size, rows * img_size),
            (47, 49, 54, 255)  # Couleur Discord dark
        )
        
        # Coller chaque image
        for idx, img in enumerate(images):
            x = (idx % cols) * img_size
            y = (idx // cols) * img_size
            grid.paste(img, (x, y), img)
        
        # Sauvegarder dans un buffer
        buffer = BytesIO()
        grid.save(buffer, format="PNG")
        buffer.seek(0)
        
        return buffer
    
    @app_commands.command(
        name="garen-rotation",
        description="Affiche la rotation gratuite des champions de la semaine"
    )
    async def rotation(self, interaction: discord.Interaction):
        """Commande pour afficher la rotation gratuite"""
        await interaction.response.defer()
        
        try:
            # Récupérer la rotation
            rotation_data = await self.riot_api.get_champion_rotation()
            
            if not rotation_data:
                embed = EmbedBuilder.create_error_embed(
                    "Erreur",
                    "Impossible de récupérer la rotation gratuite",
                    error_type="error"
                )
                await interaction.followup.send(embed=embed)
                return
            
            free_champion_ids = rotation_data.get("freeChampionIds", [])
            
            if not free_champion_ids:
                embed = EmbedBuilder.create_error_embed(
                    "Aucune Rotation",
                    "Aucun champion gratuit trouvé cette semaine",
                    error_type="warning"
                )
                await interaction.followup.send(embed=embed)
                return
            
            logger.info(f"Rotation de {len(free_champion_ids)} champions")
            
            # Récupérer les icônes
            icons = []
            for champion_id in free_champion_ids:
                champion_name = self.champion_map.get(str(champion_id))
                
                if not champion_name:
                    logger.warning(f"Champion ID {champion_id} non trouvé dans le mapping")
                    continue
                
                icon = await self.fetch_champion_icon(champion_name)
                if icon:
                    icons.append(icon)
            
            if not icons:
                embed = EmbedBuilder.create_error_embed(
                    "Erreur",
                    "Impossible de récupérer les icônes des champions",
                    error_type="error"
                )
                await interaction.followup.send(embed=embed)
                return
            
            # Créer la grille
            grid_buffer = self.create_champion_grid(icons, cols=5)
            
            # Créer l'embed
            embed = EmbedBuilder.create_rotation_embed(len(icons))
            embed.set_image(url="attachment://rotation.png")
            
            # Envoyer
            file = discord.File(fp=grid_buffer, filename="rotation.png")
            await interaction.followup.send(embed=embed, file=file)
            
            logger.info(f"Rotation envoyée: {len(icons)} champions")
        
        except RiotAPIError as e:
            logger.error(f"Erreur API Riot: {e}")
            embed = EmbedBuilder.create_error_embed(
                "Erreur API",
                "L'API Riot Games est temporairement indisponible",
                error_type="error"
            )
            await interaction.followup.send(embed=embed)
        
        except Exception as e:
            logger.error(f"Erreur inattendue dans rotation: {e}", exc_info=True)
            embed = EmbedBuilder.create_error_embed(
                "Erreur Interne",
                "Une erreur inattendue s'est produite",
                error_type="error"
            )
            await interaction.followup.send(embed=embed)

async def setup(bot: commands.Bot):
    """Charge le Cog"""
    await bot.add_cog(ChampionsCog(bot))