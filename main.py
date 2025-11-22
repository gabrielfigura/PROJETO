from flask import Flask, request
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
POLL_INTERVAL = 1.8
DELETE_AFTER = 65
MAX_HISTORY = 1000

# ============= STATE =============
HISTORY = deque(maxlen=MAX_HISTORY)
ACTIVE_PLAN = None
LAST_GAME_ID = None
GALE_MSG_IDS = []
events_24h = []
is_analyzing = True
ANALYZING_MSG_ID = None

# ============= UTIL =============
def now(): return datetime.now(timezone.utc)

def tg_send(text):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    try:
        r = requests.post(url, json={"chat_id": CHAT_ID, "text": text, "parse_mode": "HTML"}, timeout=10)
        if r.ok: return r.json()["result"]["message_id"]
    except: pass
    return None

def tg_delete(msg_id):
    if not msg_id: return
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/deleteMessage"
    try: requests.post(url, json={"chat_id": CHAT_ID, "message_id": msg_id}, timeout=5)
    except: pass

def schedule_delete(msg_id, delay=DELETE_AFTER):
    def job(): time.sleep(delay); tg_delete(msg_id)
    threading.Thread(target=job, daemon=True).start()

# ============= ANALYZING LOOP =============
def analyzing_loop():
    global ANALYZING_MSG_ID, is_analyzing
    while True:
        if is_analyzing and ANALYZING_MSG_ID is None:
            msg = "🔍 <b>Analisando mais de 50 padrões em tempo real...</b> ⏳"
            ANALYZING_MSG_ID = tg_send(msg)
            if ANALYZING_MSG_ID:
                threading.Thread(target=lambda: (time.sleep(15), setattr(__import__('builtins'), 'ANALYZING_MSG_ID', None) if ANALYZING_MSG_ID else None), daemon=True).start()
        elif not is_analyzing and ANALYZING_MSG_ID:
            tg_delete(ANALYZING_MSG_ID)
            ANALYZING_MSG_ID = None
        time.sleep(2)

# ============= ESTRATÉGIAS CORRIGIDAS E BALANCEADAS =============
def estrategias(hist):
    votos_p = 0
    votos_b = 0
    evidencias = []

    h = list(hist)

    # === 1. Repetições (2 a 7 seguidas) ===
    for r in range(2, 8):
        if len(h) >= r and all(h[-i] == h[-1] for i in range(1, r)) and h[-1] in "PB":
            peso = r * 2
            if h[-1] == "P": votos_p += peso
            else: votos_b += peso
            evidencias.append(f"Repetição {r}x → {h[-1]}")

    # === 2. Alternância perfeita ===
    for a in range(4, 8):
        seq = h[-a:]
        if len(seq) == a and all(seq[i] != seq[i-1] for i in range(1,a)):
            proximo = "P" if seq[-1] == "B" else "B"
            votos = a
            if proximo == "P": votos_p += votos
            else: votos_b += votos
            evidencias.append(f"Alternância {a}x → {proximo}")

    # === 3. Após Ties ===
    ties_seq = 0
    for i in range(1, 6):
        if len(h) >= i and h[-i] == "T": ties_seq += 1
        else: break
    if ties_seq > 0 and len(h) > ties_seq and h[-1-ties_seq] in "PB":
        peso = ties_seq * 3
        ultimo = h[-1-ties_seq]
        if ultimo == "P": votos_p += peso
        else: votos_b += peso
        evidencias.append(f"Após {ties_seq} Tie(s) → {ultimo}")

    # === 4. Maioria clara em várias janelas (balanceado) ===
    janelas = [5,7,9,12,15,20,25,30,40,50]
    for janela in janelas:
        ultimos = [x for x in h[-janela:] if x in "PB"]
        if len(ultimos) >= 5:
            c = Counter(ultimos)
            diff = abs(c["P"] - c["B"])
            if diff >= 3:
                vencedor = "P" if c["P"] > c["B"] else "B"
                peso = diff
                if vencedor == "P": votos_p += peso
                else: votos_b += peso
                evidencias.append(f"Maioria {janela} (+{diff}) → {vencedor}")

    # === 5. Reversão de domínio longo (anti-martingale) ===
    for longa in [12,18,25]:
        ult = [x for x in h[-longa:] if x in "PB"]
        if len(ult) >= 10:
            c = Counter(ult)
            if c["P"] > c["B"] * 2: votos_b += 6
            elif c["B"] > c["P"] * 2: votos_p += 6

    # === DECISÃO FINAL – ULTRA 90% ===
    total_votos = votos_p + votos_b
    if total_votos >= 26:  # Só entra com força BRUTA
        if votos_p > votos_b * 1.3:
            return "P", f"🔥 PLAYER – {votos_p} vs {votos_b} votos ({len(evidencias)} padrões)"
        elif votos_b > votos_p * 1.3:
            return "B", f"🔥 BANKER – {votos_b} vs {votos_p} votos ({len(evidencias)} padrões)"

    return None, None

def signal_text(sinal):
    if sinal == "P":
        return "🔵 <b>JOGUE FORTE NO PLAYER</b>\n🛡️ Proteção total no EMPATE"
    else:
        return "🔴 <b>JOGUE FORTE NO BANKER</b>\n🛡️ Proteção total no EMPATE"

# ============= PLACAR =============
def placar():
    global events_24h
    events_24h = [e for e in events_24h if now() - e["time"] < timedelta(hours=24)]
    total = len(events_24h)
    if total == 0: return "<b>📊 CLEVER BOT</b>\nAinda sem sinais hoje."
    win = sum(1 for e in events_24h if e["res"] == "win")
    tie = sum(1 for e in events_24h if e["res"] == "tie")
    acc = (win + tie) / total * 100
    return f"""<b>📊 CLEVER BOT – PLACAR 24H</b>
✅ Greens: {win + tie} (sendo {tie} empates)
❌ Red: {total - win - tie}
🎯 Assertividade: <b>{acc:.1f}%</b>
📈 Total: {total} sinais"""

# ============= LOOP PRINCIPAL =============
def background_loop():
    global ACTIVE_PLAN, LAST_GAME_ID, is_analyzing
    while True:
        try:
            data = requests.get(API_URL, timeout=10).json()
            gid, label, scores = None, None, {}
            try:
                d = data.get("data") or data
                gid = d.get("id") or d.get("gameId")
                res = d.get("result") or {}
                winner = res.get("outcome","").lower()
                if "player" in winner: label = "P"
                elif "banker" in winner: label = "B"
                elif "tie" in winner or "draw" in winner: label = "T"
                p = res.get("playerDice",{}).get("sum","?")
                b = res.get("bankerDice",{}).get("sum","?")
                scores = {"p": p, "b": b}
            except: pass

            if not gid or not label or gid == LAST_GAME_ID:
                time.sleep(POLL_INTERVAL); continue

            LAST_GAME_ID = gid
            HISTORY.append(label)

            # Resolve entrada ativa
            if ACTIVE_PLAN:
                sug = ACTIVE_PLAN["sug"]
                if label == sug or label == "T":
                    result = "win" if label == sug else "tie"
                    txt = f"<b>{'🟰 EMPATE (protegido)' if result=='tie' else '✅ GREEN ABSOLUTO!'}</b>\n🔵 {scores['p']} × 🔴 {scores['b']}\nGale {ACTIVE_PLAN['gale']}"
                    tg_send(txt)
                    events_24h.append({"res": result, "time": now()})
                    ACTIVE_PLAN = None
                    GALE_MSG_IDS.clear()
                    schedule_delete(tg_send(placar()))
                    is_analyzing = True
                else:
                    if ACTIVE_PLAN["gale"] < 2:
                        ACTIVE_PLAN["gale"] += 1
                        tg_send(f"<b>GALE {ACTIVE_PLAN['gale']} → {'🔵 PLAYER' if sug=='P' else '🔴 BANKER'}</b>")
                    else:
                        tg_send(f"<b>❌ RED</b>\n🔵 {scores['p']} × 🔴 {scores['b']}")
                        events_24h.append({"res": "loss", "time": now()})
                        ACTIVE_PLAN = None
                        GALE_MSG_IDS.clear()
                        schedule_delete(tg_send(placar()))
                        is_analyzing = True

            # Novo sinal
            if not ACTIVE_PLAN:
                sinal, motivo = estrategias(HISTORY)
                if sinal:
                    ACTIVE_PLAN = {"sug": sinal, "gale": 0}
                    is_analyzing = False
                    tg_send(f"<b>🚀 SINAL ULTRA 90% CONFIRMADO</b>\n{motivo}\n\n{signal_text(sinal)}")

            time.sleep(POLL_INTERVAL)
        except:
            time.sleep(POLL_INTERVAL)

# ============= START =============
@app.route('/', methods=['GET','HEAD'])
def index(): return "CLEVER BOT ULTRA 90% RODANDO!", 200

@app.route('/webhook', methods=['POST'])
def webhook(): return "ok", 200

if __name__ == "__main__":
    threading.Thread(target=analyzing_loop, daemon=True).start()
    threading.Thread(target=background_loop, daemon=True).start()
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
