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
"""Wrapper to check DISDRODB Metadata Archive Compliance from terminal."""
import sys

import click

sys.tracebacklimit = 0  # avoid full traceback error if occur


@click.command()
@click.option("--base_dir", type=str, show_default=True, default=None, help="DISDRODB base directory")
@click.option("--raise_error", type=bool, show_default=True, default=True, help="Whether to raise error of finish the check")
def disdrodb_check_metadata_archive(base_dir=None, raise_error=True):
    from disdrodb.metadata.check_metadata import check_archive_metadata_compliance

    check_archive_metadata_compliance(base_dir=base_dir, raise_error=raise_error)