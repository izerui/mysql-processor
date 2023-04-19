# mysql-processor
mysql备份导出、导入

## 运行
1. 在根目录下创建 config.ini:
类似:
```ini
[global]
databases=bboss,billing,cloud_finance,cloud_sale,crm,customer_supply

[source]
db_host=106.75.143.56
db_port=3306
db_user=***
db_pass=***

[target]
db_host=10.96.202.178
db_port=3306
db_user=***
db_pass=***
```
2. 然后运行:
```python
python main.py
```

建议:
> 在进行同步之前，最好把目标库的binlog先关闭, windows 下请修改区域与语言设置，选中统一使用unicode编码