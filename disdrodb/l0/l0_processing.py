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
"""Implement DISDRODB L0 processing."""

import datetime
import functools
import glob
import logging
import os
import time

import dask
import dask.bag as db

# Standards
from disdrodb.api.checks import check_sensor_name
from disdrodb.api.io import get_disdrodb_path
from disdrodb.configs import get_base_dir

# Directory
from disdrodb.l0.create_directories import (
    create_directory_structure,
    create_initial_directory_structure,
)
from disdrodb.l0.io import (
    get_l0a_file_list,
    get_l0a_fpath,
    get_l0b_dir,
    get_l0b_fpath,
    get_raw_file_list,
    read_l0a_dataframe,
)
from disdrodb.l0.issue import read_issue
from disdrodb.l0.l0_reader import get_station_reader_function

# Metadata & Issue
from disdrodb.l0.metadata import read_metadata

# Logger
from disdrodb.utils.logger import (
    close_logger,
    create_file_logger,
    define_summary_log,
    log_error,
    log_info,
    log_warning,
)

logger = logging.getLogger(__name__)

# -----------------------------------------------------------------------------.
#### Creation of L0A and L0B Single Station File


def _delayed_based_on_kwargs(function):
    """Decorator to make the function delayed if its `parallel` argument is True."""

    @functools.wraps(function)
    def wrapper(*args, **kwargs):
        # Check if it must be a delayed function
        parallel = kwargs.get("parallel")
        # If parallel is True
        if parallel:
            # Enforce verbose to be False
            kwargs["verbose"] = False
            # Define the delayed task
            result = dask.delayed(function)(*args, **kwargs)
        else:
            # Else run the function
            result = function(*args, **kwargs)
        return result

    return wrapper


@_delayed_based_on_kwargs
def _generate_l0a(
    filepath,
    processed_dir,
    station_name,  # retrievable from filepath
    column_names,
    reader_kwargs,
    df_sanitizer_fun,
    force,
    verbose,
    parallel,
    issue_dict={},
):
    """Generate L0A file from raw file."""
    from disdrodb.l0.l0a_processing import (
        process_raw_file,
        write_l0a,
    )

    ##------------------------------------------------------------------------.
    # Create file logger
    filename = os.path.basename(filepath)
    logger = create_file_logger(
        processed_dir=processed_dir,
        product="L0A",
        station_name=station_name,
        filename=filename,
        parallel=parallel,
    )

    if not os.environ.get("PYTEST_CURRENT_TEST"):
        logger_fpath = logger.handlers[0].baseFilename
    else:
        logger_fpath = None

    ##------------------------------------------------------------------------.
    # Log start processing
    msg = f"L0A processing of {filename} has started."
    log_info(logger=logger, msg=msg, verbose=verbose)

    ##------------------------------------------------------------------------.
    # Retrieve metadata
    attrs = read_metadata(campaign_dir=processed_dir, station_name=station_name)

    # Retrieve sensor name
    sensor_name = attrs["sensor_name"]
    check_sensor_name(sensor_name)

    ##------------------------------------------------------------------------.
    try:
        #### - Read raw file into a dataframe and sanitize to L0A format
        df = process_raw_file(
            filepath=filepath,
            column_names=column_names,
            reader_kwargs=reader_kwargs,
            df_sanitizer_fun=df_sanitizer_fun,
            sensor_name=sensor_name,
            verbose=verbose,
            issue_dict=issue_dict,
        )

        ##--------------------------------------------------------------------.
        #### - Write to Parquet
        fpath = get_l0a_fpath(df=df, processed_dir=processed_dir, station_name=station_name)
        write_l0a(df=df, fpath=fpath, force=force, verbose=verbose)

        ##--------------------------------------------------------------------.
        # Clean environment
        del df

        # Log end processing
        msg = f"L0A processing of {filename} has ended."
        log_info(logger=logger, msg=msg, verbose=verbose)

    # Otherwise log the error
    except Exception as e:
        error_type = str(type(e).__name__)
        msg = f"{error_type}: {e}"
        log_error(logger=logger, msg=msg, verbose=False)

    # Close the file logger
    close_logger(logger)

    # Return the logger file path
    return logger_fpath


def _generate_l0b(
    filepath,
    processed_dir,  # retrievable from filepath
    station_name,  # retrievable from filepath
    force,
    verbose,
    debugging_mode,
    parallel,
):
    from disdrodb.l0.l0b_processing import (
        create_l0b_from_l0a,
        write_l0b,
    )

    # -----------------------------------------------------------------.
    # Create file logger
    filename = os.path.basename(filepath)
    logger = create_file_logger(
        processed_dir=processed_dir,
        product="L0B",
        station_name=station_name,
        filename=filename,
        parallel=parallel,
    )
    if not os.environ.get("PYTEST_CURRENT_TEST"):
        logger_fpath = logger.handlers[0].baseFilename
    else:
        logger_fpath = None

    ##------------------------------------------------------------------------.
    # Log start processing
    msg = f"L0B processing of {filename} has started."
    log_info(logger, msg, verbose=verbose)

    ##------------------------------------------------------------------------.
    # Retrieve metadata
    attrs = read_metadata(campaign_dir=processed_dir, station_name=station_name)

    # Retrieve sensor name
    sensor_name = attrs["sensor_name"]
    check_sensor_name(sensor_name)

    ##------------------------------------------------------------------------.
    try:
        # Read L0A Apache Parquet file
        df = read_l0a_dataframe(filepath, verbose=verbose, debugging_mode=debugging_mode)
        # -----------------------------------------------------------------.
        # Create xarray Dataset
        ds = create_l0b_from_l0a(df=df, attrs=attrs, verbose=verbose)

        # -----------------------------------------------------------------.
        # Write L0B netCDF4 dataset
        fpath = get_l0b_fpath(ds, processed_dir, station_name)
        write_l0b(ds, fpath=fpath, force=force)

        ##--------------------------------------------------------------------.
        # Clean environment
        del ds, df

        # Log end processing
        msg = f"L0B processing of {filename} has ended."
        log_info(logger, msg, verbose=verbose)

    # Otherwise log the error
    except Exception as e:
        error_type = str(type(e).__name__)
        msg = f"{error_type}: {e}"
        log_error(logger, msg, verbose=verbose)

    # Close the file logger
    close_logger(logger)

    # Return the logger file path
    return logger_fpath


def _generate_l0b_from_nc(
    filepath,
    processed_dir,
    station_name,  # retrievable from filepath
    dict_names,
    ds_sanitizer_fun,
    force,
    verbose,
    parallel,
):
    from disdrodb.l0.l0b_nc_processing import process_raw_nc
    from disdrodb.l0.l0b_processing import write_l0b

    # -----------------------------------------------------------------.
    # Create file logger
    filename = os.path.basename(filepath)
    logger = create_file_logger(
        processed_dir=processed_dir,
        product="L0B",
        station_name=station_name,
        filename=filename,
        parallel=parallel,
    )
    logger_fpath = logger.handlers[0].baseFilename

    ##------------------------------------------------------------------------.
    # Log start processing
    msg = f"L0B processing of {filename} has started."
    log_info(logger, msg, verbose=verbose)

    ##------------------------------------------------------------------------.
    # Retrieve metadata
    attrs = read_metadata(campaign_dir=processed_dir, station_name=station_name)

    # Retrieve sensor name
    sensor_name = attrs["sensor_name"]
    check_sensor_name(sensor_name)

    ##------------------------------------------------------------------------.
    try:
        # Read the raw netCDF and convert to DISDRODB format
        ds = process_raw_nc(
            filepath=filepath,
            dict_names=dict_names,
            ds_sanitizer_fun=ds_sanitizer_fun,
            sensor_name=sensor_name,
            verbose=verbose,
            attrs=attrs,
        )
        # -----------------------------------------------------------------.
        # Write L0B netCDF4 dataset
        fpath = get_l0b_fpath(ds, processed_dir, station_name)
        write_l0b(ds, fpath=fpath, force=force)

        ##--------------------------------------------------------------------.
        # Clean environment
        del ds

        # Log end processing
        msg = f"L0B processing of {filename} has ended."
        log_info(logger, msg, verbose=verbose)

    # Otherwise log the error
    except Exception as e:
        error_type = str(type(e).__name__)
        msg = f"{error_type}: {e}"
        log_error(logger, msg, verbose=verbose)

    # Close the file logger
    close_logger(logger)

    # Return the logger file path
    return logger_fpath


####------------------------------------------------------------------------.
#### Creation of L0A and L0B Single Station Files


def run_l0a(
    raw_dir,
    processed_dir,
    station_name,
    # L0A reader argument
    glob_patterns,
    column_names,
    reader_kwargs,
    df_sanitizer_fun,
    # Processing options
    parallel,
    verbose,
    force,
    debugging_mode,
):
    """Run the L0A processing for a specific DISDRODB station.

    This function is called in each reader to convert raw text files into DISDRODB L0A products.

    Parameters
    ----------
    raw_dir : str
        The directory path where all the raw content of a specific campaign is stored.
        The path must have the following structure: ``<...>/DISDRODB/Raw/<DATA_SOURCE>/<CAMPAIGN_NAME>``.
        Inside the ``raw_dir`` directory, it is required to adopt the following structure::

            - ``/data/<station_name>/<raw_files>``
            - ``/metadata/<station_name>.yml``

        **Important points:**

        - For each ``<station_name>``, there must be a corresponding YAML file in the metadata subfolder.
        - The ``campaign_name`` are expected to be UPPER CASE.
        - The ``<CAMPAIGN_NAME>`` must semantically match between:
            - the ``raw_dir`` and ``processed_dir`` directory paths;
            - with the key ``campaign_name`` within the metadata YAML files.

    processed_dir : str
        The desired directory path for the processed DISDRODB L0A and L0B products.
        The path should have the following structure: ``<...>/DISDRODB/Processed/<DATA_SOURCE>/<CAMPAIGN_NAME>``.
        For testing purposes, this function exceptionally accepts also a directory path simply ending
        with ``<CAMPAIGN_NAME>`` (e.g., ``/tmp/<CAMPAIGN_NAME>``).

    station_name : str
    The name of the station.

    glob_patterns : str
        Glob pattern to search for data files in ``<raw_dir>/data/<station_name>``.

    column_names : list
        Column names of the raw text file.

    reader_kwargs : dict
        Arguments for Pandas ``read_csv`` function to open the text file.

    df_sanitizer_fun : callable, optional
        Sanitizer function to format the DataFrame into DISDRODB L0A standard.
        Default is ``None``.

    parallel : bool, optional
        If ``True``, process the files simultaneously in multiple processes.
        The number of simultaneous processes can be customized using the ``dask.distributed.LocalCluster``.
        If ``False``, process the files sequentially in a single process.
        Default is ``False``.

    verbose : bool, optional
        If ``True``, print detailed processing information to the terminal.
        Default is ``False``.

    force : bool, optional
        If ``True``, overwrite existing data in destination directories.
        If ``False``, raise an error if data already exists in destination directories.
        Default is ``False``.

    debugging_mode : bool, optional
        If ``True``, reduce the amount of data to process.
        Processes only the first 100 rows of 3 raw data files.
        Default is ``False``.

    """
    # ------------------------------------------------------------------------.
    # Start L0A processing
    if verbose:
        t_i = time.time()
        msg = f"L0A processing of station {station_name} has started."
        log_info(logger=logger, msg=msg, verbose=verbose)

    # ------------------------------------------------------------------------.
    # Create directory structure
    create_initial_directory_structure(
        raw_dir=raw_dir,
        processed_dir=processed_dir,
        product="L0A",
        station_name=station_name,
        force=force,
        verbose=verbose,
    )

    # -------------------------------------------------------------------------.
    # List files to process
    filepaths = get_raw_file_list(
        raw_dir=raw_dir,
        station_name=station_name,
        # L0A reader argument
        glob_patterns=glob_patterns,
        # Processing options
        verbose=verbose,
        debugging_mode=debugging_mode,
    )

    # -----------------------------------------------------------------.
    # Read issue YAML file
    issue_dict = read_issue(raw_dir=raw_dir, station_name=station_name)

    # -----------------------------------------------------------------.
    # Generate L0A files
    # - Loop over the files and save the L0A Apache Parquet files.
    # - If parallel=True, it does that in parallel using dask.delayed
    list_tasks = []
    for filepath in filepaths:
        list_tasks.append(
            _generate_l0a(
                filepath=filepath,
                processed_dir=processed_dir,
                station_name=station_name,
                # L0A reader argument
                column_names=column_names,
                reader_kwargs=reader_kwargs,
                df_sanitizer_fun=df_sanitizer_fun,
                issue_dict=issue_dict,
                # Processing options
                force=force,
                verbose=verbose,
                parallel=parallel,
            )
        )
    if parallel:
        list_logs = dask.compute(*list_tasks)
    else:
        list_logs = list_tasks
    # -----------------------------------------------------------------.
    # Define L0A summary logs
    define_summary_log(list_logs)

    # ---------------------------------------------------------------------.
    # End L0A processing
    if verbose:
        timedelta_str = str(datetime.timedelta(seconds=time.time() - t_i))
        msg = f"L0A processing of station {station_name} completed in {timedelta_str}"
        log_info(logger=logger, msg=msg, verbose=verbose)
    return None


def run_l0b(
    processed_dir,
    station_name,
    # Processing options
    parallel,
    force,
    verbose,
    debugging_mode,
):
    """
    Run the L0B processing for a specific DISDRODB station.

    Parameters
    ----------
    raw_dir : str
        The directory path where all the raw content of a specific campaign is stored.
        The path must have the following structure: ``<...>/DISDRODB/Raw/<DATA_SOURCE>/<CAMPAIGN_NAME>``.
        Inside the ``raw_dir`` directory, it is required to adopt the following structure::

            - ``/data/<station_name>/<raw_files>``
            - ``/metadata/<station_name>.yml``

        **Important points:**

        - For each ``<station_name>``, there must be a corresponding YAML file in the metadata subfolder.
        - The ``campaign_name`` are expected to be UPPER CASE.
        - The ``<CAMPAIGN_NAME>`` must semantically match between:
            - the ``raw_dir`` and ``processed_dir`` directory paths;
            - with the key ``campaign_name`` within the metadata YAML files.

    processed_dir : str
        The desired directory path for the processed DISDRODB L0A and L0B products.
        The path should have the following structure: ``<...>/DISDRODB/Processed/<DATA_SOURCE>/<CAMPAIGN_NAME>``.
        For testing purposes, this function exceptionally accepts also a directory path simply ending
        with ``<CAMPAIGN_NAME>`` (e.g., ``/tmp/<CAMPAIGN_NAME>``).

    station_name : str
        The name of the station.

    force : bool, optional
        If ``True``, overwrite existing data in destination directories.
        If ``False``, raise an error if data already exists in destination directories.
        Default is ``False``.

    verbose : bool, optional
        If ``True``, print detailed processing information to the terminal.
        Default is ``True``.

    parallel : bool, optional
        If ``True``, process the files simultaneously in multiple processes.
        The number of simultaneous processes can be customized using the ``dask.distributed.LocalCluster``.
        Ensure that the ``threads_per_worker`` (number of thread per process) is set to 1 to avoid HDF errors.
        Also, ensure to set the ``HDF5_USE_FILE_LOCKING`` environment variable to ``False``.
        If ``False``, process the files sequentially in a single process.
        Default is ``False``.

    debugging_mode : bool, optional
        If ``True``, reduce the amount of data to process.
        Only the first 3 raw data files will be processed.
        Default is ``False``.

    """
    # -----------------------------------------------------------------.
    # Retrieve metadata
    attrs = read_metadata(campaign_dir=processed_dir, station_name=station_name)

    # Skip run_l0b processing if the raw data are netCDFs
    if attrs["raw_data_format"] == "netcdf":
        return None

    # -----------------------------------------------------------------.
    # Start L0B processing
    if verbose:
        t_i = time.time()
        msg = f"L0B processing of station_name {station_name} has started."
        log_info(logger=logger, msg=msg, verbose=verbose)

    # -------------------------------------------------------------------------.
    # Create directory structure
    create_directory_structure(
        processed_dir=processed_dir,
        product="L0B",
        station_name=station_name,
        force=force,
        verbose=verbose,
    )

    ##----------------------------------------------------------------.
    # Get L0A files for the station
    filepaths = get_l0a_file_list(
        processed_dir=processed_dir,
        station_name=station_name,
        debugging_mode=debugging_mode,
    )

    # -----------------------------------------------------------------.
    # Generate L0B files
    # Loop over the L0A files and save the L0B netCDF files.
    # - If parallel=True, it does that in parallel using dask.bag
    #   Settings npartitions=len(filepaths) enable to wait prior task on a core
    #   finish before starting a new one.
    if not parallel:
        list_logs = []
        for filepath in filepaths:
            list_logs.append(
                _generate_l0b(
                    filepath=filepath,
                    processed_dir=processed_dir,
                    station_name=station_name,
                    force=force,
                    verbose=verbose,
                    debugging_mode=debugging_mode,
                    parallel=parallel,
                )
            )
    else:
        bag = db.from_sequence(filepaths, npartitions=len(filepaths))
        list_logs = bag.map(
            _generate_l0b,
            processed_dir=processed_dir,
            station_name=station_name,
            force=force,
            verbose=verbose,
            debugging_mode=debugging_mode,
            parallel=parallel,
        ).compute()

    # -----------------------------------------------------------------.
    # Define L0B summary logs
    define_summary_log(list_logs)

    # -----------------------------------------------------------------.
    # End L0B processing
    if verbose:
        timedelta_str = str(datetime.timedelta(seconds=time.time() - t_i))
        msg = f"L0B processing of station_name {station_name} completed in {timedelta_str}"
        log_info(logger=logger, msg=msg, verbose=verbose)
    return None


def run_l0b_from_nc(
    raw_dir,
    processed_dir,
    station_name,
    # Reader argument
    glob_patterns,
    dict_names,
    ds_sanitizer_fun,
    # Processing options
    parallel,
    verbose,
    force,
    debugging_mode,
):
    """Run the L0B processing for a specific DISDRODB station with raw netCDFs.

    This function is called in the reader where raw netCDF files must be converted into DISDRODB L0B format.

    Parameters
    ----------
    raw_dir : str
        The directory path where all the raw content of a specific campaign is stored.
        The path must have the following structure: ``<...>/DISDRODB/Raw/<DATA_SOURCE>/<CAMPAIGN_NAME>``.
        Inside the ``raw_dir`` directory, it is required to adopt the following structure::

            - ``/data/<station_name>/<raw_files>``
            - ``/metadata/<station_name>.yml``

        **Important points:**

        - For each ``<station_name>``, there must be a corresponding YAML file in the metadata subfolder.
        - The ``campaign_name`` are expected to be UPPER CASE.
        - The ``<CAMPAIGN_NAME>`` must semantically match between:
            - the ``raw_dir`` and ``processed_dir`` directory paths;
            - with the key ``campaign_name`` within the metadata YAML files.

    processed_dir : str
        The desired directory path for the processed DISDRODB L0A and L0B products.
        The path should have the following structure: ``<...>/DISDRODB/Processed/<DATA_SOURCE>/<CAMPAIGN_NAME>``.
        For testing purposes, this function exceptionally accepts also a directory path simply ending
        with ``<CAMPAIGN_NAME>`` (e.g., ``/tmp/<CAMPAIGN_NAME>``).

    station_name : str
        The name of the station.

    glob_patterns: str
        Glob pattern to search data files in ``<raw_dir>/data/<station_name>``.
        Example:  ``glob_patterns = "*.nc"``

    dict_names : dict
        Dictionary mapping raw netCDF variables/coordinates/dimension names
        to DISDRODB standards.

     ds_sanitizer_fun : object, optional
        Sanitizer function to format the raw netCDF into DISDRODB L0B standard.

    force : bool, optional
        If ``True``, overwrite existing data in destination directories.
        If ``False``, raise an error if data already exists in destination directories.
        Default is ``False``.

    verbose : bool, optional
        If ``True``, print detailed processing information to the terminal.
        Default is ``True``.

    parallel : bool, optional
        If ``True``, process the files simultaneously in multiple processes.
        The number of simultaneous processes can be customized using the ``dask.distributed.LocalCluster``.
        Ensure that the ``threads_per_worker`` (number of thread per process) is set to 1 to avoid HDF errors.
        Also, ensure to set the ``HDF5_USE_FILE_LOCKING`` environment variable to ``False``.
        If ``False``, process the files sequentially in a single process.
        If ``False``, multi-threading is automatically exploited to speed up I/0 tasks.
        Default is ``False``.

    debugging_mode : bool, optional
        If ``True``, reduce the amount of data to process.
        Only the first 3 raw netCDF files will be processed.
        Default is ``False``.

    """

    # ------------------------------------------------------------------------.
    # Start L0A processing
    if verbose:
        t_i = time.time()
        msg = f"L0B processing of station {station_name} has started."
        log_info(logger=logger, msg=msg, verbose=verbose)

    # ------------------------------------------------------------------------.
    # Create directory structure
    create_initial_directory_structure(
        raw_dir=raw_dir,
        processed_dir=processed_dir,
        product="L0B",
        station_name=station_name,
        force=force,
        verbose=verbose,
    )

    # -------------------------------------------------------------------------.
    # List files to process
    filepaths = get_raw_file_list(
        raw_dir=raw_dir,
        station_name=station_name,
        # Reader argument
        glob_patterns=glob_patterns,
        # Processing options
        verbose=verbose,
        debugging_mode=debugging_mode,
    )

    # -----------------------------------------------------------------.
    # Generate L0B files
    # - Loop over the raw netCDF files and convert it to DISDRODB netCDF format.
    # - If parallel=True, it does that in parallel using dask.bag
    #   Settings npartitions=len(filepaths) enable to wait prior task on a core
    #   finish before starting a new one.
    if not parallel:
        list_logs = []
        for filepath in filepaths:
            list_logs.append(
                _generate_l0b_from_nc(
                    filepath=filepath,
                    processed_dir=processed_dir,
                    station_name=station_name,
                    # Reader arguments
                    dict_names=dict_names,
                    ds_sanitizer_fun=ds_sanitizer_fun,
                    # Processing options
                    force=force,
                    verbose=verbose,
                    parallel=parallel,
                )
            )
    else:
        bag = db.from_sequence(filepaths, npartitions=len(filepaths))
        list_logs = bag.map(
            _generate_l0b_from_nc,
            processed_dir=processed_dir,
            station_name=station_name,
            # Reader arguments
            dict_names=dict_names,
            ds_sanitizer_fun=ds_sanitizer_fun,
            # Processing options
            force=force,
            verbose=verbose,
            parallel=parallel,
        ).compute()

    # -----------------------------------------------------------------.
    # Define L0B summary logs
    define_summary_log(list_logs)

    # ---------------------------------------------------------------------.
    # End L0B processing
    if verbose:
        timedelta_str = str(datetime.timedelta(seconds=time.time() - t_i))
        msg = f"L0B processing of station {station_name} completed in {timedelta_str}"
        log_info(logger=logger, msg=msg, verbose=verbose)
    return None


def run_l0b_concat(processed_dir, station_name, remove=False, verbose=False):
    """Concatenate all L0B netCDF files into a single netCDF file.

    The single netCDF file is saved at <processed_dir>/L0B.
    """
    from disdrodb.l0.l0b_processing import write_l0b
    from disdrodb.utils.netcdf import xr_concat_datasets

    # Create logger
    filename = f"concatenatation_{station_name}"
    logger = create_file_logger(
        processed_dir=processed_dir,
        product="L0B",
        station_name="",  # locate outside the station directory
        filename=filename,
        parallel=False,
    )

    # -------------------------------------------------------------------------.
    # Retrieve L0B files
    l0b_dir_path = get_l0b_dir(processed_dir, station_name)
    file_list = sorted(glob.glob(os.path.join(l0b_dir_path, "*.nc")))

    # -------------------------------------------------------------------------.
    # Check there are at least two files
    n_files = len(file_list)
    if n_files == 0:
        msg = f"No L0B file is available for concatenation in {l0b_dir_path}."
        log_error(logger=logger, msg=msg, verbose=False)
        raise ValueError(msg)

    if n_files == 1:
        msg = f"Only a single file is available for concatenation in {l0b_dir_path}."
        log_warning(logger=logger, msg=msg, verbose=verbose)

    # -------------------------------------------------------------------------.
    # Concatenate the files
    ds = xr_concat_datasets(file_list)

    # -------------------------------------------------------------------------.
    # Define the filepath of the concatenated L0B netCDF
    single_nc_fpath = get_l0b_fpath(ds, processed_dir, station_name, l0b_concat=True)
    force = True  # TODO add as argument
    write_l0b(ds, fpath=single_nc_fpath, force=force)

    # -------------------------------------------------------------------------.
    # Close file and delete
    ds.close()
    del ds

    # -------------------------------------------------------------------------.
    # If remove = True, remove all the single files
    if remove:
        log_info(logger=logger, msg="Removal of single L0B files started.", verbose=verbose)
        _ = [os.remove(fpath) for fpath in file_list]
        log_info(logger=logger, msg="Removal of single L0B files ended.", verbose=verbose)

    # -------------------------------------------------------------------------.
    # Close the file logger
    close_logger(logger)

    # Return the dataset
    return None


####--------------------------------------------------------------------------.
#### DISDRODB Station Functions


def run_l0a_station(
    # Station arguments
    data_source,
    campaign_name,
    station_name,
    # Processing options
    force: bool = False,
    verbose: bool = False,
    debugging_mode: bool = False,
    parallel: bool = True,
    base_dir: str = None,
):
    """
    Run the L0A processing of a specific DISDRODB station when invoked from the terminal.

    This function is intended to be called through the ``disdrodb_run_l0a_station``
    command-line interface.

    Parameters
    ----------
    data_source : str
        The name of the institution (for campaigns spanning multiple countries) or
        the name of the country (for campaigns or sensor networks within a single country).
        Must be provided in UPPER CASE.
    campaign_name : str
        The name of the campaign. Must be provided in UPPER CASE.
    station_name : str
        The name of the station.
    force : bool, optional
        If ``True``, existing data in the destination directories will be overwritten.
        If ``False`` (default), an error will be raised if data already exists in the destination directories.
    verbose : bool, optional
        If ``True`` (default), detailed processing information will be printed to the terminal.
        If ``False``, less information will be displayed.
    parallel : bool, optional
        If ``True``, files will be processed in multiple processes simultaneously
        with each process using a single thread.
        If ``False`` (default), files will be processed sequentially in a single process,
        and multi-threading will be automatically exploited to speed up I/O tasks.
    debugging_mode : bool, optional
        If ``True``, the amount of data processed will be reduced.
        Only the first 3 raw data files will be processed. By default, ``False``.
    base_dir : str, optional
        The base directory of DISDRODB, expected in the format ``<...>/DISDRODB``.
        If not specified, the path specified in the DISDRODB active configuration will be used.
    """
    base_dir = get_base_dir(base_dir)
    reader = get_station_reader_function(
        base_dir=base_dir,
        data_source=data_source,
        campaign_name=campaign_name,
        station_name=station_name,
    )
    # Define campaign raw_dir and process_dir
    raw_dir = get_disdrodb_path(
        base_dir=base_dir,
        product="RAW",
        data_source=data_source,
        campaign_name=campaign_name,
    )
    processed_dir = get_disdrodb_path(
        base_dir=base_dir,
        product="L0A",
        data_source=data_source,
        campaign_name=campaign_name,
        check_exist=False,
    )

    # Run L0A processing
    # --> The reader call the run_l0a within the custom defined reader function
    # --> For the special case of raw netCDF data, it calls the run_l0b_from_nc function
    reader(
        raw_dir=raw_dir,
        processed_dir=processed_dir,
        station_name=station_name,
        # Processing options
        force=force,
        verbose=verbose,
        debugging_mode=debugging_mode,
        parallel=parallel,
    )


def run_l0b_station(
    # Station arguments
    data_source,
    campaign_name,
    station_name,
    # Processing options
    force: bool = False,
    verbose: bool = True,
    parallel: bool = True,
    debugging_mode: bool = False,
    base_dir: str = None,
):
    """
    Run the L0B processing of a specific DISDRODB station when invoked from the terminal.

    This function is intended to be called through the ``disdrodb_run_l0b_station``
    command-line interface.

    Parameters
    ----------
    data_source : str
        The name of the institution (for campaigns spanning multiple countries) or
        the name of the country (for campaigns or sensor networks within a single country).
        Must be provided in UPPER CASE.
    campaign_name : str
        The name of the campaign. Must be provided in UPPER CASE.
    station_name : str
        The name of the station.
    force : bool, optional
        If ``True``, existing data in the destination directories will be overwritten.
        If ``False`` (default), an error will be raised if data already exists in the destination directories.
    verbose : bool, optional
        If ``True`` (default), detailed processing information will be printed to the terminal.
        If ``False``, less information will be displayed.
    parallel : bool, optional
        If ``True``, files will be processed in multiple processes simultaneously,
        with each process using a single thread to avoid issues with the HDF/netCDF library.
        If ``False`` (default), files will be processed sequentially in a single process,
        and multi-threading will be automatically exploited to speed up I/O tasks.
    debugging_mode : bool, optional
        If ``True``, the amount of data processed will be reduced.
        Only the first 100 rows of 3 L0A files will be processed. By default, ``False``.
    base_dir : str, optional
        The base directory of DISDRODB, expected in the format ``<...>/DISDRODB``.
        If not specified, the path specified in the DISDRODB active configuration will be used.

    """
    # Define campaign processed dir
    base_dir = get_base_dir(base_dir)
    processed_dir = get_disdrodb_path(
        base_dir=base_dir,
        product="L0B",
        data_source=data_source,
        campaign_name=campaign_name,
        check_exist=False,
    )
    # Run L0B
    run_l0b(
        processed_dir=processed_dir,
        station_name=station_name,
        # Processing options
        force=force,
        verbose=verbose,
        debugging_mode=debugging_mode,
        parallel=parallel,
    )


def run_l0b_concat_station(
    # Station arguments
    data_source,
    campaign_name,
    station_name,
    # L0B concat options
    remove_l0b=False,
    verbose=True,
    base_dir: str = None,
):
    """Define the L0B file concatenation of a station.

    This function is intended to be called through the ``disdrodb_run_l0b_concat station``
    command-line interface.

    Parameters
    ----------
    data_source : str
        The name of the institution (for campaigns spanning multiple countries) or
        the name of the country (for campaigns or sensor networks within a single country).
        Must be provided in UPPER CASE.
    campaign_name : str
        The name of the campaign. Must be provided in UPPER CASE.
    station_name : str
        The name of the station.
    verbose : bool, optional
        If ``True`` (default), detailed processing information will be printed to the terminal.
        If ``False``, less information will be displayed.
    base_dir : str, optional
        The base directory of DISDRODB, expected in the format ``<...>/DISDRODB``.
        If not specified, the path specified in the DISDRODB active configuration will be used.

    """
    # Retrieve processed_dir
    base_dir = get_base_dir(base_dir)
    processed_dir = get_disdrodb_path(
        base_dir=base_dir,
        product="L0B",
        data_source=data_source,
        campaign_name=campaign_name,
        check_exist=True,
    )

    # Run concatenation
    run_l0b_concat(
        processed_dir=processed_dir,
        station_name=station_name,
        remove=remove_l0b,
        verbose=verbose,
    )


####---------------------------------------------------------------------------.
