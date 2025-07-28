import requests
import json
import time
import asyncio
from telegram import Bot
from telegram.error import TelegramError
import logging
from tenacity import retry, stop_after_attempt, wait_exponential
from datetime import datetime, timezone
import random

# Configuração de logging
logging.basicConfig(filename='bot.log', level=logging.INFO, 
                   format='%(asctime)s - %(levelname)s - %(message)s')

# Configurações do Bot
BOT_TOKEN = "7703975421:AAG-CG5Who2xs4NlevJqB5TNvjjzeUEDz8o"
CHAT_ID = "-1002859771274"
API_URL = "https://api.casinoscores.com/svc-evolution-game-events/api/bacbo/latest"
bot = Bot(token=BOT_TOKEN)

# Lista de padrões
PADROES = [
    {"id": 1, "sequencia": ["🔴", "🔴", "🔴"], "acao": "Entrar a favor", "aposta": "🔴"},
    {"id": 2, "sequencia": ["🔵", "🔴", "🔵"], "acao": "Entrar no oposto do último", "aposta": "🔴"},
    {"id": 3, "sequencia": ["🔴", "🔴", "🔵"], "acao": "Entrar contra", "aposta": "🔵"},
    {"id": 4, "sequencia": ["🔵", "🔵", "🔴", "🔴"], "acao": "Entrar no lado que inicia", "aposta": "🔵"},
    {"id": 5, "sequencia": ["🔴", "🔴", "🔴", "🔵"], "acao": "Seguir rompimento", "aposta": "🔵"},
    {"id": 6, "sequencia": ["🔵", "🔵", "🔵"], "acao": "Entrar a favor", "aposta": "🔵"},
    {"id": 7, "sequencia": ["🔴", "🔵", "🔴"], "acao": "Seguir alternância", "aposta": "🔴"},
    {"id": 8, "sequencia": ["🔴", "🔵", "🔵"], "acao": "Seguir nova cor", "aposta": "🔵"},
    {"id": 9, "sequencia": ["🔴", "🔴", "🟡"], "acao": "Seguir 🔴", "aposta": "🔴"},
    {"id": 10, "sequencia": ["🔴", "🔵", "🟡", "🔴"], "acao": "Ignorar Tie e seguir 🔴", "aposta": "🔴"},
    {"id": 11, "sequencia": ["🔴", "🔵", "🔴", "🔵"], "acao": "Seguir alternância dupla", "aposta": "🔴"},
    {"id": 12, "sequencia": ["🔵", "🔴", "🟡"], "acao": "Seguir após empate", "aposta": "🔴"},
    {"id": 13, "sequencia": ["🔵", "🔵", "🟡", "🔵"], "acao": "Seguir após empate azul", "aposta": "🔵"},
    {"id": 14, "sequencia": ["🟡", "🔵"], "acao": "Seguir após empate", "aposta": "🔵"},
    {"id": 15, "sequencia": ["🔵", "🔴"], "acao": "Seguir alternância curta", "aposta": "🔴"},
]

historico_resultados = []
historico_sinais = []  # [(padrao_id, aposta, unidades, rodada_id, etapa, resultado, mensagem_id_gale)]
acertos = 0
perdas = 0
ultima_mensagem_espera = None
ultimo_sinal_enviado = 0
ultima_consulta = 0

def avaliar_forca_padrao(padrao, historico):
    """Avalia se o padrão é forte com base em frequência, consistência e tendência."""
    if not historico or len(historico) < 20:
        return False
    sequencia = padrao["sequencia"]
    aposta = padrao["aposta"]
    tamanho = len(sequencia)

    # Frequência recente (últimos 20 resultados)
    historico_20 = historico[-20:]
    ocorrencias = sum(1 for i in range(len(historico_20) - tamanho + 1) if historico_20[i:i + tamanho] == sequencia)
    if ocorrencias < 2:
        return False

    # Consistência (sem muitos ties ou alternâncias)
    ties = historico_20.count("🟡")
    alternancias = sum(1 for i in range(len(historico_20) - 1) if historico_20[i] != historico_20[i + 1] and historico_20[i] != "🟡" and historico_20[i + 1] != "🟡")
    if ties / len(historico_20) > 0.2 or alternancias / len(historico_20) > 0.5:
        return False

    # Tendência dominante (últimos 10 resultados)
    historico_10 = historico[-10:]
    vermelho_count = historico_10.count("🔴")
    azul_count = historico_10.count("🔵")
    tendencia = "🔴" if vermelho_count > azul_count else "🔵"
    if aposta != tendencia:
        return False

    return True

@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=4, max=10))
def obter_resultado():
    try:
        global ultima_consulta
        tempo_atual = time.time()
        if tempo_atual - ultima_consulta < 1:  # Limita consultas a 1 por segundo
            return None, None
        print("Consultando API continuamente...")
        logging.info("Consultando API continuamente...")
        headers = {"User-Agent": "Mozilla/5.0"}
        resposta = requests.get(API_URL, timeout=5, headers=headers)
        resposta.raise_for_status()
        dados = resposta.json()
        
        print(f"Resposta da API: {json.dumps(dados, indent=2)}")
        logging.info(f"Resposta da API: {json.dumps(dados, indent=2)}")
        
        if not dados or not isinstance(dados, dict) or 'data' not in dados:
            print("API retornou dados inválidos")
            logging.error("API retornou dados inválidos")
            return None, None
            
        event_data = dados['data']
        if not isinstance(event_data, dict) or 'result' not in event_data:
            print("Chave 'result' ausente ou inválida")
            logging.error("Chave 'result' ausente ou inválida")
            return None, None

        ultima_consulta = tempo_atual
        if event_data.get('status') != 'Resolved':
            print(f"Rodada não finalizada: status={event_data.get('status')}")
            logging.info(f"Rodada não finalizada: status={event_data.get('status')}")
            return None, event_data

        result = event_data['result']
        if not isinstance(result, dict):
            print("Resultado da API não é um dicionário")
            logging.error("Resultado da API não é um dicionário")
            return None, None

        player_score = result.get('playerDice', {}).get('score')
        banker_score = result.get('bankerDice', {}).get('score')
        outcome = result.get('outcome')

        if player_score is None or banker_score is None:
            print(f"Chaves de pontuação ausentes: {result.keys()}")
            logging.error(f"Chaves de pontuação ausentes: {result.keys()}")
            return None, None

        print(f"Player Score: {player_score}, Banker Score: {banker_score}, Outcome: {outcome}")
        logging.info(f"Player Score: {player_score}, Banker Score: {banker_score}, Outcome: {outcome}")

        if outcome == 'PlayerWon':
            return "🔴", event_data
        elif outcome == 'BankerWon':
            return "🔵", event_data
        elif outcome == 'Tie':
            return "🟡", event_data
        else:
            print(f"Outcome desconhecido: {outcome}")
            logging.error(f"Outcome desconhecido: {outcome}")
            return None, None

    except requests.exceptions.RequestException as e:
        print(f"Erro ao buscar resultado: {str(e)}")
        logging.error(f"Erro ao buscar resultado: {str(e)}")
        raise
    except Exception as e:
        print(f"Erro inesperado na API: {str(e)}")
        logging.error(f"Erro inesperado na API: {str(e)}")
        return None, None

def verificar_resultado_sinal(sinal, resultado_atual):
    """Verifica se o sinal foi uma vitória, derrota ou empate (empate conta como acerto)."""
    if not sinal or not resultado_atual:
        return None
    padrao_id, aposta, unidades, rodada_id, etapa, _, _ = sinal
    if etapa == "Gale" and (aposta == resultado_atual or resultado_atual == "🟡"):
        return "Vitória no Gale"
    elif etapa == "Inicial" and (aposta == resultado_atual or resultado_atual == "🟡"):
        return "Vitória Inicial"
    return None

def calcular_unidades_gale(historico_sinais, resultado_atual):
    """Calcula as unidades para o próximo sinal com base no sistema de 1 gale."""
    UNIDADE_BASE = 1
    if not historico_sinais or not historico_sinais[-1][5]:
        return UNIDADE_BASE
    ultimo_sinal = historico_sinais[-1]
    resultado_ultimo_sinal = verificar_resultado_sinal(ultimo_sinal, resultado_atual)
    print(f"Resultado do último sinal: {resultado_ultimo_sinal}")
    logging.info(f"Resultado do último sinal: {resultado_ultimo_sinal}")
    
    if resultado_ultimo_sinal in ["Vitória Inicial", "Vitória no Gale"]:
        return UNIDADE_BASE
    elif resultado_ultimo_sinal is None and ultimo_sinal[4] == "Inicial" and ultimo_sinal[1] != resultado_atual and resultado_atual != "🟡":
        return UNIDADE_BASE * 2
    return UNIDADE_BASE

def prever_padroes(historico):
    """Preve padrões com 1 rodada de antecedência."""
    print(f"Histórico atual (comprimento: {len(historico)}): {historico[-10:]}")
    logging.info(f"Histórico atual (comprimento: {len(historico)}): {historico[-10:]}")
    if len(historico) < 2:
        return None
    for padrao in PADROES:
        sequencia = padrao["sequencia"]
        tamanho = len(sequencia)
        if len(historico) >= tamanho + 1 and historico[-(tamanho + 1):-1] == sequencia[:-1]:
            print(f"Padrão previsto: #{padrao['id']}, Sequência: {sequencia}")
            logging.info(f"Padrão previsto: #{padrao['id']}, Sequência: {sequencia}")
            return padrao
    print("Nenhum padrão previsto")
    logging.info("Nenhum padrão previsto")
    return None

async def enviar_sinal(padrao, unidades, placar, ultima_mensagem_espera_id, forte=False):
    global ultima_mensagem_espera
    try:
        if ultima_mensagem_espera_id:
            await bot.delete_message(chat_id=CHAT_ID, message_id=ultima_mensagem_espera_id)
            ultima_mensagem_espera = None
        aposta = "Player" if padrao['aposta'] == "🔴" else "Banker" if padrao['aposta'] == "🔵" else "Tie"
        mensagem = f"""
🎯 Sinal Bac Bo - Entrar: {aposta} | Validade: até 1 Gale | Entrar agora!
{'🔥 Padrão Forte 🔥' if forte else ''}
"""
        print(f"Enviando sinal: Entrar {aposta} ({unidades} unidades), Forte: {forte}")
        sent_message = await bot.send_message(chat_id=CHAT_ID, text=mensagem, parse_mode="Markdown")
        logging.info(f"Sinal enviado: Entrar {aposta} ({unidades} unidades), Forte: {forte}")
        return sent_message.message_id
    except TelegramError as e:
        print(f"Erro ao enviar sinal: {str(e)}")
        logging.error(f"Erro ao enviar sinal: {str(e)}")
        return None

async def enviar_mensagem_espera():
    global ultima_mensagem_espera
    try:
        mensagem = "Detectando o gráfico…🤌"
        print(f"Enviando mensagem de espera: {mensagem}")
        sent_message = await bot.send_message(chat_id=CHAT_ID, text=mensagem, parse_mode="Markdown")
        ultima_mensagem_espera = sent_message.message_id
        logging.info(f"Mensagem de espera enviada: {mensagem}, ID: {ultima_mensagem_espera}")
        return ultima_mensagem_espera
    except TelegramError as e:
        print(f"Erro ao enviar mensagem de espera: {str(e)}")
        logging.error(f"Erro ao enviar mensagem de espera: {str(e)}")
        return None

async def enviar_mensagem_gale():
    try:
        mensagem = "Dobra a banca e vamos no 1 gale🎯"
        print(f"Enviando mensagem de gale: {mensagem}")
        sent_message = await bot.send_message(chat_id=CHAT_ID, text=mensagem, parse_mode="Markdown")
        logging.info(f"Mensagem de gale enviada: {mensagem}, ID: {sent_message.message_id}")
        return sent_message.message_id
    except TelegramError as e:
        print(f"Erro ao enviar mensagem de gale: {str(e)}")
        logging.error(f"Erro ao enviar mensagem de gale: {str(e)}")
        return None

async def enviar_placar(placar):
    try:
        mensagem = f"📈 *Placar Atualizado*\nAcertos: {placar['acertos']}, Perdas: {placar['perdas']}"
        print(f"Enviando placar: {mensagem}")
        await bot.send_message(chat_id=CHAT_ID, text=mensagem, parse_mode="Markdown")
        logging.info(f"Placar enviado: {mensagem}")
    except TelegramError as e:
        print(f"Erro ao enviar placar: {str(e)}")
        logging.error(f"Erro ao enviar placar: {str(e)}")

async def iniciar_monitoramento():
    global acertos, perdas, ultima_mensagem_espera, ultimo_sinal_enviado, ultima_consulta, ultima_rodada_id
    print("Iniciando monitoramento")
    logging.info("Iniciando monitoramento")
    try:
        print("Verificando conexão com o Telegram...")
        await bot.get_me()
        print("Bot inicializado com sucesso")
        logging.info("Bot inicializado com sucesso")
        await bot.send_message(chat_id=CHAT_ID, text="✅ Bot inicializado com sucesso!", parse_mode="Markdown")
    except TelegramError as e:
        print(f"Erro ao inicializar bot: {str(e)}")
        logging.error(f"Erro ao inicializar bot: {str(e)}")
        return

    ultimo_resultado = None
    ultima_rodada_id = None
    duracao_media_rodada = 30  # Estimativa inicial em segundos
    placar = {"acertos": 0, "perdas": 0}
    mensagem_gale_id = None
    ultimo_sinal_rodada_id = None
    consultas_sem_nova_rodada = 0
    ultimo_started_at = None

    while True:
        try:
            resultado, event_data = obter_resultado()
            if event_data:
                rodada_id = event_data.get('id')
                started_at = datetime.fromisoformat(event_data.get('startedAt', '').replace('Z', '+00:00')) if event_data.get('startedAt') else None
                settled_at = datetime.fromisoformat(event_data.get('settledAt', '').replace('Z', '+00:00')) if event_data.get('settledAt') else None

                if settled_at:
                    tempo_atual = datetime.now(timezone.utc)
                    duracao_rodada = (tempo_atual - settled_at).total_seconds() if ultima_rodada_id != rodada_id else duracao_media_rodada
                    if duracao_rodada > 0:
                        duracao_media_rodada = (duracao_media_rodada * 0.9 + duracao_rodada * 0.1)
                        print(f"Duração da rodada: {duracao_rodada:.1f}s, Média: {duracao_media_rodada:.1f}s")
                        logging.info(f"Duração da rodada: {duracao_rodada:.1f}s, Média: {duracao_media_rodada:.1f}s")

                # Adicionar resultado ao histórico se for nova rodada ou forçar progresso
                if resultado and (rodada_id != ultima_rodada_id or consultas_sem_nova_rodada > 50):  # Reduzido para 5s
                    ultima_rodada_id = rodada_id
                    consultas_sem_nova_rodada = 0
                    if resultado != ultimo_resultado or consultas_sem_nova_rodada > 50:
                        ultimo_resultado = resultado
                        historico_resultados.append(resultado)
                        print(f"Resultado: {resultado} (Rodada ID: {rodada_id})")
                        logging.info(f"Resultado: {resultado} (Rodada ID: {rodada_id})")
                        if len(historico_resultados) > 50:
                            historico_resultados.pop(0)
                else:
                    consultas_sem_nova_rodada += 1
                    if consultas_sem_nova_rodada > 50 and not historico_resultados:  # Simular resultado se histórico vazio
                        simulado = random.choice(["🔴", "🔵", "🟡"])
                        historico_resultados.append(simulado)
                        print(f"Simulando resultado: {simulado} (Histórico vazio)")
                        logging.info(f"Simulando resultado: {simulado} (Histórico vazio)")

                # Validar o último sinal enviado
                if historico_sinais and historico_sinais[-1][3] == rodada_id and event_data.get('status') == 'Resolved':
                    ultimo_sinal = historico_sinais[-1]
                    padrao_id, aposta, unidades, _, etapa, resultado_previo, mensagem_id_gale = ultimo_sinal
                    resultado_atual = verificar_resultado_sinal(ultimo_sinal, resultado)
                    if resultado_atual:
                        historico_sinais[-1] = (padrao_id, aposta, unidades, rodada_id, etapa, resultado_atual, mensagem_id_gale)
                        if etapa == "Inicial" and resultado_atual == "Vitória Inicial":
                            acertos += 1
                            await bot.send_message(chat_id=CHAT_ID, text=f"Dinheiro entrou ({aposta} acertado, +{unidades} unidades)", parse_mode="Markdown")
                            print(f"Sinal acertado de primeira: {aposta}")
                            logging.info(f"Sinal acertado de primeira: {aposta}")
                            if mensagem_id_gale:
                                await bot.delete_message(chat_id=CHAT_ID, message_id=mensagem_id_gale)
                        elif etapa == "Gale" and resultado_atual == "Vitória no Gale":
                            acertos += 1
                            await bot.send_message(chat_id=CHAT_ID, text=f"Dinheiro entrou ({aposta} acertado, +{unidades * 2} unidades)", parse_mode="Markdown")
                            print(f"Sinal acertado no gale: {aposta}")
                            logging.info(f"Sinal acertado no gale: {aposta}")
                            if mensagem_id_gale:
                                await bot.delete_message(chat_id=CHAT_ID, message_id=mensagem_id_gale)
                        elif etapa == "Inicial" and resultado_previo is None and aposta != resultado and resultado != "🟡":
                            mensagem_gale_id = await enviar_mensagem_gale()
                            historico_sinais.append((padrao_id, aposta, 2, rodada_id, "Gale", None, mensagem_id_gale))
                            print("Ativando 1 gale")
                            logging.info("Ativando 1 gale")
                        elif etapa == "Gale" and resultado_atual is None:
                            perdas += 1
                            await bot.send_message(chat_id=CHAT_ID, text="Não foi dessa…🤧", parse_mode="Markdown")
                            print("Perda confirmada após falha inicial e gale")
                            logging.info("Perda confirmada após falha inicial e gale")
                            if mensagem_id_gale:
                                await bot.delete_message(chat_id=CHAT_ID, message_id=mensagem_id_gale)
                        await enviar_placar(placar)

                # Prever e enviar novo sinal com antecedência
                if event_data.get('status') == 'Resolved' and started_at and settled_at:
                    tempo_atual = datetime.now(timezone.utc)
                    tempo_restantes = (settled_at - tempo_atual).total_seconds()
                    if tempo_restantes < 0:  # Rodada já encerrada, usar média
                        tempo_espera = max(0, duracao_media_rodada - duracao_media_rodada * 0.75 + 6)
                    else:
                        tempo_espera = max(0, tempo_restantes - 6)  # 6s de antecedência
                    if tempo_atual.timestamp() - ultimo_sinal_enviado >= 30:
                        padrao = prever_padroes(historico_resultados)
                        if padrao:
                            forte = avaliar_forca_padrao(padrao, historico_resultados)
                            unidades = calcular_unidades_gale(historico_sinais, resultado)
                            historico_sinais.append((padrao['id'], padrao['aposta'], unidades, rodada_id, "Inicial", None, None))
                            print(f"Aguardando {tempo_espera:.1f}s para enviar sinal, Duração média: {duracao_media_rodada:.1f}s, Tempo restante: {tempo_restantes:.1f}s")
                            logging.info(f"Aguardando {tempo_espera:.1f}s para enviar sinal, Duração média: {duracao_media_rodada:.1f}s, Tempo restante: {tempo_restantes:.1f}s")
                            await asyncio.sleep(tempo_espera)
                            ultima_mensagem_espera_id = ultima_mensagem_espera
                            ultimo_sinal_enviado = tempo_atual.timestamp()
                            ultimo_sinal_rodada_id = rodada_id
                            await enviar_sinal(padrao, unidades, placar, ultima_mensagem_espera_id, forte)
                            if ultima_mensagem_espera_id:
                                await bot.delete_message(chat_id=CHAT_ID, message_id=ultima_mensagem_espera_id)
                                ultima_mensagem_espera = None

                # Enviar mensagem de espera se no intervalo
                if tempo_atual.timestamp() - ultimo_sinal_enviado < 30 and not ultima_mensagem_espera and (tempo_atual.timestamp() - ultimo_sinal_enviado) % 10 < 1:
                    ultima_mensagem_espera = await enviar_mensagem_espera()

            await asyncio.sleep(0.1)  # Consulta contínua com pequeno delay
        except Exception as e:
            print(f"Erro no loop principal: {str(e)}")
            logging.error(f"Erro no loop principal: {str(e)}")
            await asyncio.sleep(10)

if __name__ == "__main__":
    asyncio.run(iniciar_monitoramento())
