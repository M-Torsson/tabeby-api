from pydantic import BaseModel, EmailStr

class PatientCreate(BaseModel):
    name: str
    email: EmailStr

class PatientOut(BaseModel):
    id: int
    name: str
    email: EmailStr

    class Config:
        from_attributes = True


# ===== Schemas for Admin/Auth =====
class AdminCreate(BaseModel):
    name: str
    email: EmailStr
    password: str


class AdminOut(BaseModel):
    id: int
    name: str
    email: EmailStr

    class Config:
        from_attributes = True


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class TokenPair(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class RefreshRequest(BaseModel):
    refresh_token: str

