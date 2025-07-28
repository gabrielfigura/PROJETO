import requests
import json
import time
from telegram import Bot
from telegram.error import TelegramError
import logging

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

def obter_resultado():
    try:
        resposta = requests.get(API_URL, timeout=5)
        resposta.raise_for_status()  # Levanta exceção para status diferente de 200
        dados = resposta.json()
        
        if not dados:
            logging.error("API retornou lista vazia")
            return None
            
        latest_event = dados[0]
        if 'playerScore' not in latest_event or 'bankerScore' not in latest_event:
            logging.error("Chaves playerScore ou bankerScore ausentes")
            return None

        player_score = latest_event['playerScore']
        banker_score = latest_event['bankerScore']

        if player_score > banker_score:
            return "🔴"
        elif banker_score > player_score:
            return "🔵"
        else:
            return "🟡"

    except requests.exceptions.RequestException as e:
        logging.error(f"Erro ao buscar resultado: {e}")
        return None

def verificar_padroes(historico):
    for padrao in PADROES:
        sequencia = padrao["sequencia"]
        tamanho = len(sequencia)
        if len(historico) >= tamanho and historico[-tamanho:] == sequencia:
            return padrao
    return None

def enviar_sinal(padrao):
    try:
        mensagem = f"""
📊 *Sinal Detectado*
Padrão #{padrao['id']}
Sequência: {' '.join(padrao['sequencia'])}
🎯 Ação: *{padrao['acao']}*
"""
        bot.send_message(chat_id=CHAT_ID, text=mensagem, parse_mode="Markdown")
        logging.info(f"Sinal enviado: Padrão #{padrao['id']}")
    except TelegramError as e:
        logging.error(f"Erro ao enviar sinal: {e}")

def iniciar_monitoramento():
    logging.info("Iniciando monitoramento")
    try:
        # Verificar se o bot está funcional
        bot.get_me()
        logging.info("Bot inicializado com sucesso")
    except TelegramError as e:
        logging.error(f"Erro ao inicializar bot: {e}")
        return

    ultimo_resultado = None
    while True:
        try:
            resultado = obter_resultado()
            if resultado and resultado != ultimo_resultado:
                ultimo_resultado = resultado
                historico_resultados.append(resultado)
                logging.info(f"Resultado: {resultado}")
                if len(historico_resultados) > 50:
                    historico_resultados.pop(0)

                padrao = verificar_padroes(historico_resultados)
                if padrao:
                    enviar_sinal(padrao)

            time.sleep(3)
        except KeyboardInterrupt:
            logging.info("Monitoramento encerrado pelo usuário")
            break
        except Exception as e:
            logging.error(f"Erro no loop principal: {e}")
            time.sleep(10)  # Espera maior em caso de erro

if __name__ == "__main__":
    iniciar_monitoramento()
