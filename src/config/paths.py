import os
from pathlib import Path

# 获取项目根目录
PROJECT_ROOT = Path(os.getenv('PROJECT_ROOT', Path(__file__).parent.parent.parent))

# 配置目录
CONFIG_DIR = Path(os.getenv('CONFIG_DIR', PROJECT_ROOT / 'config'))
PODCASTS_CONFIG = CONFIG_DIR / 'podcasts.yml'

# 数据目录
DATA_DIR = Path(os.getenv('DATA_DIR', PROJECT_ROOT / 'data'))

# 日志目录
LOGS_DIR = PROJECT_ROOT / 'logs'

# 确保基础目录存在
def ensure_base_directories():
    """确保基础目录存在"""
    directories = [
        CONFIG_DIR,
        DATA_DIR,
        LOGS_DIR
    ]
    for directory in directories:
        directory.mkdir(parents=True, exist_ok=True)

# 在导入时确保基础目录存在
ensure_base_directories()
