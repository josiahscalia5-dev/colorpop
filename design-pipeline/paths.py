"""Repository locations shared by the design pipeline scripts (run them from any directory)."""
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REF = os.path.join(ROOT, 'reference')                 # reference artwork (inputs)
ASSETS = os.path.join(ROOT, 'app-assets')             # final art shipped in the app
DATA = os.path.join(ASSETS, 'level')                  # reviewed level geometry + masks
WORK = os.path.join(ROOT, 'design-pipeline', '_work')  # intermediates and previews (not committed)


def ref(name):
    return os.path.join(REF, name)


def work(name):
    os.makedirs(WORK, exist_ok=True)
    return os.path.join(WORK, name)


def data(name):
    return os.path.join(DATA, name)


def asset_dir(*parts):
    d = os.path.join(ASSETS, *parts)
    os.makedirs(d, exist_ok=True)
    return d
