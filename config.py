from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    project_name: str = "FVR Local Server"
    debug: bool = True
    api_str: str = ""
    root_path: str = "/local"

    # POS gateway (fvr-pos)
    pos_url: str = "http://localhost:8003"
    pos_token: str = ""

    # Default printer config (used when printer is not resolved from POS)
    printer_vid: str = "0x1fc9"
    printer_pid: str = "0x2016"
    printer_ip: str = ""
    printer_port: int = 9100

    counter: str = "xxx"
    cashier: str = "xxx"


settings = Settings()
