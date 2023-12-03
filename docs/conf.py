# -*- coding: utf-8 -*-
import os
import sys
import sphinx_rtd_theme

# -- Project information -----------------------------------------------------

project = 'My Project'
author = 'Your Name'

# -- General configuration ---------------------------------------------------

extensions = [
    'sphinx.ext.autodoc',
    'sphinx.ext.napoleon',
    'sphinx_rtd_theme',
]

templates_path = ['_templates']
exclude_patterns = ['_build', 'Thumbs.db', '.DS_Store']

# -- Options for HTML output -------------------------------------------------

html_theme = 'sphinx_rtd_theme'
html_static_path = ['_static']

# -- Path setup --------------------------------------------------------------

sys.path.insert(0, os.path.abspath('../..'))

# -- Extension configuration -------------------------------------------------

# Add any custom configuration options for extensions here

# -- Additional configuration ------------------------------------------------

# Add any additional configuration options here
