import os
from dataclasses import dataclass
@dataclass(frozen=True)
class Settings:
    environment:str="development"
    database_url:str|None=None
    database_path:str="company_os.db"
    log_level:str="INFO"
    @classmethod
    def load(cls):
        return cls(os.getenv("COMPANY_OS_ENV","development"),os.getenv("DATABASE_URL"),os.getenv("COMPANY_OS_DB","company_os.db"),os.getenv("COMPANY_OS_LOG_LEVEL","INFO"))
