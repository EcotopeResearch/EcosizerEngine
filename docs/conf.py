import os
import sys

sys.path.insert(0, os.path.abspath("../src"))

project   = "EcosizerEngine"
author    = "Ecotope Inc."
copyright = "2024, Ecotope Inc."
release   = "3.0.0"

extensions = [
    "sphinx.ext.autodoc",
    "sphinx.ext.napoleon",
    "sphinx.ext.viewcode",
    "sphinx.ext.intersphinx",
]

napoleon_numpy_docstring   = True
napoleon_google_docstring  = False
napoleon_use_param         = True
napoleon_use_rtype         = True

autodoc_default_options = {
    "members":          True,
    "undoc-members":    False,
    "show-inheritance": True,
    "special-members":  "__init__",
}
autodoc_member_order = "bysource"

intersphinx_mapping = {
    "python": ("https://docs.python.org/3", None),
    "numpy":  ("https://numpy.org/doc/stable", None),
}

html_theme = "furo"
html_title = "EcosizerEngine"

exclude_patterns = ["_build"]
