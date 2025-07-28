import asyncio
import aiohttp
import logging
import os
from telegram import Bot
from telegram.error import TelegramError
from tenacity import retry, stop_after_attempt, wait_exponential

# Configurações do Bot
BOT_TOKEN = os.getenv("BOT_TOKEN", "7703975421:AAG-CG5Who2xs4NlevJqB5TNvjjzeUEDz8o")
CHAT_ID = os.getenv("CHAT_ID", "-1002859771274")
API_URL = "https://api.casinoscores.com/svc-evolution-game-events/api/bacbo/latest"

# Inicializar o bot
bot = Bot(token=BOT_TOKEN)

# Setup de logging
logging.basicConfig(level=logging.DEBUG, format="%(asctime)s - %(levelname)s - %(message)s")

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

@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=4, max=10))
async def fetch_resultado():
    async with aiohttp.ClientSession() as session:
        try:
            async with session.get(API_URL, timeout=10) as response:
                # Verificar status da resposta
                if response.status != 200:
                    logging.error(f"Erro na API: Status {response.status}, Resposta: {await response.text()}")
                    return None
                
                # Obter e logar a resposta JSON
                data = await response.json()
                logging.debug(f"Resposta da API: {data}")
                
                # Verificar se a chave 'result' existe
                if 'result' not in data:
                    logging.error(f"Chave 'result' não encontrada na resposta: {data}")
                    return None
                
                # Verificar se a chave 'outcome' existe
                if 'outcome' not in data['result']:
                    logging.error(f"Chave 'outcome' não encontrada em 'result': {data['result']}")
                    return None
                
                resultado = data['result']['outcome']
                
                # Validar resultado
                if resultado not in ["🔴", "🔵", "🟡"]:
                    logging.error(f"Resultado inválido: {resultado}")
                    return None
                
                return resultado
        except aiohttp.ClientError as e:
            logging.error(f"Erro de conexão com a API: {e}")
            return None
        except ValueError as e:
            logging.error(f"Erro ao parsear JSON: {e}")
            return None
        except Exception as e:
            logging.error(f"Erro inesperado ao buscar resultado: {e}")
            return None

async def enviar_sinal(sinal, padrao_id):
    try:
        mensagem = f"""🎯 SINAL ENCONTRADO
Padrão ID: {padrao_id}
Entrar: {sinal}
⏳ Aposte agora!"""
        await bot.send_message(chat_id=CHAT_ID, text=mensagem)
        logging.info(f"Sinal enviado: Padrão {padrao_id}, Sinal: {sinal}")
    except TelegramError as e:
        logging.error(f"Erro ao enviar sinal: {e}")

async def enviar_resultado(sinal, real):
    try:
        resultado = "✅" if sinal == real else "❌"
        placar[resultado] += 1
        msg = f"""🎲 Resultado: {real}
📊 Resultado do sinal: {resultado}
Placar: {placar['✅']}✅ | {placar['❌']}❌"""
        await bot.send_message(chat_id=CHAT_ID, text=msg)
        logging.info(f"Resultado enviado: Sinal {sinal}, Real {real}, Resultado {resultado}")
    except TelegramError as e:
        logging.error(f"Erro ao enviar resultado: {e}")

async def enviar_relatorio():
    while True:
        try:
            total = placar["✅"] + placar["❌"]
            taxa_acerto = (placar["✅"] / total * 100) if total > 0 else 0
            msg = f"📈 Relatório: {taxa_acerto:.2f}% de acertos ({placar['✅']}✅ | {placar['❌']}❌)"
            await bot.send_message(chat_id=CHAT_ID, text=msg)
            logging.info(f"Relatório enviado: {msg}")
        except TelegramError as e:
            logging.error(f"Erro ao enviar relatório: {e}")
        await asyncio.sleep(3600)  # Enviar a cada hora

async def main():
    global historico, ultimo_padrao_id
    asyncio.create_task(enviar_relatorio())  # Iniciar relatório periódico
    last_result_id = None  # Para evitar resultados duplicados

    while True:
        resultado = await fetch_resultado()
        if not resultado:
            await asyncio.sleep(5)
            continue

        # Evitar duplicatas usando o próprio resultado
        if not historico or historico[-1] != resultado:
            historico.append(resultado)
            historico = historico[-10:]  # Limita histórico a 10
            logging.info(f"Histórico atualizado: {historico}")

            # Ordenar padrões por tamanho (maior primeiro) para priorizar padrões mais longos
            padroes_ordenados = sorted(PADROES, key=lambda x: len(x["sequencia"]), reverse=True)
            for padrao in padroes_ordenados:
                seq = padrao["sequencia"]
                if len(historico) >= len(seq) and historico[-len(seq):] == seq and padrao["id"] != ultimo_padrao_id:
                    sinal = padrao["sinal"]
                    await enviar_sinal(sinal, padrao["id"])
                    ultimo_padrao_id = padrao["id"]

                    await asyncio.sleep(18)  # Tempo para o próximo resultado
                    novo_resultado = await fetch_resultado()
                    if novo_resultado:
                        await enviar_resultado(sinal, novo_resultado)
                    break

        # Resetar ultimo_padrao_id após 5 resultados para permitir repetição de padrões relevantes
        if len(historico) >= 5:
            ultimo_padrao_id = None

        await asyncio.sleep(5)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logging.info("Bot encerrado pelo usuário")
    except Exception as e:
        logging.error(f"Erro fatal no bot: {e}")
