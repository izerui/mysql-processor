import asyncio
import json
import os
import threading
import time
from datetime import datetime
from pathlib import Path
import configparser

from flask import Flask, request, jsonify, render_template
from flask_socketio import SocketIO, emit

# 导入现有的导出和导入功能
from src.dump import MyDump
from src.restore import MyRestore
from src.base import Mysql

app = Flask(__name__)
app.config['SECRET_KEY'] = 'mysql-processor-secret-key'
socketio = SocketIO(app, cors_allowed_origins="*")

# 全局变量存储活跃任务
active_tasks = {}

class TaskManager:
    """任务管理器，处理导出/导入任务"""

    def __init__(self, task_id, task_type):
        self.task_id = task_id
        self.task_type = task_type
        self.is_running = False
        self.progress = 0
        self.message = ""
        self.file_size = 0
        self.start_time = None

    def start_monitoring(self, file_path):
        """开始监控文件大小"""
        self.start_time = time.time()
        monitor_thread = threading.Thread(
            target=self._monitor_file_size,
            args=(file_path,)
        )
        monitor_thread.daemon = True
        monitor_thread.start()

    def _monitor_file_size(self, file_path):
        """监控文件大小变化"""
        last_size = 0
        while self.is_running:
            try:
                if os.path.exists(file_path):
                    current_size = os.path.getsize(file_path)
                    if current_size != last_size:
                        last_size = current_size
                        self.file_size = current_size
                        self._emit_progress({
                            'type': 'file_size',
                            'size': current_size,
                            'size_human': self._format_size(current_size)
                        })
                time.sleep(1)
            except Exception as e:
                self._emit_progress({
                    'type': 'error',
                    'message': f'监控文件时出错: {str(e)}'
                })
                break

    def _format_size(self, size_bytes):
        """格式化文件大小显示"""
        for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
            if size_bytes < 1024.0:
                return f"{size_bytes:.1f} {unit}"
            size_bytes /= 1024.0
        return f"{size_bytes:.1f} PB"

    def _emit_progress(self, data):
        """发送进度到WebSocket"""
        socketio.emit('task_progress', {
            'task_id': self.task_id,
            **data
        })

@app.route('/')
def index():
    """主页"""
    return render_template('index.html')

@app.route('/api/export', methods=['POST'])
def export_database():
    """导出数据库API"""
    try:
        data = request.json

        # 验证参数
        required_fields = ['host', 'user', 'password', 'databases', 'output_file']
        for field in required_fields:
            if field not in data:
                return jsonify({'error': f'缺少必要参数: {field}'}), 400

        # 生成任务ID
        task_id = f"export_{int(time.time())}"

        # 创建任务
        task = TaskManager(task_id, 'export')
        active_tasks[task_id] = task

        # 启动导出任务
        thread = threading.Thread(
            target=_run_export,
            args=(data, task)
        )
        thread.daemon = True
        thread.start()

        return jsonify({
            'task_id': task_id,
            'message': '导出任务已启动'
        })

    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/import', methods=['POST'])
def import_database():
    """导入数据库API"""
    try:
        data = request.json

        # 验证参数
        required_fields = ['host', 'user', 'password', 'input_file']
        for field in required_fields:
            if field not in data:
                return jsonify({'error': f'缺少必要参数: {field}'}), 400

        # 生成任务ID
        task_id = f"import_{int(time.time())}"

        # 创建任务
        task = TaskManager(task_id, 'import')
        active_tasks[task_id] = task

        # 启动导入任务
        thread = threading.Thread(
            target=_run_import,
            args=(data, task)
        )
        thread.daemon = True
        thread.start()

        return jsonify({
            'task_id': task_id,
            'message': '导入任务已启动'
        })

    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/task/<task_id>')
def get_task_status(task_id):
    """获取任务状态"""
    task = active_tasks.get(task_id)
    if not task:
        return jsonify({'error': '任务不存在'}), 404

    return jsonify({
        'task_id': task_id,
        'type': task.task_type,
        'is_running': task.is_running,
        'progress': task.progress,
        'message': task.message,
        'file_size': task.file_size
    })

def _run_export(data, task):
    """执行导出任务"""
    try:
        task.is_running = True
        task.message = "正在连接数据库..."
        task._emit_progress({'type': 'status', 'message': '正在连接数据库...'})

        # 创建MySQL连接
        mysql = Mysql(
            data['host'],
            data.get('port', 3306),
            data['user'],
            data['password']
        )

        # 创建导出器
        exporter = MyDump(mysql)

        # 准备参数
        databases = data['databases']
        if isinstance(databases, str):
            databases = [d.strip() for d in databases.split(',')]

        tables = data.get('tables')
        if tables:
            if isinstance(tables, str):
                tables = [t.strip() for t in tables.split(',')]

        output_file = data['output_file']

        # 确保输出目录存在
        os.makedirs(os.path.dirname(output_file), exist_ok=True)

        # 开始监控文件大小
        task.start_monitoring(output_file)

        task.message = "开始导出..."
        task._emit_progress({'type': 'status', 'message': f'开始导出数据库: {", ".join(databases)}'})

        # 执行导出
        success = exporter.export_dbs(databases, output_file, tables)

        if success:
            task.message = "导出完成"
            task._emit_progress({
                'type': 'complete',
                'message': '导出完成',
                'file_size': task.file_size,
                'file_path': output_file
            })
        else:
            raise Exception("导出失败")

    except Exception as e:
        task.message = f"导出失败: {str(e)}"
        task._emit_progress({
            'type': 'error',
            'message': str(e)
        })
    finally:
        task.is_running = False
        if task.task_id in active_tasks:
            del active_tasks[task.task_id]

def _run_import(data, task):
    """执行导入任务"""
    try:
        task.is_running = True
        task.message = "正在连接数据库..."
        task._emit_progress({'type': 'status', 'message': '正在连接数据库...'})

        # 创建MySQL连接
        mysql = Mysql(
            data['host'],
            data.get('port', 3306),
            data['user'],
            data['password']
        )

        # 创建导入器
        importer = MyRestore(
            mysql,
            max_allowed_packet=data.get('max_allowed_packet', '256M'),
            net_buffer_length=data.get('net_buffer_length', '65536')
        )

        input_file = data['input_file']

        if not os.path.exists(input_file):
            raise Exception(f"导入文件不存在: {input_file}")

        # 获取文件大小用于进度显示
        file_size = os.path.getsize(input_file)
        task.file_size = file_size

        task.message = "开始导入..."
        task._emit_progress({
            'type': 'status',
            'message': f'开始导入文件: {os.path.basename(input_file)} ({task._format_size(file_size)})'
        })

        # 执行导入
        success = importer.restore_db(input_file)

        if success:
            task.message = "导入完成"
            task._emit_progress({
                'type': 'complete',
                'message': '导入完成',
                'file_path': input_file
            })
        else:
            raise Exception("导入失败")

    except Exception as e:
        task.message = f"导入失败: {str(e)}"
        task._emit_progress({
            'type': 'error',
            'message': str(e)
        })
    finally:
        task.is_running = False
        if task.task_id in active_tasks:
            del active_tasks[task.task_id]

@socketio.on('connect')
def handle_connect():
    """WebSocket连接处理"""
    emit('connected', {'message': 'WebSocket已连接'})

@app.route('/api/config')
def get_config():
    """获取配置文件"""
    try:
        config = configparser.ConfigParser()
        config_path = Path(__file__).parent.parent / 'config.ini'

        if config_path.exists():
            config.read(config_path, encoding='utf-8')
        else:
            # 如果config.ini不存在，使用config.ini.sample
            config_path = Path(__file__).parent.parent / 'config.ini.sample'
            if config_path.exists():
                config.read(config_path, encoding='utf-8')
            else:
                # 使用默认配置
                config['global'] = {'databases': ''}
                config['source'] = {'db_host': 'localhost', 'db_port': '3306', 'db_user': '', 'db_pass': ''}
                config['target'] = {'db_host': 'localhost', 'db_port': '3306', 'db_user': '', 'db_pass': ''}

        return jsonify({
            'global': {
                'databases': config.get('global', 'databases', fallback=''),
                'tables': config.get('global', 'tables', fallback=''),
                'export_file': config.get('global', 'export_file', fallback='/tmp/mysql_backup.sql'),
                'import_file': config.get('global', 'import_file', fallback='/tmp/mysql_backup.sql')
            },
            'source': {
                'host': config.get('source', 'db_host', fallback='localhost'),
                'port': config.getint('source', 'db_port', fallback=3306),
                'user': config.get('source', 'db_user', fallback=''),
                'pass': config.get('source', 'db_pass', fallback='')
            },
            'target': {
                'host': config.get('target', 'db_host', fallback='localhost'),
                'port': config.getint('target', 'db_port', fallback=3306),
                'user': config.get('target', 'db_user', fallback=''),
                'pass': config.get('target', 'db_pass', fallback='')
            }
        })
    except Exception as e:
        return jsonify({
            'error': str(e),
            'global': {'databases': '', 'tables': '', 'export_file': '/tmp/mysql_backup.sql', 'import_file': '/tmp/mysql_backup.sql'},
            'source': {'host': 'localhost', 'port': 3306, 'user': '', 'pass': ''},
            'target': {'host': 'localhost', 'port': 3306, 'user': '', 'pass': ''}
        })

@socketio.on('disconnect')
def handle_disconnect():
    """WebSocket断开处理"""
    pass

def run_web_server(host='0.0.0.0', port=8000, debug=True):
    """运行Web服务器"""
    if debug:
        socketio.run(app, host=host, port=port, debug=debug, allow_unsafe_werkzeug=True)
    else:
        # 生产环境使用eventlet或gevent
        try:
            import eventlet
            eventlet.monkey_patch()
            socketio.run(app, host=host, port=port, debug=debug)
        except ImportError:
            try:
                import gevent
                from gevent import monkey
                monkey.patch_all()
                socketio.run(app, host=host, port=port, debug=debug)
            except ImportError:
                # 如果没有安装eventlet或gevent，允许使用Werkzeug
                socketio.run(app, host=host, port=port, debug=debug, allow_unsafe_werkzeug=True)

if __name__ == '__main__':
    run_web_server()
