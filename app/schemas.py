from pydantic import BaseModel, Field


class LoginForm(BaseModel):
    username: str = Field(min_length=1, max_length=50)
    password: str = Field(min_length=1)


class RegisterForm(BaseModel):
    username: str = Field(min_length=3, max_length=50)
    password: str = Field(min_length=6)
    invite_token: str = Field(min_length=1)


class RateForm(BaseModel):
    value: int = Field(ge=0, le=10)


class AddGameForm(BaseModel):
    steam_appid: int
    name: str
    thumbnail_url: str = ""
    steam_url: str = ""
