"""Constantes utilisées dans le bot"""

# Exceptions pour les noms de champions Data Dragon
CHAMPION_NAME_EXCEPTIONS = {
    "Wukong": "MonkeyKing",
    "Kog'Maw": "KogMaw",
    "Tahm Kench": "TahmKench",
    "Cho'Gath": "Chogath",
    "Dr. Mundo": "DrMundo",
    "Jarvan IV": "JarvanIV",
    "Kai'Sa": "Kaisa",
    "Lee Sin": "LeeSin",
    "Master Yi": "MasterYi",
    "Miss Fortune": "MissFortune",
    "Rek'Sai": "RekSai",
    "Vel'Koz": "Velkoz",
    "Aurelion Sol": "AurelionSol",
    "Nunu & Willump": "Nunu",
    "Kha'Zix": "Khazix",
    "Renata Glasc": "Renata",
    "Bel'Veth": "Belveth"
}

# Couleurs des tiers pour les embeds
TIER_COLORS = {
    "IRON": 0x545454,
    "BRONZE": 0xCD7F32,
    "SILVER": 0xC0C0C0,
    "GOLD": 0xFFD700,
    "PLATINUM": 0x00FFFF,
    "EMERALD": 0x00FF88,
    "DIAMOND": 0x1E90FF,
    "MASTER": 0x800080,
    "GRANDMASTER": 0xC30010,
    "CHALLENGER": 0xFF8C00
}

# Couleurs Discord standard
DISCORD_COLORS = {
    "GREEN": 0x57F287,
    "RED": 0xED4245,
    "BLUE": 0x3498DB,
    "YELLOW": 0xFEE75C,
    "PURPLE": 0x5865F2,
    "DARK": 0x2C2F33
}

# Types de queues League of Legends
QUEUE_TYPES = {
    "RANKED_SOLO_5x5": "Solo/Duo",
    "RANKED_FLEX_SR": "Flex 5v5",
    "RANKED_FLEX_TT": "Flex 3v3"
}

# Emojis pour les rangs (optionnel)
RANK_EMOJIS = {
    "IRON": "⚫",
    "BRONZE": "🟤",
    "SILVER": "⚪",
    "GOLD": "🟡",
    "PLATINUM": "🔵",
    "EMERALD": "🟢",
    "DIAMOND": "💎",
    "MASTER": "🟣",
    "GRANDMASTER": "🔴",
    "CHALLENGER": "🏆"
}

def get_winrate_color(winrate: float) -> int:
    """
    Retourne une couleur basée sur le winrate
    
    Args:
        winrate: Pourcentage de victoires (0-100)
    
    Returns:
        Code couleur hexadécimal
    """
    if winrate >= 55:
        return DISCORD_COLORS["GREEN"]
    elif winrate >= 50:
        return DISCORD_COLORS["BLUE"]
    elif winrate >= 45:
        return DISCORD_COLORS["YELLOW"]
    else:
        return DISCORD_COLORS["RED"]

def normalize_champion_name(champion_name: str) -> str:
    """
    Normalise le nom d'un champion pour Data Dragon
    
    Args:
        champion_name: Nom du champion
    
    Returns:
        Nom normalisé pour les URLs Data Dragon
    """
    # Vérifier les exceptions
    normalized = CHAMPION_NAME_EXCEPTIONS.get(champion_name, champion_name)
    
    # Supprimer espaces et apostrophes
    normalized = normalized.replace(" ", "").replace("'", "")
    
    return normalized