from flask import Flask
import requests
import time
import threading
from collections import deque, Counter
from datetime import datetime, timedelta, timezone
import os

app = Flask(__name__)

# ============= CONFIG =============
TELEGRAM_TOKEN = "8163319902:AAHE9LZ984JCIc-Lezl4WXR2FsGHPEFTxRQ"
CHAT_ID = "-1002597090660"
API_URL = "https://api.casinoscores.com/svc-evolution-game-events/api/bacbo/latest"
POLL_INTERVAL = 2.0
DELETE_AFTER = 70

# ============= STATE =============
HISTORY = deque(maxlen=1000)
LAST_GAME_ID = None
ACTIVE_PLAN = None
GALE_MSG_IDS = []
events_24h = []
ANALYZING_MSG_ID = None

def tg_send(text):
    try:
        r = requests.post(
            f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
            json={"chat_id": CHAT_ID, "text": text, "parse_mode": "HTML"},
            timeout=10
        )
        if r.status_code == 200:
            return r.json()["result"]["message_id"]
    except: pass
    return None

def tg_delete(msg_id):
    if not msg_id: return
    try:
        requests.post(
            f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/deleteMessage",
            json={"chat_id": CHAT_ID, "message_id": msg_id},
            timeout=5
        )
    except: pass

def schedule_delete(msg_id, delay=DELETE_AFTER):
    def job():
        time.sleep(delay)
        tg_delete(msg_id)
    threading.Thread(target=job, daemon=True).start()

# ============= MENSAGEM ANALISANDO (15s) =============
def analyzing_loop():
    global ANALYZING_MSG_ID
    while True:
        if ACTIVE_PLAN is None and ANALYZING_MSG_ID is None:
            msg_id = tg_send("🔍 <b>Analisando padrões em tempo real...</b> ⏳")
            if msg_id:
                ANALYZING_MSG_ID = msg_id
                threading.Thread(target=lambda: (time.sleep(15), tg_delete(msg_id) or globals().update(ANALYZING_MSG_ID=None)), daemon=True).start()
        time.sleep(3)

# ============= ESTRATÉGIAS ULTRA ASSERTIVAS (equilibradas) =============
def buscar_sinal():
    h = list(HISTORY)
    if len(h) < 10: return None, None

    p = 0  # pontos Player
    b = 0  # pontos Banker

    # 1. Repetição forte (3 a 6x)
    for r in range(3,7):
        if len(h) >= r and all(x == h[-1] for x in h[-r:]) and h[-1] in "PB":
            peso = r * 3
            p += peso if h[-1]=="P" else 0
            b += peso if h[-1]=="B" else 0

    # 2. Alternância perfeita
    for a in range(4,9):
        seq = h[-a:]
        if len(seq) == a and all(seq[i] != seq[i-1] for i in range(1,a)) and seq[0] in "PB":
            proximo = "P" if seq[-1]=="B" else "B"
            p += a if proximo=="P" else 0
            b += a if proximo=="B" else 0

    # 3. Após Ties
    ties = 0
    for i in range(1,6):
        if len(h) >= i and h[-i] == "T": ties += 1
        else: break
    if ties >= 1 and len(h) > ties and h[-1-ties] in "PB":
        p += ties*4 if h[-1-ties]=="P" else 0
        b += ties*4 if h[-1-ties]=="B" else 0

    # 4. Maioria clara nas últimas 10, 20, 30 rodadas
    for janela in [10,20,30]:
        ult = [x for x in h[-janela:] if x in "PB"]
        if len(ult) >= 8:
            cp, cb = ult.count("P"), ult.count("B")
            diff = abs(cp - cb)
            if diff >= 4:
                p += diff if cp > cb else 0
                b += diff if cb > cp else 0

    # Decisão final (muito mais equilibrada e assertiva)
    if p >= 22 and p > b * 1.4:
        return "P", f"🔥 PLAYER CONFIRMADO – {p} pontos (vs {b})"
    if b >= 22 and b > p * 1.4:
        return "B", f"🔥 BANKER CONFIRMADO – {b} pontos (vs {p})"

    return None, None

# ============= LOOP PRINCIPAL =============
def main_loop():
    global LAST_GAME_ID, ACTIVE_PLAN

    while True:
        try:
            data = requests.get(API_URL, timeout=10).json()
            game = data.get("data") or data

            gid = game.get("id") or game.get("gameId") or game.get("roundId")
            if not gid or gid == LAST_GAME_ID:
                time.sleep(POLL_INTERVAL)
                continue

            result = game.get("result") or {}
            winner = str(result.get("outcome") or "").lower()
            p_sum = result.get("playerDice", {}).get("sum", "?")
            b_sum = result.get("bankerDice", {}).get("sum", "?"")

            if "player" in winner: label = "P"
            elif "banker" in winner: label = "B"
            elif "tie" in winner or "draw" in winner: label = "T"
            else:
                time.sleep(POLL_INTERVAL)
                continue

            LAST_GAME_ID = gid
            HISTORY.append(label)

            # Resolve entrada ativa
            if ACTIVE_PLAN:
                sug = ACTIVE_PLAN["sug"]
                gale = ACTIVE_PLAN["gale"]

                if label == sug or label == "T":
                    res = "win" if label == sug else "tie"
                    txt = f"<b>{'EMPATE (protegido)' if res=='tie' else 'GREEN ABSOLUTO'}</b>\n🔵 {p_sum} × 🔴 {b_sum}\nGale {gale}"
                    tg_send(txt)
                    events_24h.append({"res": res, "time": datetime.now(timezone.utc)})
                    [tg_delete(m) for m in GALE_MSG_IDS]
                    GALE_MSG_IDS.clear()
                    schedule_delete(tg_send(placar()))
                    ACTIVE_PLAN = None
                else:
                    if gale < 2:
                        ACTIVE_PLAN["gale"] += 1
                        GALE_MSG_IDS.append(tg_send(f"<b>GALE {ACTIVE_PLAN['gale']} → {'PLAYER' if sug=='P' else 'BANKER'}</b>"))
                    else:
                        tg_send(f"<b>RED</b>\n🔵 {p_sum} × 🔴 {b_sum}")
                        events_24h.append({"res": "loss", "time": datetime.now(timezone.utc)})
                        [tg_delete(m) for m in GALE_MSG_IDS]
                        GALE_MSG_IDS.clear()
                        schedule_delete(tg_send(placar()))
                        ACTIVE_PLAN = None
            else:
                # Busca novo sinal
                sinal, motivo = buscar_sinal()
                if sinal:
                    ACTIVE_PLAN = {"sug": sinal, "gale": 0}
                    tg_delete(ANALYZING_MSG_ID)
                    globals()["ANALYZING_MSG_ID"] = None

                    emoji = "PLAYER" if sinal=="P" else "BANKER"
                    cor = "PLAYER" if sinal=="P" else "BANKER"
                    txt = f"<b>SINAL ENVIADO</b>\n{motivo}\n\n{'PLAYER' if sinal=='P' else 'BANKER'} <b>JOGUE AGORA</b>\nProteção no EMPATE"
                    tg_send(txt)

            time.sleep(POLL_INTERVAL)
        except:
            time.sleep(POLL_INTERVAL)

def placar():
    total = len(events_24h)
    if total == 0: return "<b>PLACAR CLEVER BOT</b>\nAinda sem entradas hoje."
    win_tie = sum(1 for e in events_24h if e["res"] != "loss")
    acc = win_tie / total * 100
    return f"<b>PLACAR CLEVER BOT</b>\nGreens: {win_tie}\nReds: {total-win_tie}\nAssertividade: <b>{acc:.1f}%</b>\nTotal: {total}"

# ============= START =============
@app.route('/', methods=['GET','HEAD'])
def home(): return "CLEVER BOT RODANDO 100%", 200

if __name__ == "__main__":
    threading.Thread(target=analyzing_loop, daemon=True).start()
    threading.Thread(target=main_loop, daemon=True).start()
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
