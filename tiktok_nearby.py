import asyncio
import time
import json
import sys
import random
import os

# TikTokLive-Imports
from TikTokLive import TikTokLiveClient
from TikTokLive.events import GiftEvent, CommentEvent

# GitHub Upload
from git import Repo

# --- Mapping of Boss Types to Background Files (GIFs or Images) ---
BOSS_BACKGROUNDS = {
    "fire_demon": "backgrounds/fire_demon.png",
    "dark_knight": "backgrounds/dark_knight.png",
    "ancient_dragon": "backgrounds/ancient_dragon.png",
    "boss4": "backgrounds/boss4.png",
    "boss5": "backgrounds/boss5.png",
    "boss6": "backgrounds/boss6.png",
    "boss7": "backgrounds/boss7.png",
    "boss8": "backgrounds/boss8.png",
    "boss9": "backgrounds/boss9.png",
    "boss10": "backgrounds/boss10.png",
    "boss11": "backgrounds/boss11.png",
    "boss12": "backgrounds/boss12.png",
    "boss13": "backgrounds/boss13.png",
    "boss14": "backgrounds/boss14.png",
    "boss15": "backgrounds/boss15.png"
    # Add more entries as needed (up to 40 boss types)
}

# --- Konfiguration & Globale Variablen ---
leaderboard = {}           # Current session leaderboard (resets on boss defeat)
global_leaderboard = {}    # Overall damage statistics (never reset automatically)
boss_base_hp = 200
boss_hp = boss_base_hp
damage_per_attack = 10
user_levels = {}

client = None
is_running = False
reconnect_attempts = 0
recent_attackers = {}

USERNAME = "lisaistlost"
STREAMER_USERNAME = "Lee"  # Only this user is allowed to reset the all-time leaderboard

# Liste der verfügbaren Boss-Typen (erweiterbar bis zu 40 Bosse)
BOSS_TYPES = [
    "fire_demon", "dark_knight", "ancient_dragon",
    "boss4", "boss5", "boss6", "boss7", "boss8", "boss9",
    "boss10", "boss11", "boss12", "boss13", "boss14", "boss15"
]
current_boss_index = 0

def get_current_boss_type():
    return BOSS_TYPES[current_boss_index]

# Possible gifts and their damage
GIFT_VALUES = {
    "Rose": 100,
    "TikTok Universe": 500,
    "Diamond": 250,
    "Angel": 150,
    "Love": 50
}

# --- XP Function ---
def add_experience(user, damage):
    xp_gain = damage // 10
    user_levels.setdefault(user, {"xp": 0, "level": 1})
    user_levels[user]["xp"] += xp_gain

    xp_needed = int(300 * (1.5 ** (user_levels[user]["level"] - 1)))
    while user_levels[user]["xp"] >= xp_needed:
        user_levels[user]["level"] += 1
        user_levels[user]["xp"] -= xp_needed
        print(f"🔺 {user} leveled up to {user_levels[user]['level']}!")

# --- Funktion zum Zurücksetzen des All-Time Leaderboards ---
def reset_all_time_leaderboard():
    global global_leaderboard
    global_leaderboard.clear()
    print("✅ Global (all-time) leaderboard has been reset.")

# --- Overlay Update Function (inkl. All-Time Leaderboard und Boss-Hintergrund) ---
async def update_overlay_json():
    sorted_leaderboard = sorted(leaderboard.items(), key=lambda x: x[1], reverse=True)[:5]
    sorted_global = sorted(global_leaderboard.items(), key=lambda x: x[1], reverse=True)[:5]
    current_boss_type = get_current_boss_type()
    background_path = BOSS_BACKGROUNDS.get(current_boss_type, "")

    data = {
        "title": "Can You Beat The Boss?",
        "boss": {
            "current_hp": boss_hp,
            "base_hp": boss_base_hp,
            "status": "Alive" if boss_hp > 0 else "Defeated",
            "background": background_path
        },
        "leaderboard": [
            {"rank": i + 1, "user": user, "damage": dmg}
            for i, (user, dmg) in enumerate(sorted_leaderboard)
        ],
        "all_time_leaderboard": [
            {"rank": i + 1, "user": user, "damage": dmg}
            for i, (user, dmg) in enumerate(sorted_global)
        ]
    }

    with open('/home/Endroye/canyoubeattheboss/static/overlay_data.json', 'w') as f:
        json.dump(data, f, indent=4)


# --- Automatischer GitHub-Upload ---
async def auto_upload_github():
    repo_path = "/home/Endroye/canyoubeattheboss"  # Pfad anpassen
    try:
        repo = Repo(repo_path)
    except Exception as e:
        print(f"❌ Could not open the repo: {e}")
        return

    while True:
        try:
            repo.git.add('--all')
            if repo.is_dirty():
                repo.index.commit('Overlay data updated')
                origin = repo.remote(name='origin')
                origin.push()
                print("✅ overlay_data.json successfully pushed to GitHub.")
        except Exception as e:
            print(f"❌ Error while pushing to GitHub: {e}")
        await asyncio.sleep(3)

# --- Client Reset ---
async def reset_client():
    global client
    if client is None:
        print("⚠ No client to reset.")
        return
    try:
        await client.close()
        print("♻ Previous connection was closed.")
    except Exception as e:
        print(f"⚠ Error while closing connection: {e}")
    client = None

# --- Event Callbacks ---
async def on_connect():
    print("🚀 Starting the TikTok Bot...")
    print(f"🔥 Boss HP: {boss_hp}")
    print("✅ TikTok Bot is online and waiting for your !attack commands!")
    await update_overlay_json()

async def on_gift(event: GiftEvent):
    global boss_hp, leaderboard, global_leaderboard
    user = event.user.nickname
    damage = GIFT_VALUES.get(event.gift.name, 0)
    boss_hp -= damage
    leaderboard[user] = leaderboard.get(user, 0) + damage
    global_leaderboard[user] = global_leaderboard.get(user, 0) + damage

    print(f"🎁 {user} sent a {event.gift.name}! Boss HP: {boss_hp}")
    add_experience(user, damage)
    await update_overlay_json()

    if boss_hp <= 0:
        await boss_defeated()

bot_start_time = time.time()

async def on_comment(event: CommentEvent):
    global boss_hp, leaderboard, global_leaderboard
    user = event.user.nickname
    print(f"💬 Message received: {user}: {event.comment}")

    if time.time() - bot_start_time < 3:
        print(f"⏳ IGNORED: Message from {user} (Bot is still starting).")
        return

    # Check for reset command; only streamer "Lee" can reset
    if event.comment.lower() == "!resetall":
        if user.lower() == STREAMER_USERNAME.lower():
            reset_all_time_leaderboard()
            await update_overlay_json()
            print("🔄 All-time leaderboard reset by streamer.")
        else:
            print(f"⏳ {user} is not authorized to reset the all-time leaderboard.")
        return

    if event.comment.lower() == "!attack":
        if user in recent_attackers and (time.time() - recent_attackers[user]) < 3:
            print(f"⏳ {user}, please wait at least 3 seconds between attacks to avoid spam!")
            return

        recent_attackers[user] = time.time()
        bonus = (user_levels.get(user, {}).get("level", 1) - 1) * 5
        damage = damage_per_attack + bonus
        boss_hp -= damage
        leaderboard[user] = leaderboard.get(user, 0) + damage
        global_leaderboard[user] = global_leaderboard.get(user, 0) + damage

        add_experience(user, damage)
        print(f"⚔️ {user} attacks the Boss and deals {damage} damage! Boss HP: {boss_hp}")
        await update_overlay_json()

        if boss_hp <= 0:
            await boss_defeated()

async def boss_defeated():
    global boss_hp, boss_base_hp, leaderboard, current_boss_index
    print("\n🎉 THE BOSS HAS BEEN DEFEATED! 🎉")
    print("🏆 **Leaderboard - Top Attackers:**")

    if not leaderboard:
        print("❌ No attacks recorded.")
    else:
        sorted_leaderboard = sorted(leaderboard.items(), key=lambda x: x[1], reverse=True)
        for rank, (u, dmg) in enumerate(sorted_leaderboard[:5], start=1):
            print(f"{rank}. {u}: {dmg} damage")

    boss_base_hp = int(boss_base_hp * 1.2)
    boss_hp = boss_base_hp
    leaderboard.clear()
    print(f"\n🔥 A new Boss has appeared! Boss HP: {boss_hp}")
    await update_overlay_json()

    # Switch to the next boss
    current_boss_index = (current_boss_index + 1) % len(BOSS_TYPES)

# --- Main Function ---
async def main():
    global client, is_running, reconnect_attempts
    if is_running:
        print("⚠ Bot is already running! Not starting again.")
        return

    is_running = True
    reconnect_attempts = 0

    # Start GitHub auto-upload as a background task
    asyncio.create_task(auto_upload_github())

    print("⏳ Waiting 5 seconds before starting the connection...")
    await asyncio.sleep(5)

    while reconnect_attempts < 3:
        try:
            print("🔄 Starting a new connection attempt...")
            if client is not None:
                await reset_client()

            await asyncio.sleep(10)
            print("⏳ Waiting period over. Creating new client...")

            client = TikTokLiveClient(unique_id=USERNAME)
            client.on(GiftEvent, on_gift)
            client.on(CommentEvent, on_comment)

            await on_connect()
            print("📡 Connecting to TikTok...")

            await client.start()
            await asyncio.Event().wait()
        except Exception as e:
            reconnect_attempts += 1
            print(f"❌ Error or lost connection: {e}")
            print(f"🔄 Retrying in 10 seconds... (Attempt {reconnect_attempts}/3)")
            await asyncio.sleep(10)

    print("❌ Too many failed connection attempts. Please restart manually.")
    is_running = False

# --- Simulation Mode (Stress Test) ---
class DummyUser:
    def __init__(self, nickname):
        self.nickname = nickname

class DummyGift:
    def __init__(self, name):
        self.name = name

class DummyCommentEvent:
    def __init__(self, nickname, comment):
        self.user = DummyUser(nickname)
        self.comment = comment

class DummyGiftEvent:
    def __init__(self, nickname, gift_name):
        self.user = DummyUser(nickname)
        self.gift = DummyGift(gift_name)

async def simulate_viewer(user_name, duration=30):
    start_time = time.time()
    while time.time() - start_time < duration:
        event_type = random.choices(["attack", "gift"], weights=[0.7, 0.3])[0]
        if event_type == "attack":
            await on_comment(DummyCommentEvent(user_name, "!attack"))
        else:
            gift = random.choice(list(GIFT_VALUES.keys()))
            await on_gift(DummyGiftEvent(user_name, gift))
        await asyncio.sleep(5)

async def simulate_events():
    print("⭐ Starting stress-test simulation with about 50 viewers...")
    viewers = [f"User{i}" for i in range(1, 51)]
    tasks = [simulate_viewer(user, duration=30) for user in viewers]
    await asyncio.gather(*tasks)
    print("⭐ Stress-test simulation finished.")
    with open('overlay_data.json', 'r') as f:
        overlay_data = json.load(f)
    print("Overlay Data:")
    print(json.dumps(overlay_data, indent=4))

# --- Entry Point ---
if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "simulate":
        asyncio.run(simulate_events())
    else:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(main())
