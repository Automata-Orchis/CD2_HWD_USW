from enum import Enum
from typing import Optional
from pydantic import BaseModel


class Device(str, Enum):
    cpu = "cpu"
    gpu = "gpu"


# 한 신청서(application) 의 작업 상태. 코드 호환을 위해 이름은 ImageStatus 그대로 둔다.
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


class ApplicationInfo(BaseModel):
    application_id: str
    filename: str          # 원본 파일명(PDF 또는 이미지). server/data/<template>/ 안의 파일명.
    status: ImageStatus
    page_count: int        # 1 이면 단일 이미지, >=2 이면 다중 페이지(PDF 내부 페이지 수)
    template_name: Optional[str] = None


class ApplicationSummary(BaseModel):
    application_id: str
    status: ImageStatus
    page_count: int
    fields: list[FieldResult]


class Job(BaseModel):
    job_id: str
    model: str
    device: Device
    status: JobStatus
    field_spec: list[FieldSpec]
    applications: list[ApplicationInfo]


class FewshotPair(BaseModel):
    user: str
    assistant: str


class Template(BaseModel):
    name: str
    label: str
    field_spec: list[FieldSpec]
    fewshot: list[FewshotPair] = []


class AnalyzeRequest(BaseModel):
    application_ids: list[str]
    model: str
    device: Device
    template_name: str


class EditRequest(BaseModel):
    fields: list[FieldResult]


class SheetColumn(BaseModel):
    key: str
    label: str


class SheetRow(BaseModel):
    application_id: str
    values: dict[str, Optional[str]]


class Sheet(BaseModel):
    columns: list[SheetColumn]
    rows: list[SheetRow]


class CategoryStat(BaseModel):
    template_name: str          # = yml 파일 stem (예: "direct_payment")
    label: str                  # yml.label (UI 표시명)
    total: int
    done: int
    incomplete: int
    rate: float                 # 0.0 ~ 1.0, total=0 이면 0.0
