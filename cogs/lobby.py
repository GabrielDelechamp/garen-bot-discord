import discord
from discord.ext import commands
from discord import app_commands
import logging
from typing import Optional

from utils.riot_api import RiotAPIClient, RiotAPIError
from utils.embed_builder import EmbedBuilder
from config import Config


logger = logging.getLogger(__name__)

class LobbyCog(commands.Cog):
    """Cog pour gérer les salons de jeu"""

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
        logger.error(f"RIOT_API_KEY chargé: {repr(Config.RIOT_API_KEY)}")
        await self.riot_api.__aenter__()
         
        # Précharger les données champions
        await self.riot_api.get_champion_data()
        logger.info("Client Riot API initialisé pour LobbyCog")
    
    async def cog_unload(self):
        """Nettoie le client API lors du déchargement du Cog"""
        if self.riot_api:
            await self.riot_api.__aexit__(None, None, None)
            logger.info("Client Riot API fermé pour SummonerCog")
    

    @app_commands.command(
        name="garen-lobby",
        description="Affiche les informations d'un salon de jeu League of Legends"
    )
    @app_commands.describe(
        nom="Nom de l'invocateur au format GameName#Tagline (ex: Hide on bush#KR1)"
    )
    async def lobby(self, interaction: discord.Interaction, nom: str):
        """Commande pour afficher les infos d'un lobby"""
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
            logger.info(f"Recherche du lobby pour l'invocateur: {game_name}#{tag_line}")
            
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

            # Récupérer les infos du lobby
            lobby = await self.riot_api.get_lobby_by_puuid(puuid)

            if not lobby:
                embed = EmbedBuilder.create_error_embed(
                    "Erreur",
                    "Le joueur n'est pas en partie actuellement.",
                    error_type="error"
                )
                await interaction.followup.send(embed=embed)
                return
            


            participants = lobby["participants"]
            enriched_participants = []

            for participant in participants:
                champion_id = participant["championId"]
                riot_id = participant["riotId"]
                team_id = participant["teamId"]
                participant_puuid = participant["puuid"]

                #Récupérer le pseudo du joueur
                champion_name = self.riot_api.get_champion_name_by_id(champion_id)

                if participant_puuid != None:

                    #Récupérer les statistiques de rang
                    if participant_puuid != None:
                        league_entries = await self.riot_api.get_league_entries(participant_puuid)
                        solo_rank = next(
                            (entry for entry in league_entries 
                            if entry.get("queueType") == "RANKED_SOLO_5x5"),
                            None
                        )
                    else:
                        solo_rank = None
                    # Formatter les données
                    enriched_participants.append({
                        "riot_id": riot_id,
                        "champion": champion_name,
                        "teamId": team_id,
                        "rank": solo_rank["tier"] + " " + solo_rank["rank"] if solo_rank else "Unranked",
                        "wr" : "None",
                        "tags" : "None",
                        "games" : "None",
                    })

                else :
                    enriched_participants.append({
                        "riot_id": riot_id,
                        "champion": champion_name,
                        "teamId": team_id,
                        "rank": "STREAMER MODE",
                        "wr" : "?",
                        "tags" : "?",
                        "games" : "?",
                    })
            #Créer et envoyer l'embed avec les infos du lobby
            embed = EmbedBuilder.create_lobby_embed(
                enriched_participants, 
                lobby["gameMode"],
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
    await bot.add_cog(LobbyCog(bot))