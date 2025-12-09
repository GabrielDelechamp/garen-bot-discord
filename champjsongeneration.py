import requests
import json

version = "15.24.1"  # adapte à la dernière version
url = f"https://ddragon.leagueoflegends.com/cdn/{version}/data/en_US/champion.json"
r = requests.get(url)
data = r.json()

# mapping key numérique -> nom
champions_map = {v["key"]: v["name"] for k, v in data["data"].items()}

with open("data/champions.json", "w", encoding="utf-8") as f:
    json.dump(champions_map, f, ensure_ascii=False, indent=2)

print("champions.json généré !")
