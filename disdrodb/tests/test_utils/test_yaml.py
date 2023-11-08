#!/usr/bin/env python3

# -----------------------------------------------------------------------------.
# Copyright (c) 2021-2023 DISDRODB developers
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
# -----------------------------------------------------------------------------.
"""Test YAML utility."""

import os

import pytest
import yaml

from disdrodb import __root_path__
from disdrodb.utils.yaml import read_yaml

TEST_DATA_DIR = os.path.join(__root_path__, "disdrodb", "tests", "data")


def test_read_yaml():
    # Test reading a valid YAML file
    dictionary = {"key1": "value1", "key2": "value2"}
    valid_filepath = os.path.join(TEST_DATA_DIR, "test_check_metadata", "valid.yaml")

    assert read_yaml(valid_filepath) == dictionary

    # Test reading a non-existent YAML file
    non_existent_filepath = os.path.join(TEST_DATA_DIR, "test_check_metadata", "non_existent.yaml")
    with pytest.raises(FileNotFoundError):
        read_yaml(non_existent_filepath)

    # Test reading a YAML file with invalid syntax
    invalid_yaml_filepath = os.path.join(TEST_DATA_DIR, "test_check_metadata", "invalid.yaml")
    with pytest.raises(yaml.YAMLError):
        read_yaml(invalid_yaml_filepath)