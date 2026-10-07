# Copyright (c) 2025, RTE (http://www.rte-france.com)
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0
#
import hashlib
import io
import json
import logging
import os
import shutil
import tarfile
import uuid
import zipfile
from datetime import datetime
from pathlib import Path
from tempfile import TemporaryDirectory

import requests
from energnn.problem import Problem

from .config_info import ProblemGenerationConfigInfo
from .remote_checkpoint_manager import RemoteCheckpointManager
from .remote_registry import RemoteRegistryClient
from .dataset import ProblemDataset
from .metadata import ProblemMetadata

logger = logging.getLogger(__name__)


class FeatureStoreClient(RemoteRegistryClient):
    r"""

    Client interface for interacting with an EnerGNN Feature Store server.

    This client allows registering, retrieving, and downloading configuration files,
    problem instances, and datasets related to an EnerGNN project. It manages metadata
    and data storage through HTTP requests to a remote feature store

    :param project_name: Identifies the EnerGNN project, for HTTP requests to the feature store and storage location.
    :param feature_store_url: Where to send the requests to.
    """

    project_name: str
    feature_store_url: str
    config_url: str
    instance_url: str
    dataset_url: str
    run_url: str

    def __init__(self, *, project_name: str, feature_store_url: str):
        self.project_name = project_name
        self.feature_store_url = feature_store_url
        self.config_url = self.feature_store_url + "/config"
        self.instance_url = self.feature_store_url + "/instance"
        self.dataset_url = self.feature_store_url + "/dataset"
        self.run_url = self.feature_store_url + "/run"

    def register_config(self, config_path: str, config_id: str) -> bool:
        """
        Registers a configuration file into the feature store.

        Uploads the file to remote storage and stores its hash and metadata in the feature store database.

        :param config_path: Path to the configuration file.
        :param config_id: Identifier to reference the configuration.
        :return: True if the configuration is registered successfully, False otherwise.
        """

        with open(config_path, "rb") as file:
            hash_func = hashlib.new("md5")
            hash_func.update(file.read())
            local_hash: str = hash_func.hexdigest()
        storage_uuid = uuid.uuid4()
        register_info = {
            "config_id": config_id,
            "hash": local_hash,
            "tags": {},
            "storage_path": str(storage_uuid),
        }

        zip_files_to_send(config_path)
        with open(config_path + ".zip", "rb") as file:
            response = requests.post(
                url=self.config_url,
                params={"project_name": self.project_name},
                files={
                    "config_file": file,
                    "config": (None, json.dumps(register_info), "application/json"),
                },
            )
        if not _check_response(response):
            return False
        os.remove(config_path + ".zip")
        return True

    def get_configs_metadata(self) -> list[ProblemGenerationConfigInfo]:
        """
        Retrieves metadata of all registered configurations for this project.

        :return: A list of configuration metadata.
        """
        response = requests.get(
            url=self.config_url + "s", params={"project_name": self.project_name}
        )
        return response.json()

    def get_config_metadata(self, config_id: str) -> ProblemGenerationConfigInfo | None:
        """
        Retrieves metadata of a specific configuration.

        :param config_id: Configuration identifier.
        :return: Configuration metadata if found, None otherwise.
        """
        response = requests.get(
            url=self.config_url,
            params={"project_name": self.project_name, "config_id": config_id},
        )
        if not _check_response(response):
            return None
        return response.json()

    def remove_config(self, config_id: str) -> bool:
        """
        Removes an instance generation configuration from the feature store.

        :param config_id: Configuration identifier.
        :return: True if the configuration has been removed, False instead.
        """
        response = requests.delete(
            url=self.config_url,
            params={"project_name": self.project_name, "config_id": config_id},
        )
        if not _check_response(response):
            return False
        return True

    def download_config(
        self, config_id: str, output_dir: Path, unzip: bool = True
    ) -> Path:
        response = requests.get(
            url=self.config_url + "/download",
            params={"project_name": self.project_name, "config_id": config_id},
        )
        _check_response(response, throw=True)
        return write_zip_from_response(response, output_dir, unzip)

    def register_instance(self, instance: Problem) -> bool:
        """
        Registers a problem instance into the feature store and uploads it to remote storage.

        :param instance: A Problem object to register.
        :return: True if successfully registered and uploaded, False otherwise.
        """
        distant_storage_name = str(uuid.uuid4())
        instance_infos: ProblemMetadata = instance.get_metadata()
        instance_infos["storage_path"] = distant_storage_name
        with TemporaryDirectory() as tmp_dir_name:
            tmp_dir_path = Path(tmp_dir_name)
            instance_path = tmp_dir_path / instance_infos.name
            instance.save(path=instance_path)
            zip_files_to_send(str(instance_path))
            with open(str(instance_path) + ".zip", "rb") as file:
                response = requests.post(
                    url=self.instance_url,
                    params={"project_name": self.project_name},
                    files={
                        "instance_file": file,
                        "instance": (
                            None,
                            json.dumps(instance_infos),
                            "application/json",
                        ),
                    },
                )
            if not _check_response(response):
                return False
        return True

    def get_instances_metadata(
        self,
        min_version: int,
        config_id: str | None = None,
        date_filters: dict[str, tuple[datetime, datetime]] | None = None,
        range_filters: dict[str, tuple[float, float]] | None = None,
        equal_filters: dict[str, str] | None = None,
    ) -> list[ProblemMetadata] | None:
        """
        Retrieve from the feature store the list of ProblemMetadata corresponding to the chosen filter parameters.

        :param min_version: (optional) Minimal code version of the problem to retrieve.
        :param config_id: (optional) Identifier of the configuration file used to generate the instances.
        :param date_filters: (optional) For any potential date tag in the problems metadata, defines the range
                            to select from.
        :param equal_filters: (optional) For any tag in the problems metadata, defines the exact value (as a string)
                            to select from.
        :param range_filters: (optional) For any potential float tag in the problems metadata, defines the range
                            to select from.
        :return: List of problem metadata.
        """
        params: dict = {"min_version": min_version, "project_name": self.project_name}
        body: dict = {}
        if config_id is not None:
            params["config_id"] = config_id
        if date_filters is not None:
            body["date_filters"] = date_filters
        if equal_filters is not None:
            body["equal_filters"] = equal_filters
        if range_filters is not None:
            body["range_filters"] = range_filters
        response = requests.get(url=self.instance_url + "s", params=params, json=body)
        if not _check_response(response):
            return None
        return response.json()

    def get_instance_metadata(
        self, name: str, config_id: str, code_version: int
    ) -> ProblemMetadata | None:
        """
        Retrieve from the feature store the ProblemMetadata of an instance by name, config ID and version.

        :param name: Name of the problem instance.
        :param config_id: Configuration identifier.
        :param code_version: Code version of the problem to retrieve.
        :return: Metadata if found, else None.
        """
        instance_key = {
            "project_name": self.project_name,
            "name": name,
            "config_id": config_id,
            "code_version": code_version,
        }
        response = requests.get(url=self.instance_url, params=instance_key)
        if not _check_response(response):
            return None
        return response.json()

    def download_instance(
        self,
        name: str,
        config_id: str,
        code_version: int,
        output_dir: Path,
        unzip: bool = True,
    ) -> Path:
        """
        Downloads a registered problem instance if not already available locally.

        :param name: Instance name.
        :param config_id: Configuration identifier.
        :param code_version: Code version.
        :param output_dir: Directory where to save the instance.
        :param unzip: If True, unzip the downloaded file.
        :return: Local path of the downloaded instance.
        :raises Exception: If the instance does not exist in the feature store.
        """
        metadata = self.get_instance_metadata(name, config_id, code_version)
        if metadata is None:
            raise Exception(
                f"Instance with name '{name}', config ID '{config_id}' and version {code_version} does not exist."
            )
        storage_path = metadata["storage_path"]
        local_path = output_dir / storage_path
        if not local_path.exists():
            instance_key = {
                "project_name": self.project_name,
                "name": name,
                "config_id": config_id,
                "code_version": code_version,
            }
            response = requests.get(
                url=self.instance_url + "/download", params=instance_key
            )
            _check_response(response, throw=True)
            return write_zip_from_response(response, output_dir, unzip)
        else:
            logger.info(
                f"Instance with name '{name}', config ID '{config_id}' and version {code_version} already downloaded"
            )
        return local_path

    def remove_instance(self, name: str, config_id: str, code_version: int) -> bool:
        """
        Remove from the feature store an instance by name, config ID
        and version (also remove it from the associated storage).

        :param name: Name of the problem instance.
        :param config_id: Configuration identifier.
        :param code_version: Code version of the problem to retrieve.
        :return: True if the instance was cleanly removed, False otherwise.
        """
        instance_key = {
            "project_name": self.project_name,
            "name": name,
            "config_id": config_id,
            "code_version": code_version,
        }
        response = requests.delete(url=self.instance_url, params=instance_key)
        if not _check_response(response):
            return False
        logger.info(
            f"Successfully removed instance {name}/{config_id}/{code_version} from feature store."
        )
        return True

    def register_dataset(self, dataset: ProblemDataset) -> bool:
        """
        Registers a dataset in the feature store and uploads it to remote storage.

        :param dataset: ProblemDataset object to register.
        :return: True if successfully registered and uploaded, False otherwise.
        """
        dataset_file_name = f"{dataset.name}_{dataset.split}_{dataset.version}"
        logger.info(f"Registering {dataset_file_name} in the feature store")

        storage_path = str(uuid.uuid4())
        dataset_infos = dataset.get_infos_for_feature_store()
        dataset_infos["storage_path"] = storage_path
        with TemporaryDirectory() as tmp_dir_name:
            tmp_dir_path = Path(tmp_dir_name)
            dataset_file_path = tmp_dir_path / dataset_file_name
            dataset.to_pickle(str(dataset_file_path))
            zip_files_to_send(str(dataset_file_path))
            with open(str(dataset_file_path) + ".zip", "rb") as file:
                response = requests.post(
                    url=self.dataset_url,
                    params={"project_name": self.project_name},
                    files={
                        "dataset_file": file,
                        "dataset": (
                            None,
                            json.dumps(dataset_infos),
                            "application/json",
                        ),
                    },
                )
            if not _check_response(response):
                return False
        return True

    def get_datasets_metadata(self):
        """
        Retrieve metadata of all datasets registered in the feature store.

        :return: List of dataset metadata.
        """
        response = requests.get(
            url=self.instance_url + "s", params={"project_name": self.project_name}
        )
        if not _check_response(response):
            return False
        return response.json()

    def get_dataset_metadata(self, name: str, split: str, version: int):
        """
        Retrieves metadata of a specific dataset from the feature store by name, split, version.

        :param name: Dataset name.
        :param split: Dataset split (e.g., train, test).
        :param version: Dataset version number.
        :return: Metadata if found, None otherwise.
        """
        dataset_key = {
            "project_name": self.project_name,
            "name": name,
            "split": split,
            "version": version,
        }
        response = requests.get(url=self.dataset_url, params=dataset_key)
        if not _check_response(response):
            return False
        return response.json()

    def download_dataset(
        self,
        name: str,
        split: str,
        version: int,
        output_dir: Path,
        download_instances: bool = True,
    ) -> ProblemDataset:
        """
        Downloads a dataset from the feature store, using its unique identifier (name, split, version).
        All Problem instances of the dataset are downloaded locally (if they are not already available) if the
        download_instances parameter is set to True.

        :param name: Dataset name.
        :param split: Dataset split.
        :param version: Dataset version
        :param output_dir: Local directory to store the dataset and its instances.
        :param download_instances: If True, downloads instances of the dataset not already available locally.
        :return: A ProblemDataset object, containing the metadata of the downloaded dataset and its instances' ProblemMetadata.
        :raises MissingDatasetError: If the dataset does not exist in the feature store.
        """
        key = f"{name}_{split}_{version}"
        metadata = self.get_dataset_metadata(name, split, version)
        if metadata is None:
            raise MissingDatasetError(f"Dataset {key} does not exist")
        storage_path = metadata["storage_path"]
        local_path = output_dir / storage_path
        if not local_path.exists():
            dataset_key = {
                "project_name": self.project_name,
                "name": name,
                "split": split,
                "version": version,
            }
            response = requests.get(
                url=self.dataset_url + "/download", params=dataset_key
            )
            _check_response(response, throw=True)
            write_zip_from_response(response, output_dir, unzip=True)
        else:
            logger.info(f"Dataset file for {key} already downloaded")
        dataset: ProblemDataset = ProblemDataset.from_pickle(local_path / key)

        # Download missing instances of the list contained in the dataset
        if download_instances:
            to_download = dataset.get_locally_missing_instances(str(output_dir))
            if len(to_download) == 0:
                logger.info(f"All of {key} instances already downloaded")
            else:
                logger.info(
                    f"Downloading problem instances of {key} missing locally ({len(to_download)} instances)."
                )
            for instance in to_download:
                try:
                    self.download_instance(
                        name=instance.name,
                        config_id=instance.config_id,
                        code_version=instance.code_version,
                        output_dir=output_dir,
                        unzip=False,
                    )
                except OSError as exc:
                    logger.error(
                        f"Error while downloading instances : {exc} "
                        f"(still {len(to_download) - to_download.index(instance)} to download)."
                    )
                    break

        return dataset

    def remove_dataset(self, name: str, split: str, version: int) -> bool:
        """
        Remove a dataset from the feature store.

        :param name: Dataset name.
        :param split: Dataset split.
        :param version: Dataset version.
        :return: True if the dataset was cleanly removed, False otherwise.
        """
        str_key = f"{name}_{split}_{version}"
        dataset_key = {
            "project_name": self.project_name,
            "name": name,
            "split": split,
            "version": version,
        }
        response = requests.delete(url=self.dataset_url, params=dataset_key)
        if not _check_response(response):
            return False
        logger.info(f"Successfully removed dataset {str_key} from feature store.")
        return True

    def get_checkpoint_manager(
        self,
        run_id: str,
        directory: str | None = None,
        parent_run_id: str | None = None,
        sync_from_remote: bool = False,
        **kwargs,
    ) -> RemoteCheckpointManager:
        """
        Get a checkpoint manager for managing training checkpoints in the feature store.

        :param run_id: Unique identifier for the training run.
        :param directory: Local directory for storing checkpoints.
        :param parent_run_id: Optional parent run identifier.
        :param sync_from_remote: Whether to synchronize checkpoints from remote storage.
        :return: RemoteCheckpointManager instance for managing checkpoints.
        """

        return RemoteCheckpointManager(
            self,
            run_id=run_id,
            directory=directory,
            parent_run_id=parent_run_id,
            sync_from_remote=sync_from_remote,
            **kwargs,
        )

    def register_run_step(
        self,
        checkpoint_dir: str,
        run_id: str,
        step: int,
        parent_run_id: str | None = None,
    ) -> bool:
        """
        Register a training step in the feature store.

        :param checkpoint_dir: Local directory containing the training checkpoint.
        :param run_id: Unique identifier for the training run.
        :param step: Training step number.
        :param parent_run_id: Optional parent run identifier.
        :return: True if the step was successfully registered, False otherwise.
        """

        metadata = {
            "project_name": self.project_name,
            "run_id": run_id,
            "training_step": step,
            "parent_run_id": parent_run_id,
        }

        run_name = f"{metadata['project_name']}_{metadata['run_id']}_{metadata['training_step']}"
        key_name = f"{step}.tar.gz"

        to_upload_dir = Path(checkpoint_dir)

        with TemporaryDirectory(prefix="upload_tar_") as tmpdir:
            tmpdir_path = Path(tmpdir)
            tmp_archive = tmpdir_path / key_name
            logger.info(
                "Creating archive %s from directory %s", tmp_archive, to_upload_dir
            )

            try:
                tar_compress(to_upload_dir, tmp_archive)
            except Exception:
                logger.exception(
                    "Failed to create archive %s from directory %s",
                    tmp_archive,
                    to_upload_dir,
                )
                raise

            with open(tmp_archive, "rb") as file:
                response = requests.post(
                    url=self.run_url,
                    params=metadata,
                    files={
                        "step_file": file,
                        "step": (None, json.dumps(metadata), "application/json"),
                    },
                )
            if not _check_response(response):
                return False
        logger.info(f"Successfully registered step {run_name}")
        return True

    def get_run_steps(self, run_id: str) -> list[str | int] | None:
        """
        Retrieve a list of training steps for a given run ID.

        :param run_id: Unique identifier for the training run.
        :return: List of training steps (str or int) or None if retrieval fails.
        """
        run_key = {"project_name": self.project_name, "run_id": run_id}
        try:
            response = requests.get(url=self.run_url + "/all", params=run_key)
        except requests.RequestException as exc:
            logger.error("Failed to call run service: %s", exc)
            return None
        if not _check_response(response):
            return None

        try:
            payload = response.json()
        except ValueError:
            logger.error("Run returned non-JSON response: %r", response.text)
            return None

        return [int(item["training_step"]) for item in payload]

    def remove_run_steps(self, run_id: str, steps: list[int]) -> bool:
        """
        Remove specified training steps from the feature store.

        :param run_id: Unique identifier for the training run.
        :param steps: List of training steps to remove.
        :return: True if removal was successful, False otherwise.
        """

        params = {
            "project_name": self.project_name,
            "run_id": run_id,
        }
        body = steps

        response = requests.delete(url=self.run_url, params=params, json=body)
        if not _check_response(response):
            return False
        logger.info("Successfully removed steps from feature store.")
        return True

    def download_run_step(self, checkpoints_dir: str, run_id: str, step: int) -> bool:
        """
        Download a specific training step from the feature store.

        :param checkpoints_dir: Local directory to save the downloaded checkpoint.
        :param run_id: Unique identifier for the training run.
        :param step: Training step number to download.
        :return: True if download was successful, False otherwise.
        """

        base_dir = Path(checkpoints_dir)
        dest_dir = base_dir / str(step)

        params = {
            "project_name": self.project_name,
            "run_id": run_id,
            "training_step": step,
        }

        response = requests.get(url=self.run_url + "/download", params=params)
        if not _check_response(response):
            return False

        if dest_dir.exists():
            try:
                if dest_dir.is_dir():
                    shutil.rmtree(dest_dir)
            except OSError:
                logger.exception("Failed to remove existing destination %s", dest_dir)
                return False

        try:
            with tarfile.open(
                fileobj=io.BytesIO(response.content), mode="r:*"
            ) as tar_file:
                tar_safe_extract(tar_file, base_dir)
            logger.info("Extraction succeeded to %s", dest_dir)
            return True
        except Exception:
            logger.exception("Failed to extract archive to %s", base_dir)
            # if extraction fails, attempt to clean up any partial extraction
            try:
                if dest_dir.exists():
                    shutil.rmtree(dest_dir)
            except Exception:
                logger.exception("Failed to cleanup partial extraction at %s", dest_dir)
            return False


def write_zip_from_response(
    response: requests.Response, output_dir: Path, unzip: bool
) -> Path:
    filename = response.headers["Content-Disposition"].split("filename=")[1][1:-1]
    local_path = output_dir / filename
    if not unzip:
        with open(local_path, "wb") as file:
            file.write(response.content)
    else:
        with zipfile.ZipFile(io.BytesIO(response.content)) as zip_file:
            os.mkdir(local_path)
            zip_file.extractall(local_path)
    return local_path


def tar_compress(source_path: str | Path, output_path: str | Path):
    source_path = Path(source_path)
    if not source_path.exists():
        raise FileNotFoundError(f"Local source directory does not exist: {source_path}")
    with tarfile.open(output_path, "w:gz") as tar:
        tar.add(source_path, arcname=os.path.basename(source_path))


def tar_safe_extract(tar: tarfile.TarFile, path: Path) -> None:
    for member in tar.getmembers():
        member_path = path.joinpath(member.name)
        abs_target = member_path.resolve()
        abs_base = path.resolve()
        if (
            not str(abs_target).startswith(str(abs_base) + os.sep)
            and abs_target != abs_base
        ):
            raise RuntimeError(
                "Tar file contains path traversal attempt: %s" % member.name
            )
    tar.extractall(path=str(path))


def zip_files_to_send(source_path: str):
    if os.path.isdir(source_path):
        shutil.make_archive(source_path, "zip", source_path)
    else:
        zipfile.ZipFile(source_path + ".zip", mode="w", compression=zipfile.ZIP_DEFLATED).write(
            source_path, os.path.basename(source_path)
        )


def _check_response(response: requests.Response, throw: bool = False) -> bool:
    if response.status_code != 200:
        try:
            error_message = response.json()
        except ValueError:
            error_message = response.text
        if throw:
            raise Exception(f"Request failed with code {response.status_code}: {error_message}")
        else:
            logger.error(f"Request failed with code {response.status_code}: {error_message}")
        return False
    return True


class MissingDatasetError(Exception):
    """
    Raised when a requested dataset is not found in the feature store.
    """

    pass
