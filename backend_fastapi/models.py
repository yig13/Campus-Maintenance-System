from pydantic import BaseModel, Field
from typing import Optional


class SignupRequest(BaseModel):
    username: str = Field(min_length=1, max_length=100)
    password: str = Field(min_length=6, max_length=128)
    confirmPassword: Optional[str] = Field(default=None, max_length=128)
    userId: str = Field(min_length=1, max_length=100)
    dormBuilding: str = Field(min_length=1, max_length=100)
    phone: str = Field(min_length=1, max_length=32)


class LoginRequest(BaseModel):
    userId: str = Field(min_length=1, max_length=100)
    password: str = Field(min_length=1, max_length=128)


class CreateRepairRequest(BaseModel):
    dormBuilding: str = Field(min_length=1, max_length=100)
    dormFloor: Optional[int] = Field(default=None, ge=1, le=10)
    dormRoom: str = Field(max_length=64)
    category: str = Field(min_length=1, max_length=64)
    description: str = Field(min_length=1, max_length=50)
    imageUrl: Optional[str] = Field(default=None, max_length=2048)


class PartCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    price: float = Field(ge=0, allow_inf_nan=False)
    stock: int = Field(ge=0)


class PartUpdateRequest(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=100)
    price: Optional[float] = Field(default=None, ge=0, allow_inf_nan=False)
    stock: Optional[int] = Field(default=None, ge=0)


class PartUsage(BaseModel):
    partId: str = Field(min_length=1, max_length=100)
    quantity: int = Field(gt=0)


class UpdateRepairStatus(BaseModel):
    status: Optional[str] = None
    assignedTo: Optional[str] = None
    adminNote: Optional[str] = None
    workNote: Optional[str] = None
    priority: Optional[str] = None
    partsUsed: Optional[list[PartUsage]] = Field(default=None, max_length=100)


class UpdateProfileRequest(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=100)
    phone: Optional[str] = Field(default=None, max_length=32)
    userId: Optional[str] = Field(default=None, min_length=1, max_length=100)
    dormBuilding: Optional[str] = Field(default=None, max_length=100)
    dormRoom: Optional[str] = Field(default=None, max_length=64)


class ChangePasswordRequest(BaseModel):
    oldPassword: str = Field(min_length=1, max_length=128)
    newPassword: str = Field(min_length=6, max_length=128)
    confirmNewPassword: str = Field(min_length=1, max_length=128)


class CreateAnnouncementRequest(BaseModel):
    title: str = Field(min_length=1, max_length=100)
    content: str = Field(min_length=1, max_length=2000)


class UpdateSkillsRequest(BaseModel):
    skills: str = Field(max_length=500)


class CreateAdminRequest(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    userId: str = Field(min_length=1, max_length=100)
    password: str = Field(min_length=6, max_length=128)
    phone: str = Field(min_length=1, max_length=32)


class CreateRepairmanRequest(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    password: str = Field(min_length=6, max_length=128)
    userId: str = Field(min_length=1, max_length=100)
    dormBuilding: Optional[str] = Field(default=None, max_length=100)
    phone: str = Field(min_length=1, max_length=32)
    skills: str = Field(default="", max_length=500)


class EvaluateRequest(BaseModel):
    rating: int
