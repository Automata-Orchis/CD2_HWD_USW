from enum import Enum
from typing import Optional
from pydantic import BaseModel


class Device(str, Enum):
    cpu = "cpu"
    gpu = "gpu"


class ImageStatus(str, Enum):
    blank = "blank"
    working = "working"
    done = "done"


class JobStatus(str, Enum):
    running = "running"
    stopped = "stopped"
    completed = "completed"


class FieldSpec(BaseModel):
    key: str
    label: str
    type: str = "text"


class FieldResult(BaseModel):
    key: str
    predicted: Optional[str] = None
    accuracy: Optional[float] = None
    edited: Optional[str] = None


class ImageInfo(BaseModel):
    image_id: str
    filename: str
    status: ImageStatus


class ImageSummary(BaseModel):
    image_id: str
    status: ImageStatus
    fields: list[FieldResult]


class Job(BaseModel):
    job_id: str
    model: str
    device: Device
    status: JobStatus
    field_spec: list[FieldSpec]
    images: list[ImageInfo]


class FewshotPair(BaseModel):
    user: str
    assistant: str


class Template(BaseModel):
    name: str
    label: str
    field_spec: list[FieldSpec]
    fewshot: list[FewshotPair] = []


class AnalyzeRequest(BaseModel):
    image_ids: list[str]
    model: str
    device: Device
    template_name: str


class EditRequest(BaseModel):
    fields: list[FieldResult]


class SheetColumn(BaseModel):
    key: str
    label: str


class SheetRow(BaseModel):
    image_id: str
    values: dict[str, Optional[str]]


class Sheet(BaseModel):
    columns: list[SheetColumn]
    rows: list[SheetRow]
