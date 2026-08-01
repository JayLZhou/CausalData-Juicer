from pydantic_settings import BaseSettings


class AppConfig(BaseSettings):
    app_name: str = 'svc'
    max_retries: int = 3
    debug: bool = False


def load_config(**overrides):
    return AppConfig(**overrides)