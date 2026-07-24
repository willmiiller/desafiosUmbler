
## Cenário

Um servidor de hospedagem está retornando erro 502 Bad Gateway para uma aplicação utilizando Nginx + PHP-FPM. O objetivo deste desafio é identificar possíveis causas do problema, propor um processo de diagnóstico e desenvolver uma solução automatizada para monitoramento dos serviços.

---

# Diagnóstico do Problema

Para identificar a causa de um erro 502 em um ambiente Nginx + PHP-FPM, os seguintes comandos podem ser utilizados:

## Possíveis Causas do Erro 502
### 1. Problemas de comunicação entre Proxy Reverso e Backend

Caso exista um proxy reverso na frente do Web Server da aplicação, problemas de comunicação entre o proxy e o backend podem causar erro 502.

Exemplos:

- Problemas de DNS.
- Falhas de conectividade entre os servidores.
- Firewall bloqueando a comunicação.
- Backend indisponível.


### 2. Problemas na Aplicação Backend

Falhas na aplicação podem impedir que uma resposta válida seja retornada ao servidor web.

Exemplos:

- Configuração incorreta do arquivo `.env`.
- Indisponibilidade do banco de dados.
- Falta de permissões nos diretórios da aplicação.
- Dependências ou serviços não iniciados.


### 3. Configurações de Timeout Inadequadas

Configurações de timeout inadequadas podem fazer com que o backend demore mais para responder do que o tempo configurado no proxy reverso ou no servidor web.

Exemplos:

- Consultas lentas ao banco de dados.
- Processamentos demorados na aplicação.
- Timeout configurado com valor muito baixo.
- Sobrecarga de recursos no servidor.


## Verificação dos serviços

Verificar se os serviços estão ativos:

```bash
systemctl status nginx
systemctl status php-fpm
```

ou, dependendo da distribuição Linux:

```bash
systemctl status php8.2-fpm
```

## Verificação de processos

```bash
ps aux | grep nginx
ps aux | grep php-fpm
```

## Verificação de portas

```bash
ss -tulpn
```

ou

```bash
netstat -tulpn
```

## Verificação de logs

Logs do Nginx:

```bash
tail -f /var/log/nginx/error.log
tail -f /var/log/nginx/access.log
```

Logs do PHP-FPM:

```bash
journalctl -u php-fpm -f
```

ou

```bash
tail -f /var/log/php-fpm/error.log
```

## Teste de conectividade HTTP

```bash
curl -I http://dominio.com
```

---

# Possíveis causas para o erro 502

## 1. Serviço PHP-FPM parado

O Nginx continua respondendo às requisições, porém não consegue encaminhá-las para o PHP-FPM.

### Como validar

```bash
systemctl status php-fpm
```

### Correção

```bash
systemctl restart php-fpm
```

---

## 2. Configuração incorreta entre Nginx e PHP-FPM

O Nginx pode estar apontando para um socket ou porta diferente daquela configurada no PHP-FPM.

### Como validar

Verificar os arquivos:

```bash
/etc/nginx/sites-enabled/
```

e

```bash
/var/www/php-fpm/pool.d/
```

### Correção

Garantir que a diretiva:

```nginx
fastcgi_pass
```

esteja utilizando a mesma porta ou socket definido no PHP-FPM.

---

## 3. Aplicação travada ou com consumo excessivo de recursos

Uma aplicação lenta ou travada pode fazer o PHP-FPM exceder tempos de resposta, gerando erro 502.

### Como validar

```bash
top
```

ou

```bash
htop
```

Além da análise dos logs da aplicação.

### Correção

Identificar gargalos na aplicação, otimizar consultas, corrigir processos bloqueados ou aumentar recursos do servidor.

---

# Como diferenciar a origem do problema

## Problema no servidor web (Nginx)

Sintomas:

- Serviço Nginx parado
- Erros no Nginx
- Porta 80 ou 443 indisponível

Validação:

```bash
systemctl status nginx
```

---

## Problema na aplicação

Sintomas:

- Erros 500 internos
- Exceções registradas em log
- Lentidão excessiva

Validação:

```bash
tail -f application.log
```

---

## Problema de rede

Sintomas:

- Timeouts
- Falha de comunicação entre serviços
- Problemas de DNS

Validação:

```bash
ping dominio.com
nslookup dominio.com
traceroute dominio.com
curl -I dominio.com
```

---

# Solução Implementada

Foram desenvolvidos dois scripts para automatizar a detecção e o tratamento de falhas.

---

# Script Shell - health_check.sh

O script `health_check.sh` foi desenvolvido para monitorar automaticamente a saúde do ambiente.

## Funcionalidades

- Verifica se o serviço Nginx está ativo.
- Verifica se o serviço PHP-FPM está ativo.
- Descobre automaticamente os domínios configurados no Nginx.
- Realiza testes HTTP para cada domínio encontrado.
- Registra os resultados em arquivo de log.
- Gera alertas quando alguma falha é detectada.
- Pode ser executado periodicamente via Cron.

## Exemplo de execução

```bash
./health_check.sh
```

## Exemplo de agendamento

Executar a cada 5 minutos:

```bash
*/5 * * * * /opt/scripts/health_che*k.sh >/dev/null 2>&1
```

---

# Script Python - relay-alert.py

O scpipt `relay-alert.py` foi desenvolvdo para realizar o envio de alerta* por e-mail quando uma aplicação a*resentar falhas HTTP.

## Funciona*idades

- Envio automático de e-ma*ls em formato HTML.
- Identificaçã* automática da aplicação baseada n* domínio informado.
- Identificaçã* automática do ambiente (Produção,Homologação, Desenvolvimento ou Staging).
- Tratamento de erros HTTP *a categoria 5xx.
- Geração de mens*gem detalhada contendo:
  - Aplica*ão afetada
  - Ambiente
  - Data e*hora do incidente
  - Código de er*o retornado
  - Descrição da falha*
## Exemplo de execução

```bash
p*thon3 relay-alert.py \
  --domain api1.dominio.com.br \
  --cod* 502
```

---

# Alertas Monitorad*s

Os scripts foram projetados para gerar alertas nos seguintes cenários:

- Nginx indisponível.
- PHP-F*M indisponível.
- Domínio sem resp*sta.
- Timeout de aplicação.
- Err*s HTTP:
  - 500 – Internal Server *rror
  - 502 – Bad Gateway
  - 503*– Service Unavailable
  - 504 – Ga*eway Timeout

---

# Conclusão

A solução proposta permite monitorar o ambiente Nginx + PHP-FPM, identificando falhas de infrestrutura e aplicação. A utilização do script Shell para verificações periódicas, combinada ao script Python para envio de alertas, reduz o tempo de diagnóstico e acelera a resposta a incidentes em ambientes produtivos.
