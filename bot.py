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

# Mapeamento de outcomes para emojis
OUTCOME_MAP = {
    "PlayerWon": "🔵",
    "BankerWon": "🔴",
    "Tie": "🟡"
}

def calcular_probabilidade(historico, sinal, janela=8):
    """Calcula a probabilidade de um sinal com base na tendência dos últimos resultados."""
    if len(historico) < janela:
        return 0.5  # Probabilidade neutra se histórico insuficiente
    janela = list(historico)[-janela:]
    contagem = Counter(janela)
    total = contagem["🔴"] + contagem["🔵"]  # Ignorar empates na contagem base
    if total == 0:
        return 0.5
    proporcao = contagem[sinal] / total if sinal in contagem else 0
    # Ajustar com base em empates como confirmadores (se 🟡 for recente, aumentar confiança)
    if janela[-1] == "🟡" and sinal in janela[-2:]:
        proporcao += 0.1  # Bônus de 10% se empate recente confirma tendência
    return min(proporcao, 1.0)  # Limitar a 100%

def detectar_padroes(historico):
    """Detecta os melhores padrões nos últimos 2 a 7 resultados com base em probabilidade."""
    padroes = []
    for tamanho in range(2, 8):  # Testa padrões de 2 a 7 resultados
        if len(historico) >= tamanho:
            sequencia = list(historico)[-tamanho:]
            sinal = sequencia[-1] if sequencia[-1] in ["🔴", "🔵"] else None
            if sinal:
                prob = calcular_probabilidade(historico, sinal, tamanho + 2)
                if prob > 0.6:  # Confiança mínima de 60%
                    padroes.append({"id": hash(str(sequencia)), "sequencia": sequencia, "sinal": sinal, "prob": prob})
    return sorted(padroes, key=lambda x: x["prob"], reverse=True)[:1]  # Retorna o padrão mais provável

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
    global ultima_mensagem_monitoramento
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
Padrão ID: {padrao_id}
Sequência: {sequencia_str}
Entrar: {sinal}
Proteger o empate🟡
⏳ Aposte agora!"""
        message = await bot.send_message(chat_id=CHAT_ID, text=mensagem)
        logging.info(f"Sinal enviado: Padrão {padrao_id}, Sequência: {sequencia_str}, Sinal: {sinal}, Resultado ID: {resultado_id}")
        sinais_ativos.append({
            "sinal": sinal,
            "padrao_id": padrao_id,
            "resultado_id": resultado_id,
            "sequencia": sequencia,
            "enviado_em": asyncio.get_event_loop().time(),
            "gale_nivel": 0,
            "gale_message_id": None
        })
        return message.message_id
    except TelegramError as e:
        logging.error(f"Erro ao enviar sinal: {e}")
        raise

@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10), retry=retry_if_exception_type(TelegramError))
async def enviar_resultado(resultado, player_score, banker_score, resultado_id):
    """Envia a validação de cada sinal ao Telegram após o resultado da próxima rodada."""
    global rodadas_desde_erro, ultima_mensagem_monitoramento, detecao_pausada
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
                    mensagem_validacao = f"🤑ENTROU DINHEIRO🤑\n{resultado_texto}\n📊 Resultado do sinal (Padrão {sinal_ativo['padrao_id']} Sequência: {sequencia_str})\nPlacar: {placar['✅']}✅"
                    await bot.send_message(chat_id=CHAT_ID, text=mensagem_validacao)
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
                            if sinal_ativo["gale_message_id"]:
                                try:
                                    await bot.delete_message(chat_id=CHAT_ID, message_id=sinal_ativo["gale_message_id"])
                                    logging.debug(f"Mensagem de gale apagada: ID {sinal_ativo['gale_message_id']}")
                                except TelegramError as e:
                                    logging.debug(f"Erro ao apagar mensagem de gale: {e}")
                            mensagem_validacao = f"🤑ENTROU DINHEIRO🤑\n{resultado_texto}\n📊 Resultado do sinal (Padrão {sinal_ativo['padrao_id']} Sequência: {sequencia_str})\nPlacar: {placar['✅']}✅"
                            await bot.send_message(chat_id=CHAT_ID, text=mensagem_validacao)
                            logging.info(f"Validação enviada (1 Gale): Sinal {sinal_ativo['sinal']}, Resultado {resultado}, Resultado ID: {resultado_id}, Validação: {mensagem_validacao}")
                            sinais_ativos.remove(sinal_ativo)
                            detecao_pausada = False
                        else:
                            if sinal_ativo["gale_message_id"]:
                                try:
                                    await bot.delete_message(chat_id=CHAT_ID, message_id=sinal_ativo["gale_message_id"])
                                    logging.debug(f"Mensagem de gale apagada: ID {sinal_ativo['gale_message_id']}")
                                except TelegramError as e:
                                    logging.debug(f"Erro ao apagar mensagem de gale: {e}")
                            await bot.send_message(chat_id=CHAT_ID, text="NÃO FOI DESSA🤧")
                            logging.info(f"Validação enviada (Erro 1 Gale): Sinal {sinal_ativo['sinal']}, Resultado {resultado}, Resultado ID: {resultado_id}")
                            sinais_ativos.remove(sinal_ativo)
                            detecao_pausada = False

                ultima_mensagem_monitoramento = None
            elif asyncio.get_event_loop().time() - sinal_ativo["enviado_em"] > 300:
                logging.warning(f"Sinal obsoleto removido: Padrão {sinal_ativo['padrao_id']}, Resultado ID: {sinal_ativo['resultado_id']}")
                if sinal_ativo["gale_message_id"]:
                    try:
                        await bot.delete_message(chat_id=CHAT_ID, message_id=sinal_ativo["gale_message_id"])
                        logging.debug(f"Mensagem de gale obsoleta apagada: ID {sinal_ativo['gale_message_id']}")
                    except TelegramError as e:
                        logging.debug(f"Erro ao apagar mensagem de gale obsoleta: {e}")
                sinais_ativos.remove(sinal_ativo)
                detecao_pausada = False
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
    global historico, ultimo_resultado_id, rodadas_desde_erro, detecao_pausada
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

                if not detecao_pausada and len(historico) >= 2:
                    padroes = detectar_padroes(historico)
                    for padrao in padroes:
                        await enviar_sinal(sinal=padrao["sinal"], padrao_id=padrao["id"], resultado_id=resultado_id, sequencia=padrao["sequencia"])
                        break  # Envia apenas o padrão mais provável

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
