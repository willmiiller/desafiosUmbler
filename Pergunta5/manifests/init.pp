# == Class: client_hosting
#
# Infraestrutura base para hospedagem compartilhada
#
# - Nginx
# - OpenLiteSpeed
# - LSPHP
# - MariaDB
# - WP-CLI
# - PHP CLI
# - Estrutura de clientes
#

class client_hosting (
  String $lsphp_version    = '81',
  String $base_clients_dir = '/srv/clients',
) {

  #################################################
  # NGINX
  #################################################

  package { 'nginx':
    ensure => installed,
  }

  service { 'nginx':
    ensure  => running,
    enable  => true,
    require => Package['nginx'],
  }

  file { '/etc/nginx/sites-available':
    ensure  => directory,
    require => Package['nginx'],
  }

  file { '/etc/nginx/sites-enabled':
    ensure  => directory,
    require => Package['nginx'],
  }

  #################################################
  # MARIADB
  #################################################

  package { 'mariadb-server':
    ensure => installed,
  }

  service { 'mariadb':
    ensure  => running,
    enable  => true,
    require => Package['mariadb-server'],
  }

  #################################################
  # UTILITÁRIOS
  #################################################

  package {
    [
      'curl',
      'wget',
      'php-cli',
      'php-mysql',
      'tree',
    ]:
      ensure => installed,
  }

  #################################################
  # REPOSITÓRIO LITESPEED
  #################################################

  exec { 'add-litespeed-repo':
    command => '/usr/bin/wget -O - https://repo.litespeed.sh | bash',
    creates => '/etc/apt/sources.list.d/lst_debian_repo.list',
    path    => ['/usr/bin', '/bin'],
  }

  exec { 'apt-update-after-litespeed':
    command     => '/usr/bin/apt-get update',
    refreshonly => true,
    subscribe   => Exec['add-litespeed-repo'],
  }

  #################################################
  # OPENLITESPEED
  #################################################

  package { 'openlitespeed':
    ensure  => installed,
    require => [
      Exec['add-litespeed-repo'],
      Exec['apt-update-after-litespeed'],
    ],
  }

  service { 'lsws':
    ensure  => running,
    enable  => true,
    require => Package['openlitespeed'],
  }

  #################################################
  # PHP / LSPHP
  #################################################

  package { "lsphp${lsphp_version}":
    ensure  => installed,
    require => Package['openlitespeed'],
  }

  package {
    [
      "lsphp${lsphp_version}-mysql",
      "lsphp${lsphp_version}-curl",
      "lsphp${lsphp_version}-opcache",
    ]:
      ensure  => installed,
      require => Package["lsphp${lsphp_version}"],
  }

  #################################################
  # WP-CLI
  #################################################

  exec { 'install-wp-cli':
    command => '/usr/bin/curl -sO https://raw.githubusercontent.com/wp-cli/builds/gh-pages/phar/wp-cli.phar && chmod +x wp-cli.phar && mv wp-cli.phar /usr/local/bin/wp',
    creates => '/usr/local/bin/wp',
    path    => ['/usr/bin', '/bin'],
    require => [
      Package['curl'],
      Package['php-cli'],
    ],
  }

  #################################################
  # ESTRUTURA BASE DOS CLIENTES
  #################################################

  file { $base_clients_dir:
    ensure => directory,
    owner  => 'root',
    group  => 'root',
    mode   => '0755',
  }

}