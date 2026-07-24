# client_hosting

Módulo Puppet que provisiona, como código, um novo cliente em ambiente de
hospedagem compartilhada:

- **Nginx** na borda (reverse proxy) + **OpenLiteSpeed/LSPHP** como worker PHP.
- **Ambiente isolado por cliente**: usuário/grupo dedicado, diretórios próprios
  (`public_html`, `logs`) com permissões restritas (`0750`).
- **Virtual host** por domínio no Nginx e no OpenLiteSpeed, com **LSCache**
  habilitado (full-page cache).
- **WordPress** instalado via WP-CLI, já com o plugin **LiteSpeed Cache** ativo.

## Estrutura

```
client_hosting/
├── manifests/
│   ├── init.pp    # classe base: Nginx, OpenLiteSpeed, LSPHP, WP-CLI
│   └── vhost.pp    # defined type: provisiona 1 cliente
├── templates/
│   ├── nginx_client_vhost.conf.erb
│   └── litespeed_vhost.conf.erb
├── examples/site.pp
├── metadata.json
└── README.md
```

## Uso

```puppet
client_hosting::vhost { 'cliente01':
  domain      => 'cliente01.local',
  db_name     => 'cliente01_wp',
  db_user     => 'cliente01',
  db_password => 'Senha123!',
}
```

## Dependência

`puppetlabs/mysql` (>= 17.0.0) — instalada automaticamente pelo Vagrant (ver abaixo).

## Ambiente de laboratório (Vagrant)

O projeto sobe 3 VMs via `vagrant up`:

| VM | Papel | IP | Ambiente Puppet |
|---|---|---|---|
| `puppet` | Puppet Server | `192.168.122.100` | — |
| `node-1` | Agent | `192.168.122.101` | `production` |
| `node-2` | Agent | `192.168.122.102` | `staging` |

O Vagrantfile já automatiza:
- Instalação do Puppet Server/Agent em cada VM.
- Sincronização do módulo (`manifests/`, `templates/`, `examples/`,
  `README.md`, `metadata.json`) para
  `/etc/puppetlabs/code/environments/production/modules/client_hosting`
  a cada `vagrant up`/`vagrant provision`.
- Cópia do `examples/site.pp` para o `site.pp` do ambiente `production`.
- Instalação automática do módulo `puppetlabs-mysql`.

### Primeira execução

No servidor (`puppet`), assinar os certificados pendentes dos agents:
```bash
sudo /opt/puppetlabs/bin/puppetserver ca sign --all
```

Em cada node (`node-1`/`node-2`), aplicar o catálogo:
```bash
sudo /opt/puppetlabs/bin/puppet agent -t
```

## Simplificações assumidas

- Senha de banco em texto simples no `site.pp` de exemplo — em produção usar
  Hiera + `eyaml` ou um cofre de segredos.
- OpenLiteSpeed configurado via `vhconf.conf` gerado por template, em vez da
  API do WebAdmin Console.
- Senha de admin do WordPress fixa (`changeme`) — apenas para demonstração.
- Sem HTTPS — próximo passo natural seria integrar Certbot/Let's Encrypt.