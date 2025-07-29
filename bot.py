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
historico = deque(maxlen=100)
ultimo_resultado_id = None
sinais_ativos = []
placar = {"✅": 0}
rodadas_desde_erro = 0
ultima_mensagem_monitoramento = None
detecao_pausada = False
sinal_em_processo = False

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
    {"
