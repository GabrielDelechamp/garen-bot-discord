import discord
from discord.ext import commands
from discord import app_commands
import aiohttp
import asyncio
import logging
import json
from pathlib import Path
from typing import Any, Optional

from utils.embed_builder import EmbedBuilder

logger = logging.getLogger(__name__)

DDDRAGON_VERSIONS_URL = "https://ddragon.leagueoflegends.com/api/versions.json"
CDRAGON_RAW = "https://raw.communitydragon.org"
CONCURRENT_DOWNLOADS = 10
MAX_FIELD_VALUE = 1000
MAX_FIELDS_PER_EMBED = 18
MAX_EMBED_CHARS = 6000


def dict_diffs(old: Any, new: Any, path: str = "") -> list[str]:
    """Diff simple et récursif entre deux structures JSON, pour champs pertinents."""
    diffs: list[str] = []
    if type(old) != type(new):
        diffs.append(f"{path}: type {type(old).__name__} → {type(new).__name__}")
        return diffs

    if isinstance(old, dict):
        keys = set(old.keys()) & set(new.keys())  # uniquement clés communes
        for k in sorted(keys):
            pk = f"{path}.{k}" if path else k
            if k in ("id", "nameKey", "assetPath", "modificationTimestamp"):
                continue
            diffs += dict_diffs(old[k], new[k], pk)
        return diffs

    if isinstance(old, list):
        minlen = min(len(old), len(new))
        for i in range(minlen):
            diffs += dict_diffs(old[i], new[i], f"{path}[{i}]")
        if len(new) > len(old):
            diffs.append(f"{path}: +{len(new)-len(old)} éléments ajoutés")
        if len(old) > len(new):
            diffs.append(f"{path}: -{len(old)-len(new)} éléments supprimés")
        return diffs

    if old != new:
        diffs.append(f"{path}: `{old}` → `{new}`")
    return diffs


def classify_diffs(diffs: list[str]) -> dict[str, list[str]]:
    """Sépare les diffs en Buffs / Nerfs / Autres selon comparaison numérique si possible."""
    buffs, nerfs, autres = [], [], []
    for line in diffs:
        if "→" in line:
            try:
                parts = line.split("→")
                left, right = parts[0], parts[1]
                # extraire premier nombre pour comparaison
                old_val = float("".join(c for c in left if c.isdigit() or c in "./")).split("/")[0]
                old_val = float(old_val)
                new_val = float("".join(c for c in right if c.isdigit() or c in "./")).split("/")[0]
                new_val = float(new_val)
                if new_val > old_val:
                    buffs.append(line)
                elif new_val < old_val:
                    nerfs.append(line)
                else:
                    autres.append(line)
            except Exception:
                autres.append(line)
        else:
            autres.append(line)
    result = {}
    if buffs:
        result["Buffs"] = buffs
    if nerfs:
        result["Nerfs"] = nerfs
    if autres:
        result["Autres"] = autres
    return result


def build_champion_field(diffs: list[str]) -> str:
    """Construit le texte d'un champ embed pour un champion avec Buffs/Nerfs/Autres."""
    sections = classify_diffs(diffs)
    lines = []
    for section_name, items in sections.items():
        lines.append(f"**{section_name}**")
        lines.extend([f"  {item}" for item in items])
    return "\n".join(lines)


def paginate_fields(changes_by_champ: dict[str, list[str]]) -> list[discord.Embed]:
    """Paginer les changements en plusieurs embeds si nécessaire"""
    embeds: list[discord.Embed] = []
    current_embed = discord.Embed(
        title="Patch technique — changements détectés",
        description="Données extraites et comparées depuis CommunityDragon (technique).",
        color=0x2E86C1
    )
    current_chars = len(current_embed.title) + len(current_embed.description or "")
    field_count = 0

    for champ_name, difflines in changes_by_champ.items():
        value = build_champion_field(difflines)
        if len(value) > MAX_FIELD_VALUE:
            value = value[:MAX_FIELD_VALUE] + "\n... (tronqué)"

        if field_count >= MAX_FIELDS_PER_EMBED or current_chars + len(value) > MAX_EMBED_CHARS:
            embeds.append(current_embed)
            current_embed = discord.Embed(
                title="Patch technique — suite",
                color=0x2E86C1
            )
            current_chars = 0
            field_count = 0

        current_embed.add_field(name=str(champ_name), value=value, inline=False)
        current_chars += len(value)
        field_count += 1

    embeds.append(current_embed)
    return embeds


class PatchnoteCog(commands.Cog):
    """Patch notes techniques comparant la version actuelle et la précédente via CommunityDragon"""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.session: Optional[aiohttp.ClientSession] = None
        self.sem = asyncio.Semaphore(CONCURRENT_DOWNLOADS)

    async def cog_load(self):
        self.session = aiohttp.ClientSession()
        logger.info("PatchnoteCog: session HTTP initialisée")

    async def cog_unload(self):
        if self.session:
            await self.session.close()
            logger.info("PatchnoteCog: session HTTP fermée")

    async def fetch_json(self, url: str) -> Optional[Any]:
        if not self.session:
            return None
        try:
            async with self.sem:
                async with self.session.get(url, timeout=30) as resp:
                    if resp.status != 200:
                        logger.warning(f"fetch_json: {resp.status} pour {url}")
                        return None
                    return await resp.json()
        except Exception as e:
            logger.error(f"fetch_json erreur pour {url}: {e}")
            return None

    async def get_versions(self) -> Optional[tuple[str, str]]:
        try:
            async with aiohttp.ClientSession() as s:
                async with s.get(DDDRAGON_VERSIONS_URL, timeout=15) as r:
                    if r.status != 200:
                        logger.warning(f"Impossible de récupérer versions.json ({r.status})")
                        return None
                    versions = await r.json()
        except Exception as e:
            logger.error(f"Erreur get_versions: {e}")
            return None

        if not versions or len(versions) < 2:
            return None

        current = ".".join(versions[0].split(".")[:2])
        previous = ".".join(versions[1].split(".")[:2])
        return current, previous

    async def get_champion_summary(self, version: str) -> Optional[list]:
        url = f"{CDRAGON_RAW}/{version}/plugins/rcp-be-lol-game-data/global/default/v1/champion-summary.json"
        return await self.fetch_json(url)

    async def fetch_champion(self, version: str, champ_id: int) -> Optional[dict]:
        url = f"{CDRAGON_RAW}/{version}/plugins/rcp-be-lol-game-data/global/default/v1/champions/{champ_id}.json"
        return await self.fetch_json(url)

    @app_commands.command(
        name="garen-patchnote",
        description="Affiche le patch technique pour les champions modifiés depuis la version précédente"
    )
    async def garen_patchnote(self, interaction: discord.Interaction):
        await interaction.response.defer()

        versions = await self.get_versions()
        if not versions:
            embed = EmbedBuilder.create_error_embed(
                "Erreur",
                "Impossible de récupérer les versions depuis DDragon.",
                error_type="error"
            )
            return await interaction.followup.send(embed=embed)

        current_version, previous_version = versions

        summary_prev = await self.get_champion_summary(previous_version)
        summary_cur = await self.get_champion_summary(current_version)

        if not summary_prev or not summary_cur:
            embed = EmbedBuilder.create_error_embed(
                "Erreur",
                "Impossible de récupérer les listes de champions pour une ou plusieurs versions.",
                error_type="error"
            )
            return await interaction.followup.send(embed=embed)

        champ_ids = sorted({c["id"] for c in summary_cur if "id" in c})

        # Télécharger tous les champions en parallèle
        tasks = []
        for cid in champ_ids:
            tasks.append(self.fetch_champion(previous_version, cid))
            tasks.append(self.fetch_champion(current_version, cid))
        results = await asyncio.gather(*tasks)

        previous_snapshot, current_snapshot = {}, {}
        for i, cid in enumerate(champ_ids):
            previous_snapshot[str(cid)] = results[2*i] or {}
            current_snapshot[str(cid)] = results[2*i+1] or {}

        # Comparer et ne garder que les champions modifiés
        relevant_keys = ["stats", "spells", "abilities", "passive"]
        changes_by_champ: dict[str, list[str]] = {}

        for cid_str, newdata in current_snapshot.items():
            olddata = previous_snapshot.get(cid_str)
            champ_name = newdata.get("name") or f"Champion {cid_str}"
            if not olddata:
                changes_by_champ[champ_name] = ["Champion ajouté dans la version " + current_version]
                continue

            diffs: list[str] = []
            for key in relevant_keys:
                a, b = olddata.get(key), newdata.get(key)
                if a is None and b is None:
                    continue
                diffs.extend(dict_diffs(a, b, path=key))

            if diffs:
                changes_by_champ[champ_name] = diffs

        if not changes_by_champ:
            embed = discord.Embed(
                title="Aucun changement détecté",
                description=f"Aucun changement technique détecté entre **{previous_version}** et **{current_version}**.",
                color=0x2ECC71
            )
            embed.set_footer(text="Données : CommunityDragon / ddragon")
            return await interaction.followup.send(embed=embed)

        embeds = paginate_fields(changes_by_champ)
        await interaction.followup.send(
            content=f"Changements détectés pour **{len(changes_by_champ)}** champions : **{previous_version} → {current_version}**"
        )
        for e in embeds[:10]:
            await interaction.followup.send(embed=e)


async def setup(bot: commands.Bot):
    await bot.add_cog(PatchnoteCog(bot))
