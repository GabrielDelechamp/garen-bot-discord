import aiohttp
import asyncio
import logging
from typing import Optional, Dict, Any, List
from urllib.parse import quote
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

class RateLimiter:
    """Gère le rate limiting pour l'API Riot"""
    
    def __init__(self, calls_per_second: int = 20):
        self.calls_per_second = calls_per_second
        self.calls = []
        self._lock = asyncio.Lock()
    
    async def acquire(self):
        """Attend si nécessaire avant d'autoriser un appel"""
        async with self._lock:
            now = datetime.now()
            
            # Nettoyer les appels de plus d'1 seconde
            self.calls = [call for call in self.calls 
                         if now - call < timedelta(seconds=1)]
            
            # Attendre si limite atteinte
            if len(self.calls) >= self.calls_per_second:
                sleep_time = 1.0 - (now - self.calls[0]).total_seconds()
                if sleep_time > 0:
                    await asyncio.sleep(sleep_time)
                    self.calls = []
            
            self.calls.append(now)

class RiotAPIError(Exception):
    """Exception personnalisée pour les erreurs API Riot"""
    pass

class RiotAPIClient:
    """Client asynchrone pour l'API Riot Games"""
    
    def __init__(self, api_key: str, region: str, routing: str):
        self.api_key = api_key
        self.region = region
        self.routing = routing
        self.rate_limiter = RateLimiter(calls_per_second=20)
        self.session: Optional[aiohttp.ClientSession] = None
        self._champion_cache: Optional[Dict[str, Any]] = None
    
    async def __aenter__(self):
        """Context manager entry"""
        self.session = aiohttp.ClientSession(
            headers={"X-Riot-Token": self.api_key}
        )
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit"""
        if self.session:
            await self.session.close()
    
    async def _request(
        self,
        url: str,
        max_retries: int = 3,
        **kwargs
    ) -> Optional[Dict[str, Any]]:
        """
        Effectue une requête HTTP avec retry automatique
        
        Args:
            url: URL à requêter
            max_retries: Nombre maximum de tentatives
            **kwargs: Arguments additionnels pour aiohttp
        
        Returns:
            Données JSON ou None si erreur
        
        Raises:
            RiotAPIError: Si l'API retourne une erreur
        """
        if not self.session:
            raise RuntimeError("Session non initialisée. Utilisez 'async with'")
        
        await self.rate_limiter.acquire()
        
        for attempt in range(max_retries):
            try:
                async with self.session.get(url, timeout=10, **kwargs) as response:
                    # Gestion du rate limiting
                    if response.status == 429:
                        retry_after = int(response.headers.get("Retry-After", 1))
                        logger.warning(f"Rate limited. Retry après {retry_after}s")
                        await asyncio.sleep(retry_after)
                        continue
                    
                    # Ressource non trouvée
                    if response.status == 404:
                        return None
                    
                    # Autres erreurs HTTP
                    if response.status != 200:
                        error_text = await response.text()
                        logger.error(f"Erreur API {response.status}: {error_text}")
                        
                        if attempt == max_retries - 1:
                            raise RiotAPIError(f"Erreur API {response.status}")
                        
                        await asyncio.sleep(2 ** attempt)  # Exponential backoff
                        continue
                    
                    return await response.json()
            
            except asyncio.TimeoutError:
                logger.warning(f"Timeout tentative {attempt + 1}/{max_retries}")
                if attempt == max_retries - 1:
                    raise RiotAPIError("Timeout après plusieurs tentatives")
                await asyncio.sleep(1)
            
            except aiohttp.ClientError as e:
                logger.error(f"Erreur client: {e}")
                if attempt == max_retries - 1:
                    raise RiotAPIError(f"Erreur réseau: {e}")
                await asyncio.sleep(1)
        
        return None
    
    async def get_account_by_riot_id(
        self,
        game_name: str,
        tag_line: str
    ) -> Optional[Dict[str, Any]]:
        """Récupère un compte via Riot ID (GameName#TagLine)"""
        url = (
            f"https://{self.routing}.api.riotgames.com/riot/account/v1/"
            f"accounts/by-riot-id/{quote(game_name)}/{quote(tag_line)}"
        )
        return await self._request(url)
    
    async def get_summoner_by_puuid(self, puuid: str) -> Optional[Dict[str, Any]]:
        """Récupère les infos d'un summoner via PUUID"""
        url = (
            f"https://{self.region}.api.riotgames.com/lol/summoner/v4/"
            f"summoners/by-puuid/{puuid}"
        )
        return await self._request(url)
    
    async def get_league_entries(self, puuid: str) -> List[Dict[str, Any]]:
        """Récupère les rangs d'un joueur"""
        url = (
            f"https://{self.region}.api.riotgames.com/lol/league/v4/"
            f"entries/by-puuid/{puuid}"
        )
        result = await self._request(url)
        return result if result else []
    
    async def get_champion_masteries(
        self,
        puuid: str,
        count: int = 3
    ) -> List[Dict[str, Any]]:
        """Récupère les masteries d'un joueur"""
        url = (
            f"https://{self.region}.api.riotgames.com/lol/"
            f"champion-mastery/v4/champion-masteries/by-puuid/{puuid}/top"
        )
        result = await self._request(url, params={"count": count})
        return result if result else []
    
    async def get_champion_rotation(self) -> Optional[Dict[str, Any]]:
        """Récupère la rotation gratuite de champions"""
        url = (
            f"https://{self.region}.api.riotgames.com/lol/platform/v3/"
            f"champion-rotations"
        )
        return await self._request(url)
    
    async def get_champion_data(self) -> Dict[str, Any]:
        """Récupère les données champions de Data Dragon (avec cache)"""
        if self._champion_cache:
            return self._champion_cache
        
        from config import Config
        url = Config.DDRAGON_CHAMPION_DATA_URL
        
        if not self.session:
            raise RuntimeError("Session non initialisée")
        
        async with self.session.get(url) as response:
            if response.status == 200:
                data = await response.json()
                self._champion_cache = data.get("data", {})
                return self._champion_cache
        
        return {}
    
    def get_champion_name_by_id(self, champion_id: int) -> Optional[str]:
        """Retourne le nom d'un champion à partir de son ID"""
        if not self._champion_cache:
            return None
        
        champion_id_str = str(champion_id)
        for name, data in self._champion_cache.items():
            if data.get("key") == champion_id_str:
                return name
        
        return None