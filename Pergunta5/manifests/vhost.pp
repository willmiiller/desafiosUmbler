define client_hosting::vhost (
  String $domain,
  String $db_name,
  String $db_user,
  String $db_password,
) {

  $client_root = "/srv/clients/${title}"

  #################################################
  # USUÁRIO DO CLIENTE
  #################################################

  user { $title:
    ensure     => present,
    home       => $client_root,
    shell      => '/bin/bash',
    managehome => true,
  }

  #################################################
  # ESTRUTURA DE DIRETÓRIOS
  #################################################

  file { [
    $client_root,
    "${client_root}/public_html",
    "${client_root}/logs",
    "${client_root}/tmp",
  ]:
    ensure => directory,
    owner  => $title,
    group  => $title,
    mode   => '0755',
  }

  #################################################
  # BANCO DE DADOS
  #################################################

  mysql::db { $db_name:
    user     => $db_user,
    password => $db_password,
    host     => 'localhost',
    grant    => ['ALL'],
  }

  #################################################
  # NGINX VHOST
  #################################################

  file { "/etc/nginx/sites-available/${domain}.conf":
    ensure  => file,
    content => template('client_hosting/nginx_client_vhost.conf.erb'),
    notify  => Service['nginx'],
  }

  file { "/etc/nginx/sites-enabled/${domain}.conf":
    ensure => link,
    target => "/etc/nginx/sites-available/${domain}.conf",
    notify => Service['nginx'],
  }

  #################################################
  # DOWNLOAD DO WORDPRESS
  #################################################

  exec { "download-wordpress-${title}":
    command => "/usr/local/bin/wp core download --path=${client_root}/public_html --allow-root",
    path    => ['/usr/bin', '/usr/local/bin', '/bin'],
    creates => "${client_root}/public_html/wp-config-sample.php",
    require => [
      Exec['install-wp-cli'],
      File["${client_root}/public_html"],
    ],
  }

  #################################################
  # WP-CONFIG
  #################################################

  exec { "create-config-${title}":
    command => "/usr/local/bin/wp config create --path=${client_root}/public_html --dbname=${db_name} --dbuser=${db_user} --dbpass='${db_password}' --dbhost=localhost --allow-root",
    path    => ['/usr/bin', '/usr/local/bin', '/bin'],
    creates => "${client_root}/public_html/wp-config.php",
    require => Exec["download-wordpress-${title}"],
  }

  #################################################
  # INSTALAÇÃO WORDPRESS
  #################################################

  exec { "install-wordpress-${title}":
    command => "/usr/local/bin/wp core install --path=${client_root}/public_html --url=http://${domain} --title='${title}' --admin_user=admin --admin_password='Admin123!' --admin_email=admin@${domain} --allow-root && touch ${client_root}/public_html/.wp-installed",
    path    => ['/usr/bin', '/usr/local/bin', '/bin'],
    creates => "${client_root}/public_html/.wp-installed",
    require => Exec["create-config-${title}"],
  }

  #################################################
  # LS CACHE
  #################################################

  exec { "install-lscache-${title}":
    command => "/usr/local/bin/wp plugin install litespeed-cache --activate --path=${client_root}/public_html --allow-root",
    path    => ['/usr/bin', '/usr/local/bin', '/bin'],
    unless  => "/usr/local/bin/wp plugin is-installed litespeed-cache --path=${client_root}/public_html --allow-root",
    require => Exec["install-wordpress-${title}"],
  }

  #################################################
  # PERMISSÕES
  #################################################

  exec { "fix-permissions-${title}":
    command     => "/bin/chown -R ${title}:${title} ${client_root}",
    refreshonly => true,
    subscribe   => Exec["install-lscache-${title}"],
  }

}