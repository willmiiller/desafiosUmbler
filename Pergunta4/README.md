## Objetivo

Este desafio tem como objetivo demonstrar conceitos fundamentais de conteinerização utilizando Docker e Docker Compose, abordando vantagens dos containers e o conceito de idempotência na administração de ambientes.

---

## Pergunta 1

### Qual a vantagem de usar containers em vez de configurar tudo manualmente no servidor?

A grande vantagem de usar containers é empacotar a aplicação em uma imagem contendo todas as bibliotecas, dependências e configurações necessárias para sua execução. Dessa forma, a aplicação fica abstraída do sistema operacional

Isso elimina problemas comuns como:

> "Na minha máquina funciona, mas no servidor não."

Com containers, o mesmo ambiente pode ser executado em qualquer lugar, seja no notebook do desenvolvedor, em homologação ou em produção.

### Benefícios

- Padronização dos ambientes
- Facilidade de deploy
- Isolamento de dependências
- Maior portabilidade
- Menor tempo de provisionamento

---

## Pergunta 2

### O que significa idempotência nesse contexto?

Idempotência significa que um comando pode ser executado várias vezes e o resultado final permanecerá o mesmo, sem criar indisponibildiade.

### O que acontece se `docker compose up` for executado duas vezes?

Quando executamos:

```bash
docker compose up
```

em um ambiente já configurado, o Docker Compose verifica o estado atual dos containers e compara com a definição existente no arquivo:

```yaml
docker-compose.yml
```

Se nenhuma alteração for identificada:

- Os containers continuam em execução.
- Nenhum recurso é duplicado.
- O ambiente permanece o mesmo.

Caso algum paramentro  no arquivo .yml tenha sido modificada (imagem, variáveis de ambiente, volumes ou redes,etc), apenas os componentes impactados serão recriados ou atualizados.

---

# Nginx + PHP-FPM + MariaDB (Docker Compose)

Ambiente de desenvolvimento local com **Nginx**, **PHP-FPM** e **MariaDB**, orquestrado via `docker-compose.yml`. O Nginx serve um `index.php` com uma página de status estilizada (tema Umbler), que testa em tempo real a conexão de cada serviço com o banco. Os dados do MariaDB persistem entre restarts através de um volume nomeado.

## Stack

| Serviço  | Imagem                                          | Porta (host)   |
|----------|---------------------------------------------------|----------------|
| Nginx    | build própria (`nginx:stable-alpine` + config)    | 8080           |
| PHP-FPM  | build própria (`php:8.3-fpm-alpine` + `mysqli`)   | interna (9000) |
| MariaDB  | build própria (`mariadb:11` + schema embutido)     | interna (3306) |

> Todos os três serviços usam **imagens próprias** (`nginx/Dockerfile`, `php/Dockerfile`, `db/Dockerfile`) em vez das imagens oficiais puras:
> - O Nginx já vem com o `default.conf` embutido na imagem.
> - O PHP-FPM já vem com a extensão `mysqli` instalada.
> - O MariaDB já vem com `db/init.sql` copiado para dentro da imagem (não depende de bind mount do host).

## Estrutura do projeto

```
.
├── docker-compose.yml
├── nginx/
│   ├── Dockerfile
│   └── default.conf
├── php/
│   └── Dockerfile
├── db/
│   ├── Dockerfile
│   └── init.sql
├── src/
│   └── index.php
├── .gitignore
└── README.md
```

## Como subir o ambiente

```bash
docker compose up -d --build
```

O `--build` é necessário na primeira vez (e sempre que você alterar o `Dockerfile` ou o `default.conf` do Nginx) para gerar a imagem customizada. Em subidas seguintes sem alterações, `docker compose up -d` sozinho já reaproveita a imagem existente.

Acesse: [http://localhost:8080](http://localhost:8080)

Você deve ver a página de status do ambiente, com três cards (Nginx, PHP-FPM, MariaDB) confirmando se cada serviço está de pé — o card do MariaDB testa uma conexão real via `mysqli`.

## Persistência de dados

Os dados do MariaDB são armazenados no volume nomeado `mariadb-data`, então sobrevivem a `docker compose down` e restarts dos containers. Para apagar os dados por completo:

```bash
docker compose down -v
```

### Testando a persistência na prática

A própria página em `http://localhost:8080` tem um formulário de teste: você grava mensagens numa tabela `mensagens` e confere se elas sobrevivem a um restart dos containers. A tabela é garantida de duas formas independentes:
- pelo `db/init.sql`, executado pela imagem do MariaDB na primeira inicialização do volume;
- por um `CREATE TABLE IF NOT EXISTS` que o próprio `index.php` executa a cada carregamento, como rede de segurança caso o volume já existisse antes desse script.

```bash
# 1. grave uma ou mais mensagens pela interface web

# 2. derrube os containers SEM remover o volume
docker compose down

# 3. suba de novo
docker compose up -d

# 4. recarregue http://localhost:8080 — as mensagens devem continuar lá
```

Se quiser confirmar que a persistência realmente falha sem o volume, rode `docker compose down -v` (remove o volume) e suba de novo: a tabela é recriada vazia, e as mensagens antigas somem — isso é o comportamento esperado, e serve como controle negativo do teste.

> O script `db/init.sql` (copiado para dentro da imagem em `db/Dockerfile`) só roda automaticamente quando o volume do MariaDB está **vazio** (primeira inicialização) — isso é um comportamento da imagem oficial do MariaDB, não tem como contornar via Dockerfile. Se você já tinha subido o banco antes com uma versão anterior deste projeto, rode `docker compose down -v` uma vez para forçar a recriação com a tabela `mensagens`. Depois disso, `docker compose up -d --build` normal já mantém tudo consistente.

### Sobre o formulário (Post/Redirect/Get)

Depois de gravar uma mensagem, o `index.php` responde com um **redirect** (`?gravado=1`) em vez de renderizar a página direto no mesmo `POST`. Isso segue o padrão Post/Redirect/Get: evita que um F5 na página reenvie o mesmo formulário e crie registros duplicados. Há também um fallback via `<meta http-equiv="refresh">` + JavaScript, caso o `header('Location')` não possa ser usado (ex: algum caractere sendo enviado antes da tag `<?php` do arquivo).

## Credenciais padrão do banco

| Variável              | Valor          |
|------------------------|----------------|
| `MYSQL_DATABASE`       | `appdb`        |
| `MYSQL_USER`           | `appuser`      |
| `MYSQL_PASSWORD`       | `apppassword`  |
| `MYSQL_ROOT_PASSWORD`  | `rootpassword` |

> ⚠️ Altere essas credenciais antes de qualquer uso além de desenvolvimento local. O ideal é movê-las para um arquivo `.env` (já incluído no `.gitignore`).

## Parar o ambiente

```bash
docker compose down
```

## Comandos úteis

```bash
# Ver logs de um serviço específico
docker compose logs -f nginx

# Entrar no container do PHP
docker compose exec php sh

# Entrar no MariaDB via CLI
docker compose exec mariadb mariadb -u appuser -p appdb
```

---

**Cobre:** Docker · cultura DevOps

---
## Conceitos Aprendidos

- Conteinerização
- Isolamento de aplicações
- Docker
- Docker Compose
- Idempotência
- Infraestrutura como Código (IaC)
- Automação de ambientes

