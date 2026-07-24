#!/usr/bin/env python3
"""
relay-alert.py
Envia alerta por e-mail (HTML) quando uma aplicacao apresenta erro HTTP,
e envia um segundo e-mail quando o problema for resolvido.

Mantem um arquivo de estado em disco para saber se o dominio ja estava
com problema, evitando reenviar o mesmo alerta a cada execucao do cron.

Chamado pelo health_check.sh a cada verificacao, para TODOS os dominios
(nao so os que estao com erro), passando o codigo HTTP atual.
"""

import argparse
import json
import os
import smtplib
import time
from email.mime.text import MIMEText
from datetime import datetime

# ==================== CONFIGURACOES ====================

RELAY = "dominio-com-br.mail.protection.outlook.com"
PORTA = 25

REMETENTE = "alerta@dominio.com.br"
DESTINATARIO = "infra@dominio.com.br"

# Arquivo onde o estado (OK/ERRO) de cada dominio fica salvo entre execucoes
ARQUIVO_ESTADO = "/tmp/health_check_state.json"

# =========================================================

# Mapeamento de dominios -> nome amigavel da aplicacao (ajuste/complete conforme necessario)
APLICACOES = {
    "api-01.dominio.com.br": "API-01",
    "api-02.dominio.com.br": "API-02",
    "api-03.dominio.com.br": "API-03",
}

# Mapeamento de sufixo do dominio -> nome do ambiente
AMBIENTES = {
    "hmg": "Homologação",
    "prod": "Produção",
    "dev": "Desenvolvimento",
    "stg": "Staging",
}

# Descricao de cada codigo HTTP de erro, para deixar o e-mail mais especifico
DESCRICOES_HTTP = {
    "500": ("Internal Server Error",
            "A aplicacao encontrou um erro interno inesperado ao processar a requisicao."),
    "502": ("Bad Gateway",
            "O proxy recebeu uma resposta invalida da aplicacao ou o backend nao respondeu adequadamente."),
    "503": ("Service Unavailable",
            "O servico esta temporariamente indisponivel, possivelmente por sobrecarga ou manutencao."),
    "504": ("Gateway Timeout",
            "O proxy nao recebeu resposta a tempo do backend (timeout)."),
    "000": ("Sem resposta",
            "O servidor nao respondeu a requisicao dentro do tempo limite (timeout ou conexao recusada)."),
}


def identificar_aplicacao_e_ambiente(dominio):
    """
    Descobre o nome amigavel da aplicacao e o ambiente a partir do dominio.
    """
    primeiro_rotulo = dominio.split(".")[0]

    ambiente = "Não identificado"
    sufixo_encontrado = None
    for sufixo, nome_ambiente in AMBIENTES.items():
        if primeiro_rotulo.endswith("-" + sufixo) or ("-" + sufixo + "-") in primeiro_rotulo:
            ambiente = nome_ambiente
            sufixo_encontrado = sufixo
            break

    if dominio in APLICACOES:
        nome_app = APLICACOES[dominio]
    else:
        rotulo_sem_ambiente = primeiro_rotulo
        if sufixo_encontrado:
            rotulo_sem_ambiente = rotulo_sem_ambiente.replace("-" + sufixo_encontrado, "")
        nome_app = rotulo_sem_ambiente.replace("-", " ").title() or primeiro_rotulo

    return nome_app, ambiente


### ==================== ESTADO (persistencia) ====================

def carregar_estado():
    if not os.path.exists(ARQUIVO_ESTADO):
        return {}
    try:
        with open(ARQUIVO_ESTADO, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def salvar_estado(estado):
    with open(ARQUIVO_ESTADO, "w", encoding="utf-8") as f:
        json.dump(estado, f, indent=2, ensure_ascii=False)


def formatar_duracao(segundos):
    segundos = int(segundos)
    horas = segundos // 3600
    minutos = (segundos % 3600) // 60
    segs = segundos % 60
    if horas > 0:
        return "{}h {}m {}s".format(horas, minutos, segs)
    if minutos > 0:
        return "{}m {}s".format(minutos, segs)
    return "{}s".format(segs)


### ==================== TEMPLATES DE E-MAIL ====================

def montar_html_incidente(url, dominio, codigo, nome_app, ambiente):
    titulo_erro, descricao_erro = DESCRICOES_HTTP.get(
        codigo, ("Erro no servidor", "A aplicacao retornou um erro HTTP inesperado.")
    )
    timestamp = datetime.now().strftime("%d/%m/%Y %H:%M:%S")

    return """
<html>
<head>
<style>
body {{ font-family: Arial, sans-serif; background-color: #f4f4f4; }}
.container {{ max-width: 700px; margin: auto; background-color: #ffffff; border-radius: 8px; overflow: hidden; border: 1px solid #dddddd; }}
.header {{ background-color: #d32f2f; color: white; padding: 20px; text-align: center; font-size: 24px; font-weight: bold; }}
.content {{ padding: 30px; color: #333333; }}
.alert-box {{ background-color: #fdecea; border-left: 6px solid #d32f2f; padding: 15px; margin: 20px 0; }}
.info-table {{ width: 100%; border-collapse: collapse; }}
.info-table td {{ padding: 10px; border-bottom: 1px solid #eeeeee; }}
.label {{ font-weight: bold; width: 180px; }}
.footer {{ background-color: #f5f5f5; padding: 15px; text-align: center; color: #777777; font-size: 12px; }}
</style>
</head>
<body>
<div class="container">
    <div class="header">&#128680; INCIDENTE INICIADO</div>
    <div class="content">
        <h2>Falha Detectada</h2>
        <p>O sistema de monitoramento identificou uma anomalia que requer atencao.</p>
        <div class="alert-box">
            <strong>HTTP {codigo} - {titulo_erro}</strong><br>
            {descricao_erro}
        </div>
        <table class="info-table">
            <tr><td class="label">Sistema</td><td>{nome_app} - {ambiente}</td></tr>
            <tr><td class="label">Dominio</td><td>{dominio}</td></tr>
            <tr><td class="label">URL testada</td><td>{url}</td></tr>
            <tr><td class="label">Status</td><td style="color:red;"><strong>CRITICO</strong></td></tr>
            <tr><td class="label">Codigo HTTP</td><td>{codigo} - {titulo_erro}</td></tr>
            <tr><td class="label">Iniciado em</td><td>{timestamp}</td></tr>
        </table>
        <br>
        <p>Recomenda-se verificar:</p>
        <ul>
            <li>Logs do Nginx</li>
            <li>Status do PHP-FPM</li>
            <li>Conectividade com banco de dados</li>
            <li>Consumo de CPU e memoria</li>
            <li>Timeouts configurados no proxy reverso</li>
        </ul>
    </div>
    <div class="footer">dominio &bull; Monitoramento de Infraestrutura<br>Este e-mail foi enviado automaticamente.</div>
</div>
</body>
</html>
""".format(
        codigo=codigo, titulo_erro=titulo_erro, descricao_erro=descricao_erro,
        nome_app=nome_app, ambiente=ambiente, dominio=dominio, url=url, timestamp=timestamp
    )


def montar_html_resolvido(url, dominio, nome_app, ambiente, inicio_str, duracao_str):
    timestamp = datetime.now().strftime("%d/%m/%Y %H:%M:%S")

    return """
<html>
<head>
<style>
body {{ font-family: Arial, sans-serif; background-color: #f4f4f4; }}
.container {{ max-width: 700px; margin: auto; background-color: #ffffff; border-radius: 8px; overflow: hidden; border: 1px solid #dddddd; }}
.header {{ background-color: #2e7d32; color: white; padding: 20px; text-align: center; font-size: 24px; font-weight: bold; }}
.content {{ padding: 30px; color: #333333; }}
.alert-box {{ background-color: #eaf7ea; border-left: 6px solid #2e7d32; padding: 15px; margin: 20px 0; }}
.info-table {{ width: 100%; border-collapse: collapse; }}
.info-table td {{ padding: 10px; border-bottom: 1px solid #eeeeee; }}
.label {{ font-weight: bold; width: 180px; }}
.footer {{ background-color: #f5f5f5; padding: 15px; text-align: center; color: #777777; font-size: 12px; }}
</style>
</head>
<body>
<div class="container">
    <div class="header">&#9989; INCIDENTE RESOLVIDO</div>
    <div class="content">
        <h2>Servico normalizado</h2>
        <p>A aplicacao voltou a responder normalmente.</p>
        <div class="alert-box">
            <strong>Servico OK</strong><br>
            O dominio voltou a responder com sucesso (HTTP 2xx).
        </div>
        <table class="info-table">
            <tr><td class="label">Sistema</td><td>{nome_app} - {ambiente}</td></tr>
            <tr><td class="label">Dominio</td><td>{dominio}</td></tr>
            <tr><td class="label">URL testada</td><td>{url}</td></tr>
            <tr><td class="label">Status</td><td style="color:#2e7d32;"><strong>OK</strong></td></tr>
            <tr><td class="label">Incidente iniciado em</td><td>{inicio_str}</td></tr>
            <tr><td class="label">Resolvido em</td><td>{timestamp}</td></tr>
            <tr><td class="label">Duracao do incidente</td><td>{duracao_str}</td></tr>
        </table>
    </div>
    <div class="footer">dominio &bull; Monitoramento de Infraestrutura<br>Este e-mail foi enviado automaticamente.</div>
</div>
</body>
</html>
""".format(
        nome_app=nome_app, ambiente=ambiente, dominio=dominio, url=url,
        inicio_str=inicio_str, timestamp=timestamp, duracao_str=duracao_str
    )


### ==================== ENVIO ====================

def enviar_email(assunto, html):
    msg = MIMEText(html, "html", "utf-8")
    msg["Subject"] = assunto
    msg["From"] = REMETENTE
    msg["To"] = DESTINATARIO

    try:
        with smtplib.SMTP(RELAY, PORTA) as servidor:
            servidor.sendmail(REMETENTE, [DESTINATARIO], msg.as_string())
        print("E-mail enviado com sucesso: " + assunto)
    except Exception as erro:
        print("Erro ao enviar e-mail: " + str(erro))


### ==================== LOGICA PRINCIPAL ====================

def processar(dominio, codigo, url):
    nome_app, ambiente = identificar_aplicacao_e_ambiente(dominio)
    status_atual = "OK" if codigo.startswith("2") else "ERRO"

    estado = carregar_estado()
    registro_anterior = estado.get(dominio, {"status": "OK"})
    status_anterior = registro_anterior.get("status", "OK")

    agora = time.time()
    agora_str = datetime.now().strftime("%d/%m/%Y %H:%M:%S")

    # Sem mudanca de status -> nao faz nada (evita spam a cada execucao do cron)
    if status_atual == status_anterior:
        print("Sem mudanca de status para {} (continua {})".format(dominio, status_atual))
        return

    if status_atual == "ERRO":
        # Transicao OK -> ERRO: dispara incidente iniciado
        html = montar_html_incidente(url, dominio, codigo, nome_app, ambiente)
        assunto = "[CRITICO] {} ({}) - HTTP {}".format(nome_app, ambiente, codigo)
        enviar_email(assunto, html)

        estado[dominio] = {"status": "ERRO", "desde": agora, "desde_str": agora_str, "codigo": codigo}

    else:
        # Transicao ERRO -> OK: dispara incidente resolvido
        desde = registro_anterior.get("desde", agora)
        desde_str = registro_anterior.get("desde_str", "desconhecido")
        duracao_str = formatar_duracao(agora - desde)

        html = montar_html_resolvido(url, dominio, nome_app, ambiente, desde_str, duracao_str)
        assunto = "[RESOLVIDO] {} ({}) - Servico normalizado".format(nome_app, ambiente)
        enviar_email(assunto, html)

        estado[dominio] = {"status": "OK"}

    salvar_estado(estado)


def main():
    parser = argparse.ArgumentParser(description="Envia alerta por e-mail (incidente/resolvido)")
    parser.add_argument("--domain", help="Dominio afetado, ex: nps-hmg.dominio.com.br")
    parser.add_argument("--url", help="URL completa testada (opcional, tem prioridade sobre --domain)")
    parser.add_argument("--code", required=True, help="Codigo HTTP retornado, ex: 200, 500, 502, 000")
    args = parser.parse_args()

    if not args.domain and not args.url:
        parser.error("informe --domain ou --url")

    url = args.url or ("http://" + args.domain + "/")
    dominio = args.domain or url.split("//")[-1].split("/")[0]

    processar(dominio, args.code, url)


if __name__ == "__main__":
    try:
        main()
    except Exception:
        import traceback
        print("Erro inesperado ao executar relay-alert.py:")
        traceback.print_exc()
        raise
