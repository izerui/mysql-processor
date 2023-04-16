import os
from configparser import ConfigParser

from dump import MyDump, MyImport, Mysql

if __name__ == "__main__":
    config = ConfigParser()
    config.read('config.ini')
    source = Mysql(config.get('source', 'db_host'), config.get('source', 'db_port'), config.get('source', 'db_user'),
                   config.get('source', 'db_pass'))
    target = Mysql(config.get('target', 'db_host'), config.get('target', 'db_port'), config.get('target', 'db_user'),
                   config.get('target', 'db_pass'))
    databases = config.get('global', 'databases').split(',')
    dump_folder = 'dumps'
    if not os.path.exists(dump_folder):
        os.makedirs(dump_folder)
    for db in databases:
        sql_file = f'{dump_folder}/{db}.sql'

        # 导出生产rds01库
        print(f'---------------------------------------------> 从{source.db_host}导出: {db}')
        mydump = MyDump(source)
        mydump.export_dbs([db], sql_file)
        print(f'---------------------------------------------> 成功 从{source.db_host}导出: {db}')

        # 导入uat
        print(f'---------------------------------------------> 导入{target.db_host}: {db}')
        myimport = MyImport(target)
        myimport.import_sql(sql_file)
        print(f'---------------------------------------------> 成功 导入{target.db_host}: {db}')

        # 删除导出的文件
        print(f'--------------------------------------------->> 删除临时sql文件缓存: {sql_file}')
        os.remove(sql_file)
