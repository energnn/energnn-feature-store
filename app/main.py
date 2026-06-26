import logging
import traceback
from datetime import datetime

from botocore.exceptions import ClientError
from fastapi import FastAPI, Depends, Request, Body, UploadFile
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse
from sqlalchemy.exc import NoResultFound, IntegrityError
from sqlalchemy.orm import Session

import crud
import models
import s3
import schemas
from database import engine, get_db

logger = logging.getLogger("uvicorn.error")

models.Base.metadata.create_all(bind=engine)

app = FastAPI()

tags_metadata = [
    {
        "name": "Configuration",
        "description": "Instance generation configuration metadata",
    },
    {
        "name": "Problem instances",
        "description": "Metadata of EnerGNN projects problem instances",
    },
    {"name": "Datasets", "description": "Metadata of EnerGNN projects datasets"},
    {"name": "Runs", "description": "Metadata of EnerGNN training runs"},
]

# Add middleware to handle Cross-Origin Resource Sharing (CORS)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://frontend:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["Content-Disposition", "Content-Length"],
)


@app.exception_handler(NoResultFound)
async def no_result_found_exception_handler(request: Request, exc: NoResultFound):
    return JSONResponse(
        status_code=400,
        content={"message": f"No record found for params {request.query_params}"},
    )


@app.exception_handler(IntegrityError)
async def no_result_found_exception_handler(request: Request, exc: IntegrityError):
    return JSONResponse(
        status_code=409,
        content={
            "message": f"A record with same key is already registered : {exc.orig.args}"
        },
    )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    return JSONResponse(
        status_code=422, content={"message": f"Validation error: {exc.errors()}"}
    )


@app.get("/download")
def download_s3(object_key: str):
    """
    Télécharge un objet S3 et le stream au client.
    Renvoie JSONResponse en cas d'erreur.
    """
    try:
        resp = s3.download_object(object_key)
    except ClientError as e:
        code = e.response.get("Error", {}).get("Code", "")
        msg = e.response.get("Error", {}).get("Message", str(e))
        logger.warning("S3 ClientError for key %s: %s - %s", object_key, code, msg)
        if code in ("NoSuchKey", "NotFound"):
            return JSONResponse(
                status_code=404,
                content={"message": f"No object found with key: {object_key}"},
            )
        return JSONResponse(
            status_code=502, content={"message": f"S3 error ({code}): {msg}"}
        )
    except Exception as exc:
        tb = traceback.format_exc()
        logger.exception(
            "Unexpected error while downloading S3 object %s: %s", object_key, tb
        )
        # message for frontend user
        return JSONResponse(
            status_code=500,
            content={
                "message": "Server error while preparing download. See server logs."
            },
        )

    try:
        body = resp["Body"]
        content_length = resp.get("ContentLength")
        content_type = resp.get("ContentType", "application/octet-stream")
        filename = object_key.rsplit("/", 1)[-1] or "download"

        def iterfile():
            try:
                chunk_size = 64 * 1024
                while True:
                    chunk = body.read(chunk_size)
                    if not chunk:
                        break
                    yield chunk
            finally:
                try:
                    body.close()
                except Exception:
                    pass

        headers = {"Content-Disposition": f'attachment; filename="{filename}"'}
        if content_length is not None:
            headers["Content-Length"] = str(content_length)

        return StreamingResponse(
            iterfile(), media_type=content_type, headers=headers, status_code=200
        )
    except Exception:
        tb = traceback.format_exc()
        logger.exception(
            "Error while streaming response for key %s: %s", object_key, tb
        )
        return JSONResponse(
            status_code=500,
            content={
                "message": "Server error while streaming download. See server logs."
            },
        )


@app.get("/projects", response_model=dict[str, list[str]])
def get_projects(db: Session = Depends(get_db)):
    return crud.get_projects(db)


@app.post("/instance", tags=["Problem instances"])
def register_instance(
    project_name: str,
    instance: schemas.ProblemInstance,
    instance_file: UploadFile,
    db: Session = Depends(get_db),
):
    crud.register_instance(
        db=db, project_name=project_name, instance=instance, instance_file=instance_file
    )


@app.get(
    "/instance", response_model=schemas.ProblemInstance, tags=["Problem instances"]
)
def get_instance(
    project_name: str,
    name: str,
    config_id: str,
    code_version: int,
    db: Session = Depends(get_db),
):
    res = crud.get_instance(db, project_name, name, config_id, code_version)
    if res is None:
        raise NoResultFound
    return res


@app.get(
    "/instances",
    response_model=list[schemas.ProblemInstance],
    tags=["Problem instances"],
)
def get_instances(
    project_name: str,
    min_version: int = 0,
    config_id: str | None = None,
    date_filters: dict[str, tuple[datetime, datetime]] | None = None,
    equal_filters: dict[str, str] | None = None,
    range_filters: dict[str, tuple[float, float]] | None = None,
    db: Session = Depends(get_db),
):
    logging.info(
        f"Getting instances info for filters {date_filters} and {equal_filters}."
    )
    if date_filters is None:
        date_filters = {}
    if equal_filters is None:
        equal_filters = {}
    if range_filters is None:
        range_filters = {}
    items = crud.get_instances(
        db, project_name, min_version, config_id, date_filters, equal_filters, range_filters
    )
    return items


@app.get("/instance/download", tags=["Problem instances"])
def download_instance(
    project_name: str,
    name: str,
    config_id: str,
    code_version: int,
    db: Session = Depends(get_db),
):
    res = crud.get_instance(db, project_name, name, config_id, code_version)
    if res is None:
        raise NoResultFound
    return download_s3(f"{project_name}/instances/{res.storage_path}")


@app.post(
    "/instances_page/search",
    response_model=schemas.InstancesPage,
    tags=["Problem instances"],
)
def filter_instances_page(
    project_name: str,
    body: schemas.ProblemInstanceFilter = Body(...),
    db: Session = Depends(get_db),
):

    limit = body.limit
    offset = body.offset
    cursor = body.cursor
    name_like = body.name_like
    config_id = body.config_id
    version = body.version
    min_version = body.min_version
    max_version = body.max_version
    date_filters = body.date_filters
    tag_filters = body.tag_filters
    count = body.count

    query = crud.get_instances_query(
        db=db,
        project_name=project_name,
        name_like=name_like,
        config_id=config_id,
        version=version,
        min_version=min_version,
        max_version=max_version,
        date_filters=date_filters,
        tag_filters=tag_filters,
    )
    try:
        items, next_cursor = crud.get_instances_page(
            query=query, limit=limit, offset=offset, cursor=cursor
        )
    except:
        return RequestValidationError

    resp = {
        "items": items,
        "limit": limit,
        "offset": offset if not cursor else None,
        "next_cursor": next_cursor,
    }

    if count:
        resp["total_count"] = query.count()
    return resp


@app.delete("/instance", tags=["Problem instances"])
def delete_instance(
    project_name: str,
    name: str,
    config_id: str,
    code_version: int,
    db: Session = Depends(get_db),
):
    try:
        deleted = crud.delete_instance(db, project_name, name, config_id, code_version)
    except Exception as exc:
        return JSONResponse(status_code=409, content={"message": str(exc)})
    if deleted is None:
        raise NoResultFound
    return deleted


@app.post("/config", tags=["Configuration"])
def register_config(
    project_name: str,
    config: schemas.InstanceGenerationConfig,
    config_file: UploadFile,
    db: Session = Depends(get_db),
):
    crud.register_config(
        db=db, project_name=project_name, config=config, config_file=config_file
    )


@app.get(
    "/configs",
    response_model=list[schemas.InstanceGenerationConfig],
    tags=["Configuration"],
)
def get_configs(project_name: str, db: Session = Depends(get_db)):
    return crud.get_configs(db, project_name)


@app.get(
    "/config", response_model=schemas.InstanceGenerationConfig, tags=["Configuration"]
)
def get_config_from_id(
    project_name: str, config_id: str, db: Session = Depends(get_db)
):
    logging.info(f"Getting config for project {project_name}")
    res = crud.get_config(db, project_name, config_id)
    if res is None:
        raise NoResultFound
    return res


@app.get("/config/download", tags=["Configuration"])
def download_config(project_name: str, config_id: str, db: Session = Depends(get_db)):
    res = crud.get_config(db, project_name, config_id)
    if res is None:
        raise NoResultFound
    return download_s3(f"{project_name}/config/{res.storage_path}")


@app.delete("/config", tags=["Configuration"])
def delete_config(project_name: str, config_id: str, db: Session = Depends(get_db)):
    """
    ATTENTION : L'opération va échouer si des ProblemInstances référencent encore cette config.
    """
    try:
        deleted = crud.delete_config(db, project_name, config_id)
    except Exception as exc:
        return JSONResponse(status_code=409, content={"message": str(exc)})
    if deleted is None:
        raise NoResultFound
    return deleted


@app.post("/dataset", tags=["Datasets"])
def register_dataset(
    project_name: str,
    dataset: schemas.Dataset,
    dataset_file: UploadFile,
    db: Session = Depends(get_db),
):
    crud.register_dataset(
        db=db, project_name=project_name, dataset=dataset, dataset_file=dataset_file
    )


@app.get("/datasets", response_model=list[schemas.Dataset], tags=["Datasets"])
def get_datasets(project_name: str, db: Session = Depends(get_db)):
    return crud.get_datasets(db, project_name)


@app.get("/dataset", response_model=schemas.Dataset, tags=["Datasets"])
def get_dataset_from_key(
    project_name: str,
    name: str,
    split: str,
    version: int,
    db: Session = Depends(get_db),
):
    res = crud.get_dataset(db, project_name, name, split, version)
    if res is None:
        raise NoResultFound
    return res


@app.get("/dataset/download", tags=["Datasets"])
def download_dataset(
    project_name: str,
    name: str,
    split: str,
    version: int,
    db: Session = Depends(get_db),
):
    res = crud.get_dataset(db, project_name, name, split, version)
    if res is None:
        raise NoResultFound
    return download_s3(f"{project_name}/datasets/{res.storage_path}")


@app.delete("/dataset", tags=["Datasets"])
def delete_dataset(
    project_name: str,
    name: str,
    split: str,
    version: int,
    db: Session = Depends(get_db),
):
    try:
        deleted = crud.delete_dataset(db, project_name, name, split, version)
    except Exception as exc:
        return JSONResponse(status_code=409, content={"message": str(exc)})
    if deleted is None:
        raise NoResultFound
    return deleted


@app.post("/run", tags=["Runs"])
def register_run_step(
    step: schemas.RunStep, step_file: UploadFile, db: Session = Depends(get_db)
):
    crud.register_run_step(db=db, step=step, step_file=step_file)


@app.get("/runs", response_model=list[schemas.RunStep], tags=["Runs"])
def get_runs(project_name: str, db: Session = Depends(get_db)):
    return crud.get_runs(db, project_name=project_name)


@app.get("/run", response_model=schemas.RunStep, tags=["Runs"])
def get_run_step(
    project_name: str, run_id: str, training_step: int, db: Session = Depends(get_db)
):
    res = crud.get_run_step(db, project_name, run_id, training_step)
    if res is None:
        raise NoResultFound
    return res


@app.get("/run/all", response_model=list[schemas.RunStep], tags=["Runs"])
def get_run_steps(project_name: str, run_id: str, db: Session = Depends(get_db)):
    return crud.get_run_steps(db, project_name, run_id)


@app.get("/run/download", tags=["Runs"])
def download_run_step(
    project_name: str, run_id: str, training_step: int, db: Session = Depends(get_db)
):
    res = crud.get_run_step(db, project_name, run_id, training_step)
    if res is None:
        raise NoResultFound
    run_step_key = f"{project_name}/runs/{run_id}/checkpoints/{training_step}.tar.gz"
    return download_s3(run_step_key)


@app.delete("/run", tags=["Runs"])
def delete_run(
    project_name: str,
    run_id: str,
    training_steps: list[int],
    db: Session = Depends(get_db),
):
    try:
        deleted = crud.delete_run_steps(db, project_name, run_id, training_steps)
    except Exception as exc:
        return JSONResponse(status_code=409, content={"message": str(exc)})
    if deleted is None:
        raise NoResultFound
    return deleted
