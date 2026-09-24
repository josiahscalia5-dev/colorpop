#!/bin/sh
# Rebuild all Level 1 art from reference/lvl_crop.png (about 2 minutes). Deterministic: running it
# again reproduces the committed files byte for byte.
# Needs: python3 with numpy, scipy, pillow, opencv-contrib-python-headless (for cv2.xphoto).
# lvl_seg2.py (character masks) is not re-run: its output _lvl_masks.npz was reviewed by hand.
set -e
cd "$(dirname "$0")"
python3 lvl_build.py    # clean base + character sprites
python3 lvl_holes.py    # empty holes
python3 lvl_hud.py      # pause sprite, live numbers erased
python3 lvl_ground.py   # foreground foliage, ground for tall phones, side padding -> bg.png
python3 lvl_export.py   # level.json
python3 sfx.py          # sound effects
