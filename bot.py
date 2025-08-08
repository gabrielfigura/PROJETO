import asyncio
import aiohttp
import logging
import os
from telegram import Bot
from telegram.error import TelegramError
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
from collections import Counter, deque
import numpy as np

# Configurações do Bot
BOT_TOKEN = os.getenv("BOT_TOKEN", "7758723414:AAF-Zq1QPoGy2IS-iK2Wh28PfexP0_mmHHc")
CHAT_ID = os.getenv("CHAT_ID", "-1002506692600")
API_URL = "https://api.casinoscores.com/svc-evolution-game-events/api/bacbo/latest"

# Inicializar o bot
bot = Bot(token=BOT_TOKEN)

# Configuração de logging
logging.basicConfig(level=logging.DEBUG, format="%(asctime)s - %(levelname)s - %(message)s")

# Histórico e estado
historico = deque(maxlen=25)  # Mantém até 25 resultados mais recentes
ultimo_resultado_id = None
sinais_ativos = []
placar = {"✅": 0}
ultima_mensagem_monitoramento = None
detecao_pausada = False

# Mapeamento de outcomes para emojis
OUTCOME_MAP = {
    "PlayerWon": "🔵",
    "BankerWon": "🔴",
    "Tie": "🟡"
}

# Função para calcular frequência de padrões nos últimos 3 a 5 resultados
def analisar_padroes(historico, min_len=3, max_len=5):
    padroes = {}
    historico_lista = list(historico)
    for tamanho in range(min_len, max_len + 1):
        if len(historico_lista) >= tamanho:
            padrao = tuple(historico_lista[-tamanho:])
            if padrao not in padroes:
                padroes[padrao] = {"ocorrencias": 0, "proximo_resultado": Counter()}
            # Contar ocorrências do padrão e o resultado seguinte
            for i in range(len(historico_lista) - tamanho):
                if historico_lista[i:i+tamanho] == list(padrao) and i + tamanho < len(historico_lista):
                    padroes[padrao]["ocorrencias"] += 1
                    padroes[padrao]["proximo_resultado"][historico_lista[i + tamanho]] += 1
    return padroes

# Função para determinar o sinal mais provável
def determinar_sinal(historico):
    padroes = analisar_padroes(historico)
    melhor_sinal = None
    maior_probabilidade = 0
    melhor_sequencia = None
    
    for padrao, dados in padroes.items():
        if dados["ocorrencias"] > 0:
            total = sum(dados["proximo_resultado"].values())
            for resultado, contagem in dados["proximo_resultado"].items():
                prob = contagem / total
                if prob > maior_probabilidade:
                    maior_probabilidade = prob
                    melhor_sinal = resultado
                    melhor_sequencia = list(padrao)
    
    if melhor_sinal and maior_probabilidade >= 0.6:  # Threshold mínimo para confiabilidade
        return melhor_sinal, melhor_sequencia, maior_probabilidade
    return None, None, 0

@retry(stop=stop_after_attempt(5), wait=wait_exponential(multiplier=1, min=4, max=30), retry=retry_if_exception_type((aiohttp.ClientError, asyncio.TimeoutError)))
async def fetch_resultado():
    async with aiohttp.ClientSession() as session:
        try:
            async with session.get(API_URL, timeout=aiohttp.ClientTimeout(total=15)) as response:
                if response.status != 200:
                    logging.error(f"Erro na API: Status {response.status}, Resposta: {await response.text()}")
                    return None, None, None, None
                data = await response.json()
                if 'data' not in data or 'result' not in data['data'] or 'outcome' not in data['data']['result'] or 'id' not in data:
                    logging.error(f"Estrutura inválida na resposta: {data}")
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
        except (aiohttp.ClientError, asyncio.TimeoutError, ValueError, Exception) as e:
            logging.error(f"Erro ao buscar resultado: {e}")
            return None, None, None, None

@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10), retry=retry_if_exception_type(TelegramError))
async def enviar_sinal(sinal, sequencia, probabilidade, resultado_id):
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
Sequência: {sequencia_str}
Entrar: {sinal}
Proteger o empate 🟡
Confiança: {probabilidade:.2%}
⏳ Aposte agora!"""
        message = await bot.send_message(chat_id=CHAT_ID, text=mensagem)
        logging.info(f"Sinal enviado: Sequência: {sequencia_str}, Sinal: {sinal}, Confiança: {probabilidade:.2%}, Resultado ID: {resultado_id}")
        sinais_ativos.append({
            "sinal": sinal,
            "resultado_id": resultado_id,
            "sequencia": sequencia,
            "enviado_em": asyncio.get_event_loop().time()
        })
        return message.message_id
    except TelegramError as e:
        logging.error(f"Erro ao enviar sinal: {e}")
        raise

@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10), retry=retry_if_exception_type(TelegramError))
async def enviar_resultado(resultado, player_score, banker_score, resultado_id):
    global ultima_mensagem_monitoramento, detecao_pausada, placar
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
                    mensagem_validacao = f"🤑 ENTROU DINHEIRO 🤑\n{resultado_texto}\n📊 Resultado do sinal (Sequência: {sequencia_str})\nPlacar: {placar['✅']}✅"
                    await bot.send_message(chat_id=CHAT_ID, text=mensagem_validacao)
                    logging.info(f"Validação enviada: Sinal {sinal_ativo['sinal']}, Resultado {resultado}, Resultado ID: {resultado_id}")
                else:
                    placar["✅"] = 0
                    mensagem_validacao = f"NÃO FOI DESSA 🤧\n{resultado_texto}\n📊 Resultado do sinal (Sequência: {sequencia_str})\nPlacar: {placar['✅']}✅"
                    await bot.send_message(chat_id=CHAT_ID, text=mensagem_validacao)
                    logging.info(f"Validação enviada (Erro): Sinal {sinal_ativo['sinal']}, Resultado {resultado}, Resultado ID: {resultado_id}")
                
                sinais_ativos.remove(sinal_ativo)
                detecao_pausada = False
                ultima_mensagem_monitoramento = None
            elif asyncio.get_event_loop().time() - sinal_ativo["enviado_em"] > 300:
                sinais_ativos.remove(sinal_ativo)
                detecao_pausada = False
                logging.warning(f"Sinal obsoleto removido: Sequência {sinal_ativo['sequencia']}, Resultado ID: {sinal_ativo['resultado_id']}")
    except TelegramError as e:
        logging.error(f"Erro ao enviar resultado: {e}")

@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10), retry=retry_if_exception_type(TelegramError))
async def enviar_monitoramento():
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
    while True:
        try:
            msg = f"📈 Relatório: Bot em operação\nPlacar: {placar['✅']}✅"
            await bot.send_message(chat_id=CHAT_ID, text=msg)
            logging.info(f"Relatório enviado: {msg}")
        except TelegramError as e:
            logging.error(f"Erro ao enviar relatório: {e}")
        await asyncio.sleep(3600)

async def main():
    global historico, ultimo_resultado_id, detecao_pausada
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

                await enviar_resultado(resultado, player_score, banker_score, resultado_id)

                if not detecao_pausada and len(historico) >= 3:
                    sinal, sequencia, probabilidade = determinar_sinal(historico)
                    if sinal and probabilidade >= 0.6:
                        logging.debug(f"Sinal detectado: {sinal}, Sequência: {sequencia}, Confiança: {probabilidade:.2%}")
                        await enviar_sinal(sinal, sequencia, probabilidade, resultado_id)
                    else:
                        logging.debug("Nenhum sinal confiável encontrado.")

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
