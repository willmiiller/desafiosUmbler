#!/usr/bin/env bash
#
# health_check.sh
# Verifica se o Nginx e o PHP-FPM estao ativos e respondendo.
# Descobre automaticamente TODOS os dominios (server_name) configurados
# no Nginx e testa cada um via HTTP.
# Registra o resultado em log e opcionalmente envia um alerta (webhook).
#
# Uso:
#   ./health_check.sh
#
# Exemplo de crontab (a cada 5 minutos):
#   */5 * * * * /caminho/para/health_check.sh >> /dev/null 2>&1

set -euo pipefail

### ==================== CONFIGURACAO ====================

LOG_FILE="/var/log/health_check.log"

NGINX_SERVICE="nginx"
PHP_FPM_SERVICE="php-fpm"   # ajuste para o nome real, ex: php8.2-fpm

# Pastas onde o Nginx guarda as configuracoes dos sites (ajuste se necessario)
NGINX_CONF_PATHS=(
    "/etc/nginx/sites-enabled"
    "/etc/nginx/conf.d"
)

HTTP_TIMEOUT=5

# Webhook opcional para alerta (Slack, Discord, etc). Deixe vazio para desativar.
ALERT_WEBHOOK_URL=""

ALERT_COOLDOWN=300
ALERT_STATE_FILE="/tmp/health_check_alert_state"

### ========================================================

timestamp() { date '+%Y-%m-%d %H:%M:%S'; }

log() {
    local level="$1"; shift
    echo "$(timestamp) [$level] $*" | tee -a "$LOG_FILE"
}

service_is_active() {
    systemctl is-active --quiet "$1"
}

# Varre os arquivos de config do Nginx e extrai todos os server_name (dominios)
discover_domains() {
    local paths=()
    for p in "${NGINX_CONF_PATHS[@]}"; do
        [[ -d "$p" ]] && paths+=("$p")
    done
    [[ ${#paths[@]} -eq 0 ]] && return 0

    grep -rhoE 'server_name\s+[^;]+;' "${paths[@]}" 2>/dev/null \
        | sed -E 's/server_name\s+//; s/;//' \
        | tr ' ' '\n' \
        | grep -v '^_$' \
        | grep -v '^\s*$' \
        | sort -u
}

http_is_responding() {
    local url="$1"
    # -L segue redirecionamentos (ex: HTTP -> HTTPS) e retorna o codigo final
    # -k ignora erro de certificado (util em ambientes de homologacao/self-signed)
    curl -s -L -k -o /dev/null -w '%{http_code}' --max-time "$HTTP_TIMEOUT" "$url" || echo "000"
}

# Considera "saudavel" apenas respostas 2xx (200-299)
is_healthy_code() {
    local code="$1"
    [[ "$code" =~ ^2[0-9][0-9]$ ]]
}

# Caminho do script de alerta em Python (ajuste se estiver em outro lugar)
RELAY_ALERT_SCRIPT="/root/relay-alert_v2.py"

# Chama o relay-alert.py passando o dominio e o codigo HTTP encontrado
call_relay_alert() {
    local domain="$1"
    local code="$2"

    if [[ ! -f "$RELAY_ALERT_SCRIPT" ]]; then
        log "WARN" "relay-alert_v2.py nao encontrado em $RELAY_ALERT_SCRIPT"
        return 0
    fi

    if python3 "$RELAY_ALERT_SCRIPT" --domain "$domain" --code "$code" >> "$LOG_FILE" 2>&1; then
        log "INFO" "relay-alert_v2.py verificado para $domain (HTTP $code)"
    else
        log "ERROR" "Falha ao executar relay-alert_v2.py para $domain"
    fi
}

send_alert() {
    local message="$1"

    if [[ -z "$ALERT_WEBHOOK_URL" ]]; then
        log "WARN" "Alerta nao enviado (webhook nao configurado): $message"
        return 0
    fi

    if [[ "$ALERT_COOLDOWN" -gt 0 && -f "$ALERT_STATE_FILE" ]]; then
        local last_alert now diff
        last_alert=$(cat "$ALERT_STATE_FILE" 2>/dev/null || echo 0)
        now=$(date +%s)
        diff=$(( now - last_alert ))
        [[ "$diff" -lt "$ALERT_COOLDOWN" ]] && return 0
    fi

    curl -s -X POST -H 'Content-Type: application/json' \
        -d "{\"text\": \"[health_check] $message\"}" \
        "$ALERT_WEBHOOK_URL" > /dev/null 2>&1 || log "ERROR" "Falha ao enviar alerta"

    date +%s > "$ALERT_STATE_FILE"
}

### ==================== VERIFICACOES ====================

STATUS_OK=true
FAILURES=()

# 1. Nginx ativo
if service_is_active "$NGINX_SERVICE"; then
    log "INFO" "Nginx esta ativo"
else
    log "ERROR" "Nginx NAO esta ativo"
    STATUS_OK=false
    FAILURES+=("Nginx inativo")
fi

# 2. PHP-FPM ativo
if service_is_active "$PHP_FPM_SERVICE"; then
    log "INFO" "PHP-FPM esta ativo"
else
    log "ERROR" "PHP-FPM NAO esta ativo"
    STATUS_OK=false
    FAILURES+=("PHP-FPM inativo")
fi

# 3. Descobre todos os dominios configurados no Nginx
mapfile -t DOMAINS < <(discover_domains)

if [[ ${#DOMAINS[@]} -eq 0 ]]; then
    log "WARN" "Nenhum server_name encontrado, testando apenas localhost"
    DOMAINS=("127.0.0.1")
fi

log "INFO" "Dominios encontrados (${#DOMAINS[@]}):"
for domain in "${DOMAINS[@]}"; do
    log "INFO" "  - $domain"
done

# 4. Testa HTTP de cada dominio encontrado
log "INFO" "Testando dominios..."
printf -v SEP '%.0s-' {1..60}
echo "$SEP" | tee -a "$LOG_FILE"
printf "%-45s %-10s\n" "DOMINIO" "STATUS" | tee -a "$LOG_FILE"
echo "$SEP" | tee -a "$LOG_FILE"

for domain in "${DOMAINS[@]}"; do
    url="http://${domain}/"
    code=$(http_is_responding "$url")
    if is_healthy_code "$code"; then
        printf "%-45s %-10s\n" "$domain" "OK ($code)" | tee -a "$LOG_FILE"
        call_relay_alert "$domain" "$code"
    elif [[ "$code" == "000" ]]; then
        printf "%-45s %-10s\n" "$domain" "SEM RESPOSTA" | tee -a "$LOG_FILE"
        STATUS_OK=false
        FAILURES+=("$domain sem resposta")
        call_relay_alert "$domain" "$code"
    elif [[ "$code" -ge 500 ]]; then
        printf "%-45s %-10s\n" "$domain" "ERRO ($code)" | tee -a "$LOG_FILE"
        STATUS_OK=false
        FAILURES+=("$domain retornou HTTP $code")
        call_relay_alert "$domain" "$code"
    else
        printf "%-45s %-10s\n" "$domain" "ERRO ($code)" | tee -a "$LOG_FILE"
        STATUS_OK=false
        FAILURES+=("$domain retornou HTTP $code")
        call_relay_alert "$domain" "$code"
    fi
done
echo "$SEP" | tee -a "$LOG_FILE"

### ==================== RESULTADO ====================

if [[ "$STATUS_OK" == true ]]; then
    log "INFO" "Health check OK - tudo certo"
    exit 0
else
    ALERT_MSG="Falha detectada: $(IFS='; '; echo "${FAILURES[*]}")"
    log "ERROR" "Health check FALHOU - $ALERT_MSG"
    send_alert "$ALERT_MSG"
    exit 1
fi
