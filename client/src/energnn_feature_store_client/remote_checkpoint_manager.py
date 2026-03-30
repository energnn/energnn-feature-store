# Copyright (c) 2025, RTE (http://www.rte-france.com)
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0
#
from __future__ import annotations
import tempfile
import pathlib
import logging
import threading

from orbax.checkpoint import CheckpointManager
from .remote_registry import RemoteRegistryClient

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


def _make_local_tmpdir() -> pathlib.Path:
    tmp_root = tempfile.gettempdir()
    tmpdir = pathlib.Path(tempfile.mkdtemp(prefix="orbax_ckpt", dir=tmp_root))
    return tmpdir


class RemoteCheckpointManager(CheckpointManager):

    def __init__(
        self,
        remote_client: RemoteRegistryClient,
        run_id: str,
        directory: str | None = None,
        parent_run_id: str | None = None,
        sync_from_remote: bool = False,
        **kwargs,
    ):
        self._lock = threading.RLock()
        self._remote_client = remote_client
        self._run_id = run_id
        self._parent_run_id = parent_run_id
        local_dir = directory if directory is not None else _make_local_tmpdir()
        local_dir_str = str(local_dir)
        super().__init__(directory=local_dir_str, **kwargs)

        base_dir = pathlib.Path(local_dir_str)
        base_dir.mkdir(parents=True, exist_ok=True)

        if sync_from_remote:
            self.sync_checkpoints_from_remote()

    @property
    def run_id(self):
        return self._run_id

    @property
    def parent_run_id(self):
        return self._parent_run_id

    def _save_to_remote(self, step: int) -> None:

        step_dirname = self._step_name_format.build_name(step)

        saved_remote = self._remote_client.register_run_step(
            checkpoint_dir=f"{str(self.directory)}/{step_dirname}",
            run_id=self.run_id,
            step=step,
            parent_run_id=self.parent_run_id,
        )

        if not saved_remote:
            raise RuntimeError("Failed to save checkpoint to remote registry")

        self.reload()
        local_steps = self.all_steps()
        remote_steps = self._remote_client.get_run_steps(self.run_id)

        if remote_steps is None:
            raise RuntimeError("Failed to get remote keys")
        to_delete = [int(k) for k in remote_steps if int(k) not in local_steps]

        if not to_delete:
            logger.info("Nothing to delete")
            return

        logger.info("Deleting %d remote objects", len(to_delete))
        deleted = self._remote_client.remove_run_steps(
            run_id=self.run_id, steps=to_delete
        )
        if not deleted:
            logger.warning("Failed to delete %d remote objects", len(to_delete))

    def _download_and_extract_step(self, step: int) -> bool:
        return self._remote_client.download_run_step(
            checkpoints_dir=str(self.directory), run_id=self.run_id, step=step
        )

    def sync_checkpoints_from_remote(self) -> None:

        remote_steps = self._remote_client.get_run_steps(self.run_id)
        if remote_steps is None:
            raise RuntimeError("Failed to get remote keys")
        elif len(remote_steps) == 0:
            logger.info("No objects found on remote registry")
            return

        remote_steps = [int(i) for i in remote_steps]
        failed = []
        for step in remote_steps:
            downloaded = self._download_and_extract_step(step)
            if not downloaded:
                logger.warning(
                    "Failed to download checkpoint %d from remote registry", step
                )
                failed.append(step)

        if len(failed) == len(remote_steps):
            raise RuntimeError(
                "Failed to download all checkpoints from remote registry"
            )
        elif len(failed) > 0:
            logger.warning(
                "Failed to download %d checkpoints from remote registry", len(failed)
            )

    def latest_step(self) -> int | None:
        local_latest = super().latest_step()

        remote_steps = self._remote_client.get_run_steps(self.run_id)
        if remote_steps is None:
            raise RuntimeError("Failed to fetch remote keys")

        if len(remote_steps) == 0:
            return local_latest
        else:
            remote_steps = [int(i) for i in remote_steps]
            remote_latest = max(remote_steps)
            if local_latest is None:
                return remote_latest

        return max(local_latest, remote_latest)

    def save(self, step: int, **kwargs):

        with self._lock:
            saved = super().save(step, **kwargs)
            super().wait_until_finished()
            if saved:
                self._save_to_remote(step)
        return saved

    def restore(self, step: int | None = None, **kwargs):

        directory = self.directory
        if kwargs:
            if "directory" in kwargs:
                directory = kwargs["directory"] if kwargs["directory"] else directory

        directory = pathlib.Path(directory).resolve()

        if directory == pathlib.Path(self.directory).resolve():
            if step is None:
                step = self.latest_step()
            if step is not None:
                with self._lock:
                    step_dirname = self._step_name_format.build_name(step)
                    step_dir = pathlib.Path(self.directory) / step_dirname
                    if not step_dir.exists() or step_dir.is_file():
                        downloaded = self._download_and_extract_step(step)
                        if not downloaded:
                            logger.warning(
                                "Failed to download checkpoint %d from remote registry",
                                step,
                            )

        return super().restore(step, **kwargs)

    def delete(self, step: int) -> None:

        super().delete(step)
        super().wait_until_finished()

        remote_steps = self._remote_client.get_run_steps(self.run_id)

        if remote_steps is None:
            raise RuntimeError("Failed to get remote keys")
        elif len(remote_steps) == 0:
            logger.info("No objects found on remote registry")
            return

        remote_steps = [int(i) for i in remote_steps]

        if step in remote_steps:
            deleted = self._remote_client.remove_run_steps(
                run_id=self.run_id, steps=[step]
            )
            if not deleted:
                logger.warning(
                    "Failed to delete checkpoint %d from remote registry", step
                )
