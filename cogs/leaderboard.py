import discord
from discord.ext import commands
from discord import app_commands
import logging
import json
import os
from typing import Optional, List, Dict
from datetime import datetime, timedelta
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont
from io import BytesIO
import aiohttp

from utils.riot_api import RiotAPIClient, RiotAPIError
from utils.embed_builder import EmbedBuilder
from config import Config

logger = logging.getLogger(__name__)

class LeaderboardCog(commands.Cog):
    """Commandes liées au leaderboard local des serveurs"""
    
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.riot_api: Optional[RiotAPIClient] = None
        self.data_dir = Path("data/leaderboards")
        self.data_dir.mkdir(parents=True, exist_ok=True)
        
        # Ordre des rangs pour le tri
        self.rank_order = {
            "IRON": 0, "BRONZE": 1, "SILVER": 2, "GOLD": 3,
            "PLATINUM": 4, "EMERALD": 5, "DIAMOND": 6,
            "MASTER": 7, "GRANDMASTER": 8, "CHALLENGER": 9
        }
        self.division_order = {"IV": 0, "III": 1, "II": 2, "I": 3}
    
    async def cog_load(self):
        """Initialise le client API"""
        self.riot_api = RiotAPIClient(
            api_key=Config.RIOT_API_KEY,
            region=Config.REGION,
            routing=Config.get_routing()
        )
        await self.riot_api.__aenter__()
        logger.info("Client Riot API initialisé pour LeaderboardCog")
    
    async def cog_unload(self):
        """Nettoie le client API"""
        if self.riot_api and self.riot_api.session:
            await self.riot_api.__aexit__(None, None, None)
            logger.info("Client Riot API fermé pour LeaderboardCog")
    
    def get_leaderboard_file(self, guild_id: int) -> Path:
        """Retourne le chemin du fichier leaderboard pour un serveur"""
        return self.data_dir / f"{guild_id}.json"
    
    def load_leaderboard(self, guild_id: int) -> Dict:
        """Charge le leaderboard d'un serveur"""
        file_path = self.get_leaderboard_file(guild_id)
        
        if not file_path.exists():
            return {"guild_id": str(guild_id), "players": []}
        
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Erreur lors du chargement du leaderboard: {e}")
            return {"guild_id": str(guild_id), "players": []}
    
    def save_leaderboard(self, guild_id: int, data: Dict):
        """Sauvegarde le leaderboard d'un serveur"""
        file_path = self.get_leaderboard_file(guild_id)
        
        try:
            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
        except Exception as e:
            logger.error(f"Erreur lors de la sauvegarde du leaderboard: {e}")
            raise
    
    def player_exists(self, leaderboard: Dict, puuid: str) -> bool:
        """Vérifie si un joueur existe déjà dans le leaderboard"""
        return any(p["puuid"] == puuid for p in leaderboard["players"])
    
    def get_player_by_discord_id(self, leaderboard: Dict, discord_id: int) -> List[Dict]:
        """Récupère tous les comptes d'un utilisateur Discord"""
        return [p for p in leaderboard["players"] if p["discord_user_id"] == str(discord_id)]
    
    @app_commands.command(
        name="garen-add-localserver",
        description="Ajoute un compte League of Legends au leaderboard du serveur"
    )
    @app_commands.describe(
        riot_id="Riot ID au format GameName#Tagline (ex: Hide on bush#KR1)"
    )
    async def add_localserver(self, interaction: discord.Interaction, riot_id: str):
        """Ajoute un compte au leaderboard local"""
        await interaction.response.defer()
        
        try:
            # Valider le format Riot ID
            if "#" not in riot_id:
                embed = EmbedBuilder.create_error_embed(
                    "Format Invalide",
                    "❌ Utilise le format **GameName#Tagline**\n"
                    "Exemple: `Hide on bush#KR1`",
                    error_type="warning"
                )
                await interaction.followup.send(embed=embed)
                return
            
            game_name, tag_line = riot_id.split("#", 1)
            logger.info(f"Ajout du joueur: {game_name}#{tag_line} par {interaction.user}")
            
            # Récupérer le compte Riot
            account = await self.riot_api.get_account_by_riot_id(game_name, tag_line)
            
            if not account:
                embed = EmbedBuilder.create_error_embed(
                    "Joueur Introuvable",
                    f"Le joueur **{riot_id}** n'existe pas sur **{Config.REGION.upper()}**",
                    error_type="error"
                )
                await interaction.followup.send(embed=embed)
                return
            
            puuid = account["puuid"]
            
            # Charger le leaderboard
            leaderboard = self.load_leaderboard(interaction.guild_id)
            
            # Vérifier si le compte existe déjà
            if self.player_exists(leaderboard, puuid):
                embed = EmbedBuilder.create_error_embed(
                    "Compte Déjà Ajouté",
                    f"Le compte **{riot_id}** est déjà dans le leaderboard !",
                    error_type="warning"
                )
                await interaction.followup.send(embed=embed)
                return
            
            # Ajouter le joueur
            player_data = {
                "discord_user_id": str(interaction.user.id),
                "riot_id": f"{game_name}#{tag_line}",
                "puuid": puuid,
                "added_at": datetime.utcnow().isoformat()
            }
            
            leaderboard["players"].append(player_data)
            self.save_leaderboard(interaction.guild_id, leaderboard)
            
            # Compter les comptes de l'utilisateur
            user_accounts = self.get_player_by_discord_id(leaderboard, interaction.user.id)
            
            embed = discord.Embed(
                title="✅ Compte Ajouté",
                description=f"**{riot_id}** a été ajouté au leaderboard !",
                color=discord.Color.green()
            )
            embed.add_field(
                name="👤 Ajouté par",
                value=interaction.user.mention,
                inline=True
            )
            embed.add_field(
                name="📊 Comptes enregistrés",
                value=f"{len(user_accounts)} compte(s)",
                inline=True
            )
            embed.set_footer(text=f"Serveur: {interaction.guild.name}")
            
            await interaction.followup.send(embed=embed)
            logger.info(f"Compte {riot_id} ajouté au leaderboard de {interaction.guild.name}")
        
        except RiotAPIError as e:
            logger.error(f"Erreur API Riot: {e}")
            embed = EmbedBuilder.create_error_embed(
                "Erreur API",
                "L'API Riot Games est temporairement indisponible.",
                error_type="error"
            )
            await interaction.followup.send(embed=embed)
        
        except Exception as e:
            logger.error(f"Erreur dans add_localserver: {e}", exc_info=True)
            embed = EmbedBuilder.create_error_embed(
                "Erreur Interne",
                "Une erreur s'est produite lors de l'ajout du compte.",
                error_type="error"
            )
            await interaction.followup.send(embed=embed)
    
    def calculate_rank_score(self, rank_data: Optional[Dict]) -> int:
        """Calcule un score pour trier les joueurs"""
        if not rank_data:
            return -1  # Unranked en dernier
        
        tier = rank_data.get("tier", "IRON")
        rank = rank_data.get("rank", "IV")
        lp = rank_data.get("leaguePoints", 0)
        
        # Score: tier * 1000 + division * 100 + LP
        tier_score = self.rank_order.get(tier, 0) * 1000
        
        # Master+ n'ont pas de division
        if tier in ["MASTER", "GRANDMASTER", "CHALLENGER"]:
            division_score = 300
        else:
            division_score = self.division_order.get(rank, 0) * 100
        
        return tier_score + division_score + lp
    
    async def fetch_profile_icon(self, icon_id: int) -> Optional[Image.Image]:
        """Récupère l'icône de profil d'un joueur"""
        try:
            url = f"{Config.DDRAGON_BASE_URL}/{Config.DDRAGON_VERSION}/img/profileicon/{icon_id}.png"
            
            async with self.riot_api.session.get(url) as response:
                if response.status != 200:
                    return None
                
                image_data = await response.read()
                img = Image.open(BytesIO(image_data))
                return img.convert("RGBA")
        
        except Exception as e:
            logger.error(f"Erreur lors de la récupération de l'icône {icon_id}: {e}")
            return None
    
    def create_circular_mask(self, size: int) -> Image.Image:
        """Crée un masque circulaire"""
        mask = Image.new("L", (size, size), 0)
        draw = ImageDraw.Draw(mask)
        draw.ellipse((0, 0, size, size), fill=255)
        return mask
    
    async def create_podium_image(self, top_players: List[Dict]) -> BytesIO:
        """Crée une image de podium avec les 3 meilleurs joueurs"""
        # Dimensions
        width = 800
        podium_height = 400
        
        # Couleurs
        bg_color = (47, 49, 54)
        gold = (255, 215, 0)
        silver = (192, 192, 192)
        bronze = (205, 127, 50)
        
        # Créer l'image
        img = Image.new("RGBA", (width, podium_height), bg_color)
        draw = ImageDraw.Draw(img)
        
        # Positions et hauteurs du podium
        podium_config = [
            {"pos": 1, "x": 150, "height": 180, "color": gold, "y_offset": 0},      # 1er
            {"pos": 0, "x": 30, "height": 140, "color": silver, "y_offset": 40},   # 2ème
            {"pos": 2, "x": 270, "height": 100, "color": bronze, "y_offset": 80}   # 3ème
        ]
        
        try:
            font_large = ImageFont.truetype("arial.ttf", 24)
            font_small = ImageFont.truetype("arial.ttf", 16)
        except:
            font_large = ImageFont.load_default()
            font_small = ImageFont.load_default()
        
        for idx, config in enumerate(podium_config):
            if idx >= len(top_players):
                continue
            
            player = top_players[config["pos"]]
            
            # Dessiner le podium
            podium_y = podium_height - config["height"]
            podium_rect = [
                config["x"],
                podium_y,
                config["x"] + 100,
                podium_height
            ]
            draw.rectangle(podium_rect, fill=config["color"])
            
            # Numéro de place
            place_text = f"#{config['pos'] + 1}"
            bbox = draw.textbbox((0, 0), place_text, font=font_large)
            text_width = bbox[2] - bbox[0]
            draw.text(
                (config["x"] + 50 - text_width // 2, podium_y + 10),
                place_text,
                fill=(0, 0, 0),
                font=font_large
            )
            
            # Récupérer et afficher l'icône de profil
            icon = await self.fetch_profile_icon(player.get("profile_icon_id", 1))
            
            if icon:
                icon_size = 80
                icon = icon.resize((icon_size, icon_size), Image.Resampling.LANCZOS)
                
                # Appliquer le masque circulaire
                mask = self.create_circular_mask(icon_size)
                
                # Position de l'icône (au-dessus du podium)
                icon_x = config["x"] + 10
                icon_y = podium_y - icon_size - 10 + config["y_offset"]
                
                img.paste(icon, (icon_x, icon_y), mask)
            
            # Nom du joueur (sous l'icône)
            name_parts = player["riot_id"].split("#")
            game_name = name_parts[0] if len(name_parts) > 0 else "Unknown"
            
            # Limiter la longueur du nom
            if len(game_name) > 10:
                game_name = game_name[:10] + "..."
            
            bbox = draw.textbbox((0, 0), game_name, font=font_small)
            text_width = bbox[2] - bbox[0]
            draw.text(
                (config["x"] + 50 - text_width // 2, podium_y - 25 + config["y_offset"]),
                game_name,
                fill=(255, 255, 255),
                font=font_small
            )
            
            # Rang
            rank_text = player.get("rank_display", "Unranked")
            bbox = draw.textbbox((0, 0), rank_text, font=font_small)
            text_width = bbox[2] - bbox[0]
            draw.text(
                (config["x"] + 50 - text_width // 2, podium_y + 40),
                rank_text,
                fill=(0, 0, 0),
                font=font_small
            )
            
            # LP
            lp_text = f"{player.get('lp', 0)} LP"
            bbox = draw.textbbox((0, 0), lp_text, font=font_small)
            text_width = bbox[2] - bbox[0]
            draw.text(
                (config["x"] + 50 - text_width // 2, podium_y + 65),
                lp_text,
                fill=(0, 0, 0),
                font=font_small
            )
        
        # Sauvegarder
        buffer = BytesIO()
        img.save(buffer, format="PNG")
        buffer.seek(0)
        
        return buffer
    
    def load_daily_lp_history(self, guild_id: int) -> Dict:
        """Charge l'historique LP de la journée"""
        file_path = self.data_dir / f"{guild_id}_lp_history.json"
        
        if not file_path.exists():
            return {}
        
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Erreur lors du chargement de l'historique LP: {e}")
            return {}
    
    def save_daily_lp_history(self, guild_id: int, data: Dict):
        """Sauvegarde l'historique LP de la journée"""
        file_path = self.data_dir / f"{guild_id}_lp_history.json"
        
        try:
            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
        except Exception as e:
            logger.error(f"Erreur lors de la sauvegarde de l'historique LP: {e}")
    
    def get_today_date(self) -> str:
        """Retourne la date d'aujourd'hui au format YYYY-MM-DD"""
        return datetime.utcnow().strftime("%Y-%m-%d")
    
    def calculate_lp_gain(self, puuid: str, current_lp: int, guild_id: int) -> int:
        """Calcule le gain de LP de la journée"""
        today = self.get_today_date()
        lp_history = self.load_daily_lp_history(guild_id)
        
        # Structure: {puuid: {date: lp}}
        if puuid not in lp_history:
            lp_history[puuid] = {}
        
        # Si on a déjà une entrée pour aujourd'hui, calculer la différence
        if today in lp_history[puuid]:
            start_lp = lp_history[puuid][today]
            gain = current_lp - start_lp
        else:
            # Première entrée de la journée
            lp_history[puuid][today] = current_lp
            gain = 0
        
        # Nettoyer les anciennes dates (garder seulement les 7 derniers jours)
        cutoff_date = (datetime.utcnow() - timedelta(days=7)).strftime("%Y-%m-%d")
        lp_history[puuid] = {
            date: lp for date, lp in lp_history[puuid].items()
            if date >= cutoff_date
        }
        
        # Sauvegarder
        self.save_daily_lp_history(guild_id, lp_history)
        
        return gain
    
    async def check_player_online_status(self, puuid: str) -> bool:
        """
        Vérifie si un joueur est en ligne en regardant sa dernière partie
        Note: L'API Riot ne fournit pas de statut "en ligne" direct,
        on considère qu'un joueur est en ligne s'il a joué dans les 5 dernières minutes
        """
        try:
            # Récupérer les 5 dernières parties
            match_ids = await self.riot_api.get_match_history(puuid, count=5)
            
            if not match_ids:
                return False
            
            # Vérifier la dernière partie
            last_match_id = match_ids[0]
            match_data = await self.riot_api.get_match_details(last_match_id)
            
            if not match_data:
                return False
            
            # Vérifier le timestamp de la partie
            game_end_timestamp = match_data.get("info", {}).get("gameEndTimestamp", 0)
            
            if game_end_timestamp == 0:
                return False
            
            # Convertir en secondes
            game_end_time = game_end_timestamp / 1000
            current_time = datetime.utcnow().timestamp()
            
            # Considérer en ligne si partie terminée il y a moins de 5 minutes
            time_diff = current_time - game_end_time
            return time_diff < 300  # 5 minutes en secondes
        
        except Exception as e:
            logger.error(f"Erreur lors de la vérification du statut en ligne: {e}")
            return False
    
    @app_commands.command(
        name="garen-info",
        description="Affiche tous les comptes enregistrés avec le gain de LP du jour et le statut"
    )
    async def info(self, interaction: discord.Interaction):
        """Affiche les infos détaillées de tous les joueurs du serveur"""
        await interaction.response.defer()
        
        try:
            # Charger le leaderboard
            leaderboard_data = self.load_leaderboard(interaction.guild_id)
            
            if not leaderboard_data["players"]:
                embed = EmbedBuilder.create_error_embed(
                    "Aucun Joueur",
                    "Aucun joueur enregistré sur ce serveur.\n"
                    "Utilise `/garen-add-localserver` pour ajouter des comptes !",
                    error_type="warning"
                )
                await interaction.followup.send(embed=embed)
                return
            
            logger.info(f"Récupération des infos pour {len(leaderboard_data['players'])} joueurs")
            
            # Récupérer les infos de chaque joueur
            players_info = []
            
            for player in leaderboard_data["players"]:
                try:
                    # Récupérer le summoner
                    summoner = await self.riot_api.get_summoner_by_puuid(player["puuid"])
                    if not summoner:
                        continue
                    
                    # Récupérer le rang
                    league_entries = await self.riot_api.get_league_entries(player["puuid"])
                    solo_rank = next(
                        (entry for entry in league_entries 
                         if entry.get("queueType") == "RANKED_SOLO_5x5"),
                        None
                    )
                    
                    # Calculer le gain de LP
                    current_lp = solo_rank.get("leaguePoints", 0) if solo_rank else 0
                    lp_gain = self.calculate_lp_gain(player["puuid"], current_lp, interaction.guild_id)
                    
                    # Vérifier le statut en ligne
                    is_online = await self.check_player_online_status(player["puuid"])
                    
                    # Préparer les données
                    player_data = {
                        "riot_id": player["riot_id"],
                        "discord_user_id": player["discord_user_id"],
                        "level": summoner.get("summonerLevel", 0),
                        "is_online": is_online,
                        "lp_gain": lp_gain
                    }
                    
                    # Formater les infos de rang
                    if solo_rank:
                        tier = solo_rank.get("tier", "UNRANKED")
                        rank = solo_rank.get("rank", "")
                        lp = solo_rank.get("leaguePoints", 0)
                        wins = solo_rank.get("wins", 0)
                        losses = solo_rank.get("losses", 0)
                        
                        if tier in ["MASTER", "GRANDMASTER", "CHALLENGER"]:
                            player_data["rank_display"] = f"{tier.capitalize()} {lp} LP"
                        else:
                            player_data["rank_display"] = f"{tier.capitalize()} {rank} - {lp} LP"
                        
                        player_data["record"] = f"{wins}W {losses}L"
                        player_data["rank_score"] = self.calculate_rank_score(solo_rank)
                    else:
                        player_data["rank_display"] = "Unranked"
                        player_data["record"] = "0W 0L"
                        player_data["rank_score"] = -1
                    
                    players_info.append(player_data)
                
                except Exception as e:
                    logger.error(f"Erreur pour le joueur {player['riot_id']}: {e}")
                    continue
            
            if not players_info:
                embed = EmbedBuilder.create_error_embed(
                    "Erreur",
                    "Impossible de récupérer les données des joueurs.",
                    error_type="error"
                )
                await interaction.followup.send(embed=embed)
                return
            
            # Trier par rang (meilleurs en premier)
            players_info.sort(key=lambda x: x["rank_score"], reverse=True)
            
            # Créer l'embed
            embed = discord.Embed(
                title=f"📋 Informations - {interaction.guild.name}",
                description=f"**{len(players_info)} compte(s) enregistré(s)**\n"
                           f"Gain de LP calculé depuis aujourd'hui ({self.get_today_date()})",
                color=discord.Color.blue()
            )
            
            # Grouper par utilisateur Discord
            users_dict = {}
            for player in players_info:
                discord_id = player["discord_user_id"]
                if discord_id not in users_dict:
                    users_dict[discord_id] = []
                users_dict[discord_id].append(player)
            
            # Afficher les infos par utilisateur
            for discord_id, accounts in users_dict.items():
                try:
                    discord_user = await self.bot.fetch_user(int(discord_id))
                    user_name = discord_user.display_name
                except:
                    user_name = "Utilisateur Inconnu"
                
                accounts_text = ""
                for account in accounts:
                    # Indicateur de statut
                    status_emoji = "🟢" if account["is_online"] else "⚫"
                    
                    # Indicateur de gain LP
                    lp_gain = account["lp_gain"]
                    if lp_gain > 0:
                        lp_indicator = f"📈 +{lp_gain} LP"
                        lp_color = "🟢"
                    elif lp_gain < 0:
                        lp_indicator = f"📉 {lp_gain} LP"
                        lp_color = "🔴"
                    else:
                        lp_indicator = "➖ ±0 LP"
                        lp_color = "⚪"
                    
                    accounts_text += (
                        f"{status_emoji} **{account['riot_id']}**\n"
                        f"├ {account['rank_display']}\n"
                        f"├ {account['record']}\n"
                        f"├ Niveau {account['level']}\n"
                        f"└ {lp_color} {lp_indicator}\n\n"
                    )
                
                # Limiter la longueur des fields (Discord limite à 1024 caractères)
                if len(accounts_text) > 1024:
                    accounts_text = accounts_text[:1020] + "..."
                
                embed.add_field(
                    name=f"👤 {user_name}",
                    value=accounts_text,
                    inline=False
                )
            
            # Statistiques globales
            total_online = sum(1 for p in players_info if p["is_online"])
            total_lp_gain = sum(p["lp_gain"] for p in players_info)
            
            stats_text = (
                f"🟢 En ligne: **{total_online}/{len(players_info)}**\n"
                f"📊 Gain total du jour: **{total_lp_gain:+d} LP**"
            )
            
            embed.add_field(
                name="📈 Statistiques",
                value=stats_text,
                inline=False
            )
            
            embed.set_footer(text=f"Dernière mise à jour: {datetime.utcnow().strftime('%d/%m/%Y %H:%M')} UTC")
            
            await interaction.followup.send(embed=embed)
            logger.info(f"Infos envoyées pour {interaction.guild.name}")
        
        except RiotAPIError as e:
            logger.error(f"Erreur API Riot: {e}")
            embed = EmbedBuilder.create_error_embed(
                "Erreur API",
                "L'API Riot Games est temporairement indisponible.",
                error_type="error"
            )
            await interaction.followup.send(embed=embed)
        
        except Exception as e:
            logger.error(f"Erreur dans info: {e}", exc_info=True)
            embed = EmbedBuilder.create_error_embed(
                "Erreur Interne",
                "Une erreur s'est produite lors de la récupération des informations.",
                error_type="error"
            )
            await interaction.followup.send(embed=embed)
    
    @app_commands.command(
        name="garen-leaderboard",
        description="Affiche le leaderboard du serveur"
    )
    async def leaderboard(self, interaction: discord.Interaction):
        """Affiche le leaderboard local"""
        await interaction.response.defer()
        
        try:
            # Charger le leaderboard
            leaderboard_data = self.load_leaderboard(interaction.guild_id)
            
            if not leaderboard_data["players"]:
                embed = EmbedBuilder.create_error_embed(
                    "Leaderboard Vide",
                    "Aucun joueur enregistré sur ce serveur.\n"
                    "Utilise `/garen-add-localserver` pour ajouter des comptes !",
                    error_type="warning"
                )
                await interaction.followup.send(embed=embed)
                return
            
            logger.info(f"Récupération du leaderboard pour {interaction.guild.name}")
            
            # Récupérer les infos de chaque joueur
            players_data = []
            
            for player in leaderboard_data["players"]:
                try:
                    # Récupérer le summoner
                    summoner = await self.riot_api.get_summoner_by_puuid(player["puuid"])
                    if not summoner:
                        continue
                    
                    # Récupérer le rang
                    league_entries = await self.riot_api.get_league_entries(player["puuid"])
                    solo_rank = next(
                        (entry for entry in league_entries 
                         if entry.get("queueType") == "RANKED_SOLO_5x5"),
                        None
                    )
                    
                    # Préparer les données
                    player_info = {
                        "riot_id": player["riot_id"],
                        "discord_user_id": player["discord_user_id"],
                        "profile_icon_id": summoner.get("profileIconId", 1),
                        "rank_data": solo_rank,
                        "rank_score": self.calculate_rank_score(solo_rank)
                    }
                    
                    # Formater l'affichage du rang
                    if solo_rank:
                        tier = solo_rank.get("tier", "UNRANKED")
                        rank = solo_rank.get("rank", "")
                        lp = solo_rank.get("leaguePoints", 0)
                        wins = solo_rank.get("wins", 0)
                        losses = solo_rank.get("losses", 0)
                        
                        if tier in ["MASTER", "GRANDMASTER", "CHALLENGER"]:
                            player_info["rank_display"] = tier.capitalize()
                        else:
                            player_info["rank_display"] = f"{tier.capitalize()} {rank}"
                        
                        player_info["lp"] = lp
                        player_info["wins"] = wins
                        player_info["losses"] = losses
                        player_info["winrate"] = round(wins / (wins + losses) * 100, 1) if (wins + losses) > 0 else 0
                    else:
                        player_info["rank_display"] = "Unranked"
                        player_info["lp"] = 0
                        player_info["wins"] = 0
                        player_info["losses"] = 0
                        player_info["winrate"] = 0
                    
                    players_data.append(player_info)
                
                except Exception as e:
                    logger.error(f"Erreur pour le joueur {player['riot_id']}: {e}")
                    continue
            
            if not players_data:
                embed = EmbedBuilder.create_error_embed(
                    "Erreur",
                    "Impossible de récupérer les données des joueurs.",
                    error_type="error"
                )
                await interaction.followup.send(embed=embed)
                return
            
            # Trier par score de rang
            players_data.sort(key=lambda x: x["rank_score"], reverse=True)
            
            # Limiter au top 15
            top_players = players_data[:15]
            
            # Créer l'image du podium pour le top 3
            podium_buffer = None
            if len(top_players) >= 3:
                podium_buffer = await self.create_podium_image(top_players[:3])
            
            # Créer l'embed
            embed = discord.Embed(
                title=f"🏆 Leaderboard - {interaction.guild.name}",
                description=f"**Top {len(top_players)} joueurs classés**",
                color=discord.Color.gold()
            )
            
            if podium_buffer:
                embed.set_image(url="attachment://podium.png")
            
            # Ajouter les joueurs 4-15 (ou tous si moins de 3)
            start_idx = 3 if len(top_players) >= 3 else 0
            
            if start_idx < len(top_players):
                leaderboard_text = ""
                
                for idx, player in enumerate(top_players[start_idx:], start=start_idx + 1):
                    try:
                        discord_user = await self.bot.fetch_user(int(player["discord_user_id"]))
                        discord_name = discord_user.display_name
                    except:
                        discord_name = "Inconnu"
                    
                    leaderboard_text += (
                        f"**#{idx}** • {player['riot_id']}\n"
                        f"└ {player['rank_display']} • {player['lp']} LP • "
                        f"{player['wins']}W {player['losses']}L ({player['winrate']}%)\n\n"
                    )
                
                embed.add_field(
                    name="📊 Classement",
                    value=leaderboard_text if leaderboard_text else "Aucun autre joueur",
                    inline=False
                )
            
            embed.set_footer(text=f"Total: {len(players_data)} joueurs • {datetime.utcnow().strftime('%d/%m/%Y')}")
            
            # Envoyer
            if podium_buffer:
                file = discord.File(fp=podium_buffer, filename="podium.png")
                await interaction.followup.send(embed=embed, file=file)
            else:
                await interaction.followup.send(embed=embed)
            
            logger.info(f"Leaderboard envoyé pour {interaction.guild.name}")
        
        except RiotAPIError as e:
            logger.error(f"Erreur API Riot: {e}")
            embed = EmbedBuilder.create_error_embed(
                "Erreur API",
                "L'API Riot Games est temporairement indisponible.",
                error_type="error"
            )
            await interaction.followup.send(embed=embed)
        
        except Exception as e:
            logger.error(f"Erreur dans leaderboard: {e}", exc_info=True)
            embed = EmbedBuilder.create_error_embed(
                "Erreur Interne",
                "Une erreur s'est produite lors de la récupération du leaderboard.",
                error_type="error"
            )
            await interaction.followup.send(embed=embed)

async def setup(bot: commands.Bot):
    """Charge le Cog"""
    await bot.add_cog(LeaderboardCog(bot))