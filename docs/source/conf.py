# Configuration file for the Sphinx documentation builder.
#
# This file only contains a selection of the most common options. For a full
# list see the documentation:
# https://www.sphinx-doc.org/en/master/usage/configuration.html

# -- Path setup --------------------------------------------------------------

# If extensions (or modules to document with autodoc) are in another directory,
# add these directories to sys.path here. If the directory is relative to the
# documentation root, use os.path.abspath to make it absolute, like shown here.
#
import os
import sys
import shutil
import pandas as pd

# sys.path.insert(0, os.path.abspath(".."))
sys.path.insert(0, os.path.abspath("../.."))
sys.path.insert(0, os.path.join(os.path.abspath("../.."), "disdrodb"))
# sys.path.append(os.path.abspath(os.path.dirname(__file__)))

# -- Project information -----------------------------------------------------

project = "Disdrodb"
copyright = "LTE - Environmental Remote Sensing Lab - EPFL"
author = "LTE - Environmental Remote Sensing Lab - EPFL"


# Copy tutorial notebook
root_path = os.path.dirname(os.path.dirname(os.getcwd()))

in_path = os.path.join(
    root_path, "disdrodb", "L0", "readers", "reader_preparation.ipynb"
)
out_path = os.path.join(os.getcwd(), "reader_preparation.ipynb")

shutil.copyfile(in_path, out_path)


# Get key metadata from google sheet
doc_id = "1tHXC8ZH6_v_SaR1tRffSZCphZL6Y6ktDYp6y4ysE0gg"


def download_metadata_keys(sheet_id: str, csv_file_name: str) -> None:
    sheet_id = sheet_id
    sheet_url = f"https://docs.google.com/spreadsheets/d/{doc_id}/export?format=csv&gid={sheet_id}"
    df = pd.read_csv(sheet_url)
    df = df.replace("\*", "", regex=True)
    df.to_csv(csv_file_name, index=False)


list_csv = []
list_csv.append(["0", "OTT_parsivel.csv"])
list_csv.append(["2144525638", "Thies_LPM.csv"])
list_csv.append(["846927819", "Dimensions.csv"])
list_csv.append(["593773246", "Coordinates.csv"])
list_csv.append(["1539710336", "metadata.csv"])

for i in list_csv:
    download_metadata_keys(i[0], i[1])


# -- General configuration ---------------------------------------------------

# Add any Sphinx extension module names here, as strings. They can be
# extensions coming with Sphinx (named 'sphinx.ext.*') or your custom
# ones.
extensions = [
    "sphinx.ext.napoleon",
    "sphinx.ext.autodoc",
    "sphinx.ext.viewcode",
    "sphinx.ext.autosectionlabel",
    "nbsphinx",
]


# Add any paths that contain templates here, relative to this directory.
templates_path = ["_templates"]

# List of patterns, relative to source directory, that match files and
# directories to ignore when looking for source files.
# This pattern also affects html_static_path and html_extra_path.
exclude_patterns = ["_build", "Thumbs.db", ".DS_Store"]


# -- Options for HTML output -------------------------------------------------

# The theme to use for HTML and HTML Help pages.  See the documentation for
# a list of builtin themes.
#
html_theme = "sphinx_rtd_theme"

# Add any paths that contain custom static files (such as style sheets) here,
# relative to this directory. They are copied after the builtin static files,
# so a file named "default.css" will overwrite the builtin "default.css".
html_static_path = ["static"]
