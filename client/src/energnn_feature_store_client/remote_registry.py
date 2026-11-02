# Copyright (c) 2025, RTE (http://www.rte-france.com)
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0
#
from abc import ABC, abstractmethod


class RemoteRegistryClient(ABC):

    @abstractmethod
    def __init__(self, **kwargs):

        raise NotImplementedError

    @abstractmethod
    def register_run_step(
        self,
        checkpoint_dir: str,
        run_id: str,
        step: int,
        parent_run_id: str | None = None,
    ) -> bool:
        """
        Registers a training step checkpoint to the remote registry

        :param checkpoint_dir : The local directory where the checkpoint is stored.
        :param run_id : A unique identifier for the current training run.
        :param step : The training step number being registered.
        :param parent_run_id : A unique identifier for the parent run, if applicable. Defaults to None.
        :return : True if the training step was successfully registered, False otherwise.
        """

        raise NotImplementedError

    @abstractmethod
    def get_run_steps(self, run_id: str) -> list[str | int] | None:
        """
        Retrieves all training steps for a given run ID from the remote registry.
        Returns a list of step numbers as strings or as integers or None if retrieval fails.
        """

        raise NotImplementedError

    @abstractmethod
    def remove_run_steps(self, run_id: str, steps: list[int]) -> bool:
        """
        Removes specified training steps for a given run ID from the remote registry.
        Returns True if removal is successful, False otherwise.
        """

        raise NotImplementedError

    @abstractmethod
    def download_run_step(self, checkpoints_dir: str, run_id: str, step: int) -> bool:
        """
        Downloads a specific training step checkpoint for a given run ID from the remote registry.
        Saves the checkpoint to the specified local directory.
        Returns True if download is successful, False otherwise.
        """

        raise NotImplementedError

    @abstractmethod
    def register_run_config(self, config_path: str, run_id: str) -> bool:
        """
        Registers a configuration file for a specific run into the remote registry.

        :param config_path: Path to the configuration file.
        :param run_id: Identifier of the run.
        :return: True if the configuration is registered successfully, False otherwise.
        """

        raise NotImplementedError

    @abstractmethod
    def download_run_config(self, run_id: str, output_dir: str) -> bool:
        """
        Downloads the configuration file for a specific run from the remote registry.

        :param run_id: Identifier of the run.
        :param output_dir: Local directory where the configuration will be saved.
        :return: True if the download is successful, False otherwise.
        """

        raise NotImplementedError
