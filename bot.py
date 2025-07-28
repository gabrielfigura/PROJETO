import asyncio
import aiohttp
import logging
from telegram import Bot
from telegram.error import TelegramError

# Configurações do Bot
BOT_TOKEN = "7703975421:AAG-CG5Who2xs4NlevJqB5TNvjjzeUEDz8o"
CHAT_ID = "-1002859771274"
API_URL = "https://api.casinoscores.com/svc-evolution-game-events/api/bacbo/latest"

# Inicializar o bot
bot = Bot(token=BOT_TOKEN)

# Setup de logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

# Histórico de resultados
historico = []
ultimo_padrao_id = None
placar = {"✅": 0, "❌": 0}

# Padrões
PADROES = [
    {"id": 1, "sequencia": ["🔴", "🔴", "🔴"], "sinal": "🔴"},
    {"id": 2, "sequencia": ["🔵", "🔴", "🔵"], "sinal": "🔴"},
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

async def fetch_resultado():
    async with aiohttp.ClientSession() as session:
        try:
            async with session.get(API_URL) as response:
                data = await response.json()
                return data['result']['outcome']
        except Exception as e:
            logging.error(f"Erro ao buscar resultado: {e}")
            return None

async def enviar_sinal(sinal):
    try:
        mensagem = f"🎯 SINAL ENCONTRADO
Entrar: {sinal}
⏳ Aposte agora!"
        await bot.send_message(chat_id=CHAT_ID, text=mensagem)
    except TelegramError as e:
        logging.error(f"Erro ao enviar sinal: {e}")

async def enviar_resultado(sinal, real):
    try:
        resultado = "✅" if sinal == real else "❌"
        placar[resultado] += 1
        msg = f"🎲 Resultado: {real}
📊 Resultado do sinal: {resultado}
Placar: {placar['✅']}✅ | {placar['❌']}❌"
        await bot.send_message(chat_id=CHAT_ID, text=msg)
    except TelegramError as e:
        logging.error(f"Erro ao enviar resultado: {e}")

async def main():
    global historico, ultimo_padrao_id
    while True:
        resultado = await fetch_resultado()
        if not resultado:
            await asyncio.sleep(5)
            continue

        if not historico or historico[-1] != resultado:
            historico.append(resultado)
            historico = historico[-10:]  # Limita histórico a 10

            for padrao in PADROES:
                seq = padrao["sequencia"]
                if historico[-len(seq):] == seq and padrao["id"] != ultimo_padrao_id:
                    sinal = padrao["sinal"]
                    await enviar_sinal(sinal)
                    ultimo_padrao_id = padrao["id"]

                    await asyncio.sleep(18)  # tempo para o próximo resultado
                    novo_resultado = await fetch_resultado()
                    await enviar_resultado(sinal, novo_resultado)
                    break

        await asyncio.sleep(5)

if __name__ == "__main__":
    asyncio.run(main())
