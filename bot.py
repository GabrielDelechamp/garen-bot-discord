# bot.py
import os
import discord
from discord.ext import commands
from dotenv import load_dotenv
import requests
from urllib.parse import quote
import json
from io import BytesIO
from PIL import Image
import time

load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")
GUILD_ID = int(os.getenv("GUILD_ID")) if os.getenv("GUILD_ID") else None
RIOT_API_KEY = os.getenv("RIOT_API_KEY")

intents = discord.Intents.default()  # slash commands n'ont pas besoin de message content
bot = commands.Bot(command_prefix="!", intents=intents)

REGION = "euw1" 
version = "15.24.1"

EXCEPTIONS = {
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
        "Kha'Zix": "Khazix"
    }

# Chargement des données champions DDragon une seule fois au lancement
CHAMPION_DATA_URL = f"https://ddragon.leagueoflegends.com/cdn/{version}/data/en_US/champion.json"

try:
    response = requests.get(CHAMPION_DATA_URL)
    champion_json = response.json()["data"]
except Exception as e:
    print("Erreur chargement champion.json :", e)
    champion_json = {}


def getChampionNameByKey(key: int):
    """
    Retourne le nom du champion à partir de sa key numérique.
    Exemple : 266 → "Aatrox"
    """
    key = str(key)  # La key dans champion.json est une string

    for champ_name, champ_data in champion_json.items():
        if champ_data.get("key") == key:
            return champ_name  # ex: "Aatrox"

    return None  # si non trouvé

def load_champion_map():
    """Charge le mapping ID → nom de champion."""
    with open("data/champions.json", "r", encoding="utf-8") as f:
        return json.load(f)

def fetch_champion_icon(champion_name: str, version: str):
    """
    Récupère l’image du champion depuis Data Dragon.
    Retourne None si échec.
    """
    safe_name = EXCEPTIONS.get(champion_name, champion_name)
    safe_name = safe_name.replace(" ", "").replace("'", "")

    url = f"http://ddragon.leagueoflegends.com/cdn/{version}/img/champion/{safe_name}.png"
    r = requests.get(url)

    if r.status_code != 200:
        print(f"[❌] Impossible d'obtenir l’icône pour {champion_name}")
        return None

    try:
        img = Image.open(BytesIO(r.content)).convert("RGBA").resize((64, 64))
        return img
    except Exception as e:
        print(f"[❌] Erreur PIL pour {champion_name}: {e}")
        return None

    headers = {"X-Riot-Token": RIOT_API_KEY}
    total_games = 0

    # 1️⃣ récupérer jusqu'à 100 matchs récents
    matchlist_url = (
        f"https://europe.api.riotgames.com/lol/match/v5/matches/by-puuid/"
        f"{puuid}/ids?start=0&count=100"
    )
    r = requests.get(matchlist_url, headers=headers)
    if r.status_code != 200:
        return None

    match_ids = r.json()

    # 2️⃣ boucle sur chaque match
    for match_id in match_ids:
        match_url = (
            f"https://europe.api.riotgames.com/lol/match/v5/matches/{match_id}"
        )
        r_match = requests.get(match_url, headers=headers)
        if r_match.status_code != 200:
            continue

        match = r_match.json()

        # 3️⃣ trouver notre joueur
        participants = match["info"]["participants"]
        for p in participants:
            if p["puuid"] == puuid:
                if p["championId"] == champion_id:
                    total_games += 1

    return total_games


    """Analyse les matchs et renvoie wins/losses/winrate pour une queue donnée (ex: 450 = ARAM)."""
    headers = {"X-Riot-Token": RIOT_API_KEY}
    region_prefix = "europe"

    # ❌ Riot ne supporte plus le paramètre "queue" → on le retire
    url = f"https://{region_prefix}.api.riotgames.com/lol/match/v5/matches/by-puuid/{puuid}/ids"
    params = {"start": 0, "count": max_matches}

    try:
        r = requests.get(url, headers=headers, params=params, timeout=5)
    except requests.exceptions.Timeout:
        print("⛔ Timeout matchlist")
        return (0, 0, 0)

    if r.status_code != 200:
        print(f"⚠️ API ERROR {r.status_code} for matchlist")
        return (0, 0, 0)

    match_ids = r.json()
    wins = 0
    losses = 0

    for match_id in match_ids:
        time.sleep(0.35)  # Évite les rate-limits

        match_url = f"https://{region_prefix}.api.riotgames.com/lol/match/v5/matches/{match_id}"

        try:
            r_match = requests.get(match_url, headers=headers, timeout=5)
        except:
            continue

        if r_match.status_code != 200:
            continue

        data = r_match.json()

        # ❌ Skip si ce n'est pas le bon mode (ex: ARAM = 450)
        if data["info"]["queueId"] != queue_id:
            continue

        # Trouver le joueur dans la partie
        participant = next((p for p in data["info"]["participants"] if p["puuid"] == puuid), None)

        if participant:
            if participant["win"]:
                wins += 1
            else:
                losses += 1

    total = wins + losses
    wr = round((wins / total) * 100, 1) if total > 0 else 0

    return (wins, losses, wr)



@bot.event
async def on_ready():
    print(f"Connecté comme {bot.user} (id: {bot.user.id})")
    print("Commandes trouvées :", [c.name for c in bot.tree.get_commands()])
    print("Serveurs connectés :")
    for g in bot.guilds:
        print("-", g.name, g.id)
    # Sync des commandes sur un serveur spécifique (rapide pour le dev)
    if GUILD_ID:
        try:
            guild = discord.Object(id=GUILD_ID)
            synced = await bot.tree.sync()
            print(f"{len(synced)} commandes synchronisées pour le serveur de test.")
        except Exception as e:
            print("Erreur sync:", e)
    else:
        # sync global (peut prendre du temps)
        try:
            synced = await bot.tree.sync()
            print(f"{len(synced)} commandes synchronisées globalement.")
        except Exception as e:
            print("Erreur sync globale:", e)




# Commande garen-summoner(riot#id):
@bot.tree.command(name="garen-summoner", description="Infos d'un invocateur LoL via Riot API")
@discord.app_commands.describe(nom="Nom de l'invocateur au format GameName#Tagline")
async def summoner(interaction: discord.Interaction, nom: str):
    await interaction.response.defer()
    try:
        # ✅ Split GameName#Tagline
        try:
            gameName, tagLine = nom.split("#")
        except ValueError:
            await interaction.followup.send("Format invalide. Utilise GameName#Tagline, ex: GolemDePisse#URINE")
            return

        headers = {"X-Riot-Token": RIOT_API_KEY}

        # Récupération du puuid via Riot ID
        riotid_url = f"https://europe.api.riotgames.com/riot/account/v1/accounts/by-riot-id/{quote(gameName)}/{quote(tagLine)}"
        r1 = requests.get(riotid_url, headers=headers, timeout=5)
        if r1.status_code == 404:
            await interaction.followup.send(f"Le joueur {nom} n'existe pas sur le serveur {REGION}")
            return
        elif r1.status_code != 200:
            await interaction.followup.send(f"Erreur Riot API ({r1.status_code})")
            return
        data1 = r1.json()
        puuid = data1["puuid"]
        print(puuid)

        # Récupération des infos du compte via puuid
        summoner_url = f"https://{REGION}.api.riotgames.com/lol/summoner/v4/summoners/by-puuid/{puuid}"
        r2 = requests.get(summoner_url, headers=headers, timeout=5)
        if r2.status_code != 200:
            await interaction.followup.send(f"Erreur récupération infos summoner ({r2.status_code})")
            return
        summoner_data = r2.json()
        summoner_level = summoner_data["summonerLevel"]
        profile_icon_id = summoner_data["profileIconId"]

        # Récupération du rang Solo/Duo via puuid
        rank_url = f"https://{REGION}.api.riotgames.com/lol/league/v4/entries/by-puuid/{puuid}"
        r3 = requests.get(rank_url, headers=headers, timeout=5)
        rank_data = r3.json() if r3.status_code == 200 else []
        solo_rank = next((x for x in rank_data if x["queueType"] == "RANKED_SOLO_5x5"), None)

        # Récupération de la plus haute mastery
        mastery_url = f"https://{REGION}.api.riotgames.com/lol/champion-mastery/v4/champion-masteries/by-puuid/{puuid}/top"
        r4 = requests.get(mastery_url, headers=headers, timeout=5)
        mastery_data = r4.json() if r4.status_code == 200 else []
        if len(mastery_data) == 0:
            mastery_ch_key = None
            mastery_ch_lvl = None
            mastery_ch_pts = None
        else:
            top = mastery_data[0]  # ⬅️ PREMIER CHAMPION
            mastery_ch_key = top["championId"]
            mastery_ch_lvl = top["championLevel"]
            mastery_ch_pts = top["championPoints"]
        champion_name = getChampionNameByKey(mastery_ch_key)
        mastery_field = f"{champion_name} : level {mastery_ch_lvl} ({mastery_ch_pts} pts)"

        # Calcul Winrate et couleurs
        if solo_rank:
            wins = solo_rank['wins']
            losses = solo_rank['losses']
            total_games = wins + losses
            winrate = round((wins / total_games) * 100) if total_games > 0 else 0

            wins_str = f"✅ {wins}"
            losses_str = f"❌ {losses}"
            rank_field = f"{solo_rank['tier']} {solo_rank['rank']} ({solo_rank['leaguePoints']} LP)\n" \
                         f"{wins_str} / {losses_str} | Winrate: {winrate}%"
        else:
            rank_field = "Non classé ou inaccessible avec cette clé dev"

        # Couleur embed selon tier
        tier_colors = {
            "IRON": 0x545454, "BRONZE": 0xCD7F32, "SILVER": 0xC0C0C0,
            "GOLD": 0xFFD700, "PLATINUM": 0x00FFFF, "DIAMOND": 0x1E90FF,
            "MASTER": 0x800080, "GRANDMASTER":0xC30010, "CHALLENGER": 0xFF8C00
        }
        color = tier_colors.get(solo_rank["tier"].upper(), 0x00FF00) if solo_rank else 0x00FF00

        # couleurs Discord
        GREEN = 0x57F287
        RED = 0xED4245
        BLUE = 0x3498DB

        def color_for_wr(winrate):
            if winrate >= 50:
                return GREEN
            if winrate >= 40:
                return BLUE
            return RED   

        # Création embed
        embed = discord.Embed(
            title=f"{gameName}#{tagLine} - Level {summoner_level}",
            color=color
        )
        embed.add_field(name="Solo/Duo", value=rank_field, inline=False)
        embed.add_field(name="Highest Mastery", value=mastery_field)

        # Profile icon
        icon_url = f"https://ddragon.leagueoflegends.com/cdn/13.24.1/img/profileicon/{profile_icon_id}.png"
        embed.set_thumbnail(url=icon_url)

        embed.set_footer(text="Source: Riot API | League of Legends")
        embed.timestamp = interaction.created_at

        await interaction.followup.send(embed=embed)

    except requests.exceptions.RequestException as e:
        await interaction.followup.send(f"Erreur requête API : {e}")

# Commande garen-rotation():
@bot.tree.command(name="garen-rotation", description="Montre la rotation gratuite de champions de la semaine")
async def garen_rotation(interaction: discord.Interaction):
    await interaction.response.defer()
    
    try:
        headers = {"X-Riot-Token": RIOT_API_KEY}
        url = f"https://{REGION}.api.riotgames.com/lol/platform/v3/champion-rotations"
        r = requests.get(url, headers=headers, timeout=5)

        if r.status_code != 200:
            await interaction.followup.send(f"Erreur Riot API : {r.status_code}")
            return

        free_ids = r.json().get("freeChampionIds", [])

        # Charger mapping et version Data Dragon
        champions_map = load_champion_map()
        version = "15.24.1"

        icons = []

        for ch_id in free_ids:
            name = champions_map.get(str(ch_id))
            if not name:
                continue

            img = fetch_champion_icon(name, version)
            if img:
                icons.append(img)

        if not icons:
            await interaction.followup.send("Impossible de récupérer les icônes.")
            return

        # Grille d’images
        cols = 5
        rows = (len(icons) + cols - 1) // cols
        combined = Image.new("RGBA", (cols * 64, rows * 64), (255, 255, 255, 0))

        for idx, img in enumerate(icons):
            x = (idx % cols) * 64
            y = (idx // cols) * 64
            combined.paste(img, (x, y), img)

        buffer = BytesIO()
        combined.save(buffer, format="PNG")
        buffer.seek(0)

        embed = discord.Embed(
            title="Rotation gratuite de la semaine",
            description="Voici les champions gratuits à jouer cette semaine !",
            color=discord.Color.blue()
        )
        embed.set_image(url="attachment://rotation.png")

        await interaction.followup.send(
            embed=embed,
            file=discord.File(fp=buffer, filename="rotation.png")
        )

    except Exception as e:
        await interaction.followup.send(f"Erreur : {e}")




if __name__ == "__main__":
    bot.run(TOKEN)
