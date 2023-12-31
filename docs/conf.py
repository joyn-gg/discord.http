import os
import sys

sys.path.insert(0, os.path.abspath(".."))
sys.path.append(os.path.abspath("extensions"))

project = "discord_http"
copyright = "2023, joyn.gg"
author = "AlexFlipnote"
release = "0.0.1"

extensions = [
    # Sphinx's own extensions
    "sphinx.ext.autodoc",
    "sphinx.ext.extlinks",
    "sphinx.ext.napoleon",
    "sphinx.ext.viewcode",
    "sphinx.ext.intersphinx",

    # Third party extensions
    "myst_parser",
    "google_analytics",
]

exclude_patterns = ["_build", "Thumbs.db", ".DS_Store"]
pygments_style = "sphinx"

html_static_path = ["_static"]
html_theme = "furo"
html_title = "discord.http docs"
html_favicon = "favicon.ico"
master_doc = "index"

# Google Analytics
ga_enabled = True
ga_id = "G-HVZQ2H4TGR"

source_suffix = {
    ".rst": "restructuredtext",
    ".txt": "markdown",
    ".md": "markdown",
}

# Link tree
extlinks = {
    "github": ("https://github.com/joyn-gg/discord.http%s", "%s"),
    "discord": ("https://discord.gg/jV2PgM5MHR%s", "%s"),
}
