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

# Configuração de logging
logging.basicConfig(level=logging.DEBUG, format="%(asctime)s - %(levelname)s - %(message)s")

# Histórico e estado
historico = []
ultimo_padrao_id = None
ultimo_resultado_id = None  # Inicialização explícita
placar = {"✅": 0, "❌": 0}
sinal_ativo = None  # Armazena o último sinal enviado e seu ID

# Mapeamento de outcomes para emojis
OUTCOME_MAP = {
    "PlayerWon": "🔵",
    "BankerWon": "🔴",
    "Tie": "🟡"
}

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
    """Busca o resultado mais recente da API e retorna o emoji mapeado e os dados brutos."""
    async with aiohttp.ClientSession() as session:
        try:
            async with session.get(API_URL, timeout=10) as response:
                if response.status != 200:
                    logging.error(f"Erro na API: Status {response.status}, Resposta: {await response.text()}")
                    return None, None, None, None
                data = await response.json()
                logging.debug(f"Resposta da API: {data}")
                
                if 'data' not in data or 'result' not in data['data'] or 'outcome' not in data['data']['result']:
                    logging.error(f"Estrutura inválida na resposta: {data}")
                    return None, None, None, None
                if 'id' not in data:
                    logging.error(f"Chave 'id' não encontrada na resposta: {data}")
                    return None, None, None, None
                
                if data['data'].get('status') != 'Resolved':
                    logging.debug(f"Jogo não resolvido: Status {data['data'].get('status')}")
                    return None, None, None, None
                
                resultado_id = data['id']
                outcome = data['data']['result']['outcome']
                player_score = data['data']['result']['playerDice']['score']
                banker_score = data['data']['result']['bankerDice']['score']
                
                if outcome not in OUTCOME_MAP:
                    logging.error(f"Outcome inválido: {outcome}")
                    return None, None, None, None
                resultado = OUTCOME_MAP[outcome]
                
                return resultado, resultado_id, player_score, banker_score
        except aiohttp.ClientError as e:
            logging.error(f"Erro de conexão com a API: {e}")
            return None, None, None, None
        except ValueError as e:
            logging.error(f"Erro ao parsear JSON: {e}")
            return None, None, None, None
        except Exception as e:
            logging.error(f"Erro inesperado ao buscar resultado: {e}")
            return None, None, None, None

async def enviar_sinal(sinal, padrao_id):
    """Envia uma mensagem de sinal ao Telegram."""
    global sinal_ativo
    try:
        mensagem = f"""🎯 SINAL ENCONTRADO
Padrão ID: {padrao_id}
Entrar: {sinal}
⏳ Aposte agora!"""
        await bot.send_message(chat_id=CHAT_ID, text=mensagem)
        logging.info(f"Sinal enviado: Padrão {padrao_id}, Sinal: {sinal}, Tempo: {asyncio.get_event_loop().time()}")
        sinal_ativo = {"sinal": sinal, "padrao_id": padrao_id, "enviado_em": asyncio.get_event_loop().time()}
    except TelegramError as e:
        logging.error(f"Erro ao enviar sinal: {e}")

async def enviar_resultado(sinal, resultado, player_score, banker_score):
    """Envia a validação do resultado ao Telegram com a nova lógica."""
    global placar
    try:
        resultado_texto = f"🎲 Resultado: "
        if resultado == "🟡":
            resultado_texto += f"EMPATE: {player_score}:{banker_score}"
        else:
            resultado_texto += f"AZUL: {player_score} VS VERMELHO: {banker_score}"

        if resultado == sinal:
            resultado_sinal = "✅ ENTROU DINHEIRO🤑🤌"
            placar["✅"] += 1
        else:
            resultado_sinal = "❌ NÃO FOI DESSA🤧"
            placar["✅"] = 0  # Zera o placar de acertos em caso de erro

        msg = f"{resultado_texto}\n📊 Resultado do sinal: {resultado_sinal}\nPlacar: {placar['✅']}✅"
        await bot.send_message(chat_id=CHAT_ID, text=msg)
        logging.info(f"Resultado enviado: Sinal {sinal}, Resultado {resultado}, Player {player_score}, Banker {banker_score}, Resultado {resultado_sinal}")
    except TelegramError as e:
        logging.error(f"Erro ao enviar resultado: {e}")

async def enviar_relatorio():
    """Envia um relatório periódico da taxa de acertos."""
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

async def enviar_placar():
    """Envia o placar atual de acertos."""
    try:
        msg = f"Placar: {placar['✅']}✅"
        await bot.send_message(chat_id=CHAT_ID, text=msg)
        logging.info(f"Placar enviado: {placar['✅']}✅")
    except TelegramError as e:
        logging.error(f"Erro ao enviar placar: {e}")

async def monitorar_resultado(sinal, padrao_id):
    """Monitora a API em tempo real para validar o resultado após enviar o sinal."""
    global ultimo_resultado_id, sinal_ativo
    max_wait_time = 60  # Timeout máximo de 60 segundos
    start_time = asyncio.get_event_loop().time()
    
    while asyncio.get_event_loop().time() - start_time < max_wait_time:
        resultado, resultado_id, player_score, banker_score = await fetch_resultado()
        if resultado and resultado_id and (ultimo_resultado_id is None or resultado_id != ultimo_resultado_id):
            logging.debug(f"Monitorando: Novo resultado detectado - ID: {resultado_id}, Último ID: {ultimo_resultado_id}")
            ultimo_resultado_id = resultado_id
            await enviar_resultado(sinal, resultado, player_score, banker_score)
            sinal_ativo = None  # Limpa o sinal ativo após validação
            break
        elif not resultado and resultado_id:
            logging.warning(f"Monitorando: Resultado inválido ou incompleto - ID: {resultado_id}")
        await asyncio.sleep(2)  # Frequência de 2 segundos para tempo real
    if sinal_ativo:
        logging.error(f"Timeout de {max_wait_time}s atingido. Sinal {sinal} não validado.")
        sinal_ativo = None

async def main():
    """Loop principal do bot."""
    global historico, ultimo_padrao_id, ultimo_resultado_id, sinal_ativo
    asyncio.create_task(enviar_relatorio())  # Iniciar relatório periódico

    while True:
        resultado, resultado_id, player_score, banker_score = await fetch_resultado()
        if not resultado or not resultado_id:
            await asyncio.sleep(2)  # Frequência de 2 segundos
            continue

        if ultimo_resultado_id is None or resultado_id != ultimo_resultado_id:
            historico.append(resultado)
            historico = historico[-10:]  # Limita histórico a 10
            ultimo_resultado_id = resultado_id
            logging.info(f"Histórico atualizado: {historico} (ID: {resultado_id})")

            # Ordenar padrões por tamanho (maior primeiro)
            padroes_ordenados = sorted(PADROES, key=lambda x: len(x["sequencia"]), reverse=True)
            for padrao in padroes_ordenados:
                seq = padrao["sequencia"]
                if len(historico) >= len(seq) and historico[-len(seq):] == seq and padrao["id"] != ultimo_padrao_id:
                    await enviar_placar()  # Envia o placar antes do sinal
                    sinal = padrao["sinal"]
                    await enviar_sinal(sinal, padrao["id"])
                    ultimo_padrao_id = padrao["id"]
                    asyncio.create_task(monitorar_resultado(sinal, padrao["id"]))  # Inicia monitoramento assíncrono
                    break

        # Resetar ultimo_padrao_id após 5 resultados
        if len(historico) >= 5:
            ultimo_padrao_id = None

        await asyncio.sleep(2)  # Frequência de 2 segundos

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logging.info("Bot encerrado pelo usuário")
    except Exception as e:
        logging.error(f"Erro fatal no bot: {e}")
