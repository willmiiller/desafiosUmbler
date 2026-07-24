# client_hosting — módulo Puppet de provisionamento de clientes

Módulo que provisiona, como código, um novo cliente em um ambiente de
hospedagem compartilhada, atendendo aos requisitos da Pergunta 5:

- Stack web: **Nginx** na borda (reverse proxy) + **OpenLiteSpeed/LSPHP** como worker PHP.
- **Ambiente isolado do cliente**: usuário/grupo Linux dedicado, estrutura de
  diretórios própria (`public_html`, `logs`) e permissões restritas (`0750`).
- **Virtual host** dedicado ao domínio do cliente, tanto no Nginx (borda)
  quanto no OpenLiteSpeed (worker), com **LSCache habilitado** para full-page cache.
- **WordPress instalado** via WP-CLI, já com o plugin **LiteSpeed Cache**
  instalado e ativo (full-page cache operante desde o primeiro acesso).

## Estrutura

```
client_hosting/
├── manifests/
│   ├── init.pp      # classe base: instala Nginx, OpenLiteSpeed, LSPHP, WP-CLI
│   └── vhost.pp      # defined type: provisiona 1 cliente (parametrizado)
├── templates/
│   ├── nginx_client_vhost.conf.erb      # vhost Nginx (borda -> proxy)
│   └── litespeed_vhost.conf.erb         # vhost OpenLiteSpeed (worker + LSCache)
├── examples/
│   └── site.pp        # exemplo de uso com 2 clientes
└── README.md
```

## Como funciona o fluxo

1. `include client_hosting` instala a stack base uma única vez no servidor
   (Nginx, OpenLiteSpeed, LSPHP, WP-CLI).
2. Para cada novo cliente, chama-se o defined type:

```puppet
client_hosting::vhost { 'cliente1':
  domain      => 'cliente1.com.br',
  db_password => Sensitive('senha-forte'),
}
```

O `title` (`cliente1`) vira o identificador do cliente — nome do usuário
Linux, nome do banco (`wp_cliente1`) e diretório home
(`/srv/clients/cliente1`) — mas todos esses valores podem ser
sobrescritos individualmente se necessário.

3. O defined type então, em ordem, com dependências explícitas (`require`/`notify`):
   - cria usuário/grupo isolado;
   - cria a estrutura de diretórios com permissões restritas;
   - gera o vhost do Nginx e o habilita (`sites-enabled`);
   - gera o vhost do OpenLiteSpeed com LSPHP como worker e o LSCache
     habilitado para full-page cache;
   - cria o banco de dados MySQL do cliente;
   - baixa, configura e instala o WordPress via WP-CLI;
   - instala e ativa o plugin **LiteSpeed Cache**.

## Rodar o exemplo

```bash
puppet apply --modulepath=/etc/puppetlabs/code/environments/production/modules examples/site.pp
```

(assumindo o módulo copiado para o `modulepath` do Puppet, ex.:
`/etc/puppetlabs/code/environments/production/modules/client_hosting`)

## Dependências externas

O módulo assume a presença do módulo `puppetlabs/mysql` no ambiente
(usado apenas para o resource `mysql::db`). Isso pode ser instalado com:

```bash
puppet module install puppetlabs-mysql
```

## Decisões de design / simplificações assumidas

Este é um projeto **simplificado**, propositalmente enxuto para
demonstrar a lógica de provisionamento como código. Em um cenário
produtivo, alguns pontos mereceriam evolução:

- **Segredos**: a senha do banco usa o tipo `Sensitive`, mas em produção
  o ideal é buscar via Hiera + `eyaml` ou um cofre de segredos (Vault),
  em vez de literal no manifesto.
- **OpenLiteSpeed via arquivo**: o OLS normalmente é administrado pelo
  WebAdmin Console/API própria; aqui geramos o `vhconf.conf` direto por
  ser a abordagem suportada e mais "Puppet-idiomática" para
  infra-como-código, mas outra opção seria automatizar via API REST do
  WebAdmin.
  - **Senha de admin do WordPress**: fixa (`changeme`) só para fins de
    exemplo — em produção deve ser gerada aleatoriamente por cliente e
    entregue de forma segura.
- **HTTPS**: não incluído aqui por simplicidade; o próximo passo natural
  seria integrar Certbot/Let's Encrypt por domínio.


#server
sudo /opt/puppetlabs/bin/puppetserver ca sign --all

#agent
sudo /opt/puppetlabs/bin/puppet agent -t