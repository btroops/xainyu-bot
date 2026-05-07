from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    api_key: str
    model_name: str = "qwen-max"
    model_base_url: str = "https://dashscope.aliyuncs.com/compatible-mode/v1"
    cookies_str: str
    log_level: str = "INFO"
    heartbeat_interval: int = 15
    heartbeat_timeout: int = 5
    token_refresh_interval: int = 3600
    token_retry_interval: int = 300
    manual_mode_timeout: int = 3600
    message_expire_time: int = 300000
    toggle_keywords: str = "。"
    simulate_human_typing: bool = False
    db_path: str = "data/chat_history.db"

    model_config = {"env_file": ".env", "extra": "ignore"}