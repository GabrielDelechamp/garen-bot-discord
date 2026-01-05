import discord
from discord.ext import commands
import logging
import asyncio
from pathlib import Path
from config import Config

# Configuration du logging
def setup_logging():
    """Configure le système de logging"""
    # Créer le dossier logs s'il n'existe pas
    Path("logs").mkdir(exist_ok=True)
    
    # Format des logs
    log_format = logging.Formatter(
        '[{asctime}] [{levelname:<8}] {name}: {message}',
        datefmt='%Y-%m-%d %H:%M:%S',
        style='{'
    )
    
    # Handler console
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(log_format)
    console_handler.setLevel(logging.INFO)
    
    # Handler fichier
    file_handler = logging.FileHandler(
        Config.LOG_FILE,
        encoding='utf-8',
        mode='a'
    )
    file_handler.setFormatter(log_format)
    file_handler.setLevel(logging.DEBUG)
    
    # Configuration du logger racine
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.DEBUG)
    root_logger.addHandler(console_handler)
    root_logger.addHandler(file_handler)
    
    # Réduire le niveau de logging pour discord.py
    logging.getLogger('discord').setLevel(logging.WARNING)
    logging.getLogger('discord.http').setLevel(logging.WARNING)

# Setup logging
setup_logging()
logger = logging.getLogger(__name__)

class GarenBot(commands.Bot):
    """Bot Discord personnalisé pour League of Legends"""
    
    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = False  # Pas nécessaire pour les slash commands
        
        super().__init__(
            command_prefix="!",  # Prefix pour les commandes texte (optionnel)
            intents=intents,
            help_command=None  # Désactiver la commande help par défaut
        )
        
        self.initial_extensions = [
            'cogs.summoner',
            'cogs.champions',
            'cogs.patchnote',
            'cogs.leaderboard',
            'cogs.lobby',
            ]
    
    async def setup_hook(self):
        """Hook appelé lors de l'initialisation du bot"""
        logger.info("Initialisation du bot...")
        
        # Charger les cogs
        for extension in self.initial_extensions:
            try:
                await self.load_extension(extension)
                logger.info(f"✅ Extension chargée: {extension}")
            except Exception as e:
                logger.error(f"❌ Impossible de charger {extension}: {e}", exc_info=True)
        
        # Sync des commandes
        if Config.GUILD_ID:
            # Sync rapide pour un serveur spécifique (dev)
            guild = discord.Object(id=Config.GUILD_ID)
            self.tree.copy_global_to(guild=guild)
            await self.tree.sync(guild=guild)
            logger.info(f"Commandes synchronisées pour le serveur {Config.GUILD_ID}")
        else:
            # Sync global (peut prendre jusqu'à 1h)
            await self.tree.sync()
            logger.info("Commandes synchronisées globalement")
    
    async def on_ready(self):
        """Appelé quand le bot est prêt"""
        logger.info("=" * 50)
        logger.info(f"Bot connecté: {self.user.name} (ID: {self.user.id})")
        logger.info(f"Discord.py version: {discord.__version__}")
        logger.info(f"Serveurs connectés: {len(self.guilds)}")
        
        for guild in self.guilds:
            logger.info(f"  - {guild.name} (ID: {guild.id})")
        
        logger.info(f"Commandes disponibles: {len(self.tree.get_commands())}")
        for cmd in self.tree.get_commands():
            logger.info(f"  - /{cmd.name}: {cmd.description}")
        
        logger.info("=" * 50)
        
        # Statut du bot
        activity = discord.Activity(
            type=discord.ActivityType.watching,
            name="League of Legends | /garen-summoner"
        )
        await self.change_presence(activity=activity, status=discord.Status.online)
    
    async def on_guild_join(self, guild: discord.Guild):
        """Appelé quand le bot rejoint un serveur"""
        logger.info(f"Bot ajouté au serveur: {guild.name} (ID: {guild.id})")
    
    async def on_guild_remove(self, guild: discord.Guild):
        """Appelé quand le bot quitte un serveur"""
        logger.info(f"Bot retiré du serveur: {guild.name} (ID: {guild.id})")
    
    async def on_command_error(self, ctx, error):
        """Gestion globale des erreurs de commandes"""
        if isinstance(error, commands.CommandNotFound):
            return
        
        logger.error(f"Erreur de commande: {error}", exc_info=error)
    
    async def on_app_command_error(
        self,
        interaction: discord.Interaction,
        error: discord.app_commands.AppCommandError
    ):
        """Gestion des erreurs pour les slash commands"""
        logger.error(
            f"Erreur slash command /{interaction.command.name}: {error}",
            exc_info=error
        )
        
        if not interaction.response.is_done():
            await interaction.response.send_message(
                "❌ Une erreur s'est produite lors de l'exécution de la commande.",
                ephemeral=True
            )
        else:
            await interaction.followup.send(
                "❌ Une erreur s'est produite.",
                ephemeral=True
            )

async def main():
    """Fonction principale"""
    try:
        # Valider la configuration
        Config.validate()
        logger.info("Configuration validée")
        
        # Créer et lancer le bot
        bot = GarenBot()
        
        async with bot:
            logger.info("Démarrage du bot...")
            await bot.start(Config.DISCORD_TOKEN)
    
    except ValueError as e:
        logger.critical(f"Configuration invalide: {e}")
    except Exception as e:
        logger.critical(f"Erreur critique: {e}", exc_info=True)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Bot arrêté par l'utilisateur (Ctrl+C)")
    except Exception as e:
        logger.critical(f"Erreur fatale: {e}", exc_info=True)