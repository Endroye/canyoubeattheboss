import asyncio
import time
import json
from TikTokLive import TikTokLiveClient
from TikTokLive.events import GiftEvent, CommentEvent

# --- Konfiguration und globale Variablen ---

# Leaderboard für Top-Schaden-Dealer
leaderboard = {}

# Boss-HP
boss_base_hp = 200           # Start-HP des Bosses
boss_hp = boss_base_hp       # Aktuelle HP des Bosses

damage_per_attack = 10       # Basis-Schaden pro "!attack" (ohne Bonus)

# Globale Variable für Zuschauer-Level und XP
user_levels = {}

def add_experience(user, damage):
    """
    Berechnet XP-Gewinn als 10% des verursachten Schadens.
    XP-Schwelle für den nächsten Level:
      xp_needed = 300 * (1.5)^(aktuelles Level - 1)
    """
    xp_gain = damage // 10
    user_levels.setdefault(user, {"xp": 0, "level": 1})
    user_levels[user]["xp"] += xp_gain

    xp_needed = int(300 * (1.5 ** (user_levels[user]["level"] - 1)))
    while user_levels[user]["xp"] >= xp_needed:
        user_levels[user]["level"] += 1
        user_levels[user]["xp"] -= xp_needed
        print(f"🔺 {user} ist auf Level {user_levels[user]['level']} aufgestiegen!")
        xp_needed = int(300 * (1.5 ** (user_levels[user]["level"] - 1)))

# Mapping der TikTok-Geschenke (Basiswerte)
GIFT_VALUES = {
    "Rose": 100,
    "TikTok Universe": 500,
    "Diamond": 250,
    "Angel": 150,
    "Love": 50
}

# TikTok Username (ohne @)
USERNAME = "ml_gameryt"

# TikTok Live Client
client = None
is_running = False
reconnect_attempts = 0

# Spam-Schutz: Letzte Angriffe
recent_attackers = {}

# --- Overlay-Update-Funktion ---
async def update_overlay_json():
    sorted_leaderboard = sorted(leaderboard.items(), key=lambda x: x[1], reverse=True)[:5]
    data = {
        "boss_hp": boss_hp,
        "leaderboard": [{"user": user, "damage": dmg} for user, dmg in sorted_leaderboard]
    }
    with open('overlay_data.json', 'w') as f:
        json.dump(data, f, indent=4)

# --- Funktionen für den Live-Modus ---

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
    await update_overlay_json()  # Overlay initial aktualisieren

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

    # Nachrichten in den ersten 3 Sekunden (Bot-Start) ignorieren
    if time.time() - bot_start_time < 3:
        print(f"⏳ IGNORIERT: Nachricht von {user} (Bot startet noch).")
        return

    if event.comment.lower() == "!attack":
        # Spam-Schutz: mind. 3 Sekunden zwischen den Angriffen
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
    # Boss-Upgrade: Basis-HP um 20% erhöhen
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

    print("⏳ Warte 5 Sekunden, bevor die Verbindung gestartet wird...")
    await asyncio.sleep(5)

    while reconnect_attempts < 3:
        try:
            print("🔄 Starte neuen Verbindungsversuch...")
            print("🔄 Client wird zurückgesetzt...")
            if client is not None:
                await reset_client()
                print("✅ Client erfolgreich zurückgesetzt!")
            else:
                print("⚠️ Kein Client vorhanden, kein Reset nötig.")

            await asyncio.sleep(10)
            print("⏳ Wartezeit beendet. Erstelle neuen Client...")

            if not USERNAME or not isinstance(USERNAME, str):
                print("⛔ Fehler: TikTok-Username ist ungültig!")
                return

            print("📡 Erstelle TikTokLiveClient...")
            client = TikTokLiveClient(unique_id=USERNAME)
            print("✅ TikTokLiveClient erfolgreich erstellt!")

            client.on(GiftEvent, on_gift)
            client.on(CommentEvent, on_comment)

            await on_connect()

            print("📡 Starte TikTok Client...")
            try:
                await asyncio.wait_for(client.start(), timeout=60)
                print("✅ TikTok Client läuft!")
            except asyncio.TimeoutError:
                print("⏳ Timeout: TikTok Client konnte nicht starten!")
                return

            await asyncio.Event().wait()

        except Exception as e:
            reconnect_attempts += 1
            print(f"⚠️ Verbindung verloren: {e}")
            print(f"🔄 Versuche erneut zu verbinden in 10 Sekunden... (Versuch {reconnect_attempts}/3)")
            await asyncio.sleep(10)

    print("❌ Zu viele fehlgeschlagene Verbindungsversuche. Bitte manuell neu starten.")
    is_running = False

if __name__ == "__main__":
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(main())
