from flask import Flask, request, abort
import requests
import json
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
POLL_INTERVAL = 1.8
DELETE_AFTER = 65
MAX_HISTORY = 800
MAX_LOSS_STREAK = 10

# ============= STATE =============
HISTORY = deque(maxlen=MAX_HISTORY)
ACTIVE_PLAN = None
LAST_GAME_ID = None
GALE_MSG_IDS = []
CONSECUTIVE_LOSSES = 0
events_24h = []

# ============= UTIL =============
def now(): return datetime.now(timezone.utc)
def tg_send(text):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    try:
        r = requests.post(url, json={"chat_id": CHAT_ID, "text": text, "parse_mode": "HTML"}, timeout=10)
        if r.status_code == 200:
            return r.json()["result"]["message_id"]
    except: pass
    return None

def tg_delete(msg_id):
    if not msg_id: return
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/deleteMessage"
    try: requests.post(url, json={"chat_id": CHAT_ID, "message_id": msg_id}, timeout=5)
    except: pass

def schedule_delete(msg_id, delay=DELETE_AFTER):
    def job(): 
        time.sleep(delay)
        tg_delete(msg_id)
    threading.Thread(target=job, daemon=True).start()

# ============= ESTRATÉGIAS =============
def get_label(res): 
    r = str(res).lower()
    if "player" in r: return "P"
    if "banker" in r: return "B"
    if any(x in r for x in ["tie","draw","empate"]): return "T"
    return None

def parse_result(data):
    try:
        d = data.get("data") or data
        gid = d.get("id") or d.get("gameId") or d.get("roundId")
        res = d.get("result") or d.get("outcome") or {}
        winner = res.get("outcome") or res.get("winner")
        label = get_label(winner)
        p_score = res.get("playerDice", {}).get("sum") or "?"
        b_score = res.get("bankerDice", {}).get("sum") or "?"
        return gid, label, {"p": p_score, "b": b_score}
    except: return None, None, {}

def estrategias(hist, extra):
    sinais = []
    # Repetição
    if len(hist)>=3 and hist[-1]==hist[-2]==hist[-3] and hist[-1] in "PB":
        sinais.append(("Repetição 3x", hist[-1]))
    # Alternância ABAB
    if len(hist)>=4:
        l4 = hist[-4:]
        if l4[0]==l4[2] and l4[1]==l4[3] and l4[0]!=l4[1] and l4[0] in "PB":
            sinais.append(("Alternância ABAB", "P" if l4[-1]=="B" else "B"))
    # Após empate
    if len(hist)>=2 and hist[-2]=="T" and hist[-1] in "PB":
        sinais.append(("Sequência de Tie", hist[-1]))
    # Última vencedora
    if hist and hist[-1] in "PB":
        sinais.append(("Última Vencedora", hist[-1]))
    # Maioria 5
    last5 = [x for x in list(hist)[-5:] if x in "PB"]
    if len(last5)>=3:
        sinais.append(("Maioria 5", Counter(last5).most_common(1)[0][0]))
    return sinais[:1]  # só o mais forte

def signal_text(s): 
    return "JOGAR NO PLAYER\nPROTEÇÃO EMPATE" if s=="P" else "JOGAR NO BANKER\nPROTEÇÃO EMPATE"

# ============= PLACAR =============
def placar():
    total = len(events_24h)
    wins = sum(1 for e in events_24h if e["res"] in ["win","tie"])
    acc = (wins/total*100) if total else 0
    return f"""CLEVER – PLACAR ATUAL

G0+G1+G2: {wins}  
EMPATES: {sum(1 for e in events_24h if e["res"]=="tie")}
LOSS: {total-wins}

ACERTIVIDADE: {acc:.1f}%
TOTAL: {total}"""

# ============= LOOP PRINCIPAL =============
def background_loop():
    global ACTIVE_PLAN, LAST_GAME_ID, CONSECUTIVE_LOSSES
    while True:
        try:
            data = requests.get(API_URL, timeout=10).json()
            gid, label, scores = parse_result(data)
            if not gid or not label or gid == LAST_GAME_ID:
                time.sleep(POLL_INTERVAL); continue
            LAST_GAME_ID = gid
            HISTORY.append(label)

            # Resolve plano ativo
            if ACTIVE_PLAN and not ACTIVE_PLAN["done"]:
                if label == ACTIVE_PLAN["sug"] or label == "T":
                    result = "win" if label == ACTIVE_PLAN["sug"] else "tie"
                    txt = f"{'EMPATE' if result=='tie' else 'WIN DO CLEVER BOT'}\nResultado: {scores['p']} | {scores['b']}\nGale: {ACTIVE_PLAN['gale']}"
                    tg_send(txt)
                    events_24h.append({"res": result})
                    ACTIVE_PLAN = None
                    for mid in GALE_MSG_IDS: tg_delete(mid)
                    GALE_MSG_IDS.clear()
                    schedule_delete(tg_send(placar()))
                else:
                    if ACTIVE_PLAN["gale"] < 2:
                        ACTIVE_PLAN["gale"] += 1
                        mid = tg_send(f"GALÉ {ACTIVE_PLAN['gale']} {'PLAYER' if ACTIVE_PLAN['sug']=='P' else 'BANKER'}")
                        GALE_MSG_IDS.append(mid)
                    else:
                        tg_send(f"LOSS\nResultado: {scores['p']} | {scores['b']}\nGale: 2")
                        events_24h.append({"res": "loss"})
                        ACTIVE_PLAN = None
                        for mid in GALE_MSG_IDS: tg_delete(mid)
                        GALE_MSG_IDS.clear()
                        schedule_delete(tg_send(placar()))

            # Novo sinal
            if not ACTIVE_PLAN:
                sinais = estrategias(HISTORY, scores)
                if sinais:
                    padrao, sug = sinais[0]
                    ACTIVE_PLAN = {"sug": sug, "gale": 0, "done": False}
                    tg_send(f"ANÁLISE ENVIADA\nESTRATÉGIA: {padrao}\nENTRADA: {signal_text(sug)}")

            time.sleep(POLL_INTERVAL)
        except: 
            time.sleep(POLL_INTERVAL)

# ============= WEBHOOK =============
@app.route('/', methods=['GET', 'HEAD'])
def index():
    return "Clever Bac Bo rodando!", 200

@app.route('/webhook', methods=['POST'])
def webhook():
    return "ok", 200

if __name__ == "__main__":
    threading.Thread(target=background_loop, daemon=True).start()
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
