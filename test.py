from configparser import ConfigParser

from dump import Mysql

if __name__ == '__main__':
    config = ConfigParser()
    config.read('config.ini')
    source = Mysql(config.get('source', 'db_host'), config.get('source', 'db_port'), config.get('source', 'db_user'), config.get('source', 'db_pass'))
    target = Mysql(config.get('target', 'db_host'), config.get('target', 'db_port'), config.get('target', 'db_user'),
                   config.get('target', 'db_pass'))
    databases = config.get('global', 'databases').split(',')
    print(source, target, databases, config)