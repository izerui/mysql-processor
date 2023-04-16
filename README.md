# mysql 导出导入

在根目录下创建 config.ini:
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
然后运行:
```python
python main.py
```

建议:
> 在进行同步之前，最好把目标库的binlog先关闭