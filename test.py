from configparser import ConfigParser

from dump import Mysql

if __name__ == '__main__':
    d = 'manufacture.demand_view,manufacture.pro_demand,manufacture.pro_demand_copy1,manufacture.pro_task,manufacture.xxxxxxxx'
    ds = d.split(',')
    # ignores = ''
    # for index, dsi in enumerate(ds):
    #     if index == 0:
    #         ignores = f'--ignore-table={dsi}'
    #     else:
    #         ignores = ignores + f' --ignore-table={dsi}'
    s = " --ignore-table=".join(ds)
    s = '--ignore-table=' + s + ' \\'
    print(s)