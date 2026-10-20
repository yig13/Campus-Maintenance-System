from pydantic import BaseModel
from typing import Optional


class SignupRequest(BaseModel):
    username: str
    password: str
    confirmPassword: Optional[str] = None
    userId: str
    dormBuilding: str
    phone: str


class LoginRequest(BaseModel):
    userId: str
    password: str


class CreateRepairRequest(BaseModel):
    dormBuilding: str
    dormRoom: str
    category: str
    description: str
    priority: str = "normal"
    imageUrl: Optional[str] = None


class PartCreateRequest(BaseModel):
    name: str
    price: float
    stock: int


class PartUpdateRequest(BaseModel):
    name: Optional[str] = None
    price: Optional[float] = None
    stock: Optional[int] = None


class PartUsage(BaseModel):
    partId: str
    quantity: int


class UpdateRepairStatus(BaseModel):
    status: Optional[str] = None
    assignedTo: Optional[str] = None
    adminNote: Optional[str] = None
    workNote: Optional[str] = None
    priority: Optional[str] = None
    partsUsed: Optional[list[PartUsage]] = None


class UpdateProfileRequest(BaseModel):
    name: Optional[str] = None
    phone: Optional[str] = None
    userId: Optional[str] = None
    dormBuilding: Optional[str] = None
    dormRoom: Optional[str] = None


class ChangePasswordRequest(BaseModel):
    oldPassword: str
    newPassword: str
    confirmNewPassword: str


class CreateAnnouncementRequest(BaseModel):
    title: str
    content: str


class UpdateSkillsRequest(BaseModel):
    skills: str

class CreateAdminRequest(BaseModel):
    name: str
    userId: str
    password: str
    phone: str

class CreateRepairmanRequest(BaseModel):
    name: str
    password: str
    userId: str
    dormBuilding: Optional[str] = None
    phone: str
    skills: str = ""

class EvaluateRequest(BaseModel):
    rating: int
