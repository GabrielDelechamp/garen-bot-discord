import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    """Configuration centralisée du bot"""
    
    # Discord
    DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
    GUILD_ID = int(os.getenv("GUILD_ID")) if os.getenv("GUILD_ID") else None
    
    # Riot API
    RIOT_API_KEY = os.getenv("RIOT_API_KEY")
    REGION = os.getenv("REGION", "euw1")
    
    # Data Dragon
    DDRAGON_VERSION = "15.24.1"
    DDRAGON_BASE_URL = "https://ddragon.leagueoflegends.com/cdn"
    DDRAGON_CHAMPION_DATA_URL = f"{DDRAGON_BASE_URL}/{DDRAGON_VERSION}/data/en_US/champion.json"
    
    # Rate Limiting
    RATE_LIMIT_CALLS = 20  # Appels par seconde autorisés
    RATE_LIMIT_PERIOD = 1  # Période en secondes
    REQUEST_TIMEOUT = 10   # Timeout des requêtes en secondes
    MAX_RETRIES = 3        # Nombre de tentatives en cas d'échec
    
    # Logging
    LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
    LOG_FILE = "logs/bot.log"
    
    # Routing régional
    REGION_ROUTING = {
        "euw1": "europe",
        "eun1": "europe",
        "kr": "asia",
        "jp1": "asia",
        "na1": "americas",
        "la1": "americas",
        "la2": "americas",
        "br1": "americas",
        "oc1": "sea",
        "tr1": "europe",
        "ru": "europe"
    }
    
    @classmethod
    def get_routing(cls) -> str:
        """Retourne le routing pour la région configurée"""
        return cls.REGION_ROUTING.get(cls.REGION.lower(), "europe")
    
    @classmethod
    def validate(cls) -> bool:
        """Valide que toutes les variables essentielles sont présentes"""
        required = [cls.DISCORD_TOKEN, cls.RIOT_API_KEY]
        if not all(required):
            missing = []
            if not cls.DISCORD_TOKEN:
                missing.append("DISCORD_TOKEN")
            if not cls.RIOT_API_KEY:
                missing.append("RIOT_API_KEY")
            
            raise ValueError(f"Variables d'environnement manquantes: {', '.join(missing)}")
        return True