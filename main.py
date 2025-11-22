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
is_analyzing = True
ANALYZING_MSG_ID = None
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
# ============= ANALYZING LOOP =============
def analyzing_loop():
    global ANALYZING_MSG_ID
    while True:
        if is_analyzing:
            if ANALYZING_MSG_ID is None:
                msg = "🔍 Analisando padrões para o próximo sinal... ⏳"
                ANALYZING_MSG_ID = tg_send(msg)
                if ANALYZING_MSG_ID:
                    schedule_delete(ANALYZING_MSG_ID, 15)
                    def reset():
                        time.sleep(15)
                        global ANALYZING_MSG_ID
                        ANALYZING_MSG_ID = None
                    threading.Thread(target=reset, daemon=True).start()
            time.sleep(1)
        else:
            if ANALYZING_MSG_ID is not None:
                tg_delete(ANALYZING_MSG_ID)
                ANALYZING_MSG_ID = None
            time.sleep(1)
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
def get_pb_last_n(n, hist):
    return [x for x in list(hist)[-n:] if x in "PB"]
def is_alternating(l):
    for i in range(1, len(l)):
        if l[i] == l[i-1] or l[i] not in "PB" or l[i-1] not in "PB":
            return False
    return True
def estrategias(hist, extra):
    sinais = []
    # Repetições variadas (2x a 6x)
    for k in range(2, 7):
        if len(hist) >= k and all(hist[-i] == hist[-1] for i in range(1, k)) and hist[-1] in "PB":
            sinais.append((f"Repetição {k}x", hist[-1]))
    # Alternâncias variadas (3x a 5x)
    for m in range(3, 6):
        lastm = list(hist)[-m:]
        if len(lastm) == m and is_alternating(lastm):
            next_s = "P" if lastm[-1] == "B" else "B"
            sinais.append((f"Alternância {m}x", next_s))
    # Após ties variados (1 a 3)
    for k in range(1, 4):
        if len(hist) >= k + 1 and all(hist[-i-1] == "T" for i in range(k)) and hist[-1] in "PB":
            sinais.append((f"Após {k} Ties", hist[-1]))
    # Maiorias em janelas variadas
    for n in [3,4,5,6,7,8,9,10,15,20]:
        lastn = get_pb_last_n(n, hist)
        if lastn:
            c = Counter(lastn)
            if c['P'] != c['B']:
                mc = 'P' if c['P'] > c['B'] else 'B'
                sinais.append((f"Maioria last {n}", mc))
    # Minorias em janelas variadas (reversão)
    for n in [3,4,5,6,7,8,9,10,15,20]:
        lastn = get_pb_last_n(n, hist)
        if lastn:
            c = Counter(lastn)
            if c['P'] != c['B']:
                mc = 'P' if c['P'] < c['B'] else 'B'
                sinais.append((f"Minoria last {n} (reversão)", mc))
    # Votação para sinal extremamente acertivo
    if sinais:
        votes = Counter([s[1] for s in sinais])
        top = votes.most_common(1)[0]
        if top[1] >= 8:  # Threshold para acurácia
            return [("Multi-estratégias avançadas", top[0])]
    return []
def signal_text(s):
    if s == "P":
        return "🔵 Jogue no PLAYER!\n🛡️ Proteção no EMPATE"
    else:
        return "🔴 Jogue no BANKER!\n🛡️ Proteção no EMPATE"
# ============= PLACAR =============
def placar():
    global events_24h
    events_24h = [e for e in events_24h if now() - e["time"] < timedelta(hours=24)]
    total = len(events_24h)
    if not total:
        return "<b>📊 Placar Atual do Clever Bot</b>\nSem dados ainda."
    wins = sum(1 for e in events_24h if e["res"] == "win")
    ties = sum(1 for e in events_24h if e["res"] == "tie")
    losses = sum(1 for e in events_24h if e["res"] == "loss")
    sucess = wins + ties
    acc = (sucess / total * 100) if total else 0
    return f"""<b>📊 Placar Atual do Clever Bot</b>
✅ Sucessos (G0+G1+G2): {sucess}
   dos quais 🟰 Empates: {ties}
❌ Losses: {losses}
🎯 Acertividade: {acc:.1f}%
🔢 Total de Sinais: {total}"""
# ============= LOOP PRINCIPAL =============
def background_loop():
    global ACTIVE_PLAN, LAST_GAME_ID, CONSECUTIVE_LOSSES, is_analyzing
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
                    txt = f"<b>{'🟰 EMPATE! ⚖️' if result=='tie' else '✅ WIN DO CLEVER BOT! 🎉'}</b>\nResultado: 🔵 {scores['p']} | 🔴 {scores['b']}\nGale: {ACTIVE_PLAN['gale']}"
                    tg_send(txt)
                    events_24h.append({"res": result, "time": now()})
                    ACTIVE_PLAN = None
                    for mid in GALE_MSG_IDS: tg_delete(mid)
                    GALE_MSG_IDS.clear()
                    mid = tg_send(placar())
                    schedule_delete(mid)
                    is_analyzing = True
                else:
                    if ACTIVE_PLAN["gale"] < 2:
                        ACTIVE_PLAN["gale"] += 1
                        txt = f"<b>📈 GALÉ {ACTIVE_PLAN['gale']} {'🔵 PLAYER' if ACTIVE_PLAN['sug']=='P' else '🔴 BANKER'}</b>"
                        mid = tg_send(txt)
                        GALE_MSG_IDS.append(mid)
                    else:
                        txt = f"<b>❌ LOSS 😔</b>\nResultado: 🔵 {scores['p']} | 🔴 {scores['b']}\nGale: 2"
                        tg_send(txt)
                        events_24h.append({"res": "loss", "time": now()})
                        ACTIVE_PLAN = None
                        for mid in GALE_MSG_IDS: tg_delete(mid)
                        GALE_MSG_IDS.clear()
                        mid = tg_send(placar())
                        schedule_delete(mid)
                        is_analyzing = True
            # Novo sinal
            if not ACTIVE_PLAN:
                sinais = estrategias(HISTORY, scores)
                if sinais:
                    padrao, sug = sinais[0]
                    ACTIVE_PLAN = {"sug": sug, "gale": 0, "done": False}
                    is_analyzing = False
                    tg_send(f"<b>🚨 SINAL ENVIADO 🚨</b>\n📈 Estratégia: {padrao}\n{signal_text(sug)}")
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
    threading.Thread(target=analyzing_loop, daemon=True).start()
    threading.Thread(target=background_loop, daemon=True).start()
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
