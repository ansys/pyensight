"""Sphinx documentation configuration file."""
from datetime import datetime
import json
import os
import sys

from ansys.pyensight.core import VERSION as __version__
from ansys_sphinx_theme import ansys_favicon, get_version_match, pyansys_logo_black
from sphinx_gallery.sorting import FileNameSortKey

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "src"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "src", "ansys"))

# Project information
project = "ansys.pyensight.core"
copyright = f"(c) {datetime.now().year} ANSYS, Inc. All rights reserved"
author = "Ansys Inc."
release = version = __version__

cname = os.getenv("DOCUMENTATION_CNAME", "ensight.docs.pyansys.com")
"""The canonical name of the webpage hosting the documentation."""

# HTML output options
html_short_title = html_title = "PyEnSight"
html_logo = pyansys_logo_black
html_theme = "ansys_sphinx_theme"
html_favicon = ansys_favicon
html_theme_options = {
    "check_switcher": False,
    "switcher": {
        "json_url": f"https://{cname}/release/versions.json",
        "version_match": get_version_match(__version__),
    },
    "navbar_end": ["version-switcher", "theme-switcher", "navbar-icon-links"],
    "github_url": "https://github.com/ansys/pyensight",
    "show_prev_next": False,
    "show_breadcrumbs": True,
    "sidebarwidth": 250,
}

# Sphinx extensions
extensions = [
    # "sphinx.ext.napoleon",
    "numpydoc",
    "sphinx.ext.autodoc",
    "sphinx.ext.autosummary",
    "sphinx.ext.coverage",
    "sphinx.ext.doctest",
    "sphinx.ext.extlinks",
    "sphinx.ext.intersphinx",
    "sphinx_copybutton",
    "sphinx_gallery.gen_gallery",
    "sphinxcontrib.mermaid",
    "sphinxcontrib.jquery",
    "sphinxcontrib.openapi",
    # "ansys_sphinx_theme",
]

autoapi_options = [
    "members",
    "undoc-members",
    "private-members",
    "special-members",
    "show-inheritance",
    "show-module-summary",
    "imported-members",
]

# Intersphinx mapping
intersphinx_mapping = {
    "python": ("https://docs.python.org/3", None),
    # kept here as an example
    # "scipy": ("https://docs.scipy.org/doc/scipy/reference", None),
    # "numpy": ("https://numpy.org/devdocs", None),
    # "matplotlib": ("https://matplotlib.org/stable", None),
    # "pandas": ("https://pandas.pydata.org/pandas-docs/stable", None),
    # "pyvista": ("https://docs.pyvista.org/", None),
}

# numpydoc configuration
numpydoc_show_class_members = False
numpydoc_xref_param_type = True

linkcheck_ignore = [
    r"http://localhost:\d+/",
    r"https://cubit.sandia.gov/public/verdict.html",
    r"https://github.com/ansys/pyensight/issues",
]


# Consider enabling numpydoc validation. See:
# https://numpydoc.readthedocs.io/en/latest/validation.html#
numpydoc_validate = True
numpydoc_validation_checks = {
    "GL06",  # Found unknown section
    "GL07",  # Sections are in the wrong order.
    # "GL08",  # The object does not have a docstring
    "GL09",  # Deprecation warning should precede extended summary
    "GL10",  # reST directives {directives} must be followed by two colons
    # "SS01",  # No summary found
    "SS02",  # Summary does not start with a capital letter
    # "SS03", # Summary does not end with a period
    "SS04",  # Summary contains heading whitespaces
    # "SS05", # Summary must start with infinitive verb, not third person
    "RT02",  # The first line of the Returns section should contain only the
    # type, unless multiple values are being returned"
}

# -- Sphinx Gallery Options
examples_source = os.path.join(os.path.dirname(__file__), "examples_source")
default_thumb = os.path.join(os.path.dirname(__file__), "_static", "default_thumb.png")

sphinx_gallery_conf = {
    # convert rst to md for ipynb
    "pypandoc": False,
    # path to your examples scripts
    "examples_dirs": [examples_source],
    # path where to save gallery generated examples
    "gallery_dirs": ["_examples"],
    # Pattern to search for example files
    "filename_pattern": r"\.py",
    # Remove the "Download all examples" button from the top level gallery
    "download_all_examples": False,
    # Sort gallery example by file name instead of number of lines (default)
    "within_subsection_order": FileNameSortKey,
    # directory where function granular galleries are stored
    "backreferences_dir": None,
    # the initial notebook cell
    "first_notebook_cell": ("# PyEnSight example Notebook\n" "#\n"),
    "default_thumb_file": default_thumb,
    "plot_gallery": False,
}

add_module_names = False
# static path
html_static_path = ["_static"]

html_js_files = [
    "js/mermaid.js",
    "jquery.js",
]

html_css_files = [
    "css/ansys-sphinx-theme.css",
    "css/breadcrumbs.css",
]

# Add any paths that contain templates here, relative to this directory.
templates_path = ["_templates"]

# The suffix(es) of source filenames.
source_suffix = ".rst"
if os.environ.get("FASTDOCS", "0") == "1":
    exclude_patterns = [
        "class_documentation.rst",
        "object_documentation.rst",
        "native_documentation.rst",
    ]

# The master toctree document.
master_doc = "index"

# The language for content autogenerated by Sphinx. Refer to documentation
# for a list of supported languages.
#
# This is also used if you do content translation via gettext catalogs.
# Usually you set "language" from the command line for these cases.
language = "en"

# exclude traditional Python prompts from the copied code
copybutton_prompt_text = r">>> ?|\.\.\. "
copybutton_prompt_is_regexp = True


# In PyEnSight we have both upper and lowercase versions of the
# ENSOBJ properties.  We need to suppress the lowercase versions
# of the properties for Linux sphinx generation.
with open("skip_items.json", "r") as fp:
    s = fp.read()
skip_items = json.loads(s)


def lowercase_property_skip(app, what, name, obj, skip, options):
    # Testing:
    # print(app, what, name, obj, skip, options)
    if what == "property":
        if name.islower():
            # Filter out the "duplicate" lowercase properties, for ENS_OBJ subclasses
            # These have a special note in their docstrings
            if "Note: both '" in obj.__doc__:
                return True
    if name.startswith("__") and name.endswith("__"):
        return not (name == "__OBJID__")
    if name in skip_items:
        if what == skip_items[name].get("what", ""):
            return True
    if name.startswith("_"):
        return True
    return False


# Attach lowercase_property_skip to the skip event
def setup(app):
    app.connect("autodoc-skip-member", lowercase_property_skip)
