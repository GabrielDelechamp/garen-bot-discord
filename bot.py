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


load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")
GUILD_ID = int(os.getenv("GUILD_ID")) if os.getenv("GUILD_ID") else None
RIOT_API_KEY = os.getenv("RIOT_API_KEY")

intents = discord.Intents.default()  # slash commands n'ont pas besoin de message content
bot = commands.Bot(command_prefix="!", intents=intents)

REGION = "euw1" 
version = "15.24.1"

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

        # 1️⃣ Récupération du puuid via Riot ID
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

        # 2️⃣ Récupération des infos du compte via puuid
        summoner_url = f"https://{REGION}.api.riotgames.com/lol/summoner/v4/summoners/by-puuid/{puuid}"
        r2 = requests.get(summoner_url, headers=headers, timeout=5)
        if r2.status_code != 200:
            await interaction.followup.send(f"Erreur récupération infos summoner ({r2.status_code})")
            return
        summoner_data = r2.json()
        summoner_level = summoner_data["summonerLevel"]
        profile_icon_id = summoner_data["profileIconId"]

        # 3️⃣ Récupération du rang Solo/Duo via puuid
        rank_url = f"https://{REGION}.api.riotgames.com/lol/league/v4/entries/by-puuid/{puuid}"
        r3 = requests.get(rank_url, headers=headers, timeout=5)
        rank_data = r3.json() if r3.status_code == 200 else []
        solo_rank = next((x for x in rank_data if x["queueType"] == "RANKED_SOLO_5x5"), None)

        # 4️⃣ Calcul Winrate et couleurs
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

        # 5️⃣ Couleur embed selon tier
        tier_colors = {
            "IRON": 0x545454, "BRONZE": 0xCD7F32, "SILVER": 0xC0C0C0,
            "GOLD": 0xFFD700, "PLATINUM": 0x00FFFF, "DIAMOND": 0x1E90FF,
            "MASTER": 0x800080, "GRANDMASTER":0xC30010, "CHALLENGER": 0xFF8C00
        }
        color = tier_colors.get(solo_rank["tier"].upper(), 0x00FF00) if solo_rank else 0x00FF00

        # 6️⃣ Création embed
        embed = discord.Embed(
            title=f"{gameName}#{tagLine} - Niveau {summoner_level}",
            color=color
        )
        embed.add_field(name="Solo/Duo", value=rank_field, inline=False)

        # 7️⃣ Profile icon
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

    try:
        # 1️⃣ Récupération rotation gratuite Riot API
        headers = {"X-Riot-Token": RIOT_API_KEY}
        url = f"https://{REGION}.api.riotgames.com/lol/platform/v3/champion-rotations"
        r = requests.get(url, headers=headers, timeout=5)
        if r.status_code != 200:
            await interaction.followup.send(f"Erreur Riot API : {r.status_code}")
            return
        free_ids = r.json().get("freeChampionIds", [])

        # 2️⃣ Chargement champions.json
        champions_map_path = "data/champions.json"
        if not os.path.exists(champions_map_path):
            os.makedirs("data", exist_ok=True)
            url_dd = f"https://ddragon.leagueoflegends.com/cdn/{version}/data/en_US/champion.json"
            r2 = requests.get(url_dd)
            dd_data = r2.json()
            # Utiliser "id" pour avoir le nom exact utilisé dans l'URL des icônes
            champions_map = {v["key"]: v["id"] for k, v in dd_data["data"].items()}
            with open(champions_map_path, "w", encoding="utf-8") as f:
                json.dump(champions_map, f, ensure_ascii=False, indent=2)
        else:
            with open(champions_map_path, "r", encoding="utf-8") as f:
                champions_map = json.load(f)

        # 3️⃣ Récupérer les icônes
        icons = []
        for ch_id in free_ids:
            name = champions_map.get(str(ch_id))
            if not name:
                continue  # skip si pas de mapping
            name = EXCEPTIONS.get(name, name)
            name = name.replace(" ", "").replace("'", "")  # sécurité pour les autres cas
            icon_url = f"http://ddragon.leagueoflegends.com/cdn/{version}/img/champion/{name}.png"
            r_icon = requests.get(icon_url)
            if r_icon.status_code != 200:
                print(f"Impossible de récupérer l'icône pour {name}")
                continue
            try:
                img = Image.open(BytesIO(r_icon.content)).convert("RGBA").resize((64, 64))
                icons.append(img)
            except Exception as e:
                print(f"Erreur PIL pour {name} : {e}")
                continue

        if not icons:
            await interaction.followup.send("Impossible de récupérer les icônes des champions gratuits.")
            return

        # 4️⃣ Créer l'image combinée (grille)
        cols = 5
        rows = (len(icons) + cols - 1) // cols
        combined = Image.new("RGBA", (cols*64, rows*64), (255, 255, 255, 0))
        for idx, img in enumerate(icons):
            x = (idx % cols) * 64
            y = (idx // cols) * 64
            combined.paste(img, (x, y), img)

        # 5️⃣ Envoyer l'image dans Discord
        buffer = BytesIO()
        combined.save(buffer, format="PNG")
        buffer.seek(0)

        embed = discord.Embed(
            title="Rotation gratuite de la semaine",
            description="Voici les champions gratuits à jouer cette semaine !",
            color=discord.Color.blue()
        )
        embed.set_image(url="attachment://rotation.png")
        embed.set_footer(text="Source: Riot Games | League of Legends")

        await interaction.followup.send(embed=embed, file=discord.File(fp=buffer, filename="rotation.png"))

    except requests.exceptions.RequestException as e:
        await interaction.followup.send(f"Erreur requête API : {e}")



if __name__ == "__main__":
    bot.run(TOKEN)
