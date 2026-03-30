import json
import uuid
from datetime import datetime

from pydantic import BaseModel, model_validator


class BaseAlongsideFile(BaseModel):
    @model_validator(mode="before")
    @classmethod
    def validate_to_json(cls, value):
        if isinstance(value, str):
            return cls(**json.loads(value))
        return value


class InstanceKey(BaseModel):
    project_name: str
    name: str
    config_id: str
    code_version: int


class DatasetKey(BaseModel):
    name: str
    split: str
    version: int


class ProblemInstance(BaseAlongsideFile):
    name: str
    config_id: str
    code_version: int
    context_shape: dict
    decision_shape: dict
    filter_tags: dict
    storage_path: uuid.UUID


class ProblemInstanceFilter(BaseModel):
    limit: int = 100
    offset: int | None = (None,)
    cursor: str | None = None
    name_like: str | None = None
    config_id: str | None = None
    version: int | None = None
    min_version: int | None = None
    max_version: int | None = None
    date_filters: dict[str, tuple[datetime, datetime]] | None = None
    tag_filters: dict | None = None
    count: bool = False


class InstancesPage(BaseModel):
    items: list[ProblemInstance]
    limit: int
    offset: int | None = None
    next_cursor: str | None = None
    total_count: int | None = None


class InstanceGenerationConfig(BaseAlongsideFile):
    config_id: str
    hash: str
    tags: dict
    storage_path: uuid.UUID


class Dataset(BaseAlongsideFile):
    name: str
    split: str
    version: int
    size: int
    generation_date: datetime
    context_max_shape: dict
    decision_max_shape: dict
    selection_criteria: dict
    tags: dict
    storage_path: uuid.UUID


class RunStep(BaseAlongsideFile):
    project_name: str
    run_id: str
    training_step: int
    parent_run_id: str | None = None
    # best: bool
    # last: bool
    # tags: dict
    # storage_path: uuid.UUID
