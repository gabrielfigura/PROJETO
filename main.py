import os
import asyncio
import logging
from typing import List, Optional, Dict, Any
from datetime import datetime
import pytz

import aiohttp
from telegram import Bot
from telegram.error import TelegramError
from dotenv import load_dotenv

load_dotenv()

# Configurações
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "8308362105:AAELmmAUIcTgbJ3xozM1mhsLPk-8EqOSOgY")
TELEGRAM_CHANNEL_ID = os.getenv("TELEGRAM_CHANNEL_ID", "-1003278747270")  # MUDE SE NECESSÁRIO

API_URL = "https://api-cs.casino.org/svc-evolution-game-events/api/bacbo/latest"

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
    'Accept': 'application/json',
    'Accept-Language': 'en-US,en;q=0.9',
}

ANGOLA_TZ = pytz.timezone('Africa/Luanda')

OUTCOME_MAP = {
    "PlayerWon": "🔵",
    "BankerWon": "🔴",
    "Tie": "🟡",
    "🔵": "🔵",
    "🔴": "🔴",
    "🟡": "🟡",
}

# 50 padrões mais comentados/populares (baseado em relatos recentes 2024-2025)
PADROES = [
    {"id": 26, "sequencia": ["🔴", "🔵", "🔴", "🔵", "🔴"], "sinal": "🔴"},
  {"id": 209, "sequencia": ["🔵", "🔴", "🔵", "🔴", "🔵"], "sinal": "🔵"},
  {"id": 308, "sequencia": ["🔵", "🔴", "🔴", "🔴", "🔵", "🔵", "🔴"], "sinal": "🔵"},
  {"id": 103, "sequencia": ["🔴", "🔵", "🔵", "🔵", "🔴", "🔴", "🔵"], "sinal": "🔴"},
  {"id": 107, "sequencia": ["🔵", "🔴", "🔴", "🔴", "🔵", "🔵", "🔴"], "sinal": "🔵"},
  {"id": 506, "sequencia": ["🔴", "🔵", "🔴", "🔴", "🔴", "🔴", "🔴", "🔵", "🔵", "🔵", "🔴", "🔴"], "sinal": "🔵"},
{"id": 54, "sequencia": ["🔵", "🔴", "🔵", "🔵", "🔵", "🔵", "🔵", "🔴", "🔴", "🔴", "🔵", "🔵"], "sinal": "🔴"},
{"id": 780, "sequencia": ["🔴", "🔵", "🔴", "🔵", "🔵", "🔴", "🔴", "🔴"], "sinal": "🔵"},
{"id": 378, "sequencia": ["🔵", "🔴", "🔵", "🔴", "🔴", "🔵", "🔵", "🔵"], "sinal": "🔴"},
{"id": 270, "sequencia": ["🔴", "🔵", "🔴", "🔴", "🔴", "🔴"], "sinal": "🔵"},
{"id": 341, "sequencia": ["🔵", "🔴", "🔵", "🔵", "🔵", "🔵"], "sinal": "🔴"},
{"id": 708, "sequencia": ["🔴", "🔵", "🔴", "🔵", "🔵", "🔴", "🔴", "🔵"], "sinal": "🔵"},
{"id": 43, "sequencia": ["🔵", "🔴", "🔵", "🔴", "🔴", "🔵", "🔵", "🔴"], "sinal": "🔴"},
{"id": 444, "sequencia": ["🔴", "🔵", "🔴", "🔵", "🔵", "🔴", "🔴", "🔵", "🔵"], "sinal": "🔴"},
{"id": 123, "sequencia": ["🔵", "🔴", "🔵", "🔴", "🔴", "🔵", "🔵", "🔴", "🔴"], "sinal": "🔵"},
{"id": 237, "sequencia": ["🔵", "🔴", "🔵", "🔴", "🔴", "🔵", "🔴", "🔴", "🔵"], "sinal": "🔴"},
{"id": 870, "sequencia": ["🔴", "🔵", "🔴", "🔵", "🔵", "🔴", "🔵", "🔵", "🔴"], "sinal": "🔵"},
{"id": 654, "sequencia": ["🔵", "🔴", "🔵", "🔵", "🔵", "🔵", "🔴", "🔴", "🔴", "🔴"], "sinal": "🔵"},
{"id": 555, "sequencia": ["🔴", "🔵", "🔴", "🔴", "🔴", "🔴", "🔵", "🔵", "🔵", "🔵"], "sinal": "🔴"},
{"id": 64, "sequencia": ["🔵", "🔴", "🔵", "🔵", "🔴", "🔴", "🔴", "🔵", "🔵"], "sinal": "🔴"},
{"id": 56, "sequencia": ["🔴", "🔵", "🔴", "🔴", "🔵", "🔵", "🔵", "🔴", "🔴"], "sinal": "🔵"},
{"id": 77, "sequencia": ["🔴", "🔵", "🔴", "🔴", "🔴", "🔴", "🔴", "🔵"], "sinal": "🔴"},
{"id": 88, "sequencia": ["🔵", "🔴", "🔵", "🔵", "🔵", "🔵", "🔵", "🔴"], "sinal": "🔵"},
{"id": 763, "sequencia": ["🔴", "🔴", "🔵", "🔵", "🔵", "🔴", "🔴"], "sinal": "🔵"},
{"id": 390, "sequencia": ["🔵", "🔵", "🔴", "🔴", "🔴", "🔵", "🔵"], "sinal": "🔴"}
]

API_POLL_INTERVAL = 3
SIGNAL_CYCLE_INTERVAL = 5
ANALISE_REFRESH_INTERVAL = 15

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)-5s | %(message)s'
)
logger = logging.getLogger("BacBoBot")

bot = Bot(token=TELEGRAM_BOT_TOKEN)

state: Dict[str, Any] = {
    "history": [],
    "last_round_id": None,
    "waiting_for_result": False,
    "last_signal_color": None,
    "martingale_count": 0,
    "entrada_message_id": None,
    "martingale_message_ids": [],  # Lista com IDs das mensagens GALE 1 e GALE 2
    "greens_seguidos": 0,
    "total_greens": 0,
    "total_empates": 0,
    "total_losses": 0,
    "last_signal_pattern_id": None,
    "last_signal_sequence": None,
    "last_signal_round_id": None,
    "signal_cooldown": False,
    "analise_message_id": None,
    "last_reset_date": None,
    "last_analise_refresh": 0.0,
    "last_result_round_id": None,
}

async def send_to_channel(text: str, parse_mode="HTML") -> Optional[int]:
    try:
        msg = await bot.send_message(
            chat_id=TELEGRAM_CHANNEL_ID,
            text=text,
            parse_mode=parse_mode,
            disable_web_page_preview=True
        )
        return msg.message_id
    except TelegramError as te:
        logger.error(f"Telegram Error: {te}")
        return None
    except Exception as e:
        logger.exception("Erro ao enviar mensagem")
        return None

async def send_error_to_channel(error_msg: str):
    timestamp = datetime.now(ANGOLA_TZ).strftime("%Y-%m-%d %H:%M:%S")
    text = f"⚠️ <b>ERRO DETECTADO</b> ⚠️\n<code>{timestamp}</code>\n\n{error_msg}"
    await send_to_channel(text)

async def delete_messages(message_ids: List[int]):
    if not message_ids:
        return
    for mid in message_ids[:]:
        try:
            await bot.delete_message(TELEGRAM_CHANNEL_ID, mid)
        except:
            pass

def should_reset_placar() -> bool:
    now = datetime.now(ANGOLA_TZ)
    current_date = now.date()
    if state["last_reset_date"] is None or state["last_reset_date"] != current_date:
        state["last_reset_date"] = current_date
        return True
    if state["total_losses"] >= 10:
        return True
    return False

def reset_placar_if_needed():
    if should_reset_placar():
        state["total_greens"] = 0
        state["total_empates"] = 0
        state["total_losses"] = 0
        state["greens_seguidos"] = 0
        logger.info("🔄 Placar resetado (diário ou por 10 losses)")

def calcular_acertividade() -> str:
    total_decisoes = state["total_greens"] + state["total_losses"]
    if total_decisoes == 0:
        return "—"
    perc = (state["total_greens"] / total_decisoes) * 100
    return f"{perc:.1f}%"

def format_placar() -> str:
    acert = calcular_acertividade()
    return (
        "🏆 <b>DEERY_PLACAR</b> 🏆\n"
        f"✅ GREENS: <b>{state['total_greens']}</b>\n"
        f"🤝 EMPATES: {state['total_empates']}\n"
        f"⛔ LOSS: <b>{state['total_losses']}</b>\n"
        f"🎯 ACERTIVIDADE: <b>{acert}</b>"
    )

def format_analise_text() -> str:
    return (
        "🎲 <b>ANALISANDO...</b> 🎲\n\n"
        "<i>Aguarde o próximo sinal</i>"
    )

async def refresh_analise_message():
    now = datetime.now().timestamp()
    if (now - state["last_analise_refresh"]) < ANALISE_REFRESH_INTERVAL:
        return

    await delete_analise_message()
    msg_id = await send_to_channel(format_analise_text())
    if msg_id:
        state["analise_message_id"] = msg_id
        state["last_analise_refresh"] = now

async def delete_analise_message():
    if state["analise_message_id"] is not None:
        await delete_messages([state["analise_message_id"]])
        state["analise_message_id"] = None

async def fetch_api(session: aiohttp.ClientSession) -> Optional[Dict]:
    try:
        async with session.get(API_URL, headers=HEADERS, timeout=12) as resp:
            if resp.status != 200:
                await send_error_to_channel(f"API retornou status {resp.status}")
                return None
            return await resp.json()
    except Exception as e:
        await send_error_to_channel(f"Erro na API: {str(e)}")
        return None

async def update_history_from_api(session):
    reset_placar_if_needed()
    data = await fetch_api(session)
    if not data:
        return
    try:
        if "data" in data:
            data = data["data"]
        round_id = data.get("id")
        outcome_raw = (data.get("result") or {}).get("outcome")
        if not round_id or not outcome_raw:
            return
        outcome = OUTCOME_MAP.get(outcome_raw)
        if not outcome:
            s = str(outcome_raw).lower()
            if "player" in s: outcome = "🔵"
            elif "banker" in s: outcome = "🔴"
            elif any(x in s for x in ["tie", "empate", "draw"]): outcome = "🟡"
        if outcome and state["last_round_id"] != round_id:
            state["last_round_id"] = round_id
            state["history"].append(outcome)
            if len(state["history"]) > 200:
                state["history"].pop(0)
            logger.info(f"Novo resultado → {outcome} | round {round_id}")
            state["signal_cooldown"] = False
    except Exception as e:
        await send_error_to_channel(f"Erro processando API: {str(e)}")

def history_ends_with(history: List[str], seq: List[str]) -> bool:
    n = len(seq)
    return len(history) >= n and history[-n:] == seq

def find_matching_pattern(history: List[str]) -> Optional[Dict]:
    for pat in PADROES:
        if history_ends_with(history, pat["sequencia"]):
            return pat
    return None

def main_entry_text(color: str) -> str:
    cor_nome = "AZUL" if color == "🔵" else "VERMELHO"
    emoji = color
    return (
        f"🎲 <b>ENTRADA DO DEERY</b> 🎲\n"
        f"🧠 APOSTA EM: <b>{emoji} {cor_nome}</b>\n"
        f"🛡️ Proteja o TIE <b>🟡</b>\n"
        f"<b>FAZER ATÉ 2 GALE</b>\n"
        f"🤑 <b>VAI ENTRAR DINHEIRO</b> 🤑"
    )

def green_text(greens: int) -> str:
    return (
        f"✅ <b>ACERTAMOS</b> ✅\n"
        f"🎲 <b>MAIS FOCO E MENOS GANÂNCIA</b> 🎲"
    )

async def send_gale_warning(level: int):
    if level not in (1, 2):
        return
    text = f"🔄 <b>GALE {level}</b> 🔄\nContinuar na mesma cor!"
    msg_id = await send_to_channel(text)
    if msg_id:
        state["martingale_message_ids"].append(msg_id)

async def clear_gale_messages():
    await delete_messages(state["martingale_message_ids"])
    state["martingale_message_ids"] = []

async def resolve_after_result():
    if not state.get("waiting_for_result", False) or not state.get("last_signal_color"):
        return

    if state["last_result_round_id"] == state["last_round_id"]:
        return

    if not state["history"]:
        return

    last_outcome = state["history"][-1]

    if state["last_signal_round_id"] == state["last_round_id"]:
        return

    state["last_result_round_id"] = state["last_round_id"]
    target = state["last_signal_color"]

    placar_text = format_placar()

    # Empate ou Green → green / empate
    if last_outcome in ("🟡", target):
        if last_outcome == "🟡":
            state["total_empates"] += 1
            state["greens_seguidos"] = 0  # Empate não conta como green seguido
        else:
            state["greens_seguidos"] += 1
            state["total_greens"] += 1

        await send_to_channel(green_text(state["greens_seguidos"]))
        await send_to_channel(placar_text)

        await clear_gale_messages()

        state.update({
            "waiting_for_result": False,
            "last_signal_color": None,
            "martingale_count": 0,
            "entrada_message_id": None,
            "last_signal_pattern_id": None,
            "last_signal_sequence": None,
            "last_signal_round_id": None,
            "signal_cooldown": True
        })
        return

    # Perdeu a entrada/gale atual
    state["martingale_count"] += 1

    if state["martingale_count"] == 1:
        await send_gale_warning(1)
    elif state["martingale_count"] == 2:
        await send_gale_warning(2)

    if state["martingale_count"] >= 3:  # Perdeu os 2 gales → loss final
        state["greens_seguidos"] = 0
        state["total_losses"] += 1
        await send_to_channel("🟥 <b>LOSS 🟥</b>")
        await send_to_channel(placar_text)

        await clear_gale_messages()

        state.update({
            "waiting_for_result": False,
            "last_signal_color": None,
            "martingale_count": 0,
            "entrada_message_id": None,
            "last_signal_pattern_id": None,
            "last_signal_sequence": None,
            "last_signal_round_id": None,
            "signal_cooldown": True
        })

    reset_placar_if_needed()
    await refresh_analise_message()

async def try_send_signal():
    if state["waiting_for_result"]:
        await delete_analise_message()
        return

    if state["signal_cooldown"]:
        await refresh_analise_message()
        return

    if len(state["history"]) < 3:
        await refresh_analise_message()
        return

    pat = find_matching_pattern(state["history"])
    if not pat:
        await refresh_analise_message()
        return

    color = pat["sinal"]
    seq = state["history"][-len(pat["sequencia"]):]

    if (state["last_signal_pattern_id"] == pat["id"] and 
        state["last_signal_sequence"] == seq):
        await refresh_analise_message()
        return

    await delete_analise_message()
    state["martingale_message_ids"] = []

    msg_id = await send_to_channel(main_entry_text(color))
    if msg_id:
        state["entrada_message_id"] = msg_id
        state["waiting_for_result"] = True
        state["last_signal_color"] = color
        state["martingale_count"] = 0
        state["last_signal_pattern_id"] = pat["id"]
        state["last_signal_sequence"] = seq
        state["last_signal_round_id"] = state["last_round_id"]
        logger.info(f"Sinal enviado: {color}")

async def api_worker():
    async with aiohttp.ClientSession() as session:
        while True:
            try:
                await update_history_from_api(session)
                await resolve_after_result()
            except Exception as e:
                logger.exception("Erro no api_worker")
                await send_error_to_channel(f"Erro grave no loop da API:\n<code>{str(e)}</code>")
                await asyncio.sleep(10)
            await asyncio.sleep(API_POLL_INTERVAL)

async def scheduler_worker():
    await asyncio.sleep(3)
    while True:
        try:
            await refresh_analise_message()
            await try_send_signal()
        except Exception as e:
            logger.exception("Erro no scheduler")
            await send_error_to_channel(f"Erro no envio de sinais:\n<code>{str(e)}</code>")
        await asyncio.sleep(SIGNAL_CYCLE_INTERVAL)

async def main():
    logger.info("🤖 Bot iniciado...")
    await send_to_channel("🤖 Bot iniciado - procurando sinais...")
    await asyncio.gather(api_worker(), scheduler_worker())

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Bot parado pelo usuário")
    except Exception as e:
        logger.critical("Erro fatal", exc_info=True)
        try:
            asyncio.run(send_error_to_channel(f"ERRO FATAL: {str(e)}"))
        except:
            pass
