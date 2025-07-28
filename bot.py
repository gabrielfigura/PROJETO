import asyncio
import aiohttp
import logging
import os
from telegram import Bot
from telegram.error import TelegramError
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

# Configurações do Bot
BOT_TOKEN = os.getenv("BOT_TOKEN",  "7703975421:AAG-CG5Who2xs4NlevJqB5TNvjjzeUEDz8o")
CHAT_ID = os.getenv("CHAT_ID", "-1002859771274")
API_URL = "https://api.casinoscores.com/svc-evolution-game-events/api/bacbo/latest"

# Inicializar o bot
bot = Bot(token=BOT_TOKEN)

# Configuração de logging
logging.basicConfig(level=logging.DEBUG, format="%(asctime)s - %(levelname)s - %(message)s")

# Histórico e estado
historico = []
ultimo_padrao_id = None
ultimo_resultado_id = None
sinais_ativos = []

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

@retry(stop=stop_after_attempt(5), wait=wait_exponential(multiplier=1, min=4, max=30), retry=retry_if_exception_type((aiohttp.ClientError, asyncio.TimeoutError)))
async def fetch_resultado():
    """Busca o resultado mais recente da API com retry e timeout aumentado."""
    async with aiohttp.ClientSession() as session:
        try:
            async with session.get(API_URL, timeout=aiohttp.ClientTimeout(total=15)) as response:
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
                player_score = data['data']['result'].get('playerDice', {}).get('score', 0)
                banker_score = data['data']['result'].get('bankerDice', {}).get('score', 0)
                
                if outcome not in OUTCOME_MAP:
                    logging.error(f"Outcome inválido: {outcome}")
                    return None, None, None, None
                resultado = OUTCOME_MAP[outcome]
                
                return resultado, resultado_id, player_score, banker_score
        except (aiohttp.ClientError, asyncio.TimeoutError) as e:
            logging.error(f"Erro de conexão com a API: {e}")
            return None, None, None, None
        except ValueError as e:
            logging.error(f"Erro ao parsear JSON: {e}")
            return None, None, None, None
        except Exception as e:
            logging.error(f"Erro inesperado ao buscar resultado: {e}")
            return None, None, None, None

@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10), retry=retry_if_exception_type(TelegramError))
async def enviar_sinal(sinal, padrao_id, resultado_id, sequencia):
    """Envia uma mensagem de sinal ao Telegram com retry, incluindo a sequência de cores."""
    try:
        sequencia_str = " ".join(sequencia)
        mensagem = f"""🎯 SINAL ENCONTRADO
Padrão ID: {padrao_id}
Sequência: {sequencia_str}
Entrar: {sinal}
⏳ Aposte agora!"""
        await bot.send_message(chat_id=CHAT_ID, text=mensagem)
        logging.info(f"Sinal enviado: Padrão {padrao_id}, Sequência: {sequencia_str}, Sinal: {sinal}, Resultado ID: {resultado_id}, Tempo: {asyncio.get_event_loop().time()}")
        sinais_ativos.append({"sinal": sinal, "padrao_id": padrao_id, "resultado_id": resultado_id, "sequencia": sequencia, "enviado_em": asyncio.get_event_loop().time()})
    except TelegramError as e:
        logging.error(f"Erro ao enviar sinal: {e}")
        raise

async def enviar_resultado(resultado, player_score, banker_score, resultado_id):
    """Envia a validação de cada sinal ao Telegram após o resultado da mesma rodada."""
    try:
        for sinal_ativo in sinais_ativos[:]:
            if sinal_ativo["resultado_id"] == resultado_id:
                resultado_texto = f"🎲 Resultado: "
                if resultado == "🟡":
                    resultado_texto += f"EMPATE: {player_score}:{banker_score}"
                else:
                    resultado_texto += f"AZUL: {player_score} VS VERMELHO: {banker_score}"

                sequencia_str = " ".join(sinal_ativo["sequencia"])
                if resultado == sinal_ativo["sinal"]:
                    mensagem_validacao = "ENTROU DINHEIRO🤑"
                else:
                    mensagem_validacao = "NÃO FOI DESSA🤧"

                msg = f"{resultado_texto}\n📊 Resultado do sinal (Padrão {sinal_ativo['padrao_id']}, Sequência: {sequencia_str}): {mensagem_validacao}"
                await bot.send_message(chat_id=CHAT_ID, text=msg)
                logging.info(f"Validação enviada: Sinal {sinal_ativo['sinal']}, Resultado {resultado}, Resultado ID: {resultado_id}, Validação: {mensagem_validacao}")
                sinais_ativos.remove(sinal_ativo)
                break
    except TelegramError as e:
        logging.error(f"Erro ao enviar resultado: {e}")

async def enviar_relatorio():
    """Envia um relatório periódico."""
    while True:
        try:
            msg = "📈 Relatório: Bot em operação"
            await bot.send_message(chat_id=CHAT_ID, text=msg)
            logging.info(f"Relatório enviado: {msg}")
        except TelegramError as e:
            logging.error(f"Erro ao enviar relatório: {e}")
        await asyncio.sleep(3600)

async def monitorar_resultado():
    """Monitora a API em tempo real para validar sinais ativos."""
    global ultimo_resultado_id
    while True:
        try:
            resultado, resultado_id, player_score, banker_score = await fetch_resultado()
            if resultado and resultado_id:
                if ultimo_resultado_id is None or resultado_id != ultimo_resultado_id:
                    ultimo_resultado_id = resultado_id
                    logging.info(f"Novo resultado detectado: ID {resultado_id}, Resultado {resultado}, Player {player_score}, Banker {banker_score}, Sinais ativos: {len(sinais_ativos)}")
                    await enviar_resultado(resultado, player_score, banker_score, resultado_id)
                else:
                    logging.debug(f"Resultado repetido: ID {resultado_id}")
            elif not resultado and resultado_id:
                logging.warning(f"Resultado inválido ou incompleto: ID {resultado_id}")
            await asyncio.sleep(2)
        except Exception as e:
            logging.error(f"Erro no monitoramento: {e}")
            await asyncio.sleep(5)

async def main():
    """Loop principal do bot com reconexão."""
    global historico, ultimo_padrao_id, ultimo_resultado_id
    asyncio.create_task(enviar_relatorio())

    # Variável para controlar sinais pendentes para validação de gale
    sinal_pendente = None
    gale_ativo = False
    gale_1_resultado_id = None

    while True:
        try:
            resultado, resultado_id, player_score, banker_score = await fetch_resultado()
            if not resultado or not resultado_id:
                await asyncio.sleep(2)
                continue

            historico.append(resultado)
            historico = historico[-25:]  # Mantém os últimos 25 resultados

            # Detecta padrão e envia sinal
            if ultimo_resultado_id is None or resultado_id != ultimo_resultado_id:
                ultimo_resultado_id = resultado_id
                logging.info(f"Histórico atualizado: {historico} (ID: {resultado_id})")

                padroes_ordenados = sorted(PADROES, key=lambda x: len(x["sequencia"]), reverse=True)
                for padrao in padroes_ordenados:
                    seq = padrao["sequencia"]
                    if len(historico) >= len(seq) and historico[-len(seq):] == seq and padrao["id"] != ultimo_padrao_id:
                        sinal = padrao["sinal"]
                        # Sinal detectado, prepara para validar próximos 2 resultados
                        sinal_pendente = {
                            "sinal": sinal,
                            "padrao_id": padrao["id"],
                            "sequencia": seq,
                            "resultado_id": resultado_id,
                            "gale": 0,
                            "gale_1_resultado_id": None
                        }
                        await enviar_sinal(sinal, padrao["id"], resultado_id, seq)
                        ultimo_padrao_id = padrao["id"]
                        gale_ativo = False
                        break

                if len(historico) >= 5:
                    ultimo_padrao_id = None

            # Validação do sinal e gale
            if sinal_pendente:
                # Verifica se já validou o sinal (gale 0)
                idx_seq = historico.index(sinal_pendente["sequencia"][-1]) if sinal_pendente["sequencia"][-1] in historico else -1
                # O resultado imediatamente após a sequência
                idx_sinal = len(historico) - 1
                idx_gale_1 = len(historico) - 2
                # Só valida se o resultado atual for após a sequência
                if idx_seq >= 0 and idx_seq < len(historico) - 1:
                    # Gale 0: resultado imediatamente após a sequência
                    resultado_apos_seq = historico[idx_seq + 1]
                    if resultado_apos_seq == sinal_pendente["sinal"]:
                        # Green sem gale
                        sequencia_str = " ".join(sinal_pendente["sequencia"])
                        msg = f"ENTROU DINHEIRO🤑\nPadrão ID: {sinal_pendente['padrao_id']}\nSequência: {sequencia_str}\nSinal: {sinal_pendente['sinal']}"
                        await bot.send_message(chat_id=CHAT_ID, text=msg)
                        sinal_pendente = None
                        gale_ativo = False
                    elif idx_seq + 2 < len(historico):
                        # Gale 1: resultado seguinte
                        resultado_gale_1 = historico[idx_seq + 2]
                        if not gale_ativo:
                            # Ativa gale 1
                            gale_ativo = True
                            msg_gale = "⚠️ Calma lá, vamos ao Gale 1!"
                            await bot.send_message(chat_id=CHAT_ID, text=msg_gale)
                        if resultado_gale_1 == sinal_pendente["sinal"]:
                            sequencia_str = " ".join(sinal_pendente["sequencia"])
                            msg = f"ENTROU DINHEIRO🤑\nPadrão ID: {sinal_pendente['padrao_id']}\nSequência: {sequencia_str}\nSinal: {sinal_pendente['sinal']} (Gale 1)"
                            await bot.send_message(chat_id=CHAT_ID, text=msg)
                            sinal_pendente = None
                            gale_ativo = False
                        else:
                            # Red após gale 1
                            sequencia_str = " ".join(sinal_pendente["sequencia"])
                            msg = f"NÃO FOI DESSA🤧\nPadrão ID: {sinal_pendente['padrao_id']}\nSequência: {sequencia_str}\nSinal: {sinal_pendente['sinal']}"
                            await bot.send_message(chat_id=CHAT_ID, text=msg)
                            sinal_pendente = None
                            gale_ativo = False

            await asyncio.sleep(2)
        except Exception as e:
            logging.error(f"Erro no loop principal: {e}")
            await asyncio.sleep(10)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logging.info("Bot encerrado pelo usuário")
    except Exception as e:
        logging.error(f"Erro fatal no bot: {e}")
