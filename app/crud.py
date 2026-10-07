import base64
import json

from botocore.exceptions import ClientError
from fastapi import UploadFile
from sqlalchemy.orm import Session
from sqlalchemy import or_, and_, DateTime, Float
import models, schemas
from datetime import datetime
import s3


def get_projects(db: Session):

    # Instances
    instance_projects = db.query(models.ProblemInstance.project_name).distinct().all()
    instance_projects = sorted({p[0] for p in instance_projects if p[0]})

    # Configs
    config_projects = (
        db.query(models.InstanceGenerationConfig.project_name).distinct().all()
    )
    config_projects = sorted({p[0] for p in config_projects if p[0]})

    # Datasets
    dataset_projects = db.query(models.ProblemDataset.project_name).distinct().all()
    dataset_projects = sorted({p[0] for p in dataset_projects if p[0]})

    # runs
    run_projects = db.query(models.RunStep.project_name).distinct().all()
    run_projects = sorted({p[0] for p in run_projects if p[0]})

    return {
        "instances": instance_projects,
        "configs": config_projects,
        "datasets": dataset_projects,
        "runs": run_projects,
    }


def get_instance(
    db: Session, project_name: str, name: str, config_id: str, code_version: int
):
    return db.query(models.ProblemInstance).get(
        (project_name, name, config_id, code_version)
    )


def get_instances(
    db: Session,
    project_name: str,
    min_version: int,
    config_id: str,
    date_filters: dict[str, tuple[datetime, datetime]],
    equal_filters: dict[str, str],
    range_filters: dict[str, tuple[float, float]]
):
    query = db.query(models.ProblemInstance).filter(
        (models.ProblemInstance.project_name == project_name)
        & (models.ProblemInstance.code_version >= min_version)
    )
    for k, v in date_filters.items():
        query = query.filter(
            models.ProblemInstance.filter_tags[k]
                .astext.cast(DateTime)
                .between(v[0], v[1])
        )
    for k, v in range_filters.items():
        query = query.filter(
            models.ProblemInstance.filter_tags[k]
                  .astext.cast(Float)
                  .between(v[0], v[1])
        )
    for k, v in equal_filters.items():
        query = query.filter(models.ProblemInstance.filter_tags[k].astext == v)
    if config_id is not None:
        query = query.filter(models.ProblemInstance.config_id == config_id)
    return query.all()


def _encode_cursor(obj: dict) -> str:
    """Encode a dict in base64 json for cursor."""
    j = json.dumps(obj, separators=(",", ":"), ensure_ascii=False)
    b = j.encode("utf-8")
    return base64.urlsafe_b64encode(b).decode("utf-8")


def _decode_cursor(cursor: str) -> dict:
    """Decode a cursor base64."""
    try:
        b = base64.urlsafe_b64decode(cursor.encode("utf-8"))
        j = b.decode("utf-8")
        return json.loads(j)
    except Exception as exc:
        raise ValueError("Invalid cursor") from exc


def get_instances_query(
    db: Session,
    project_name: str,
    name_like: str | None = None,
    config_id: str | None = None,
    version: int | None = None,
    min_version: int | None = None,
    max_version: int | None = None,
    date_filters: dict[str, tuple[datetime, datetime]] | None = None,
    numerical_filters: dict[str, tuple[float | None, float | None]] | None = None,
    text_filters: dict | None = None,
):

    query = db.query(models.ProblemInstance).filter(
        models.ProblemInstance.project_name == project_name
    )
    if name_like:
        like = f"%{name_like}%"
        query = query.filter(models.ProblemInstance.name.ilike(like))
    if config_id:
        query = query.filter(models.ProblemInstance.config_id == config_id)
    if version is not None:
        query = query.filter(models.ProblemInstance.code_version == version)
    if min_version is not None:
        query = query.filter(models.ProblemInstance.code_version >= min_version)
    if max_version is not None:
        query = query.filter(models.ProblemInstance.code_version <= max_version)
    if date_filters:
        for k, v in date_filters.items():
            query = query.filter(
                models.ProblemInstance.filter_tags[k]
                .astext.cast(DateTime)
                .between(v[0], v[1])
            )
    if numerical_filters:
        for k, v in numerical_filters.items():
            col = models.ProblemInstance.filter_tags[k].astext.cast(Float)
            if v[0] is not None and v[1] is not None:
                query = query.filter(col.between(v[0], v[1]))
            elif v[0] is not None:
                query = query.filter(col >= v[0])
            elif v[1] is not None:
                query = query.filter(col <= v[1])
    if text_filters:
        for k, v in text_filters.items():
            query = query.filter(models.ProblemInstance.filter_tags[k].astext == v)
    return query


def get_instances_page(
    query, limit: int = 100, offset: int | None = None, cursor: str | None = None
) -> tuple[list, str | None]:

    # sanitize limit
    max_limit = 1000
    if limit is None or limit <= 0:
        limit = 100
    if limit > max_limit:
        limit = max_limit

    # exclusive params check
    if offset is not None and cursor is not None:
        raise ValueError("Provide either offset OR cursor, not both.")

    # ---- offset pagination ----
    if offset is not None:
        if not isinstance(offset, int):
            raise ValueError("Invalid offset (must be an integer)")
        if offset < 0:
            raise ValueError("Invalid offset (must be >= 0)")
        # ordering consistent with keyset
        query = query.order_by(
            models.ProblemInstance.code_version.desc(),
            models.ProblemInstance.name.asc(),
        )
        query = query.offset(offset)
        items = query.limit(limit).all()
        return items, None

    # ---- KEYSET mode (cursor or first page) ----
    last = None
    if cursor:
        last = _decode_cursor(cursor)

    # apply keyset filter if last present
    if last:
        lv = last.get("code_version")
        ln = last.get("name")
        if lv is not None and ln is not None:
            query = query.filter(
                or_(
                    models.ProblemInstance.code_version < lv,
                    and_(
                        models.ProblemInstance.code_version == lv,
                        models.ProblemInstance.name > ln,
                    ),
                )
            )

    # apply ordering for keyset
    query = query.order_by(
        models.ProblemInstance.code_version.desc(), models.ProblemInstance.name.asc()
    )

    # fetch limit+1 to determine if there is a next page
    fetch_limit = limit + 1
    fetched = query.limit(fetch_limit).all()

    next_cursor = None
    if len(fetched) > limit:
        # there is another page; compute cursor from the (limit)th element (last returned to client)
        last_item = fetched[limit - 1]
        cursor_obj = {"code_version": last_item.code_version, "name": last_item.name}
        next_cursor = _encode_cursor(cursor_obj)
        items = fetched[:limit]
    else:
        items = fetched

    return items, next_cursor


def register_instance(
    db: Session,
    project_name: str,
    instance: schemas.ProblemInstance,
    instance_file: UploadFile,
):
    db_instance = models.ProblemInstance(
        project_name=project_name,
        name=instance.name,
        config_id=instance.config_id,
        code_version=instance.code_version,
        context_shape=instance.context_shape,
        decision_shape=instance.decision_shape,
        filter_tags=instance.filter_tags,
        storage_path=instance.storage_path,
    )
    try:
        db.add(db_instance)
        db.flush()
        s3.upload_object(
            f"{project_name}/instances/{instance.storage_path}", instance_file.file
        )
        db.commit()

    except Exception as exc:
        db.rollback()
        raise exc

    return db_instance


def delete_instance(
    db: Session, project_name: str, name: str, config_id: str, code_version: int
):
    inst = get_instance(db, project_name, name, config_id, code_version)
    if inst is None:
        return None
    try:
        db.delete(inst)
        db.flush()
        s3.delete_object(f"{project_name}/instances/{inst.storage_path}")
        db.commit()
        return inst
    except Exception as exc:
        db.rollback()
        raise Exception(f"Error occurs when deleting instance record: {str(exc)}")


def get_configs(db: Session, project_name: str):
    return (
        db.query(models.InstanceGenerationConfig)
        .filter(models.InstanceGenerationConfig.project_name == project_name)
        .all()
    )


def get_config(
    db: Session, project_name: str, config_id: str
) -> models.InstanceGenerationConfig | None:
    return db.query(models.InstanceGenerationConfig).get((project_name, config_id))


def register_config(
    db: Session,
    project_name: str,
    config: schemas.InstanceGenerationConfig,
    config_file: UploadFile,
):
    cfg = get_config(db, project_name, config.config_id)
    if cfg is not None:
        expected_hash = cfg.hash
        if config.hash != expected_hash:
            raise ValueError(
                "Configuration file does not match the stored one for this config id,"
                + " change the id if real changes have been made to the file."
            )
        return cfg
    else:
        db_config = models.InstanceGenerationConfig(
            project_name=project_name,
            config_id=config.config_id,
            hash=config.hash,
            tags=config.tags,
            storage_path=config.storage_path,
        )
        db.add(db_config)
        db.flush()
        object_key = f"{project_name}/config/{config.storage_path}"
        try:
            s3.upload_object(object_key, config_file.file)
        except ClientError as e:
            db.rollback()
            raise e
        db.commit()
        return db_config


def delete_config(db: Session, project_name: str, config_id: str):
    cfg = get_config(db, project_name, config_id)
    if cfg is None:
        return None
    try:
        db.delete(cfg)
        db.flush()
        s3.delete_object(f"{project_name}/config/{cfg.storage_path}")
        db.commit()
        return cfg
    except Exception as exc:
        db.rollback()
        raise Exception(f"Error occurs when deleting config record: {str(exc)}")


def get_datasets(db: Session, project_name: str):
    return (
        db.query(models.ProblemDataset)
        .filter(models.ProblemDataset.project_name == project_name)
        .all()
    )


def get_dataset(db: Session, project_name: str, name: str, split: str, version: int):
    return db.query(models.ProblemDataset).get((project_name, name, split, version))


def register_dataset(
    db: Session, project_name: str, dataset: schemas.Dataset, dataset_file: UploadFile
):
    db_dataset = models.ProblemDataset(
        project_name=project_name,
        name=dataset.name,
        split=dataset.split,
        version=dataset.version,
        size=dataset.size,
        generation_date=dataset.generation_date,
        context_max_shape=dataset.context_max_shape,
        decision_max_shape=dataset.decision_max_shape,
        selection_criteria=dataset.selection_criteria,
        tags=dataset.tags,
        storage_path=dataset.storage_path,
    )
    try:
        db.add(db_dataset)
        db.flush()
        s3.upload_object(
            f"{project_name}/datasets/{dataset.storage_path}", dataset_file.file
        )
        db.commit()
        return db_dataset
    except Exception as exc:
        db.rollback()
        raise exc


def delete_dataset(db: Session, project_name: str, name: str, split: str, version: int):
    ds = get_dataset(db, project_name, name, split, version)
    if ds is None:
        return None
    try:
        db.delete(ds)
        db.flush()
        s3.delete_object(f"{project_name}/datasets/{ds.storage_path}")
        db.commit()
        return ds
    except Exception as exc:
        db.rollback()
        raise Exception(f"Error occurs when deleting dataset record: {str(exc)}")


def register_run_step(db: Session, step: schemas.RunStep, step_file: UploadFile):
    db_run = models.RunStep(
        project_name=step.project_name,
        run_id=step.run_id,
        training_step=step.training_step,
        parent_run_id=step.parent_run_id,
        # best=step.best,
        # last=step.last,
        # tags=step.tags,
        # storage_path=step.storage_path
    )
    try:
        db.add(db_run)
        db.flush()
        run_step_key = f"{step.project_name}/runs/{step.run_id}/checkpoints/{step.training_step}.tar.gz"
        s3.upload_object(run_step_key, step_file.file)
        db.commit()
        return db_run
    except Exception as exc:
        db.rollback()
        raise exc


def get_runs(db: Session, project_name: str):
    return (
        db.query(models.RunStep)
        .filter(models.RunStep.project_name == project_name)
        .all()
    )


def get_run_steps(db: Session, project_name: str, run_id: str):
    steps = (
        db.query(models.RunStep)
        .filter(
            and_(
                models.RunStep.project_name == project_name,
                models.RunStep.run_id == run_id,
            )
        )
        .all()
    )
    return steps


def get_run_step(db: Session, project_name: str, run_id: str, training_step: int):
    return db.query(models.RunStep).get((project_name, run_id, training_step))


def filter_run_steps(
    db: Session, project_name: str, run_id: str, training_steps: list[int]
):
    if not training_steps:
        return None
    return db.query(models.RunStep).filter(
        models.RunStep.project_name == project_name,
        models.RunStep.run_id == run_id,
        models.RunStep.training_step.in_(training_steps),
    )


def delete_run_steps(
    db: Session, project_name: str, run_id: str, training_steps: list[int]
):
    query = filter_run_steps(db, project_name, run_id, training_steps)
    if query is None:
        return None

    instances = query.all()
    if not instances:
        return []

    to_delete = [
        f"{project_name}/runs/{run_id}/checkpoints/{step.training_step}.tar.gz"
        for step in instances
    ]

    try:

        deleted_count = query.delete(synchronize_session=False)
        db.flush()
        s3.delete_objects(to_delete)
        db.commit()
        return deleted_count
    except Exception as exc:
        db.rollback()
        raise Exception(f"Error occurs when deleting run record: {str(exc)}")
