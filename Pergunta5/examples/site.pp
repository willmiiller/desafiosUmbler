# Exemplo de uso do módulo client_hosting
#
# Provisiona dois clientes em ambientes isolados na mesma
# infraestrutura de hospedagem compartilhada.

include client_hosting

client_hosting::vhost { 'cliente1':
  domain      => 'cliente1.com.br',
  db_password => Sensitive('S3nh4F0rte!'),
}

client_hosting::vhost { 'cliente2':
  domain      => 'cliente2.com.br',
  db_password => Sensitive('OutraS3nh4!'),
}
