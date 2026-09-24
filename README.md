# Color Pop — Android game (work in progress)

**Status: art preparation stage. There is NO buildable Android app in this folder yet.**
Do not start over — continue from the assets and measurements below.

Screens in scope for the first build (nothing else):
1. Welcome / Home screen
2. Level 1 gameplay ("HIT THE GREEN ONES!")

The visual source of truth is `reference/color_pop_reference.png` (left phone = Home, right phone = Level 1).
The owner wants the screens to match the reference as exactly as technically possible — no redesign,
no substitute art, no colour/layout changes.

## Approach (decided)

The reference image itself is cut into layers, so every pixel comes from the owner's artwork:

- Background layer = reference with the UI elements removed and filled in.
- Every interactive element is its own sprite cut from the reference, drawn at its exact reference position,
  with real touch handling and a press animation.
- Only numbers that must change during play are re-rendered live (Lilita One font, white fill, dark outline,
  drop shadow — the closest match found to the reference lettering).
- Rendering: pure Java custom `SurfaceView`/`View` game loop, no AndroidX dependencies.
- Portrait, immersive full screen, no black bars.

### Fitting taller phones (reference is ~1.85:1, most phones ~2.2:1)
- **Home:** width-fit; art anchored to the bottom (title → beaver → tagline → PLAY → nav keep the exact
  reference arrangement); coin counter + settings pinned to the top; extra height becomes more sky above the
  title (`bg_full.png` already contains a ray-consistent sky extension, `pad_top` in `_meta.json`).
- **Level 1:** width-fit; HUD and scene stay exactly as in the reference from the top; extra height becomes
  more ground below the bottom holes (still to be built).
- Short (16:9) screens: height-fit with a few px of side bleed (`pad_side`).

## What exists

`reference/`
- `color_pop_reference.png` — original upload.
- `home_crop.png` (628×1157) and `lvl_crop.png` (622×1156) — the two phone screens cropped inside the bezel.
  **All coordinates below are in these crop pixel units.**

`app-assets/home/` (done)
- `bg_full.png` — Home background with coin pill, gear, PLAY and nav removed, fake "9:41" status bar and bezel
  corners removed, plus sky extension. Art origin inside it = (`pad_side`, `pad_top`) from `_meta.json`.
- Sprites with real alpha: `coin_pill.png`, `plus.png`, `gear.png`, `play.png`,
  `nav_missions.png`, `nav_shop.png`, `nav_rewards.png`, `nav_profile.png`.
- `_meta.json` — each sprite's top-left (x, y), size, and touch rectangle ("hit") in crop coordinates.
  Touch rects: coin pill (204,57)-(465,135); plus (400,64)-(461,129); gear centre (564.5,101.5) r40;
  PLAY (50,901)-(568,1045); Missions (14,1051)-(157,1149); Shop (163,1051)-(299,1149);
  Rewards (306,1051)-(450,1149); Profile (457,1051)-(606,1149).
- The inpainted areas under PLAY/nav are only seen briefly during the press animation.

`app-assets/level/` (in progress)
- `_lvl_geom.json` — the six holes (inner opening ellipse + outer rim ellipse, cx/cy/a/b) and which reference
  character sits in each: h1 green, h2 green, h3 green, h4 red, h5 green, h6 yellow.
- `_lvl_masks.npz` — reviewed GrabCut masks for all six characters (c1–c6), clipped at each hole's front rim.
- `characters/char_c1..c6.png` — the six characters cut from the reference with alpha; body colour extended ~34 px below the rim line so they can rise out of the hole (the part below the rim is hidden by a clip in-game). `characters/_meta.json` gives each sprite's position in crop coords and its hole.
- `design-pipeline/lvl_holes.py` — first attempt at empty holes + ground extension. The hole interiors work; the ground extension below the reference and parts of the rebuilt back rims (hole 2, hole 5 right side) still have visible defects and must be redone before shipping.

Level 1 HUD measurements (crop coords):
- Pause button: circle centre (65,116.5), r≈42.
- LEVEL 1 pill (170,79)-(402,145) — static art, translucent.
- Timer pill (431,79)-(602,145); live digits area (498,98)-(585,131), left-aligned after the stopwatch icon;
  the round starts at 00:30 so it reads 00:28 two seconds in, like the reference.
- Objective panel (29,170)-(600,308); live "12" area (508,210)-(582,282), centred; counts green targets left.
- Score panel (112,317)-(516,391), translucent; keep the art "SCORE:" and redraw only the number,
  left-aligned where the "0" is (352,335)-(374,369).

`design-pipeline/` — the Python scripts that produced the assets (OpenCV contrib + Pillow; paths inside the
scripts point at the original sandbox and need adjusting). `fonts/LilitaOne-Regular.ttf` is SIL OFL
(`OFL.txt` included) and can ship in the app.

## Remaining work, in order
1. Level 1 art: export character sprites from the masks; build empty holes (dark interior + back rim);
   pause sprite; erase the three live numbers from the panels; ground extension below the scene.
2. Android project (Java, minSdk 21, targetSdk 35), assets under `app/src/main/assets/`.
3. Home: sprites + real controls (PLAY → Level 1; settings opens sound/vibration toggles; nav and + show
   "coming soon" until those screens exist).
4. Level 1 gameplay: characters pop up/down in the six holes; tapping green = pop effect + score + target
   counter down; red/yellow react but never count; 30 s countdown; pause freezes everything; when the timer
   hits 0 or all greens are hit, stop and offer Play again / Home (placeholder until the Level Complete
   screen is designed).
5. Build, run on emulator/phone, screenshot both screens next to the reference, fix differences.

Not in scope yet: other levels, Level Complete screen, Worlds screen, coin economy.
