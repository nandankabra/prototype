"""Environment settings. Generated local signing keys persist with the data volume."""
from pathlib import Path
import secrets
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import field_validator
from typing import Literal


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file='.env', extra='ignore')
    app_env: str = 'development'
    database_url: str = 'sqlite:///./data/bytecode.db'
    qdrant_url: str = 'http://localhost:6333'
    jwt_secret: str = ''
    llm_provider: str = 'mock'
    llm_api_key: str = ''
    llm_base_url: str = 'https://api.openai.com/v1'
    llm_model: str = 'gpt-4o-mini'
    ocr_provider: str = 'paddle'
    vector_provider: str = 'qdrant'
    enable_heavy_ml: bool = False
    match_threshold: float = 0.95
    review_threshold: float = 0.80
    upload_max_mb: int = 15
    data_dir: str = './data'
    hosted_mode: bool = False
    document_storage: Literal['local', 'database'] = 'local'
    warm_seed_on_startup: bool = True

    @field_validator('database_url')
    @classmethod
    def postgres_driver(cls, value: str) -> str:
        for prefix in ('postgres://', 'postgresql://'):
            if value.startswith(prefix):
                return 'postgresql+psycopg://' + value[len(prefix):]
        return value

    def signing_key(self) -> str:
        if self.hosted_mode and (not self.jwt_secret or not self.database_url.startswith('postgresql') or self.document_storage != 'database'):
            raise RuntimeError('Hosted deployments require JWT_SECRET, PostgreSQL, and database document storage')
        if self.jwt_secret:
            return self.jwt_secret
        path = Path(self.data_dir) / '.session-key'
        path.parent.mkdir(parents=True, exist_ok=True)
        try:
            with path.open('x') as handle:
                handle.write(secrets.token_hex(48))
            path.chmod(0o600)
        except FileExistsError:
            pass
        return path.read_text().strip()


settings = Settings()
Path(settings.data_dir).mkdir(parents=True, exist_ok=True)
