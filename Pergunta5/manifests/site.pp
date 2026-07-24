node default {

  include client_hosting

  client_hosting::vhost { 'cliente01':
    domain      => 'cliente01.local',
    db_name     => 'cliente01_wp',
    db_user     => 'cliente01',
    db_password => 'Senha123!',
  }

}