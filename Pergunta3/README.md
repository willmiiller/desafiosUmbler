## Cenário
Um cliente relata que os e-mails enviados pelo site dele estão caindo em spam ou não chegam ao destino. Você precisa investigar e orientar o cliente (que não é técnico).


**Onde verificar os logs de entrega no Exim**
Debian/Ubuntu: /var/log/exim4/
RHEL/CentOS: /var/log/exim/

## Como descobrir o ID da mensagem
Antes de rastrear o ciclo de vida no `mainlog`, você precisa do ID (formato `1uXyZ2-000AbC-1a`). Formas mais comuns de encontrá-lo:

## Buscando pelo endereço de e-mail (mais rápido)**
exigrep endereco@cliente.com /var/log/exim4/mainlog

## Investigação dos logs
Para investigar a entrega dos e-mails, o mainlog é o principal registro dos logs com os seguintes status:

## <= → recebida
2026-07-21 09:14:02 1uXyZ2-000AbC-1a <= cliente@dominio.com.br H=mail-relay.provedor.com [203.0.113.10] P=esmtp S=4521 id=abc123@dominio.com.br T="Confirmação de pedido"

## => → entregue com sucesso
2026-07-21 09:14:05 1uXyZ2-000AbC-1a => destinatario@gmail.com R=dnslookup T=remote_smtp H=gmail-smtp-in.l.google.com [142.250.0.27] X=TLS1.3 C="250 2.0.0 OK 1721552045 accepted"

## ** → falha permanente/bounce
2026-07-21 09:14:07 1uXyZ2-000AbC-1a ** destinatario@outlook.com R=dnslookup T=remote_smtp: SMTP error from remote mail server after end of data: host outlook-com.olc.protection.outlook.com [40.92.0.1]: 550 5.7.1 Unfortunately, messages from [198.51.100.5] weren't sent. Please contact your Internet service provider.

## == → falha temporária, nova tentativa
2026-07-21 09:14:09 1uXyZ2-000AbC-1a == destinatario@empresa.com.br R=dnslookup T=remote_smtp defer (-53): retry timeout exceeded; SMTP error from remote mail server after RCPT TO: host mx.empresa.com.br [198.18.0.20]: 421 4.7.0 Temporary rejection, try again later

## Completed → fila finalizada
2026-07-21 09:14:10 1uXyZ2-000AbC-1a Completed


**Como verificar se o IP está em blacklist**

## Descobrir o IP de saída
Acessar o site https://www.meuip.com.br/ para descobrir o seu IP

Caso não tenha interface grafica e for linux
curl ifconfig.me


## Consultar o ip do resultado em sites de blacklist
https://mxtoolbox.com/blacklists.aspx
https://multirbl.valli.org/
https://check.spamhaus.org/


## Como usar o scirpt audit_dns_email.py
**Instalar dnspython com o seguinte comanado - pip install dnspython**

**Rodar o script python3 audit_dns_email.py seudominio.com.br**
