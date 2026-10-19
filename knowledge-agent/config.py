"""配置读取：把 .env 里的配置项集中解析成 CONFIG 对象。"""

import os

from dotenv import load_dotenv

# 占位符 key，视为未配置
PLACEHOLDER_KEY = "把你的key粘贴到这里"

# 项目根目录，相对路径都基于它解析
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# 优先加载 knowledge-agent/.env，如果不存在则加载项目根目录 .env
_env_path = os.path.join(BASE_DIR, ".env")
if not os.path.exists(_env_path):
    _parent_env = os.path.join(os.path.dirname(BASE_DIR), ".env")
    if os.path.exists(_parent_env):
        _env_path = _parent_env
load_dotenv(_env_path)



def _clean_path(value):
    """清理路径字符串：去掉首尾空白和成对引号。"""
    if value is None:
        return ""
    text = value.strip()
    if len(text) >= 2 and text[0] == text[-1] and text[0] in ("\"", "'"):
        text = text[1:-1].strip()
    return text


def _resolve_path(value):
    """把路径解析为绝对路径，相对路径以项目根目录为基准。"""
    text = _clean_path(value)
    if not text:
        return ""
    if os.path.isabs(text):
        return os.path.normpath(text)
    return os.path.normpath(os.path.join(BASE_DIR, text))


def _read_int(name, default):
    """读取整数配置项，非法值回退默认值。"""
    raw = os.getenv(name)
    if raw is None or not raw.strip():
        return default
    try:
        return int(raw.strip())
    except ValueError:
        return default


class Config:
    """运行期配置，字段全部来自 .env。"""

    def __init__(self):
        self.llm_base_url = _clean_path(os.getenv("LLM_BASE_URL")) or "https://api.deepseek.com"
        self.llm_api_key = _clean_path(os.getenv("LLM_API_KEY"))
        self.llm_model = _clean_path(os.getenv("LLM_MODEL")) or "deepseek-chat"
        default_data = os.path.normpath(os.path.join(BASE_DIR, "..", "输出资料存放处"))
        if not os.path.exists(default_data):
            default_data = os.path.join(BASE_DIR, "data_test")
        self.data_path = _resolve_path(os.getenv("DATA_PATH")) or default_data
        self.db_path = _resolve_path(os.getenv("DB_PATH")) or os.path.join(BASE_DIR, "db")
        self.top_k = _read_int("TOP_K", 5)

    @property
    def has_valid_key(self):
        """判断是否配置了可用的 LLM key。"""
        return bool(self.llm_api_key) and self.llm_api_key != PLACEHOLDER_KEY


CONFIG = Config()
