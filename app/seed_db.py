from io import BytesIO

from faker import Faker
import random
import uuid
from datetime import datetime, timedelta, timezone
import argparse
import logging
import io
import pickle
import zipfile
import tarfile

import numpy as np
from fastapi import UploadFile

import crud
import schemas
import models
from database import SessionLocal, engine

import os
import boto3
from botocore.client import Config

# S3 configuration from env
s3_endpoint = os.environ.get("S3_ENDPOINT")
bucket = os.environ.get("S3_BUCKET")
secret_key_path = os.environ.get("SECRET_KEY_BIN")  # path to the SSE-C binary key

# Initializes the S3 client (with v4 signature)
s3 = boto3.client(
    "s3", endpoint_url=s3_endpoint, config=Config(signature_version="s3v4")
)

# verification and creation of the bucket if necessary
try:
    s3.head_bucket(Bucket=bucket)
    print("Bucket exists:", bucket)
except Exception:
    print("Creating bucket:", bucket)
    try:
        s3.create_bucket(Bucket=bucket)
    except Exception as exc:
        print("Failed to create bucket:", exc)
        raise

fake = Faker()
logging.basicConfig(level=logging.INFO)


def _make_random_payload(kind: str) -> dict:
    """Creates a small random non-empty dict to simulate a stored object."""
    payload = {
        "kind": kind,
        "summary": fake.sentence(nb_words=6),
        "created": datetime.now(timezone.utc).isoformat(),
        "meta": {
            "score": random.random(),
            "tags": [fake.word() for _ in range(random.randint(1, 4))],
            "count": random.randint(1, 1000),
        },
    }
    if random.choice([True, False]):
        payload["notes"] = fake.paragraph(nb_sentences=2)
    if random.choice([True, False]):
        payload["params"] = {"alpha": random.randint(0, 10), "beta": fake.word()}
    return payload


def _zip_pickle_bytes(obj: object) -> bytes:
    """Pickle the object and return a zip (bytes) containing data.pkl."""
    pkl = pickle.dumps(obj, protocol=pickle.HIGHEST_PROTOCOL)
    bio = io.BytesIO()
    with zipfile.ZipFile(bio, mode="w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("data.pkl", pkl)
    bio.seek(0)
    return bio.read()


def _tar_pickle_bytes(obj: object) -> bytes:
    """Pickle the object and return a tar.gz archive (bytes) containing data.pkl."""

    # sérialisation pickle
    pkl = pickle.dumps(obj, protocol=pickle.HIGHEST_PROTOCOL)

    bio = io.BytesIO()

    # création de l'archive tar.gz en mémoire
    with tarfile.open(fileobj=bio, mode="w:gz") as tar:
        info = tarfile.TarInfo(name="data.pkl")
        info.size = len(pkl)

        tar.addfile(info, io.BytesIO(pkl))

    bio.seek(0)
    return bio.read()


def seed(
    project_names=None,
    configs_per_project=2,
    datasets_per_project=3,
    instances_per_config=4,
    run_by_project=2,
):
    """
    Seed the DB. Ensures tables exist, then inserts config/dataset/instance test data
    and uploads a zipped pickled payload to S3 for each record. If upload fails,
    the DB record is removed to keep consistency.
    """
    # Ensure tables exist (idempotent)
    models.Base.metadata.create_all(bind=engine)

    db = SessionLocal()
    created = {"configs": 0, "datasets": 0, "instances": 0, "runs": 0}
    try:
        if project_names is None:
            project_names = [fake.word() for _ in range(2)]

        for project in project_names:
            logging.info(f"Seeding project: {project}")

            # Create some configs
            config_ids = []
            for i in range(configs_per_project):
                # Make config_id globally unique by prefixing the project name
                cfg_id = f"{project}_cfg_{i+1}"
                storage_uuid = uuid.uuid4()
                config_schema = schemas.InstanceGenerationConfig(
                    config_id=cfg_id,
                    hash=fake.sha1(),
                    tags={
                        "env": random.choice(["dev", "staging", "prod"]),
                        "note": fake.sentence(nb_words=3),
                    },
                    storage_path=storage_uuid,
                )

                # Idempotent: check exist (by composite key project+config_id)
                existing = crud.get_config(db, project, cfg_id)
                if existing is None:
                    try:
                        payload = _make_random_payload("configs")
                        zip_bytes = _zip_pickle_bytes(payload)
                        key = f"{project}/configs/{str(storage_uuid)}"
                        upload_file = UploadFile(file=BytesIO(zip_bytes), filename=key)
                        crud.register_config(
                            db,
                            project_name=project,
                            config=config_schema,
                            config_file=upload_file,
                        )
                        created["configs"] += 1
                        logging.info(f"Inserted config {cfg_id} for project {project}")
                    except Exception as e:
                        logging.error(f"Error while registering {cfg_id}: {e}")
                else:
                    logging.debug(
                        f"Config {cfg_id} already exists for project {project}"
                    )
                config_ids.append(cfg_id)

            # Create some datasets
            for j in range(datasets_per_project):
                ds_name = f"dataset_{j+1}"
                split = random.choice(["train", "val", "test"])
                version = random.randint(1, 3)
                storage_uuid = uuid.uuid4()
                dataset_schema = schemas.Dataset(
                    name=ds_name,
                    split=split,
                    version=version,
                    size=random.randint(100, 10000),
                    generation_date=(
                        datetime.now(timezone.utc)
                        - timedelta(days=random.randint(0, 365))
                    ),
                    context_max_shape={
                        "rows": random.randint(1, 100),
                        "cols": random.randint(1, 20),
                    },
                    decision_max_shape={"out_dim": random.randint(1, 10)},
                    selection_criteria={"by": "random", "pct": random.randint(1, 100)},
                    tags={
                        "source": fake.word(),
                        "quality": random.choice(["good", "ok", "bad"]),
                    },
                    storage_path=storage_uuid,
                )
                existing_ds = crud.get_dataset(db, project, ds_name, split, version)
                if existing_ds is None:
                    try:
                        payload = _make_random_payload("datasets")
                        dataset_file = UploadFile(BytesIO(_zip_pickle_bytes(payload)))
                        crud.register_dataset(
                            db,
                            project_name=project,
                            dataset=dataset_schema,
                            dataset_file=dataset_file,
                        )
                        created["datasets"] += 1
                        logging.info(
                            f"Inserted dataset {ds_name}:{split}:v{version} for project {project}"
                        )
                    except Exception as e:
                        logging.error(f"Error while registering dataset {ds_name}: {e}")

            # Create instances linked to configs
            for cfg in config_ids:
                for k in range(instances_per_config):
                    inst_name = f"inst_{k+1}"
                    code_version = random.randint(1, 5)
                    storage_uuid = uuid.uuid4()
                    instance_schema = schemas.ProblemInstance(
                        name=inst_name,
                        config_id=cfg,
                        code_version=code_version,
                        context_shape={
                            "n": random.randint(1, 50),
                            "features": random.randint(1, 40),
                        },
                        decision_shape={"k": random.randint(1, 5)},
                        filter_tags={
                            "status": random.choice(["new", "processed", "failed"]),
                            "size": random.randint(1, 100),
                            "created_at": (
                                datetime.now(timezone.utc)
                                - timedelta(days=random.randint(0, 365))
                            ).isoformat(),
                        },
                        storage_path=storage_uuid,
                    )
                    existing_inst = crud.get_instance(
                        db, project, inst_name, cfg, code_version
                    )
                    if existing_inst is None:
                        try:
                            payload = _make_random_payload("instances")
                            instance_file = UploadFile(
                                BytesIO(_zip_pickle_bytes(payload))
                            )
                            crud.register_instance(
                                db,
                                project_name=project,
                                instance=instance_schema,
                                instance_file=instance_file,
                            )
                            created["instances"] += 1
                            logging.info(
                                f"Inserted instance {inst_name} (cfg={cfg}, v={code_version}) for project {project}"
                            )
                        except Exception as e:
                            logging.error(
                                f"Error while registering instance {inst_name}: {e}"
                            )

            # Create some runs steps
            for i in range(run_by_project):
                run_id = f"run_{i+1}"
                for s in np.random.choice(range(1, 11), size=3, replace=False):
                    # storage_uuid = uuid.uuid4()
                    run_schema = schemas.RunStep(
                        project_name=project,
                        run_id=run_id,
                        training_step=s,
                        parent_run_id=None,
                        # best=random.choice([True, False]),
                        # last=random.choice([True, False]),
                        # tags={"source": fake.word(), "quality": random.choice(["good", "ok", "bad"])},
                        # storage_path=storage_uuid
                    )
                    existing_run = crud.get_run_step(
                        db, project, run_id, run_schema.training_step
                    )
                    if existing_run is None:
                        try:
                            payload = _make_random_payload("run")
                            run_file = UploadFile(BytesIO(_tar_pickle_bytes(payload)))
                            crud.register_run_step(
                                db, step=run_schema, step_file=run_file
                            )
                            created["runs"] += 1
                            logging.info(
                                f"Inserted run {run_id}:{run_schema.training_step} for project {project}"
                            )
                        except Exception as e:
                            logging.error(f"Error while registering run {run_id}: {e}")

    finally:
        db.close()

    logging.info("Seeding complete:")
    logging.info(f"  configs created: {created['configs']}")
    logging.info(f"  datasets created: {created['datasets']}")
    logging.info(f"  instances created: {created['instances']}")
    logging.info(f"  runs created: {created['runs']}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Seed DB with fake data")
    parser.add_argument(
        "--projects", type=int, default=4, help="Number of fake projects"
    )
    parser.add_argument("--configs", type=int, default=3, help="Configs per project")
    parser.add_argument("--datasets", type=int, default=5, help="Datasets per project")
    parser.add_argument(
        "--instances", type=int, default=25, help="Instances per config"
    )
    parser.add_argument(
        "--runs", type=int, default=8, help="Number of runs runs per project"
    )
    args = parser.parse_args()

    # Prepare a small list of project names
    project_list = [fake.word() for _ in range(args.projects)]

    # Example explicit projects:
    # project_list = ["tvc", "regul", "overload"]

    seed(
        project_names=project_list,
        configs_per_project=args.configs,
        datasets_per_project=args.datasets,
        instances_per_config=args.instances,
        run_by_project=args.runs,
    )
