from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
	database_url:str
	database_url_pooled:str
	jwt_secret_key:str
	jwt_algorithm:str
	access_token_expire_minutes:int
	storage_dir:str="./storage"

	model_config=SettingsConfigDict(
		env_file=".env",
		env_file_encoding="utf-8",
		extra="ignore"
	)

settings = Settings()