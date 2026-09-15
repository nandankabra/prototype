"""Environment settings. Generated demo signing keys persist with the data volume."""
from pathlib import Path
import secrets
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file='.env', extra='ignore')
    app_env: str = 'demo'
    demo_mode: bool = True
    database_url: str = 'sqlite:///./data/bytecode.db'
    mock_gov_api_url: str = 'http://localhost:8001'
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

    def signing_key(self) -> str:
        if self.jwt_secret:
            return self.jwt_secret
        if not self.demo_mode:
            raise RuntimeError('JWT_SECRET is required outside demo mode')
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
