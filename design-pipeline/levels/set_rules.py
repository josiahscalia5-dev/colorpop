"""Write a level script's RULES into its app-assets/<level>/level.json (no art rebuilt).

  python3 levels/set_rules.py level8
"""
import os, sys, json, importlib
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from paths import ROOT

name = sys.argv[1]
mod = importlib.import_module('levels.' + name)
path = os.path.join(ROOT, 'app-assets', name, 'level.json')
level = json.load(open(path))
level['rules'] = mod.RULES
json.dump(level, open(path, 'w'), indent=1)
print(name, 'rules:', json.dumps(mod.RULES))
