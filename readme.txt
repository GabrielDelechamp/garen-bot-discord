# Garen Discord Bot

Garen is a Discord bot built for League of Legends communities.  
It integrates the **Riot Games API** to provide real-time game data directly inside Discord servers.

The bot is designed for **non-commercial use**, focusing on small communities and friends who want to track their stats, activity, and ongoing games in a simple way.

---

## Features

### 🧙 Summoner Profile
- Retrieve a summoner profile using a Riot ID
- Display:
  - Summoner level
  - Ranked tier and division
  - Wins and losses

### 🏆 Server Leaderboard
- Add summoners to a **server-based leaderboard**
- Display rankings for registered players
- Track **daily LP gains**

### 📊 Player Overview
- List all registered players on the server
- Show:
  - Linked Riot accounts
  - Current LP progression
  - Online / in-game status

### 🎮 Live Game (Lobby)
- Get a **live summary** of an ongoing match
- Display all participants:
  - Teams
  - Champions
  - Ranked information

### 🔄 Free Champion Rotation
- Display the current weekly free champion rotation

### 📰 Patch Notes
- Retrieve and display the latest League of Legends patch notes

---

## Commands

| Command | Description |
|-------|------------|
| `/garen-summoner <riotID>` | Display summoner profile and ranked stats |
| `/garen-add-localserver <riotID>` | Add a summoner to the server leaderboard |
| `/garen-leaderboard` | Show the server leaderboard |
| `/garen-info` | Show registered players, LP gain, and online status |
| `/garen-lobby <riotID>` | Display live game information |
| `/garen-rotation` | Show the free champion rotation |
| `/garen-patchnote` | Show the latest patch notes |

---

## Technology Stack

- **Python**
- **discord.py**
- **Riot Games API**
- REST APIs
- JSON-based local storage (per server)

---

## Data & Privacy

- The bot only uses **public data** provided by the Riot Games API
- No personal or private data is collected
- No user authentication is required
- Data is stored locally only for leaderboard purposes

---

## Riot Games API Compliance

This project uses the Riot Games API but is **not endorsed or certified by Riot Games**.

All data usage follows:
- Riot Games API Terms of Use
- Rate limits and data access rules

---

## Purpose

The goal of this project is to improve the Discord experience for League of Legends players by providing accurate and real-time game information in a friendly and automated way.

This bot is developed as a **personal and educational project**.

---

## Disclaimer

Garen Discord Bot is not affiliated with Riot Games, Inc.  
League of Legends and Riot Games are trademarks or registered trademarks of Riot Games, Inc.
