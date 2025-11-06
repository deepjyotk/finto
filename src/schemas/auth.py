from typing import Optional
from pydantic import BaseModel, EmailStr, Field
from uuid import UUID


class UserBase(BaseModel):
    username: str = Field(..., description="Unique username", example="johndoe")
    email: EmailStr = Field(..., description="User email address", example="john@example.com")
    full_name: str = Field(..., description="User's full name", example="John Doe")


class UserCreate(UserBase):
    password: str = Field(..., min_length=8, description="User password (min 8 characters)", example="SecurePass123!")

    model_config = {
        "json_schema_extra": {
            "example": {
                "username": "johndoe",
                "email": "john@example.com",
                "full_name": "John Doe",
                "password": "SecurePass123!"
            }
        }
    }


class UserLogin(BaseModel):
    username: str = Field(..., description="Username for login", example="johndoe")
    password: str = Field(..., description="User password", example="SecurePass123!")

    model_config = {
        "json_schema_extra": {
            "example": {
                "username": "johndoe",
                "password": "SecurePass123!"
            }
        }
    }


class UserResponse(UserBase):
    user_id: UUID = Field(..., description="Unique user identifier")

    model_config = {
        "from_attributes": True,
        "json_schema_extra": {
            "example": {
                "user_id": "123e4567-e89b-12d3-a456-426614174000",
                "username": "johndoe",
                "email": "john@example.com",
                "full_name": "John Doe"
            }
        }
    }


class TokenData(BaseModel):
    username: Optional[str] = None
    user_id: Optional[str] = None

