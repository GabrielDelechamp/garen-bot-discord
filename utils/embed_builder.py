import discord
from typing import List, Optional, Dict, Any
from config import Config
from utils.constants import TIER_COLORS, DISCORD_COLORS, QUEUE_TYPES, RANK_EMOJIS

class EmbedBuilder:
    """Constructeur d'embeds Discord pour le bot LoL"""
    
    @staticmethod
    def create_summoner_embed(
        game_name: str,
        tag_line: str,
        level: int,
        rank_data: Optional[Dict[str, Any]],
        mastery_data: Optional[Dict[str, Any]],
        profile_icon_id: int
    ) -> discord.Embed:
        """
        Crée un embed pour afficher les infos d'un summoner
        
        Args:
            game_name: Nom du joueur
            tag_line: Tag du joueur
            level: Niveau du compte
            rank_data: Données de classement
            mastery_data: Données de maîtrise
            profile_icon_id: ID de l'icône de profil
        
        Returns:
            Embed Discord formaté
        """
        # Déterminer la couleur selon le rang
        color = DISCORD_COLORS["BLUE"]
        if rank_data:
            tier = rank_data.get("tier", "").upper()
            color = TIER_COLORS.get(tier, DISCORD_COLORS["BLUE"])
        
        # Créer l'embed de base
        embed = discord.Embed(
            title=f"{game_name}#{tag_line}",
            description=f"📊 **Niveau {level}**",
            color=color,
            timestamp=discord.utils.utcnow()
        )
        
        # Ajouter le classement
        rank_text = EmbedBuilder._format_rank_data(rank_data)
        embed.add_field(
            name="🏆 Solo/Duo",
            value=rank_text,
            inline=False
        )
        
        # Ajouter la maîtrise
        if mastery_data:
            mastery_text = EmbedBuilder._format_mastery_data(mastery_data)
            embed.add_field(
                name="⭐ Meilleure Maîtrise",
                value=mastery_text,
                inline=False
            )
        
        # Ajouter l'icône de profil
        icon_url = (
            f"{Config.DDRAGON_BASE_URL}/{Config.DDRAGON_VERSION}/"
            f"img/profileicon/{profile_icon_id}.png"
        )
        embed.set_thumbnail(url=icon_url)
        
        embed.set_footer(
            text="Données fournies par Riot Games",
            icon_url="https://static.wikia.nocookie.net/leagueoflegends/images/1/12/League_of_Legends_icon.png"
        )
        
        return embed
    
    @staticmethod
    def create_lobby_embed(participants: List[Dict], game_mode: str) -> discord.Embed:
        """Crée un embed pour afficher un lobby"""
        
        # Séparer les équipes
        team_red = [p for p in participants if p["teamId"] == 100]
        team_blue = [p for p in participants if p["teamId"] == 200]
        
        # Mapper le game mode
        mode_names = {
            "CLASSIC": "🏆 Ranked Solo/Duo",
            "ARAM": "🎲 ARAM",
            "URF": "⚡ URF",
            # ... autres modes
        }
        
        embed = discord.Embed(
            title=f"🎮 Lobby en cours",
            description=f"Mode: **{mode_names.get(game_mode, game_mode)}**",
            color=discord.Color.blue()
        )
        
        # Fonction helper pour formater un joueur
        def format_player(player_data):
            # player_data contient : pseudo, champion, rank, winrate, tags
            champion = player_data["champion"]
            tags_str = " • ".join(player_data["tags"]) if player_data["tags"] else "Aucun tag"
            
            return (
                f"**{player_data['riot_id']}**\n"
                f"├ {champion} ({player_data['games']} games • {player_data['wr']}% WR)\n"
                f"├ {player_data['rank']}\n"
                f"└ {tags_str}\n"
            )
        
        # Ajouter équipe rouge
        red_text = "\n".join([format_player(p) for p in team_red])
        embed.add_field(
            name="🔴 ÉQUIPE ROUGE",
            value=red_text or "Aucun joueur",
            inline=False
        )
        
        # Ajouter équipe bleue
        blue_text = "\n".join([format_player(p) for p in team_blue])
        embed.add_field(
            name="🔵 ÉQUIPE BLEUE", 
            value=blue_text or "Aucun joueur",
            inline=False
        )
        
        return embed
    @staticmethod
    def _format_rank_data(rank_data: Optional[Dict[str, Any]]) -> str:
        """Formate les données de classement"""
        if not rank_data:
            return "```\nNon classé\n```"
        
        tier = rank_data.get("tier", "UNRANKED")
        rank = rank_data.get("rank", "")
        lp = rank_data.get("leaguePoints", 0)
        wins = rank_data.get("wins", 0)
        losses = rank_data.get("losses", 0)
        
        total = wins + losses
        winrate = round((wins / total) * 100, 1) if total > 0 else 0
        
        # Emoji du rang
        emoji = RANK_EMOJIS.get(tier.upper(), "")
        
        # Construction du texte
        rank_line = f"{emoji} **{tier.title()} {rank}** - {lp} LP"
        
        # Couleurs des stats selon le winrate
        if winrate >= 50:
            wr_indicator = "🟢"
        elif winrate >= 45:
            wr_indicator = "🟡"
        else:
            wr_indicator = "🔴"
        
        stats_line = f"```\n✅ {wins}W  ❌ {losses}L\n{wr_indicator} {winrate}% WR\n```"
        
        return f"{rank_line}\n{stats_line}"
    
    @staticmethod
    def _format_mastery_data(mastery_data: Dict[str, Any]) -> str:
        """Formate les données de maîtrise"""
        champion_name = mastery_data.get("champion_name", "Unknown")
        level = mastery_data.get("level", 0)
        points = mastery_data.get("points", 0)
        
        # Emojis pour les niveaux de maîtrise
        mastery_emojis = {
            7: "💎",
            6: "💜",
            5: "🔵",
        }
        emoji = mastery_emojis.get(level, "⚪")
        
        return (
            f"{emoji} **{champion_name}**\n"
            f"```\nNiveau {level}\n"
            f"{points:,} points\n```"
        )
    
    @staticmethod
    def create_rotation_embed(champion_count: int) -> discord.Embed:
        """
        Crée un embed pour la rotation gratuite
        
        Args:
            champion_count: Nombre de champions gratuits
        
        Returns:
            Embed Discord formaté
        """
        embed = discord.Embed(
            title="🎮 Rotation Gratuite de la Semaine",
            description=f"**{champion_count} champions** sont disponibles gratuitement cette semaine !",
            color=DISCORD_COLORS["PURPLE"],
            timestamp=discord.utils.utcnow()
        )
        
        embed.set_footer(text="La rotation change chaque mardi")
        
        return embed

    @staticmethod
    def create_patchnote_embed(changes_by_champ: dict, patch_old: str, patch_new: str) -> list[discord.Embed]:
        """
        Crée des embeds Discord pour les changements de patchs

        Args:
            changes_by_champ: dict champ -> (old_data, new_data)
            patch_old: str, version précédente
            patch_new: str, version actuelle

        Returns:
            List[discord.Embed]: Embeds prêts à l'envoi
        """
        embeds = []
        current_embed = discord.Embed(
            title=f"Patch technique — {patch_old} → {patch_new}",
            description="Données extraites et comparées depuis CommunityDragon (technique).",
            color=0x2E86C1
        )

        field_count = 0
        for champ_name, (olddata, newdata) in changes_by_champ.items():
            value_lines = []

            # Stats de base
            stats_map = {
                "hp": "HP",
                "mana": "Mana",
                "attackDamage": "BaseAD",
                "armor": "Armor",
                "magicResist": "MR",
                "attackSpeed": "AttackSpeed"
            }
            for key, label in stats_map.items():
                old_val = olddata.get("stats", {}).get(key)
                new_val = newdata.get("stats", {}).get(key)
                if old_val is not None and new_val is not None and old_val != new_val:
                    value_lines.append(f"{label}: {old_val} → {new_val}")

            # Spells
            spell_names = ["Q", "W", "E", "R"]
            for i, spell_name in enumerate(spell_names):
                old_spell = olddata.get("spells", [{}])[i] if i < len(olddata.get("spells", [])) else {}
                new_spell = newdata.get("spells", [{}])[i] if i < len(newdata.get("spells", [])) else {}
                old_effects = old_spell.get("effectAmounts", {}).get("Effect1Amount")
                new_effects = new_spell.get("effectAmounts", {}).get("Effect1Amount")
                if old_effects and new_effects and old_effects != new_effects:
                    old_str = "/".join(str(x) for x in old_effects)
                    new_str = "/".join(str(x) for x in new_effects)
                    value_lines.append(f"{spell_name} Damage: {old_str} → {new_str}")

            if not value_lines:
                value_lines.append("Aucun changement lisible détecté")

            value = "\n".join(value_lines)
            if len(value) > 1000:
                value = value[:1000] + "\n... (tronqué)"

            try:
                current_embed.add_field(name=champ_name, value=value, inline=False)
                field_count += 1
            except Exception:
                embeds.append(current_embed)
                current_embed = discord.Embed(title="Patch technique — suite", color=0x2E86C1)
                current_embed.add_field(name=champ_name, value=value, inline=False)
                field_count = 1

            if field_count >= 18:
                embeds.append(current_embed)
                current_embed = discord.Embed(title="Patch technique — suite", color=0x2E86C1)
                field_count = 0

        embeds.append(current_embed)
        return embeds

    @staticmethod
    def create_error_embed(
        title: str,
        description: str,
        error_type: str = "error"
    ) -> discord.Embed:
        """
        Crée un embed pour afficher une erreur
        
        Args:
            title: Titre de l'erreur
            description: Description de l'erreur
            error_type: Type d'erreur (error, warning, info)
        
        Returns:
            Embed Discord formaté
        """
        colors = {
            "error": DISCORD_COLORS["RED"],
            "warning": DISCORD_COLORS["YELLOW"],
            "info": DISCORD_COLORS["BLUE"]
        }
        
        emojis = {
            "error": "❌",
            "warning": "⚠️",
            "info": "ℹ️"
        }
        
        embed = discord.Embed(
            title=f"{emojis.get(error_type, '')} {title}",
            description=description,
            color=colors.get(error_type, DISCORD_COLORS["RED"])
        )
        
        return embed
    
    @staticmethod
    def create_latest_patch_embed(title: str, url: str, image_url: str) -> discord.Embed:
        """
        Crée un embed pour le dernier patch LoL avec image et lien.

        Args:
            title: Titre du patch
            url: URL vers le patch complet
            image_url: URL de l'image principale du patch

        Returns:
            discord.Embed
        """
        embed = discord.Embed(
            title=title,
            description=f"[Voir le patch complet]({url})",
            color=0x1a73e8
        )
        embed.set_image(url=image_url)
        embed.set_footer(
            text="Données fournies par Riot Games",
            icon_url="https://static.wikia.nocookie.net/leagueoflegends/images/1/12/League_of_Legends_icon.png"
        )
        return embed
