import asyncio
import time
import json
import sys
import random
from TikTokLive import TikTokLiveClient
from TikTokLive.events import GiftEvent, CommentEvent

# --- Konfiguration und globale Variablen ---

leaderboard = {}
boss_base_hp = 200
boss_hp = boss_base_hp
damage_per_attack = 10
user_levels = {}

def add_experience(user, damage):
    xp_gain = damage // 10
    user_levels.setdefault(user, {"xp": 0, "level": 1})
    user_levels[user]["xp"] += xp_gain
    xp_needed = int(300 * (1.5 ** (user_levels[user]["level"] - 1)))
    while user_levels[user]["xp"] >= xp_needed:
        user_levels[user]["level"] += 1
        user_levels[user]["xp"] -= xp_needed
        print(f"🔺 {user} ist auf Level {user_levels[user]['level']} aufgestiegen!")
        xp_needed = int(300 * (1.5 ** (user_levels[user]["level"] - 1)))

GIFT_VALUES = {
    "Rose": 100,
    "TikTok Universe": 500,
    "Diamond": 250,
    "Angel": 150,
    "Love": 50
}

USERNAME = "ml_gameryt"
client = None
is_running = False
reconnect_attempts = 0
recent_attackers = {}

# --- Overlay-Update-Funktion (Leaderboard bis Platz 5) ---
async def update_overlay_json():
    sorted_leaderboard = sorted(leaderboard.items(), key=lambda x: x[1], reverse=True)[:5]
    data = {
        "title": "Can You Beat The Boss?",
        "boss": {
            "current_hp": boss_hp,
            "base_hp": boss_base_hp,
            "status": "Alive" if boss_hp > 0 else "Defeated"
        },
        "leaderboard": [
            {"rank": i + 1, "user": user, "damage": dmg}
            for i, (user, dmg) in enumerate(sorted_leaderboard)
        ]
    }
    with open('overlay_data.json', 'w') as f:
        json.dump(data, f, indent=4)

async def reset_client():
    global client
    if client is None:
        print("⚠ Kein Client zum Zurücksetzen vorhanden.")
        return
    try:
        await client.close()
        print("♻️ Vorherige Verbindung wurde geschlossen.")
    except Exception as e:
        print(f"⚠️ Fehler beim Schließen der Verbindung: {e}")
    client = None

async def on_connect():
    print("🚀 Starte den TikTok Bot...")
    print(f"🔥 Boss-HP: {boss_hp}")
    print("✅ TikTok Bot ist online und wartet auf eure !attack-Kommandos!")
    await update_overlay_json()

async def on_gift(event: GiftEvent):
    global boss_hp, leaderboard
    user = event.user.nickname
    damage = GIFT_VALUES.get(event.gift.name, 0)
    boss_hp -= damage
    leaderboard[user] = leaderboard.get(user, 0) + damage
    print(f"🎁 {user} hat ein {event.gift.name} gesendet! Boss-HP: {boss_hp}")
    add_experience(user, damage)
    await update_overlay_json()
    if boss_hp <= 0:
        await boss_defeated()

bot_start_time = time.time()

async def on_comment(event: CommentEvent):
    global boss_hp, leaderboard
    user = event.user.nickname
    print(f"💬 Nachricht empfangen: {user}: {event.comment}")
    if time.time() - bot_start_time < 3:
        print(f"⏳ IGNORIERT: Nachricht von {user} (Bot startet noch).")
        return
    if event.comment.lower() == "!attack":
        if user in recent_attackers and (time.time() - recent_attackers[user]) < 3:
            print(f"⏳ {user}, bitte warte mindestens 3 Sekunden zwischen den Angriffen, um Spam zu vermeiden!")
            return
        recent_attackers[user] = time.time()
        bonus = (user_levels.get(user, {}).get("level", 1) - 1) * 5
        damage = damage_per_attack + bonus
        boss_hp -= damage
        leaderboard[user] = leaderboard.get(user, 0) + damage
        add_experience(user, damage)
        print(f"⚔️ {user} greift den Boss an und verursacht {damage} Schaden! Boss-HP: {boss_hp}")
        await update_overlay_json()
        if boss_hp <= 0:
            await boss_defeated()

async def boss_defeated():
    global boss_hp, boss_base_hp, leaderboard
    print("\n🎉 DER BOSS WURDE BESIEGT! 🎉")
    print("🏆 **Leaderboard - Top Angreifer:**")
    if not leaderboard:
        print("❌ Keine Angriffe registriert.")
    else:
        sorted_leaderboard = sorted(leaderboard.items(), key=lambda x: x[1], reverse=True)
        for rank, (u, dmg) in enumerate(sorted_leaderboard[:5], start=1):
            print(f"{rank}. {u}: {dmg} Schaden")
    boss_base_hp = int(boss_base_hp * 1.2)
    boss_hp = boss_base_hp
    leaderboard.clear()
    print(f"\n🔥 Ein neuer Boss ist erschienen! Boss-HP: {boss_hp}")
    await update_overlay_json()

async def main():
    global client, is_running, reconnect_attempts
    if is_running:
        print("⚠️ Bot läuft bereits! Starte nicht erneut.")
        return
    is_running = True
    reconnect_attempts = 0

    # ✅ Hier startest du die automatische GitHub-Aktualisierung
    asyncio.create_task(auto_upload_github())

    print("⏳ Warte 5 Sekunden, bevor die Verbindung gestartet wird...")
    await asyncio.sleep(5)
    while reconnect_attempts < 3:
        try:
            print("🔄 Starte neuen Verbindungsversuch...")
            if client is not None:
                await reset_client()
            await asyncio.sleep(10)
            client = TikTokLiveClient(unique_id=USERNAME)
            client.on(GiftEvent, on_gift)
            client.on(CommentEvent, on_comment)
            await on_connect()
            await client.start()
            await asyncio.Event().wait()
        except Exception as e:
            reconnect_attempts += 1
            await asyncio.sleep(10)
    is_running = False


# --- Simulationsmodus: Stress-Test mit ca. 50 Zuschauern (5 Sekunden Abstand pro Aktion) ---
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
        # Warten Sie 5 Sekunden zwischen den Aktionen
        await asyncio.sleep(5)

async def simulate_events():
    print("⭐ Starte Stress-Test-Simulation mit ca. 50 Zuschauern ...")
    viewers = [f"User{i}" for i in range(1, 51)]
    tasks = [simulate_viewer(user, duration=30) for user in viewers]
    await asyncio.gather(*tasks)
    print("⭐ Stress-Test-Simulation abgeschlossen.")
    with open('overlay_data.json', 'r') as f:
        overlay_data = json.load(f)
    print("Overlay-Daten:")
    print(json.dumps(overlay_data, indent=4))

if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "simulate":
        asyncio.run(simulate_events())
    else:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(main())

# --- Automatisches Hochladen auf GitHub von PythonAnywhere ---
from git import Repo
import os

async def auto_upload_github():
    repo_path = '/home/Endroye/canyoubeattheboss'  # Anpassen!
    repo = Repo(repo_path)

    while True:
        try:
            repo.git.add('overlay_data.json')
            repo.index.commit('Overlay-Daten aktualisiert')
            origin = repo.remote(name='origin')
            origin.push()
            print("✅ Overlay-Daten auf GitHub aktualisiert.")
        except Exception as e:
            print(f"❌ Fehler beim Hochladen: {e}")
        await asyncio.sleep(3)

# Ergänze diese Zeile innerhalb deiner main()-Funktion:
asyncio.create_task(auto_upload_github())

