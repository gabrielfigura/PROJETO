import requests
import time
import json
import telebot
from datetime import datetime
import threading
import os

# ================= CONFIGURAÇÕES =================
API_URL = "https://api.casinoscores.com/svc-evolution-game-events/api/bacbo/latest"
TELEGRAM_TOKEN = "8163319902:AAHE9LZ984JCIc-Lezl4WXR2FsGHPEFTxRQ"
CHAT_ID = "-1002597090660"

bot = telebot.TeleBot(TELEGRAM_TOKEN)

# Placares
sem_gale = com_gale1 = com_gale2 = perdas = 0
gale_ativo = 0
ultimo_sinal = None
historico = []
ultimo_id_jogo = None  # Para detectar jogo novo com precisão

# ============== ENVIA MENSAGEM QUANDO SOBE ==============
def enviar_startup():
    texto = f"""
BOT BAC BO ONLINE E ATIVO!
Iniciado com sucesso: {datetime.now().strftime('%d/%m/%Y às %H:%M:%S')}
Monitorando Bac Bo 24 horas por dia
Primeiro sinal sai em alguns segundos...
    """
    try:
        bot.send_message(CHAT_ID, texto, parse_mode='HTML')
        print("Mensagem de startup enviada!")
    except Exception as e:
        print("Erro ao enviar startup:", e)

# ============== PEGAR RESULTADOS ==============
def get_ultimos_resultados():
    global ultimo_id_jogo
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)',
            'Accept': 'application/json',
            'Referer': 'https://casinoscores.com/'
        }
        r = requests.get(API_URL, headers=headers, timeout=12)
        data = r.json()

        resultados = []
        novo_id = None

        for jogo in data['results'][-25:]:
            id_jogo = jogo.get('gameId') or jogo.get('roundId')
            player = jogo['playerTotal']
            banker = jogo['bankerTotal']

            if player > banker:
                resultados.append(("P", id_jogo))
            elif banker > player:
                resultados.append(("B", id_jogo))
            else:
                resultados.append(("T", id_jogo))

            if novo_id is None:
                novo_id = id_jogo

        # Detecta novo jogo
        if novo_id and novo_id != ultimo_id_jogo:
            ultimo_id_jogo = novo_id

        return [r[0] for r in resultados[::-1]]  # retorna só P/B/T, mais antigo primeiro

    except Exception as e:
        print("Erro na API:", e)
        return historico[-20:] if historico else ["P", "B", "T", "P", "B"]

# ============== ANÁLISE DE TENDÊNCIA ==============
def analisar_tendencia():
    resultados = get_ultimos_resultados()
    if len(resultados) < 10:
        return None, "Aguardando histórico..."

    ultimo = resultados[-1]
    p_streak = b_streak = 0
    for r in reversed(resultados):
        if r == ultimo:
            if ultimo == "P": p_streak += 1
            if ultimo == "B": b_streak += 1
        else:
            break

    choppy = len(set(resultados[-14:])) > 9

    if p_streak >= 4:
        return "B", f"Quebra de streak PLAYER ({p_streak} seguidos)"
    if b_streak >= 4:
        return "P", f"Quebra de streak BANKER ({b_streak} seguidos)"

    seq = "".join(resultados[-8:])
    if "PBPBP" in seq or "BPBPB" in seq:
        return ultimo, "Chop forte → seguir último"

    if resultados[-3:] == ["P", "B", "P"]:
        return "B", "Padrão PBP → próximo B"
    if resultados[-3:] == ["B", "P", "B"]:
        return "P", "Padrão BPB → próximo P"

    if resultados[-2:] == ["T", "T"]:
        return "P" if resultados[-3] == "B" else "B", "Dois Ties → oposto do anterior"

    if choppy:
        return None, "Muito choppy – sem sinal"

    return ultimo, "Seguindo tendência atual"

# ============== ENVIO DE SINAL ==============
def enviar_sinal(sinal, motivo):
    global ultimo_sinal, gale_ativo
    ultimo_sinal = sinal
    gale_ativo = 0

    texto = f"""
NOVO SINAL BAC BO
Aposte agora → {'PLAYER' if sinal == 'P' else 'BANKER'}
Motivo: {motivo}
{datetime.now().strftime('%H:%M:%S')}
ENTRE AGORA!
    """
    bot.send_message(CHAT_ID, texto, parse_mode='HTML')

# ============== ATUALIZAR PLACAR ==============
def atualizar_placar(acertou, gales_usados):
    global sem_gale, com_gale1, com_gale2, perdas

    if acertou:
        if gales_usados == 0:
            sem_gale += 1
            status = "ACERTO SEM GALE"
        elif gales_usados == 1:
            com_gale1 += 1
            status = "RECUPEROU NO 1º GALE"
        else:
            com_gale2 += 1
            status = "RECUPEROU NO 2º GALE"
    else:
        perdas += 1
        status = "PERDA TOTAL (2 gales perdidos)"

    total = sem_gale + com_gale1 + com_gale2 + perdas
    taxa = (sem_gale + com_gale1 + com_gale2) / total * 100 if total > 0 else 0

    placar = f"""
PLACAR ATUALIZADO
Sem Gale: {sem_gale}
Com 1 Gale: {com_gale1}
Com 2 Gale: {com_gale2}
Perdas: {perdas}
Taxa de acerto: {taxa:.1f}%
    """
    bot.send_message(CHAT_ID, f"{status}\n{placar}", parse_mode='HTML')

# ============== MONITORAMENTO ==============
def monitorar():
    global ultimo_sinal, gale_ativo, historico, ultimo_id_jogo

    print("Monitoramento iniciado...")
    time.sleep(5)

    while True:
        try:
            resultados = get_ultimos_resultados()
            if len(resultados) > len(historico):
                novo_resultado = resultados[-1]
                historico = resultados

                # Se tinha sinal pendente e saiu resultado novo
                if ultimo_sinal:
                    acertou = (novo_resultado in ("T", ultimo_sinal))

                    if acertou:
                        atualizar_placar(True, gale_ativo)
                        ultimo_sinal = None
                        gale_ativo = 0
                    else:
                        if gale_ativo < 2:
                            gale_ativo += 1
                            bot.send_message(CHAT_ID, f"GALE {gale_ativo} → Continuar no {'PLAYER' if ultimo_sinal=='P' else 'BANKER'}")
                        else:
                            atualizar_placar(False, 0)
                            ultimo_sinal = None
                            gale_ativo = 0

            # Só gera novo sinal se não estiver em gale
            if not ultimo_sinal and len(historico) >= 10:
                sinal, motivo = analisar_tendencia()
                if sinal:
                    enviar_sinal(sinal, motivo)

            time.sleep(7)

        except Exception as e:
            print("Erro no loop:", e)
            time.sleep(10)

# ============== COMANDO /placar ==============
@bot.message_handler(commands=['placar'])
def placar_cmd(message):
    total = sem_gale + com_gale1 + com_gale2 + perdas
    taxa = (sem_gale + com_gale1 + com_gale2) / total * 100 if total > 0 else 0
    texto = f"""
PLACAR BAC BO BOT
Sem Gale: {sem_gale}
Com 1 Gale: {com_gale1}
Com 2 Gale: {com_gale2}
Perdas: {perdas}
Taxa de acerto: {taxa:.1f}%
    """
    bot.reply_to(message, texto)

# ============== INICIO ==============
if __name__ == "__main__":
    print("Iniciando Bac Bo Signal Bot...")
    enviar_startup()  # <--- ESSA É A MENSAGEM QUE VOCÊ QUERIA
    threading.Thread(target=monitorar, daemon=True).start()
    bot.infinity_polling()
