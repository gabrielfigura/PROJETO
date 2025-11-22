import os
import time
import json
import csv
import threading
import traceback
from collections import deque, Counter
from datetime import datetime, timedelta, timezone
import requests

# ---------------- CONFIG ----------------
TELEGRAM_TOKEN = "8163319902:AAHE9LZ984JCIc-Lezl4WXR2FsGHPEFTxRQ"  # seu token aqui
CHAT_ID = "-1002597090660"         # seu chat_id aqui
API_URL = "https://api.casinoscores.com/svc-evolution-game-events/api/bacbo/latest"
POLL_INTERVAL = 1.5
DELETE_ANALYSIS_AFTER = 60
HISTORY_MAX = 800
EVENTS_FILE = "events_24h.json"
CSV_LOG = "history_log.csv"
USER_AGENT = "Mozilla/5.0 (compatible; CleverBot/1.0)"
MAX_LOSSES = 10  # Zerar placar após 10 losses consecutivos

# ---------------- STATE ----------------
HISTORY = deque(maxlen=HISTORY_MAX)
ACTIVE_PLAN = None
LAST_GAME_ID = None
GALE_MSG_IDS = []
CONSECUTIVE_LOSSES = 0

# ---------------- UTIL ----------------
def now_iso():
    return datetime.now(timezone.utc).isoformat()

def log(msg):
    print(f"[{datetime.now().astimezone().strftime('%Y-%m-%d %H:%M:%S')}] {msg}", flush=True)

# ---------------- PERSISTÊNCIA ----------------
events = []

def load_events():
    global events
    try:
        with open(EVENTS_FILE, "r", encoding="utf-8") as f:
            events = json.load(f)
    except Exception:
        events = []
    prune_events()

def save_events():
    try:
        with open(EVENTS_FILE, "w", encoding="utf-8") as f:
            json.dump(events, f)
    except Exception as e:
        log(f"Erro ao salvar events: {e}")

def prune_events():
    global events
    cutoff = datetime.now(timezone.utc) - timedelta(hours=24)
    events = [e for e in events if datetime.fromisoformat(e["ts"]) >= cutoff]
    save_events()

def append_event(outcome, padrao, sugestao, gale, game_id=None, details=None):
    global events, CONSECUTIVE_LOSSES
    events.append({
        "ts": now_iso(),
        "outcome": outcome,
        "padrao": padrao,
        "sugestao": sugestao,
        "gale": gale,
        "game_id": game_id,
        "details": details or {}
    })
    prune_events()
    try:
        header = not os.path.exists(CSV_LOG)
        with open(CSV_LOG, "a", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            if header:
                w.writerow(["ts", "outcome", "padrao", "sugestao", "gale", "game_id", "details"])
            w.writerow([now_iso(), outcome, padrao, sugestao, gale, game_id or "", json.dumps(details or {})])
    except Exception as e:
        log(f"Erro append_event CSV: {e}")
    
    # Atualiza losses consecutivos
    if outcome == "loss":
        CONSECUTIVE_LOSSES += 1
    else:
        CONSECUTIVE_LOSSES = 0

# ---------------- TELEGRAM ----------------
def tg_send(text):
    if not TELEGRAM_TOKEN or TELEGRAM_TOKEN.strip() == "":
        log("Telegram token vazio. Mensagem não enviada.")
        return None
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    try:
        r = requests.post(url, data={"chat_id": CHAT_ID, "text": text}, timeout=12)
        if r.status_code == 200:
            return r.json().get("result", {}).get("message_id")
        else:
            log(f"Telegram send error {r.status_code}: {r.text}")
    except Exception as e:
        log(f"Telegram send exception: {e}")
    return None

def tg_delete(message_id):
    if not message_id:
        return False
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/deleteMessage"
    try:
        r = requests.post(url, data={"chat_id": CHAT_ID, "message_id": message_id}, timeout=8)
        return r.status_code == 200
    except Exception as e:
        log(f"tg_delete exception: {e}")
        return False

def schedule_delete(msg_id, delay=60):
    if not msg_id:
        return
    def job(mid, d):
        time.sleep(d)
        try:
            tg_delete(mid)
        except Exception:
            pass
    threading.Thread(target=job, args=(msg_id, delay), daemon=True).start()

# ---------------- API ----------------
def fetch_api():
    headers = {"User-Agent": USER_AGENT}
    try:
r = requests.get(API_URL, headers=headers, timeout=12)
        if r.status_code == 200:
            return r.json()
        else:
            log(f"API HTTP {r.status_code}: {r.text if hasattr(r, 'text') else ''}")
    except Exception as e:
        log(f"API fetch exception: {e}")
    return None

def outcome_to_label(outcome_str):
    if not outcome_str: return None
    s = str(outcome_str).lower()
    if "player" in s: return "P"
    if "banker" in s: return "B"
    if "tie" in s or "draw" in s or "empate" in s: return "T"
    if s=="p": return "P"
    if s=="b": return "B"
    if s=="t": return "T"
    return None

def parse_latest_from_api(data):
    try:
        payload = data.get("data") or data
        game_id = None
        label = None
        extra = {}
        if isinstance(payload, dict):
            game_id = payload.get("id") or payload.get("gameId") or payload.get("roundId")
            result = payload.get("result") or (payload.get("game") or {}).get("result") or payload.get("outcome") or payload.get("winner")
            if isinstance(result, dict):
                outcome = result.get("outcome") or result.get("winner") or result.get("result")
                label = outcome_to_label(outcome)
                pl = result.get("playerDice") or result.get("player") or {}
                bk = result.get("bankerDice") or result.get("banker") or {}
                def get_score(obj):
                    if not isinstance(obj, dict):
                        return None
                    for k in ("score","sum","total","points"):
                        v = obj.get(k)
                        if v is None: continue
                        try: return int(v)
                        except Exception:
                            try: return int(str(v))
                            except Exception: return None
                    return None
                extra["player_score"] = get_score(pl)
                extra["banker_score"] = get_score(bk)
                return game_id,label,True,extra
        return game_id,label,False,{}
    except Exception:
        return None,None,False,{}

# ---------------- ESTRATÉGIAS ----------------
def oposto(c): return 'P' if c=='B' else 'B'

def estrategia_repeticao(hist):
    if len(hist)>=3 and hist[-1]==hist[-2]==hist[-3] and hist[-1] in ("P","B"): return ("𝘙𝘦𝘱𝘦𝘵𝘪𝘤𝘢𝘰 3x", hist[-1])
    if len(hist)>=2 and hist[-1]==hist[-2] and hist[-1] in ("P","B"): return ("𝘙𝘦𝘱𝘦𝘵𝘪𝘤𝘢𝘰 2x", hist[-1])
    return None

def estrategia_alternancia_new(hist):
    if len(hist)>=4:
        last4 = hist[-4:]
        if all(x in ("P","B") for x in last4) and last4[0]==last4[2] and last4[1]==last4[3] and last4[0]!=last4[1]:
            return ("𝘈𝘭𝘵𝘦𝘳𝘯𝘢𝘯𝘤𝘪𝘢 𝘈𝘉𝘈𝘉", oposto(last4[-1]))
    return None

def estrategia_seq_empate(hist):
    if len(hist)>=2 and hist[-2]=='T' and hist[-1] in ('P','B'): return ("𝘴𝘦𝘲𝘶𝘦𝘯𝘤𝘪𝘢 𝘥𝘦 𝘵𝘪𝘦", hist[-1])
    return None

def estrategia_ultima(hist):
    if len(hist)>=1 and hist[-1] in ('P','B'): return ("𝘜𝘭𝘵𝘪𝘮𝘢 𝘷𝘦𝘯𝘤𝘦𝘥𝘰𝘳𝘢", hist[-1])
    return None

def estrategia_maj5(hist):
    window = [x for x in list(hist)[-5:] if x in ('P','B')]
    if len(window)>=3:
        cnt = Counter(window)
        most,_ = cnt.most_common(1)[0]
        return ("𝘔𝘢𝘪𝘰𝘳𝘪𝘢5", most)
    return None

def estrategia_paridade(extra):
    try:
        ps = extra.get("player_score")
        bs = extra.get("banker_score")
        if ps is None or bs is None: return None
        if ps%2==1 and bs%2==0: return ("𝘗𝘢𝘳𝘪𝘋𝘦𝘋𝘢𝘥𝘰𝘴","P")
        if bs%2==1 and ps%2==0: return ("𝘗𝘢𝘳𝘪𝘋𝘦𝘋𝘢𝘥𝘰𝘴","B")
    except Exception: pass
    return None

def gerar_todas_estrategias(hist, extra=None):
    sinais=[]
    funcs=[estrategia_repeticao,estrategia_alternancia_new,estrategia_seq_empate,estrategia_ultima,estrategia_maj5]
    seen=set()
    uniq=[]
    for f in funcs:
        try:
            res=f(hist)
            if res and res[1] not in seen:
                uniq.append(res)
                seen.add(res[1])
                except Exception: pass
    res=estrategia_paridade(extra or {})
    if res and res[1] not in seen: uniq.append(res)
    return uniq

# ---------------- MENSAGENS ----------------
ANALYSE_TEXT="⬇️ 𝘚𝘐𝘕𝘈𝘓 𝘈𝘕𝘈𝘓𝘐𝘚𝘈𝘋𝘖 ⬇️"
def signal_text(sug):
    if sug=='P': return "🔵 JOGAR NO PLAYER\n🛡️ PROTEÇÃO EMPATE: 🟠"
    if sug=='B': return "🔴 JOGAR NO BANKER\n🛡️ PROTEÇÃO EMPATE: 🟠"
    if sug=='T': return "🚀 POSSÍVEL EMPATE 🟠"
    return "💡JOGADA DETECTADA💡"

def gale_text(n,s):
    em="🔵" if s=='P' else ("🔴" if s=='B' else "🟡")
    return f" 🔄 GALÉ {n}  {em}"

# ---------------- PLACAR ----------------
def compute_scoreboard():
    global CONSECUTIVE_LOSSES
    prune_events()
    total = len(events)
    wins_g0 = sum(1 for e in events if e['outcome'] == 'win' and e['gale'] == 0)
    wins_g1 = sum(1 for e in events if e['outcome'] == 'win' and e['gale'] == 1)
    wins_g2 = sum(1 for e in events if e['outcome'] == 'win' and e['gale'] == 2)
    ties = sum(1 for e in events if e['outcome'] == 'tie')
    losses = sum(1 for e in events if e['outcome'] == 'loss')
    accuracy = ((wins_g0 + wins_g1 + wins_g2 + ties) / total * 100) if total else 0.0
    max_streak = 0
    cur = 0
    for e in events:
        if e['outcome'] in ('win', 'tie'):
            cur += 1
            max_streak = max(max_streak, cur)
        else:
            cur = 0
    cur_streak = 0
    for e in reversed(events):
        if e['outcome'] in ('win', 'tie'):
            cur_streak += 1
        else:
            break
    # Zerar se 10 losses consecutivos
    if CONSECUTIVE_LOSSES >= MAX_LOSSES:
        CONSECUTIVE_LOSSES = 0
        events.clear()
        save_events()
        total = wins_g0 = wins_g1 = wins_g2 = ties = losses = cur_streak = accuracy = 0
    return {
        "total": total,
        "wins_g0": wins_g0,
        "wins_g1": wins_g1,
        "wins_g2": wins_g2,
        "ties": ties,
        "losses": losses,
        "accuracy": accuracy,
        "cur_streak": cur_streak
    }

def montar_painel_text():
    s = compute_scoreboard()
    return (
        f"📊 CLEVER – PLACAR ATUAL\n\n"
        f"🏅 G0: {s['wins_g0']}   |   G1: {s['wins_g1']}   |   G2: {s['wins_g2']}\n"
        f"🛡️ EMPATES: {s['ties']}\n"
        f"❌ LOSS: {s['losses']}\n\n"
        f"🎯 ACERTIVIDADE: {s['accuracy']:.2f}%\n"
        f"🔥 WINS SEGUIDOS: {s['cur_streak']}\n"
        f"📉 TOTAL JOGADAS: {s['total']}\n"
    )

# ---------------- PLAN ----------------
class Plan:
    def __init__(self,padrao,sugestao):
        self.padrao=padrao
        self.sugestao=sugestao
        self.gale=0
        self.completed=False

def announce_plan(padrao,sugestao):
    return tg_send(f"{ANALYSE_TEXT}\n🎯 ESTRETEGIA: {padrao}\n👉 ENTRADA: {signal_text(sugestao)}")

def post_result_and_stats(game_id,plan,extra,outcome):
    gale = plan.gale
    sug = plan.sugestao
    padrao = plan.padrao
    ps = extra.get("player_score", "?")
    bs = extra.get("banker_score", "?")
    if outcome=="win" or outcome=="tie":
        texto = f"🤑 WIN DO CLEVER BOT\nResultado: 🔵 {ps} | 🔴 {bs}\nGale usado: {gale}"
        if outcome=="tie":
            texto = f"🟠 WIN NO EMPATE\nResultado: 🔵 {ps} | 🔴 {bs}\nGale usado: {gale}"
    else:
        texto = f"❌ LOSS\nResultado: 🔵 {ps} | 🔴 {bs}\nGale usado: {gale}"
    tg_send(texto)
    append_event(outcome,padrao,sug,gale,game_id,extra)
    msg_placar = tg_send(montar_painel_text())
    schedule_delete(msg_placar, delay=DELETE_ANALYSIS_AFTER)

def settle_plan(plan,hist,extra):
    global GALE_MSG_IDS
    if not plan or plan.completed: return
    last = hist[-1] if hist else None
    sug = plan.sugestao
    if last==sug or last=="T":
        post_result_and_stats(None,plan,extra,"win" if last==sug else "tie")
        for mid in GALE_MSG_IDS: tg_delete(mid)
        GALE_MSG_IDS=[]
        plan.completed=True
    else:
        if plan.gale==0:
            plan.gale=1
            mid = tg_send(gale_text(plan.gale, sug))
            GALE_MSG_IDS.append(mid)
        elif plan.gale==1:
            plan.gale=2

mid = tg_send(gale_text(plan.gale, sug))
            GALE_MSG_IDS.append(mid)
        else:
            post_result_and_stats(None,plan,extra,"loss")
            for mid in GALE_MSG_IDS: tg_delete(mid)
            GALE_MSG_IDS=[]
            plan.completed=True

# ---------------- MAIN LOOP ----------------
def main_loop():
    global HISTORY, ACTIVE_PLAN, LAST_GAME_ID
    load_events()
    log("Iniciando CLEVER BOT...")
    while True:
        try:
            data=fetch_api()
            if not data:
                time.sleep(POLL_INTERVAL)
                continue
            game_id,label,valid,extra=parse_latest_from_api(data)
            if not valid or not label:
                time.sleep(POLL_INTERVAL)
                continue
            if game_id==LAST_GAME_ID:
                time.sleep(POLL_INTERVAL)
                continue
            LAST_GAME_ID=game_id
            HISTORY.append(label)
            if ACTIVE_PLAN and not ACTIVE_PLAN.completed:
                settle_plan(ACTIVE_PLAN,HISTORY,extra)
            if not ACTIVE_PLAN or ACTIVE_PLAN.completed:
                sinais=gerar_todas_estrategias(HISTORY,extra)
                if sinais:
                    padrao,sugestao=sinais[0]
                    ACTIVE_PLAN=Plan(padrao,sugestao)
                    announce_plan(padrao,sugestao)
            time.sleep(POLL_INTERVAL)
        except Exception as e:
            log(f"Erro no loop principal: {e}")
            log(traceback.format_exc())
            time.sleep(POLL_INTERVAL)

if __name__=="__main__":
    main_loop()
        
    
