from sqlalchemy import (
    Column,
    Integer,
    String,
    DateTime,
    UUID,
    ForeignKeyConstraint,
    Boolean,
)
from sqlalchemy.dialects.postgresql import JSONB
from database import Base


class ProblemInstance(Base):
    __tablename__ = "problem_instance"

    project_name = Column(String, index=True, primary_key=True)
    name = Column(String, index=True, primary_key=True)
    config_id = Column(String, index=True, primary_key=True)
    code_version = Column(Integer, index=True, primary_key=True)
    context_shape = Column(JSONB)
    decision_shape = Column(JSONB)
    filter_tags = Column(JSONB)
    storage_path = Column(UUID)
    __table_args__ = (
        ForeignKeyConstraint(
            [config_id, project_name],
            [
                "instance_generation_config.config_id",
                "instance_generation_config.project_name",
            ],
        ),
        {},
    )


class InstanceGenerationConfig(Base):
    __tablename__ = "instance_generation_config"

    project_name = Column(String, index=True, primary_key=True)
    config_id = Column(String, index=True, primary_key=True, unique=True)
    hash = Column(String, unique=True)
    tags = Column(JSONB)
    storage_path = Column(UUID)


class ProblemDataset(Base):
    __tablename__ = "dataset"

    project_name = Column(String, index=True, primary_key=True)
    name = Column(String, index=True, primary_key=True)
    split = Column(String, index=True, primary_key=True)
    version = Column(Integer, index=True, primary_key=True)
    size = Column(Integer)
    generation_date = Column(DateTime)
    context_max_shape = Column(JSONB)
    decision_max_shape = Column(JSONB)
    selection_criteria = Column(JSONB)
    tags = Column(JSONB)
    storage_path = Column(UUID)


class RunStep(Base):
    __tablename__ = "run_step"

    project_name = Column(String, index=True, primary_key=True)
    run_id = Column(String, index=True, primary_key=True)
    training_step = Column(Integer, index=True, primary_key=True)
    parent_run_id = Column(String, nullable=True)
    # best = Column(Boolean)
    # last = Column(Boolean)
    # tags = Column(JSONB)
    # storage_path = Column(UUID)
