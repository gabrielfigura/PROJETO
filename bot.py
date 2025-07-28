import asyncio
import aiohttp
import logging
import os
from telegram import Bot
from telegram.error import TelegramError
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

# Configurações do Bot
BOT_TOKEN = os.getenv("BOT_TOKEN", "7703975421:AAG-CG5Who2xs4NlevJqB5TNvjjzeUEDz8o")
CHAT_ID = os.getenv("CHAT_ID", "-1002859771274")
API_URL = "https://api.casinoscores.com/svc-evolution-game-events/api/bacbo/latest"

# Inicializar o bot
bot = Bot(token=BOT_TOKEN)

# Logging
logging.basicConfig(level=logging.DEBUG, format="%(asctime)s - %(levelname)s - %(message)s")

# Estado
historico = []
ultimo_padrao_id = None
ultimo_resultado_id = None
placar = {"✅": 0, "❌": 0}
sinais_ativos = []

OUTCOME_MAP = {
    "PlayerWon": "🔵",
    "BankerWon": "🔴",
    "Tie": "🟡"
}

# Padrões (resumido para caber, use seus padrões completos)
PADROES = [
    {"id": 1, "sequencia": ["🔴", "🔴", "🔴"], "sinal": "🔴"},
    {"id": 2, "sequencia": ["🔵", "🔵", "🔵"], "sinal": "🔵"},
     {"id": 3, "sequencia": ["🔴", "🔴", "🔵"], "sinal": "🔵"},
    {"id": 4, "sequencia": ["🔵", "🔵", "🔴", "🔴"], "sinal": "🔵"},
    {"id": 5, "sequencia": ["🔴", "🔴", "🔴", "🔵"], "sinal": "🔵"},
    {"id": 6, "sequencia": ["🔵", "🔵", "🔵"], "sinal": "🔵"},
    {"id": 7, "sequencia": ["🔴", "🔵", "🔴"], "sinal": "🔵"},
    {"id": 8, "sequencia": ["🔴", "🔵", "🔵"], "sinal": "🔵"},
    {"id": 9, "sequencia": ["🔴", "🔴", "🟡"], "sinal": "🔴"},
    {"id": 10, "sequencia": ["🔴", "🔵", "🟡", "🔴"], "sinal": "🔴"},
    {"id": 11, "sequencia": ["🔵", "🔴", "🔴"], "sinal": "🔴"},
    {"id": 12, "sequencia": ["🔴", "🔵", "🔵"], "sinal": "🔵"},
    {"id": 13, "sequencia": ["🔵", "🔵", "🔴", "🔵"], "sinal": "🔵"},
    {"id": 14, "sequencia": ["🔴", "🟡", "🔴"], "sinal": "🔴"},
    {"id": 15, "sequencia": ["🔴", "🔴", "🔴", "🔴"], "sinal": "🔴"},
    {"id": 16, "sequencia": ["🔵", "🔵", "🔵", "🔴"], "sinal": "🔵"},
    {"id": 17, "sequencia": ["🔴", "🔵", "🔴", "🔵"], "sinal": "🔴"},
    {"id": 18, "sequencia": ["🔴", "🔵", "🔵", "🔴"], "sinal": "🔴"},
    {"id": 19, "sequencia": ["🔵", "🟡", "🔵"], "sinal": "🔵"},
    {"id": 20, "sequencia": ["🔴", "🔵", "🟡", "🔵", "🔵"], "sinal": "🔵"},
    {"id": 21, "sequencia": ["🔵", "🔵", "🔴", "🔴", "🔵"], "sinal": "🔵"},
    {"id": 22, "sequencia": ["🔴", "🔴", "🔵", "🔴"], "sinal": "🔴"},
    {"id": 23, "sequencia": ["🔵", "🔴", "🔵", "🔴", "🔴"], "sinal": "🔴"},
    {"id": 24, "sequencia": ["🔴", "🔵", "🔴", "🔴"], "sinal": "🔴"},
    {"id": 25, "sequencia": ["🔴", "🔴", "🔴", "🟡", "🔴"], "sinal": "🔴"},
    {"id": 26, "sequencia": ["🔵", "🔴", "🔴", "🔵", "🔵"], "sinal": "🔵"},
    {"id": 27, "sequencia": ["🔴", "🟡", "🔵"], "sinal": "🔵"},
    {"id": 28, "sequencia": ["🔵", "🔵", "🟡", "🔵", "🔵"], "sinal": "🔵"},
    {"id": 29, "sequencia": ["🔴", "🔴", "🔵", "🔵", "🔴"], "sinal": "🔴"},
    {"id": 30, "sequencia": ["🔵", "🔵", "🔴", "🔵", "🔵"], "sinal": "🔵"},
    {"id": 31, "sequencia": ["🔴", "🔴", "🔴", "🔴", "🔴"], "sinal": "🔴"},
    {"id": 32, "sequencia": ["🔵", "🔴", "🔵", "🔴", "🔵"], "sinal": "🔴"},
    {"id": 33, "sequencia": ["🔴", "🔵", "🔴", "🟡", "🔵"], "sinal": "🔵"},
    {"id": 34, "sequencia": ["🔵", "🔵", "🔴", "🔴", "🔴"], "sinal": "🔴"},
    {"id": 35, "sequencia": ["🔴", "🟡", "🔴", "🔵"], "sinal": "🔵"},
    {"id": 36, "sequencia": ["🔴", "🔴", "🟡", "🔵", "🔵"], "sinal": "🔵"},
    {"id": 37, "sequencia": ["🔵", "🔴", "🟡", "🔵", "🔴"], "sinal": "🔴"},
    {"id": 38, "sequencia": ["🔴", "🔴", "🔴", "🔵", "🔴", "🔴"], "sinal": "🔴"},
    {"id": 39, "sequencia": ["🔵", "🔵", "🔵", "🔴", "🔵"], "sinal": "🔵"},
    {"id": 40, "sequencia": ["🔴", "🔴", "🔴", "🟡", "🔵", "🔵"], "sinal": "🔵"},
    {"id": 41, "sequencia": ["🔴", "🔵", "🔴", "🔴", "🔵"], "sinal": "🔵"},
    {"id": 42, "sequencia": ["🔵", "🔴", "🔴", "🔵", "🔵", "🔴", "🔴"], "sinal": "🔴"},
    {"id": 43, "sequencia": ["🔴", "🔴", "🔵", "🔵", "🔴", "🔴"], "sinal": "🔴"},
    {"id": 44, "sequencia": ["🔵", "🔴", "🔴", "🔴", "🔵"], "sinal": "🔴"},
    {"id": 45, "sequencia": ["🔴", "🔵", "🟡", "🔴", "🔴"], "sinal": "🔴"},
    {"id": 46, "sequencia": ["🔴", "🔴", "🔵", "🔵", "🔴", "🔴", "🔵", "🔵"], "sinal": "🔵"},
    {"id": 47, "sequencia": ["🔵", "🔵", "🔵", "🔴", "🔴", "🔴", "🔵"], "sinal": "🔵"},
    {"id": 48, "sequencia": ["🔴", "🔴", "🔴", "🔵", "🔴", "🔴"], "sinal": "🔴"},
    {"id": 49, "sequencia": ["🔵", "🔴", "🔴", "🔵", "🔵", "🔴", "🔴"], "sinal": "🔴"},
    {"id": 50, "sequencia": ["🔴", "🔴", "🟡", "🔵", "🔵", "🔴"], "sinal": "🔴"},
]

@retry(stop=stop_after_attempt(5), wait=wait_exponential(multiplier=1, min=4, max=30), retry=retry_if_exception_type((aiohttp.ClientError, asyncio.TimeoutError)))
async def fetch_resultado():
    async with aiohttp.ClientSession() as session:
        try:
            async with session.get(API_URL, timeout=aiohttp.ClientTimeout(total=15)) as response:
                if response.status != 200:
                    logging.error(f"Erro na API: {response.status}")
                    return None, None, None, None
                data = await response.json()
                if 'data' not in data or 'result' not in data['data']:
                    return None, None, None, None
                if data['data'].get('status') != 'Resolved':
                    return None, None, None, None

                resultado_id = data['id']
                outcome = data['data']['result']['outcome']
                player_score = data['data']['result'].get('playerDice', {}).get('score', 0)
                banker_score = data['data']['result'].get('bankerDice', {}).get('score', 0)
                resultado = OUTCOME_MAP.get(outcome, None)

                return resultado, resultado_id, player_score, banker_score
        except Exception as e:
            logging.error(f"Erro ao buscar resultado: {e}")
            return None, None, None, None

@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10), retry=retry_if_exception_type(TelegramError))
async def enviar_sinal(sinal, padrao_id, resultado_id):
    try:
        mensagem = f"""🎯 SINAL ENCONTRADO
Padrão ID: {padrao_id}
Entrar: {sinal}
⏳ Aposte agora!"""
        await bot.send_message(chat_id=CHAT_ID, text=mensagem)
        sinais_ativos.append({
            "sinal": sinal,
            "padrao_id": padrao_id,
            "resultado_id": resultado_id,
            "enviado_em": asyncio.get_event_loop().time()
        })
    except TelegramError as e:
        logging.error(f"Erro ao enviar sinal: {e}")
        raise

async def enviar_resultado(sinal, resultado, player_score, banker_score, resultado_id):
    """Valida o sinal com o resultado e envia mensagem no Telegram."""
    global placar

    try:
        if resultado == "🟡" or resultado == sinal:
            resultado_sinal = "✅ ENTROU DINHEIRO🤑🤌"
            placar["✅"] += 1
        else:
            resultado_sinal = "❌ NÃO FOI DESSA🤧"
            placar["✅"] = 0

        if resultado == "🟡":
            resultado_texto = f"🎲 Resultado: EMPATE 🟡 ({player_score}:{banker_score})"
        else:
            resultado_texto = f"🎲 Resultado: AZUL 🔵 {player_score} VS VERMELHO 🔴 {banker_score}"

        msg = f"""{resultado_texto}
📊 Resultado do sinal: {resultado_sinal}
Placar: {placar['✅']}✅"""
        
        await bot.send_message(chat_id=CHAT_ID, text=msg)
        logging.info(f"[VALIDAÇÃO] Resultado enviado | Sinal: {sinal}, Resultado: {resultado}, Resultado ID: {resultado_id}")
    
    except TelegramError as e:
        logging.error(f"Erro ao enviar resultado: {e}")

async def enviar_placar():
    try:
        await bot.send_message(chat_id=CHAT_ID, text=f"Placar: {placar['✅']}✅")
    except TelegramError as e:
        logging.error(f"Erro ao enviar placar: {e}")

async def monitorar_resultado():
    global ultimo_resultado_id
    while True:
        try:
            resultado, resultado_id, player_score, banker_score = await fetch_resultado()
            if resultado and resultado_id and resultado_id != ultimo_resultado_id:
                ultimo_resultado_id = resultado_id
                for sinal_ativo in sinais_ativos[:]:
                    if sinal_ativo["resultado_id"] == resultado_id:
                        await enviar_resultado(sinal_ativo["sinal"], resultado, player_score, banker_score, resultado_id)
                        sinais_ativos.remove(sinal_ativo)
                        break
                    elif asyncio.get_event_loop().time() - sinal_ativo["enviado_em"] > 120:
                        sinais_ativos.remove(sinal_ativo)
            await asyncio.sleep(2)
        except Exception as e:
            logging.error(f"Erro no monitoramento: {e}")
            await asyncio.sleep(5)

async def main():
    global historico, ultimo_padrao_id, ultimo_resultado_id
    asyncio.create_task(monitorar_resultado())

    while True:
        try:
            resultado, resultado_id, player_score, banker_score = await fetch_resultado()
            if not resultado or not resultado_id:
                await asyncio.sleep(2)
                continue

            if ultimo_resultado_id is None or resultado_id != ultimo_resultado_id:
                historico.append(resultado)
                historico = historico[-10:]
                ultimo_resultado_id = resultado_id

                padroes_ordenados = sorted(PADROES, key=lambda x: len(x["sequencia"]), reverse=True)
                for padrao in padroes_ordenados:
                    seq = padrao["sequencia"]
                    if len(historico) >= len(seq) and historico[-len(seq):] == seq and padrao["id"] != ultimo_padrao_id:
                        await enviar_placar()
                        await enviar_sinal(padrao["sinal"], padrao["id"], resultado_id)
                        ultimo_padrao_id = padrao["id"]
                        break

                if len(historico) >= 5:
                    ultimo_padrao_id = None

            await asyncio.sleep(2)
        except Exception as e:
            logging.error(f"Erro no loop principal: {e}")
            await asyncio.sleep(10)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("Bot encerrado manualmente.")
