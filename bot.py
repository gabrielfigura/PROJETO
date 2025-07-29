import asyncio
import aiohttp
import logging
import os
from telegram import Bot
from telegram.error import TelegramError
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
from collections import Counter, deque

# Configurações do Bot
BOT_TOKEN = os.getenv("BOT_TOKEN", "7703975421:AAG-CG5Who2xs4NlevJqB5TNvjjzeUEDz8o")
CHAT_ID = os.getenv("CHAT_ID", "-1002859771274")
API_URL = "https://api.casinoscores.com/svc-evolution-game-events/api/bacbo/latest"

# Inicializar o bot
bot = Bot(token=BOT_TOKEN)

# Configuração de logging
logging.basicConfig(level=logging.DEBUG, format="%(asctime)s - %(levelname)s - %(message)s")

# Histórico e estado
historico = deque(maxlen=100)  # Histórico de até 100 resultados para análise
ultimo_resultado_id = None
sinais_ativos = []
placar = {"✅": 0}
rodadas_desde_erro = 0
ultima_mensagem_monitoramento = None
detecao_pausada = False
sinal_em_processo = False  # Flag para controlar a espera pela validação

# Mapeamento de outcomes para emojis
OUTCOME_MAP = {
    "PlayerWon": "🔵",
    "BankerWon": "🔴",
    "Tie": "🟡"
}

# Padrões fixos como fallback
PADROES_FIXOS = [
    {"id": 10, "sequencia": ["🔵", "🔴"], "sinal": "🔵"},
    {"id": 11, "sequencia": ["🔴", "🔵"], "sinal": "🔴"},
    {"id": 13, "sequencia": ["🔵", "🔵", "🔵", "🔴", "🔴", "🔵", "🔵"], "sinal": "🔴"},
    {"id": 14, "sequencia": ["🔴", "🔴", "🔴", "🔵", "🔵", "🔴", "🔴"], "sinal": "🔵"},
    {"id": 15, "sequencia": ["🔴", "🔴", "🟡"], "sinal": "🔴"},
    {"id": 16, "sequencia": ["🔵", "🔵", "🟡"], "sinal": "🔵"},
    {"id": 17, "sequencia": ["🔴", "🔴", "🔵", "🔵", "🔴"], "sinal": "🔴"},
    {"id": 18, "sequencia": ["🔵", "🔵", "🔴", "🔴", "🔵"], "sinal": "🔵"},
    {"id": 19, "sequencia": ["🔴", "🔵", "🔴", "🔴"], "sinal": "🔵"},
    {"id": 20, "sequencia": ["🔵", "🔴", "🔵", "🔵"], "sinal": "🔴"},
    {"id": 21, "sequencia": ["🔵", "🔵", "🔵", "🔴", "🔵", "🔵"], "sinal": "🔵"},
    {"id": 22, "sequencia": ["🔴", "🔴", "🔴", "🔵", "🔴", "🔴"], "sinal": "🔴"},
    {"id": 23, "sequencia": ["🔵", "🔵", "🔴", "🔵", "🔵"], "sinal": "🔴"},
    {"id": 24, "sequencia": ["🔴", "🔴", "🔵", "🔴", "🔴"], "sinal": "🔵"},
    {"id": 25, "sequencia": ["🔵", "🔵", "🔵", "🔵"], "sinal": "🔵"},
    {"id": 26, "sequencia": ["🔴", "🔴", "🔴", "🔴"], "sinal": "🔴"},
    {"id": 31, "sequencia": ["🔴", "🔴", "🔴"], "sinal": "🔵"},
    {"id": 34, "sequencia": ["🔵", "🔵", "🔵"], "sinal": "🔴"},
    {"id": 35, "sequencia": ["🔴", "🔴", "🟡"], "sinal": "🔴"},
    {"id": 36, "sequencia": ["🔵", "🔵", "🟡"], "sinal": "🔵"},
    {"id": 39, "sequencia": ["🔴", "🟡", "🔴", "🔵"], "sinal": "🔵"},
    {"id": 40, "sequencia": ["🔵", "🟡", "🔵", "🔴"], "sinal": "🔴"},
    {"id": 41, "sequencia": ["🔴", "🔵", "🟡", "🔴"], "sinal": "🔴"},
    {"id": 42, "sequencia": ["🔵", "🔴", "🟡", "🔵"], "sinal": "🔵"},
    {"id": 43, "sequencia": ["🔴", "🔴", "🔵", "🟡"], "sinal": "🔴"},
    {"id": 44, "sequencia": ["🔵", "🔵", "🔴", "🟡"], "sinal": "🔵"},
    {"id": 45, "sequencia": ["🔵", "🟡", "🟡"], "sinal": "🔵"},
    {"id": 46, "sequencia": ["🔴", "🟡", "🟡"], "sinal": "🔴"},
    {"id": 1, "sequencia": ["🔵", "🔴", "🔵", "🔴"], "sinal": "🔵"},
    {"id": 2, "sequencia": ["🔴", "🔴", "🔴", "🔴", "🔴"], "sinal": "🔴"},
    {"id": 3, "sequencia": ["🔵", "🔵", "🔵", "🔵", "🔵"], "sinal": "🔵"},
    {"id": 4, "sequencia": ["🔴", "🔴", "🔵", "🔵"], "sinal": "🔴"},
    {"id": 5, "sequencia": ["🔴", "🔵", "🔴", "🔵"], "sinal": "🔴"},
    {"id": 6, "sequencia": ["🔴", "🔴", "🔴", "🔴", "🔵"], "sinal": "🔵"},
    {"id": 7, "sequencia": ["🔵", "🔵", "🔵", "🔵", "🔴"], "sinal": "🔴"},
    {"id": 8, "sequencia": ["🔴", "🔵", "🔴", "🔵", "🔴"], "sinal": "🔵"},
    {"id": 9, "sequencia": ["🔵", "🔴", "🔵", "🔴", "🔵"], "sinal": "🔴"},
    {"id": 249, "sequencia": ["🔴", "🔵", "🔵", "🔴"], "sinal": "🔴"},
    {"id": 150, "sequencia": ["🔵", "🔴", "🔴", "🔵"], "sinal": "🔵"},
    {"id": 420, "sequencia": ["🔴", "🟡", "🔴"], "sinal": "🔴"},
    {"id": 424, "sequencia": ["🔵", "🟡", "🔵"], "sinal": "🔵"},
    {"id": 525, "sequencia": ["🔴", "🔴", "🔴", "🔵"], "sinal": "🔵"},
    {"id": 526, "sequencia": ["🔵", "🔵", "🔵", "🔴"], "sinal": "🔴"}
]

def calcular_probabilidade(historico, sinal, janela=8):
    """Calcula a probabilidade de um sinal com base na tendência dos últimos resultados."""
    if len(historico) < janela:
        return 0.0
    janela = list(historico)[-janela:]
    contagem = Counter(janela)
    total = contagem["🔴"] + contagem["🔵"]
    if total == 0:
        return 0.0
    proporcao = contagem[sinal] / total if sinal in contagem else 0
    if janela[-1] == "🟡" and sinal in janela[-2:]:
        proporcao += 0.1
    return min(proporcao, 1.0)

def detectar_padroes(historico):
    """Detecta padrões dinâmicos ou usa padrões fixos sem limites."""
    padroes = []
    for tamanho in range(2, 8):
        if len(historico) >= tamanho:
            sequencia = list(historico)[-tamanho:]
            sinal = sequencia[-1] if sequencia[-1] in ["🔴", "🔵"] else None
            if sinal:
                prob = calcular_probabilidade(historico, sinal, tamanho + 2)
                if prob > 0.65:
                    padroes.append({"id": hash(str(sequencia)), "sequencia": sequencia, "sinal": sinal, "prob": prob})
    if len(historico) >= 2:
        for padrao in PADROES_FIXOS:
            if len(historico) >= len(padrao["sequencia"]) and list(historico)[-len(padrao["sequencia"]):] == padrao["sequencia"]:
                padroes.append({"id": padrao["id"], "sequencia": padrao["sequencia"], "sinal": padrao["sinal"], "prob": 0.5})
    return padroes

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
    """Envia uma mensagem de sinal ao Telegram sem Padrão ID."""
    global ultima_mensagem_monitoramento, sinal_em_processo
    try:
        if ultima_mensagem_monitoramento:
            try:
                await bot.delete_message(chat_id=CHAT_ID, message_id=ultima_mensagem_monitoramento)
                logging.debug("Mensagem de monitoramento apagada antes de enviar sinal")
            except TelegramError as e:
                logging.debug(f"Erro ao apagar mensagem de monitoramento: {e}")
            ultima_mensagem_monitoramento = None

        sequencia_str = " ".join(sequencia)
        mensagem = f"""🎯 SINAL ENCONTRADO
Sequência: {sequencia_str}
Entrar: {sinal}
Proteger o empate🟡
⏳ Aposte agora!"""
        message = await bot.send_message(chat_id=CHAT_ID, text=mensagem)
        logging.info(f"Sinal enviado: Sequência: {sequencia_str}, Sinal: {sinal}, Resultado ID: {resultado_id}")
        sinais_ativos.append({
            "sinal": sinal,
            "padrao_id": padrao_id,
            "resultado_id": resultado_id,
            "sequencia": sequencia,
            "enviado_em": asyncio.get_event_loop().time(),
            "gale_nivel": 0,
            "gale_message_id": None
        })
        sinal_em_processo = True  # Marca que um sinal está em processo
        return message.message_id
    except TelegramError as e:
        logging.error(f"Erro ao enviar sinal: {e}")
        raise

@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10), retry=retry_if_exception_type(TelegramError))
async def enviar_resultado(resultado, player_score, banker_score, resultado_id):
    """Envia a validação de cada sinal ao Telegram, apagando a mensagem de gale após validação."""
    global rodadas_desde_erro, ultima_mensagem_monitoramento, detecao_pausada, sinal_em_processo
    try:
        for sinal_ativo in sinais_ativos[:]:
            if sinal_ativo["resultado_id"] != resultado_id:
                resultado_texto = f"🎲 Resultado: "
                if resultado == "🟡":
                    resultado_texto += f"EMPATE: {player_score}:{banker_score}"
                else:
                    resultado_texto += f"AZUL: {player_score} VS VERMELHO: {banker_score}"

                sequencia_str = " ".join(sinal_ativo["sequencia"])
                if resultado == sinal_ativo["sinal"] or resultado == "🟡":
                    placar["✅"] += 1
                    mensagem_validacao = f"🤑ENTROU DINHEIRO🤑\n{resultado_texto}\n📊 Resultado do sinal (Sequência: {sequencia_str})\nPlacar: {placar['✅']}✅"
                    await bot.send_message(chat_id=CHAT_ID, text=mensagem_validacao)
                    if sinal_ativo["gale_message_id"]:
                        try:
                            await bot.delete_message(chat_id=CHAT_ID, message_id=sinal_ativo["gale_message_id"])
                            logging.debug(f"Mensagem de gale apagada após validação: ID {sinal_ativo['gale_message_id']}")
                        except TelegramError as e:
                            logging.debug(f"Erro ao apagar mensagem de gale: {e}")
                    logging.info(f"Validação enviada: Sinal {sinal_ativo['sinal']}, Resultado {resultado}, Resultado ID: {resultado_id}, Validação: {mensagem_validacao}")
                    sinais_ativos.remove(sinal_ativo)
                else:
                    if sinal_ativo["gale_nivel"] == 0:
                        detecao_pausada = True
                        mensagem_gale = "BORA GANHAR NO 1 GALE🎯"
                        message = await bot.send_message(chat_id=CHAT_ID, text=mensagem_gale)
                        sinal_ativo["gale_nivel"] = 1
                        sinal_ativo["gale_message_id"] = message.message_id
                        sinal_ativo["resultado_id"] = resultado_id
                        logging.info(f"Mensagem de gale enviada: {mensagem_gale}, ID: {message.message_id}")
                    else:
                        if resultado == sinal_ativo["sinal"] or resultado == "🟡":
                            placar["✅"] += 1
                            mensagem_validacao = f"🤑ENTROU DINHEIRO🤑\n{resultado_texto}\n📊 Resultado do sinal (Sequência: {sequencia_str})\nPlacar: {placar['✅']}✅"
                            await bot.send_message(chat_id=CHAT_ID, text=mensagem_validacao)
                            if sinal_ativo["gale_message_id"]:
                                try:
                                    await bot.delete_message(chat_id=CHAT_ID, message_id=sinal_ativo["gale_message_id"])
                                    logging.debug(f"Mensagem de gale apagada após validação: ID {sinal_ativo['gale_message_id']}")
                                except TelegramError as e:
                                    logging.debug(f"Erro ao apagar mensagem de gale: {e}")
                            logging.info(f"Validação enviada (1 Gale): Sinal {sinal_ativo['sinal']}, Resultado {resultado}, Resultado ID: {resultado_id}, Validação: {mensagem_validacao}")
                            sinais_ativos.remove(sinal_ativo)
                            detecao_pausada = False
                        else:
                            await bot.send_message(chat_id=CHAT_ID, text="NÃO FOI DESSA🤧")
                            if sinal_ativo["gale_message_id"]:
                                try:
                                    await bot.delete_message(chat_id=CHAT_ID, message_id=sinal_ativo["gale_message_id"])
                                    logging.debug(f"Mensagem de gale apagada após validação: ID {sinal_ativo['gale_message_id']}")
                                except TelegramError as e:
                                    logging.debug(f"Erro ao apagar mensagem de gale: {e}")
                            logging.info(f"Validação enviada (Erro 1 Gale): Sinal {sinal_ativo['sinal']}, Resultado {resultado}, Resultado ID: {resultado_id}")
                            sinais_ativos.remove(sinal_ativo)
                            detecao_pausada = False
                sinal_em_processo = False  # Libera a detecção após validação

                ultima_mensagem_monitoramento = None
            elif asyncio.get_event_loop().time() - sinal_ativo["enviado_em"] > 300:
                logging.warning(f"Sinal obsoleto removido: Sequência {sinal_ativo['sequencia']}, Resultado ID: {sinal_ativo['resultado_id']}")
                if sinal_ativo["gale_message_id"]:
                    try:
                        await bot.delete_message(chat_id=CHAT_ID, message_id=sinal_ativo["gale_message_id"])
                        logging.debug(f"Mensagem de gale obsoleta apagada: ID {sinal_ativo['gale_message_id']}")
                    except TelegramError as e:
                        logging.debug(f"Erro ao apagar mensagem de gale obsoleta: {e}")
                sinais_ativos.remove(sinal_ativo)
                detecao_pausada = False
                sinal_em_processo = False  # Libera a detecção se o sinal expirar
    except TelegramError as e:
        logging.error(f"Erro ao enviar resultado: {e}")

@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10), retry=retry_if_exception_type(TelegramError))
async def enviar_monitoramento():
    """Envia mensagem de monitoramento a cada 15 segundos, apagando a anterior."""
    global ultima_mensagem_monitoramento
    while True:
        try:
            if not sinais_ativos:
                if ultima_mensagem_monitoramento:
                    try:
                        await bot.delete_message(chat_id=CHAT_ID, message_id=ultima_mensagem_monitoramento)
                        logging.debug("Mensagem de monitoramento anterior apagada")
                    except TelegramError as e:
                        logging.debug(f"Erro ao apagar mensagem de monitoramento: {e}")
                message = await bot.send_message(chat_id=CHAT_ID, text="MONITORANDO A MESA…🤌")
                ultima_mensagem_monitoramento = message.message_id
                logging.debug(f"Mensagem de monitoramento enviada: ID {ultima_mensagem_monitoramento}")
            else:
                logging.debug("Monitoramento pausado: Sinal ativo pendente")
        except TelegramError as e:
            logging.error(f"Erro ao enviar monitoramento: {e}")
        await asyncio.sleep(15)

@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10), retry=retry_if_exception_type(TelegramError))
async def enviar_relatorio():
    """Envia um relatório periódico com o placar."""
    while True:
        try:
            msg = f"📈 Relatório: Bot em operação\nPlacar: {placar['✅']}✅"
            await bot.send_message(chat_id=CHAT_ID, text=msg)
            logging.info(f"Relatório enviado: {msg}")
        except TelegramError as e:
            logging.error(f"Erro ao enviar relatório: {e}")
        await asyncio.sleep(3600)

async def main():
    """Loop principal do bot com reconexão."""
    global historico, ultimo_resultado_id, rodadas_desde_erro, detecao_pausada, sinal_em_processo
    asyncio.create_task(enviar_relatorio())
    asyncio.create_task(enviar_monitoramento())

    while True:
        try:
            resultado, resultado_id, player_score, banker_score = await fetch_resultado()
            if not resultado or not resultado_id:
                await asyncio.sleep(2)
                continue

            if ultimo_resultado_id is None or resultado_id != ultimo_resultado_id:
                ultimo_resultado_id = resultado_id
                historico.append(resultado)
                logging.info(f"Histórico atualizado: {list(historico)} (ID: {resultado_id})")

                rodadas_desde_erro += 1
                await enviar_resultado(resultado, player_score, banker_score, resultado_id)

                if not detecao_pausada and len(historico) >= 2 and not sinal_em_processo:
                    padroes = detectar_padroes(historico)
                    for padrao in padroes:
                        await enviar_sinal(sinal=padrao["sinal"], padrao_id=padrao["id"], resultado_id=resultado_id, sequencia=padrao["sequencia"])

            else:
                logging.debug(f"Resultado repetido ignorado: ID {resultado_id}")

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
