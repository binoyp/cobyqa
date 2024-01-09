# Configuration file for the Sphinx documentation builder.
#
# For the full list of built-in configuration values, see the documentation:
# https://www.sphinx-doc.org/en/master/usage/configuration.html
import inspect
import json
import re
import sys
from datetime import datetime
from pathlib import Path
from urllib.request import urlopen

import cobyqa


# -- Project information -----------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#project-information

project = 'COBYQA'
author = 'Tom M. Ragonneau and Zaikun Zhang'
copyright = f'2021\u2013{datetime.now().year}, {author}'

# Short version (including .devX, rcX, b1 suffixes if present).
version = re.sub(r'(\d+\.\d+)\.\d+(.*)', r'\1\2', cobyqa.__version__)
version = re.sub(r'(\.dev\d+).*?$', r'\1', version)

# Full version, including alpha/beta/rc tags.
release = cobyqa.__version__

# Retrieve statistics.
archive = urlopen('https://raw.githubusercontent.com/cobyqa/stats/main/archives/total.json')
downloads = json.loads(archive.read())


# -- General configuration ---------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#general-configuration

extensions = [
    'sphinx.ext.doctest',
    'sphinx.ext.intersphinx',
    'sphinx.ext.linkcode',
    'numpydoc',
    'sphinx_copybutton',
    'sphinx_substitution_extensions',
    'sphinxcontrib.bibtex',
]

templates_path = ['_templates']

exclude_patterns = []

today_fmt = '%B %d, %Y'

# The ReST default role to use for all documents.
default_role = 'autolink'

# Whether parentheses are appended to function and method role text.
add_function_parentheses = False

# String to include at the beginning of every source file.
rst_prolog = f"""
.. |release| replace:: {release}
.. |year| replace:: {datetime.now().year}
.. |pypi_downloads| replace:: {downloads['pypi']:,}
.. |github_downloads| replace:: {downloads['github']:,}
.. |total_downloads| replace:: {sum(downloads.values()):,}
"""

# Suppress 'WARNING: unknown mimetype for ..., ignoring'.
suppress_warnings = ['epub.unknown_project_files']


# -- Options for HTML output -------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#options-for-html-output

html_theme = 'pydata_sphinx_theme'

html_static_path = ['_static']

html_context = {
    'github_user': 'cobyqa',
    'github_repo': 'cobyqa',
    'github_version': 'main',
    'doc_path': 'doc/source',
}

html_theme_options = {
    'logo': {
        'text': project,
    },
    'switcher': {
        'json_url': 'https://www.cobyqa.com/en/latest/_static/switcher.json',
        'version_match': release,
    },
    'show_version_warning_banner': True,
    'icon_links': [
        {
            'name': f'GitHub ({downloads["github"]:,} downloads)',
            'url': f'https://github.com/{html_context["github_user"]}/{html_context["github_repo"]}',
            'icon': 'fa-brands fa-github',
        },
        {
            'name': f'PyPI ({downloads["pypi"]:,} downloads)',
            'url': 'https://pypi.org/project/cobyqa',
            'icon': 'fa-solid fa-box',
        },
    ],
    'navbar_persistent': ['search-button'],
    'navbar_end': ['version-switcher', 'theme-switcher', 'navbar-icon-links'],
    'navbar_align': 'left',
    'navigation_depth': 1,
    # 'announcement': '<p></p>',
}

html_title = f'{project} v{version} Manual'

htmlhelp_basename = 'cobyqa'


# -- Options for LaTeX output -------------------------------------------------

# Grouping the document tree into LaTeX files.
latex_documents = [
    ('index', 'cobyqa-ref.tex', 'COBYQA Manual', author, 'manual'),
]

latex_elements = {
    'papersize': 'a4paper',
    'fontenc': r'\usepackage[LGR,T1]{fontenc}',
    'preamble': r"""
\usepackage[bb=dsfontserif]{mathalpha}
\newcommand{\R}{\mathbb{R}}
\newcommand{\transpose}[1]{#1^{\mathsf{T}}}
\newcommand{\aeq}{A_{\scriptscriptstyle \mathcal{E}}}
\newcommand{\aub}{A_{\scriptscriptstyle \mathcal{I}}}
\newcommand{\beq}{b_{\scriptscriptstyle \mathcal{E}}}
\newcommand{\bub}{b_{\scriptscriptstyle \mathcal{I}}}
\newcommand{\ceq}{c_{\scriptscriptstyle \mathcal{E}}}
\newcommand{\cub}{c_{\scriptscriptstyle \mathcal{I}}}
\newcommand{\obj}{f}
\newcommand{\xbd}{\mathcal{X}}
\newcommand{\xl}{l}
\newcommand{\xu}{u}

% Increase the default table of content depth.
\setcounter{tocdepth}{2}
    """,
}


# -- Math support for HTML outputs -------------------------------------------

mathjax3_config = {
    'tex': {
        'macros': {
            'R': r'\mathbb{R}',
            'transpose': [r'#1^{\mathsf{T}}', 1],
            'aeq': r'A_{\scriptscriptstyle \mathcal{E}}',
            'aub': r'A_{\scriptscriptstyle \mathcal{I}}',
            'beq': r'b_{\scriptscriptstyle \mathcal{E}}',
            'bub': r'b_{\scriptscriptstyle \mathcal{I}}',
            'ceq': r'c_{\scriptscriptstyle \mathcal{E}}',
            'cub': r'c_{\scriptscriptstyle \mathcal{I}}',
            'obj': r'f',
            'xbd': r'\mathcal{X}',
            'xl': r'l',
            'xu': r'u',
        }
    }
}


# -- Generate autodoc summaries -----------------------------------------------

autosummary_generate = True


# -- Link to other projects' documentation ------------------------------------

intersphinx_mapping = {
    'numpy': ('https://numpy.org/doc/stable/', None),
    'scipy': ('https://docs.scipy.org/doc/scipy/', None),
}


# -- BibTeX citations ---------------------------------------------------------

bibtex_bibfiles = ['_static/cobyqa.bib']

bibtex_encoding = 'latin'

bibtex_default_style = 'plain'

bibtex_bibliography_header = """.. only:: html or text

    .. rubric:: References
"""

bibtex_footbibliography_header = bibtex_bibliography_header

bibtex_cite_id = 'cite-{bibliography_count}-{key}'

bibtex_footcite_id = 'footcite-{key}'

bibtex_bibliography_id = 'bibliography-{bibliography_count}'

bibtex_footbibliography_id = 'footbibliography-{footbibliography_count}'


# -- Add external links to source code ----------------------------------------

def linkcode_resolve(domain, info):
    if domain != 'py':
        return None

    # Get the object indicated by the module name.
    obj = sys.modules.get(info['module'])
    if obj is None:
        return None
    for part in info['fullname'].split('.'):
        try:
            obj = getattr(obj, part)
        except AttributeError:
            return None

    # Strip the decorators of the object.
    try:
        unwrap = inspect.unwrap
    except AttributeError:
        pass
    else:
        obj = unwrap(obj)

    # Get the relative path to the source of the object.
    try:
        fn = Path(inspect.getsourcefile(obj)).resolve(True)
    except TypeError:
        return None
    else:
        fn = fn.relative_to(Path(cobyqa.__file__).resolve(True).parent)

    # Ignore re-exports as their source files are not within the repository.
    module = inspect.getmodule(obj)
    if module is not None and not module.__name__.startswith('cobyqa'):
        return None

    # Get the line span of the object in the source file.
    try:
        source, lineno = inspect.getsourcelines(obj)
        lines = f'#L{lineno}-L{lineno + len(source) - 1}'
    except OSError:
        lines = ''

    repository = f'https://github.com/{html_context["github_user"]}/{html_context["github_repo"]}'
    if 'dev' in release:
        return f'{repository}/blob/{html_context["github_version"]}/cobyqa/{fn}{lines}'
    else:
        return f'{repository}/blob/v{release}/cobyqa/{fn}{lines}'
