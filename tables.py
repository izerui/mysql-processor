import os
from configparser import ConfigParser

from dump import MyDump, Mysql

if __name__ == "__main__":
    config = ConfigParser()
    config.read('config.ini')
    source = Mysql(config.get('source', 'db_host'), config.get('source', 'db_port'), config.get('source', 'db_user'),
                   config.get('source', 'db_pass'))

    database = 'manufacture'
    tables = ['production_demand_material']
    dump_folder = 'dumps'
    sql_file = f'{dump_folder}/production_demand_material.sql'
    if not os.path.exists(dump_folder):
        os.makedirs(dump_folder)
    # 导出
    print(f'---------------------------------------------> 从{database}导出: {tables}')
    mydump = MyDump(source)
    mydump.export_tables(database, tables, sql_file)
    print(f'---------------------------------------------> 成功 从{source.db_host}导出: {database} {tables}')

