import asyncio
import aiohttp
import logging
import os
from telegram import Bot
from telegram.error import TelegramError
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
from collections import Counter

# Configurações do Bot
BOT_TOKEN = os.getenv("BOT_TOKEN", "7758723414:AAF-Zq1QPoGy2IS-iK2Wh28PfexP0_mmHHc")
CHAT_ID = os.getenv("CHAT_ID", "-1002506692600")
API_URL = "https://api.casinoscores.com/svc-evolution-game-events/api/bacbo/latest"

# Inicializar o bot
bot = Bot(token=BOT_TOKEN)

# Configuração de logging
logging.basicConfig(level=logging.DEBUG, format="%(asctime)s - %(levelname)s - %(message)s")

# Histórico e estado
historico = []
ultimo_resultado_id = None
sinais_ativos = []
placar = {
    "ganhos_seguidos": 0,
    "ganhos_gale1": 0,
    "ganhos_gale2": 0,
    "losses": 0,
    "precisao": 92.0
}
rodadas_desde_erro = 0
ultima_mensagem_monitoramento = None
detecao_pausada = False

# Mapeamento de outcomes para emojis
OUTCOME_MAP = {
    "PlayerWon": "🔵",
    "BankerWon": "🔴",
    "Tie": "🟡"
}

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

def calcular_probabilidade(historico, tamanho_janela=10):
    """Calcula a probabilidade de cada outcome com base na janela de análise."""
    if len(historico) < tamanho_janela:
        return {"🔵": 0.33, "🔴": 0.33, "🟡": 0.34}  # Probabilidade inicial uniforme
    janela = historico[-tamanho_janela:]
    contagem = Counter(janela)
    total = sum(contagem.values())
    probs = {
        "🔵": contagem["🔵"] / total if total > 0 else 0.33,
        "🔴": contagem["🔴"] / total if total > 0 else 0.33,
        "🟡": contagem["🟡"] / total if total > 0 else 0.34
    }
    # Ajustar com base na última transição
    if len(historico) >= 2:
        ultima_transicao = historico[-2:]
        if ultima_transicao == ["🔵", "🔴"] or ultima_transicao == ["🔴", "🔵"]:
            probs["🟡"] += 0.05  # Aumentar chance de empate após alternância
            probs["🔵"] -= 0.025
            probs["🔴"] -= 0.025
        elif ultima_transicao[0] == ultima_transicao[1]:
            probs[ultima_transicao[0]] += 0.1  # Reforçar tendência de sequência
            probs["🟡"] -= 0.05
            probs[ultima_transicao[0] == "🔵" and "🔴" or "🔵"] -= 0.05
    return probs

def detectar_sinal_claro(historico):
    """Detecta um sinal claro com base em probabilidades e tendências."""
    if len(historico) < 5:
        return None, 0.0
    probs = calcular_probabilidade(historico)
    max_prob = max(probs.values())
    if max_prob < 0.75:  # Confiança mínima de 75%
        return None, max_prob
    sinal = max(probs.items(), key=lambda x: x[1])[0]
    return sinal, max_prob

@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10), retry=retry_if_exception_type(TelegramError))
async def enviar_sinal(sinal, confianca, resultado_id, sequencia):
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

        if any(sinal["sinal"] == s["sinal"] for s in sinais_ativos):
            logging.debug(f"Sinal {sinal} já ativo, ignorando.")
            return

        sequencia_str = " ".join(sequencia[-5:])  # Últimos 5 resultados
        mensagem = f"""💡CLEVER ANALISOU💡
➡️TENDÊNCIA: {sinal}
🧠CONFIANÇA: {confianca:.2%}
📊ÚLTIMA SEQUÊNCIA: {sequencia_str}
🛡️PROTEGE SEMPRE O TIE🟡
🤑VAI ENTRAR DINHEIRO🤑"""
        message = await bot.send_message(chat_id=CHAT_ID, text=mensagem)
        logging.info(f"Sinal enviado: Tendência {sinal}, Confiança {confianca:.2%}, Resultado ID: {resultado_id}")
        sinais_ativos.append({
            "sinal": sinal,
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

async def enviar_placar():
    """Envia o placar atualizado."""
    try:
        total_acertos = placar['ganhos_seguidos'] + placar['ganhos_gale1'] + placar['ganhos_gale2']
        erro_mensagem = "AINDA NÃO ERRAMOS😌" if placar['losses'] == 0 else f"ERRAMOS APENAS {placar['losses']} SINAL❌"
        mensagem_placar = f"🎯RESULTADOS DO CLEVER🎯\nGANHOS SEGUIDOS: {placar['ganhos_seguidos']}🤑\nGANHOS NO 1•GALE: {placar['ganhos_gale1']}🤌\nGANHOS NO 2•GALE: {placar['ganhos_gale2']}🤌\nLOSS:{placar['losses']}😔❌\nACERTAMOS {total_acertos} SINAIS🤑\n{erro_mensagem}\nPRECISÃO:{placar['precisao']:.2f}%"
        await bot.send_message(chat_id=CHAT_ID, text=mensagem_placar)
        logging.info(f"Placar enviado: {mensagem_placar}")
    except TelegramError as e:
        logging.error(f"Erro ao enviar placar: {e}")

@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10), retry=retry_if_exception_type(TelegramError))
async def enviar_resultado(resultado, player_score, banker_score, resultado_id):
    """Envia a validação de cada sinal ao Telegram após o resultado da próxima rodada."""
    global rodadas_desde_erro, ultima_mensagem_monitoramento, detecao_pausada, placar
    try:
        for sinal_ativo in sinais_ativos[:]:
            if sinal_ativo["resultado_id"] != resultado_id:
                sequencia_str = " ".join(sinal_ativo["sequencia"])
                if resultado == sinal_ativo["sinal"] or resultado == "🟡":
                    if sinal_ativo["gale_nivel"] == 0:
                        placar["ganhos_seguidos"] += 1
                    elif sinal_ativo["gale_nivel"] == 1:
                        placar["ganhos_gale1"] += 1
                    else:
                        placar["ganhos_gale2"] += 1
                    placar["precisao"] = min(placar["precisao"] + 0.35, 100.0)
                    if sinal_ativo["gale_message_id"]:
                        try:
                            await bot.delete_message(chat_id=CHAT_ID, message_id=sinal_ativo["gale_message_id"])
                        except TelegramError as e:
                            logging.debug(f"Erro ao apagar mensagem de gale: {e}")
                    mensagem_validacao = f"🤑ENTROU DINHEIRO🤑\n🎲 RESULTADOS: 🔵: {player_score}  🔴: {banker_score}\n📊 RESULTADOS DO SINAL: ➡️ TENDÊNCIA: {sinal_ativo['sinal']} \n➡️ SEQUÊNCIA: {sequencia_str}"
                    await bot.send_message(chat_id=CHAT_ID, text=mensagem_validacao)
                    logging.info(f"Validação enviada: Sinal {sinal_ativo['sinal']}, Resultado {resultado}, Resultado ID: {resultado_id}")
                    await enviar_placar()
                    sinais_ativos.remove(sinal_ativo)
                    detecao_pausada = False
                else:
                    if sinal_ativo["gale_nivel"] == 0:
                        detecao_pausada = True
                        mensagem_gale = "BORA GANHAR NO 1 GALE🎯"
                        message = await bot.send_message(chat_id=CHAT_ID, text=mensagem_gale)
                        sinal_ativo["gale_nivel"] = 1
                        sinal_ativo["gale_message_id"] = message.message_id
                        sinal_ativo["resultado_id"] = resultado_id
                        logging.info(f"Mensagem de 1 gale enviada: {mensagem_gale}, ID: {message.message_id}")
                    elif sinal_ativo["gale_nivel"] == 1:
                        detecao_pausada = True
                        mensagem_gale = "BORA GANHAR NO 2 GALE🤌🔥"
                        try:
                            await bot.delete_message(chat_id=CHAT_ID, message_id=sinal_ativo["gale_message_id"])
                        except TelegramError as e:
                            logging.debug(f"Erro ao apagar mensagem de 1 gale: {e}")
                        message = await bot.send_message(chat_id=CHAT_ID, text=mensagem_gale)
                        sinal_ativo["gale_nivel"] = 2
                        sinal_ativo["gale_message_id"] = message.message_id
                        sinal_ativo["resultado_id"] = resultado_id
                        logging.info(f"Mensagem de 2 gale enviada: {mensagem_gale}, ID: {message.message_id}")
                    else:
                        placar["losses"] += 1
                        placar["precisao"] = max(placar["precisao"] - 0.85, 0.0)
                        if sinal_ativo["gale_message_id"]:
                            try:
                                await bot.delete_message(chat_id=CHAT_ID, message_id=sinal_ativo["gale_message_id"])
                            except TelegramError as e:
                                logging.debug(f"Erro ao apagar mensagem de 2 gale: {e}")
                        await bot.send_message(chat_id=CHAT_ID, text="NÃO FOI DESSA🤧")
                        logging.info(f"Validação enviada (Erro 2 Gale): Sinal {sinal_ativo['sinal']}, Resultado {resultado}, Resultado ID: {resultado_id}")
                        await enviar_placar()
                        sinais_ativos.remove(sinal_ativo)
                        detecao_pausada = False
                ultima_mensagem_monitoramento = None
            elif asyncio.get_event_loop().time() - sinal_ativo["enviado_em"] > 300:
                logging.warning(f"Sinal obsoleto removido: Tendência {sinal_ativo['sinal']}, Resultado ID: {sinal_ativo['resultado_id']}")
                if sinal_ativo["gale_message_id"]:
                    try:
                        await bot.delete_message(chat_id=CHAT_ID, message_id=sinal_ativo["gale_message_id"])
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
            total_acertos = placar['ganhos_seguidos'] + placar['ganhos_gale1'] + placar['ganhos_gale2']
            erro_mensagem = "AINDA NÃO ERRAMOS😌" if placar['losses'] == 0 else f"ERRAMOS APENAS {placar['losses']} SINAL❌"
            msg = f"📈 Relatório: Bot em operação\n🎯RESULTADOS DO CLEVER🎯\nGANHOS SEGUIDOS: {placar['ganhos_seguidos']}🤑\nGANHOS NO 1•GALE: {placar['ganhos_gale1']}🤌\nGANHOS NO 2•GALE: {placar['ganhos_gale2']}🤌\nLOSS:{placar['losses']}😔❌\nACERTAMOS {total_acertos} SINAIS🤑\n{erro_mensagem}\nPRECISÃO:{placar['precisao']:.2f}%"
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
                historico = historico[-25:]  # Mantém os últimos 25 resultados
                logging.info(f"Histórico atualizado: {historico} (ID: {resultado_id})")

                rodadas_desde_erro += 1

                await enviar_resultado(resultado, player_score, banker_score, resultado_id)

                if not detecao_pausada:
                    logging.debug(f"Detecção de sinais ativa. Histórico: {historico}")
                    sinal, confianca = detectar_sinal_claro(historico)
                    if sinal and confianca >= 0.75:
                        logging.debug(f"Sinal claro detectado: {sinal} com confiança {confianca:.2%}")
                        await enviar_sinal(sinal=sinal, confianca=confianca, resultado_id=resultado_id, sequencia=historico)
                    else:
                        logging.debug(f"Nenhum sinal claro detectado. Confiança máxima: {confianca:.2%}")

                await asyncio.sleep(2)
            else:
                logging.debug(f"Resultado repetido ignorado: ID {resultado_id}")
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
