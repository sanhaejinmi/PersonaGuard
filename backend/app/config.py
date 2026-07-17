from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    HOST: str = "127.0.0.1"
    PORT: int = 8000

    MODEL_NAME: str = "EXAONE"

    DEBUG: bool = True

    class Config:
        env_file = ".env"


settings = Settings()