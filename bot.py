import requests
import json
import time
import asyncio
from telegram import Bot
from telegram.error import TelegramError
import logging
from tenacity import retry, stop_after_attempt, wait_exponential
from datetime import datetime, timezone

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
    {"id": 1, "sequencia": ["🔴", "🔴", "🔴"], "acao": "Entrar a favor"},
    {"id": 2, "sequencia": ["🔵", "🔴", "🔵"], "acao": "Entrar no oposto do último"},
    {"id": 3, "sequencia": ["🔴", "🔴", "🔵"], "acao": "Entrar contra"},
    {"id": 4, "sequencia": ["🔵", "🔵", "🔴", "🔴"], "acao": "Entrar no lado que inicia"},
    {"id": 5, "sequencia": ["🔴", "🔴", "🔴", "🔵"], "acao": "Seguir rompimento"},
    {"id": 6, "sequencia": ["🔵", "🔵", "🔵"], "acao": "Entrar a favor"},
    {"id": 7, "sequencia": ["🔴", "🔵", "🔴"], "acao": "Seguir alternância"},
    {"id": 8, "sequencia": ["🔴", "🔵", "🔵"], "acao": "Seguir nova cor"},
    {"id": 9, "sequencia": ["🔴", "🔴", "🟡"], "acao": "Seguir 🔴"},
    {"id": 10, "sequencia": ["🔴", "🔵", "🟡", "🔴"], "acao": "Ignorar Tie e seguir 🔴"},
    {"id": 11, "sequencia": ["🔵", "🔴", "🔴"], "acao": "Seguir 🔴"},
    {"id": 12, "sequencia": ["🔴", "🔵", "🔵"], "acao": "Seguir 🔵"},
    {"id": 13, "sequencia": ["🔵", "🔵", "🔴", "🔵"], "acao": "Voltar para 🔵"},
    {"id": 14, "sequencia": ["🔴", "🟡", "🔴"], "acao": "Seguir 🔴"},
    {"id": 15, "sequencia": ["🔴", "🔴", "🔴", "🔴"], "acao": "Entrar a favor"},
    {"id": 16, "sequencia": ["🔵", "🔵", "🔵", "🔴"], "acao": "Entrar contra 🔴"},
    {"id": 17, "sequencia": ["🔴", "🔵", "🔴", "🔵"], "acao": "Seguir alternância"},
    {"id": 18, "sequencia": ["🔴", "🔵", "🔵", "🔴"], "acao": "Entrar contra 🔵"},
    {"id": 19, "sequencia": ["🔵", "🟡", "🔵"], "acao": "Seguir 🔵"},
    {"id": 20, "sequencia": ["🔴", "🔵", "🟡", "🔵", "🔵"], "acao": "Seguir 🔵"},
    {"id": 21, "sequencia": ["🔵", "🔵", "🔴", "🔴", "🔵"], "acao": "Seguir 🔵"},
    {"id": 22, "sequencia": ["🔴", "🔴", "🔵", "🔴"], "acao": "Seguir 🔴"},
    {"id": 23, "sequencia": ["🔵", "🔴", "🔵", "🔴", "🔴"], "acao": "Seguir 🔴"},
    {"id": 24, "sequencia": ["🔴", "🔵", "🔴", "🔴"], "acao": "Seguir 🔴"},
    {"id": 25, "sequencia": ["🔴", "🔴", "🔴", "🟡", "🔴"], "acao": "Seguir 🔴"},
    {"id": 26, "sequencia": ["🔵", "🔴", "🔴", "🔵", "🔵"], "acao": "Seguir pares"},
    {"id": 27, "sequencia": ["🔴", "🟡", "🔵"], "acao": "Seguir 🔵"},
    {"id": 28, "sequencia": ["🔵", "🔵", "🟡", "🔵", "🔵"], "acao": "Seguir 🔵"},
    {"id": 29, "sequencia": ["🔴", "🔴", "🔵", "🔵", "🔴"], "acao": "Seguir 🔴"},
    {"id": 30, "sequencia": ["🔵", "🔵", "🔴", "🔵", "🔵"], "acao": "Seguir 🔵"},
    {"id": 31, "sequencia": ["🔴", "🔴", "🔴", "🔴", "🔴"], "acao": "Seguir 🔴"},
    {"id": 32, "sequencia": ["🔵", "🔴", "🔵", "🔴", "🔵"], "acao": "Seguir alternância"},
    {"id": 33, "sequencia": ["🔴", "🔵", "🔴", "🟡", "🔵"], "acao": "Seguir 🔵"},
    {"id": 34, "sequencia": ["🔵", "🔵", "🔴", "🔴", "🔴"], "acao": "Seguir 🔴"},
    {"id": 35, "sequencia": ["🔴", "🟡", "🔴", "🔵"], "acao": "Seguir 🔵"},
    {"id": 36, "sequencia": ["🔴", "🔴", "🟡", "🔵", "🔵"], "acao": "Seguir 🔵"},
    {"id": 37, "sequencia": ["🔵", "🔴", "🟡", "🔵", "🔴"], "acao": "Seguir alternância"},
    {"id": 38, "sequencia": ["🔴", "🔴", "🔴", "🔵", "🔴", "🔴"], "acao": "Seguir 🔴"},
    {"id": 39, "sequencia": ["🔵", "🔵", "🔵", "🔴", "🔵"], "acao": "Voltar para 🔵"},
    {"id": 40, "sequencia": ["🔴", "🔴", "🔴", "🟡", "🔵", "🔵"], "acao": "Seguir 🔵"},
    {"id": 41, "sequencia": ["🔴", "🔵", "🔴", "🔴", "🔵"], "acao": "Seguir 🔵"},
    {"id": 42, "sequencia": ["🔵", "🔴", "🔴", "🔵", "🔵", "🔴", "🔴"], "acao": "Seguir pares"},
    {"id": 43, "sequencia": ["🔴", "🔴", "🔵", "🔵", "🔴", "🔴"], "acao": "Seguir ciclo"},
    {"id": 44, "sequencia": ["🔵", "🔴", "🔴", "🔴", "🔵"], "acao": "Seguir 🔴"},
    {"id": 45, "sequencia": ["🔴", "🔵", "🟡", "🔴", "🔴"], "acao": "Seguir 🔴"},
    {"id": 46, "sequencia": ["🔴", "🔴", "🔵", "🔵", "🔴", "🔴", "🔵", "🔵"], "acao": "Seguir pares"},
    {"id": 47, "sequencia": ["🔵", "🔵", "🔵", "🔴", "🔴", "🔴", "🔵"], "acao": "Novo início"},
    {"id": 48, "sequencia": ["🔴", "🔴", "🔴", "🔵", "🔴", "🔴"], "acao": "Seguir 🔴"},
    {"id": 49, "sequencia": ["🔵", "🔴", "🔴", "🔵", "🔵", "🔴", "🔴"], "acao": "Seguir padrão 2x"},
    {"id": 50, "sequencia": ["🔴", "🔴", "🟡", "🔵", "🔵", "🔴"], "acao": "Seguir 🔴"}
]

historico_resultados = []

@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=4, max=10))
def obter_resultado():
    try:
        print("Tentando buscar resultado da API...")
        logging.info("Tentando buscar resultado da API...")
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

        if event_data.get('status') != 'Resolved':
            print(f"Rodada não finalizada: status={event_data.get('status')}")
            logging.info(f"Rodada não finalizada: status={event_data.get('status')}")
            return None, None

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

def verificar_padroes(historico):
    print(f"Histórico atual: {historico[-10:]}")
    logging.info(f"Histórico atual: {historico[-10:]}")
    for padrao in PADROES:
        sequencia = padrao["sequencia"]
        tamanho = len(sequencia)
        if len(historico) >= tamanho and historico[-tamanho:] == sequencia:
            print(f"Padrão encontrado: #{padrao['id']}")
            logging.info(f"Padrão encontrado: #{padrao['id']}")
            return padrao
    return None

async def enviar_sinal(padrao):
    try:
        mensagem = f"""
📊 *Sinal Detectado*
Padrão #{padrao['id']}
Sequência: {' '.join(padrao['sequencia'])}
🎯 Ação: *{padrao['acao']}*
"""
        print(f"Enviando sinal: Padrão #{padrao['id']}")
        await bot.send_message(chat_id=CHAT_ID, text=mensagem, parse_mode="Markdown")
        logging.info(f"Sinal enviado: Padrão #{padrao['id']}")
    except TelegramError as e:
        print(f"Erro ao enviar sinal: {str(e)}")
        logging.error(f"Erro ao enviar sinal: {str(e)}")

async def iniciar_monitoramento():
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
    while True:
        try:
            resultado, event_data = obter_resultado()
            if resultado and event_data and event_data['id'] != ultima_rodada_id:
                # Atualizar ID da rodada para evitar duplicatas
                ultima_rodada_id = event_data['id']
                
                # Calcular duração da rodada para ajustar a temporização
                started_at = datetime.fromisoformat(event_data['startedAt'].replace('Z', '+00:00'))
                settled_at = datetime.fromisoformat(event_data['settledAt'].replace('Z', '+00:00'))
                duracao_rodada = (settled_at - started_at).total_seconds()
                duracao_media_rodada = (duracao_media_rodada * 0.9 + duracao_rodada * 0.1)  # Média ponderada
                print(f"Duração da rodada: {duracao_rodada:.1f}s, Média: {duracao_media_rodada:.1f}s")
                logging.info(f"Duração da rodada: {duracao_rodada:.1f}s, Média: {duracao_media_rodada:.1f}s")

                # Adicionar resultado ao histórico
                if resultado != ultimo_resultado:
                    ultimo_resultado = resultado
                    historico_resultados.append(resultado)
                    print(f"Resultado: {resultado}")
                    logging.info(f"Resultado: {resultado}")
                    if len(historico_resultados) > 50:
                        historico_resultados.pop(0)

                    # Verificar padrões
                    padrao = verificar_padroes(historico_resultados)
                    if padrao:
                        # Estimar o tempo para enviar o sinal antes dos últimos 7 segundos
                        tempo_espera = max(0, duracao_media_rodada - 7 - 5)  # Subtrai 5s do intervalo
                        print(f"Aguardando {tempo_espera:.1f}s para enviar sinal")
                        await asyncio.sleep(tempo_espera)
                        await enviar_sinal(padrao)

            time.sleep(5)  # Intervalo de 5 segundos
        except Exception as e:
            print(f"Erro no loop principal: {str(e)}")
            logging.error(f"Erro no loop principal: {str(e)}")
            time.sleep(10)

if __name__ == "__main__":
    asyncio.run(iniciar_monitoramento())
