import discord
from discord.ext import commands
from discord import app_commands
import logging
from typing import Optional

from utils.riot_api import RiotAPIClient, RiotAPIError
from utils.embed_builder import EmbedBuilder
from config import Config

logger = logging.getLogger(__name__)

class SummonerCog(commands.Cog):
    """Commandes liées aux invocateurs League of Legends"""
    
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.riot_api: Optional[RiotAPIClient] = None
    
    async def cog_load(self):
        """Initialise le client API lors du chargement du Cog"""
        self.riot_api = RiotAPIClient(
            api_key=Config.RIOT_API_KEY,
            region=Config.REGION,
            routing=Config.get_routing()
        )
        await self.riot_api.__aenter__()
        
        # Précharger les données champions
        await self.riot_api.get_champion_data()
        logger.info("Client Riot API initialisé pour SummonerCog")
    
    async def cog_unload(self):
        """Nettoie le client API lors du déchargement du Cog"""
        if self.riot_api:
            await self.riot_api.__aexit__(None, None, None)
            logger.info("Client Riot API fermé pour SummonerCog")
    
    @app_commands.command(
        name="garen-summoner",
        description="Affiche les informations d'un invocateur League of Legends"
    )
    @app_commands.describe(
        nom="Nom de l'invocateur au format GameName#Tagline (ex: Hide on bush#KR1)"
    )
    async def summoner(self, interaction: discord.Interaction, nom: str):
        """Commande pour afficher les infos d'un summoner"""
        await interaction.response.defer()
        
        try:
            # Valider et parser le Riot ID
            if "#" not in nom:
                embed = EmbedBuilder.create_error_embed(
                    "Format Invalide",
                    "❌ Utilise le format **GameName#Tagline**\n"
                    "Exemple: `Hide on bush#KR1`",
                    error_type="warning"
                )
                await interaction.followup.send(embed=embed)
                return
            
            game_name, tag_line = nom.split("#", 1)
            logger.info(f"Recherche du joueur: {game_name}#{tag_line}")
            
            # Récupérer le compte
            account = await self.riot_api.get_account_by_riot_id(game_name, tag_line)
            
            if not account:
                embed = EmbedBuilder.create_error_embed(
                    "Joueur Introuvable",
                    f"Le joueur **{nom}** n'existe pas sur **{Config.REGION.upper()}**",
                    error_type="error"
                )
                await interaction.followup.send(embed=embed)
                return
            
            puuid = account["puuid"]
            
            # Récupérer les infos du summoner
            summoner = await self.riot_api.get_summoner_by_puuid(puuid)
            
            if not summoner:
                embed = EmbedBuilder.create_error_embed(
                    "Erreur",
                    "Impossible de récupérer les informations du summoner",
                    error_type="error"
                )
                await interaction.followup.send(embed=embed)
                return
            
            # Récupérer le rang
            league_entries = await self.riot_api.get_league_entries(puuid)
            solo_rank = next(
                (entry for entry in league_entries 
                 if entry.get("queueType") == "RANKED_SOLO_5x5"),
                None
            )
            
            # Récupérer la maîtrise
            masteries = await self.riot_api.get_champion_masteries(puuid, count=1)
            mastery_data = None
            
            if masteries:
                top_mastery = masteries[0]
                champion_name = self.riot_api.get_champion_name_by_id(
                    top_mastery["championId"]
                )
                
                if champion_name:
                    mastery_data = {
                        "champion_name": champion_name,
                        "level": top_mastery["championLevel"],
                        "points": top_mastery["championPoints"]
                    }
            
            # Créer et envoyer l'embed
            embed = EmbedBuilder.create_summoner_embed(
                game_name=game_name,
                tag_line=tag_line,
                level=summoner["summonerLevel"],
                rank_data=solo_rank,
                mastery_data=mastery_data,
                profile_icon_id=summoner["profileIconId"]
            )
            
            await interaction.followup.send(embed=embed)
            logger.info(f"Infos envoyées pour {game_name}#{tag_line}")
        
        except RiotAPIError as e:
            logger.error(f"Erreur API Riot: {e}")
            embed = EmbedBuilder.create_error_embed(
                "Erreur API",
                "L'API Riot Games est temporairement indisponible. Réessaye plus tard.",
                error_type="error"
            )
            await interaction.followup.send(embed=embed)
        
        except Exception as e:
            logger.error(f"Erreur inattendue dans summoner: {e}", exc_info=True)
            embed = EmbedBuilder.create_error_embed(
                "Erreur Interne",
                "Une erreur inattendue s'est produite. Contacte un administrateur.",
                error_type="error"
            )
            await interaction.followup.send(embed=embed)

async def setup(bot: commands.Bot):
    """Charge le Cog"""
    await bot.add_cog(SummonerCog(bot))