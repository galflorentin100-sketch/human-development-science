import os
from dataclasses import dataclass

VALID_ENVIRONMENTS={"development","test","production"}

@dataclass(frozen=True)
class Settings:
    environment:str="development"
    database_url:str|None=None
    database_path:str="company_os.db"
    log_level:str="INFO"

    def __post_init__(self):
        if self.environment not in VALID_ENVIRONMENTS:
            raise ValueError(f"invalid COMPANY_OS_ENV: {self.environment}")
        if self.environment=="production" and not self.database_url:
            raise ValueError("production requires DATABASE_URL")

    @classmethod
    def load(cls):
        return cls(
            os.getenv("COMPANY_OS_ENV","development"),
            os.getenv("DATABASE_URL"),
            os.getenv("COMPANY_OS_DB","company_os.db"),
            os.getenv("COMPANY_OS_LOG_LEVEL","INFO"),
        )
