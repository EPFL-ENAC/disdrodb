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
import shutil
import sys

# sys.path.insert(0, os.path.abspath(".."))
sys.path.insert(0, os.path.abspath("../.."))
sys.path.insert(0, os.path.join(os.path.abspath("../.."), "disdrodb"))


# -- Project information -----------------------------------------------------

project = "disdrodb"
copyright = "LTE - Environmental Remote Sensing Lab - EPFL"
author = "LTE - Environmental Remote Sensing Lab - EPFL"


# Copy tutorial notebook
root_path = os.path.dirname(os.path.dirname(os.getcwd()))

in_path = os.path.join(root_path, "tutorials", "reader_preparation.ipynb")
out_path = os.path.join(os.getcwd(), "reader_preparation.ipynb")

shutil.copyfile(in_path, out_path)


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
    "sphinx_mdinclude",
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
html_theme = "sphinx_book_theme"
html_title = "disdrodb"
html_theme_options = {
    "repository_url": "https://github.com/ltelab/disdrodb",
    "use_repository_button": True,
    "tocdepth": 2,  # Adjust the depth as needed
}

# Add any paths that contain custom static files (such as style sheets) here,
# relative to this directory. They are copied after the builtin static files,
# so a file named "default.css" will overwrite the builtin "default.css".
html_static_path = ["static"]


# -- Automatically run apidoc to generate rst from code ----------------------
# https://github.com/readthedocs/readthedocs.org/issues/1139
def run_apidoc(_):
    from sphinx.ext.apidoc import main

    sys.path.append(os.path.join(os.path.dirname(__file__), ".."))
    cur_dir = os.path.abspath(os.path.dirname(__file__))

    module_dir = os.path.join(cur_dir, "..", "..", "disdrodb")
    output_dir = os.path.join(cur_dir, "api")
    main(["-f", "-o", output_dir, module_dir])


def setup(app):
    app.connect("builder-inited", run_apidoc)
