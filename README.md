# Color Pop — Android game (work in progress)

**Status: playable test build 0.9 (before Level 10): Level 3 rebuilt in high resolution (owner-approved) with its tap-and-fire; Level 8 in its new, owner-approved design, with its harder rules.** Home and Levels 1, 3, 6 and 8 are implemented as an Android app
(Java, no dependencies) and verified by rendering the real screens on 14 phone configurations and
comparing them with the reference. Do not start over — continue from here.

Screens:
1. Welcome / Home screen — done
2. Level 1 ("HIT THE GREEN ONES!") — done
3. Level 3 ("HIT THE PURPLE ONES!", combo, tap-and-fire with a demonstration) — done, rebuilt in high resolution (see below)
4. Level 6 ("HIT THE STARS!", combo, bombs) — done
5. Level 8 ("HIT THE GOLD ONES!", look-alike decoys, SPEED INCREASED!) — done, new design (see below)
6. Level 10, Level Complete, Worlds — to do (second reference sheet)

The levels are played in the order 1 → 3 → 6 → 8 (→ 10); winning one unlocks the next (saved) and the
round-over panel offers NEXT LEVEL. PLAY goes straight into Level 1 until another level is unlocked;
from then on it opens LEVELS (placeholder panel in the HUD style), where every level reached can be
replayed, the first one not won yet is green and the rest are locked.

Difficulty rises gradually through the rules only (the screens are the references):

| Level | Time | Targets | New challenge |
|---|---|---|---|
| 1 | 30 s | 12 | tap the greens (red and yellow don't count) |
| 3 | 30 s | 12 | tap-and-fire: a tap launches a purple gem from the player's side (bottom centre) that flies to the tapped character and strikes it -- a purple pops in a purple energy burst and scores when the shot lands, a red or pink one only wobbles (no credit, combo broken), a tap on the ground lands as dust; combo multiplier, swipe fires at every character slid over; an opening demonstration (the hand taps the front purple, its shot strikes it) |
| 6 | 30 s | 15 | bombs cost 3 s; faster pop-ups |
| 8 | 40 s | 28 | only gold miners count: tapping a decoy (yellow or brown) fails the round, "WRONG MINER!", and Level 8 starts again; characters change holes while up (more often later); pop-ups get steadily faster; quick pops; at 00:20 SPEED INCREASED! (faster, shorter, one more up) |

`ScreenRenderTest.difficultyRisesGraduallyAndStaysFair` plays every level with a simulated human
(0.45–0.85 s reactions, 1 miss in 8, 1 decoy in 12 tapped by mistake): Levels 1, 3 and 6 are always won,
each leaving less time to spare than the one before (16, 14, 12 s). On Level 8 a decoy ends the round, so
it is measured with a careful player (0.05 s slower, 1 decoy in 50): it wins 42 % of rounds (the rest are
lost on a decoy or on time), a careless one 21 %. Level 8's rules (level.json): `decoy_fails`,
`hop` {chance at the start / end of the round, seconds up before moving}, `ramp` {hold, gap, rise factors
reached at the end}; levels without them play exactly as before.

The visual source of truth is `reference/color_pop_reference.png` (left phone = Home, right phone = Level 1)
for Home and Level 1, and `reference/sheet/` (the owner's 8-screen sheet and its enlargements) for the
other screens; `design-pipeline/screens_import.py` turns them into `reference/screens/<screen>.png`.
The owner wants the screens to match the reference as exactly as technically possible — no redesign,
no substitute art, no colour/layout changes.

## Approach (decided)

The reference image itself is cut into layers, so every pixel comes from the owner's artwork:

- Background layer = reference with the UI elements removed and filled in.
- Every interactive element is its own sprite cut from the reference, drawn at its exact reference position,
  with real touch handling and a press animation.
- Only numbers that must change during play are re-rendered live (Lilita One font, white fill, dark outline,
  drop shadow — the closest match found to the reference lettering, weight calibrated against it).
- Rendering: one custom `View` driven by `Choreographer` (vsync), pure Java, no AndroidX.
- Portrait, immersive full screen, no black bars.

### Responsive layout (all phones)
Both screens are laid out in **reference-art pixels** (Home 628×1157, Level 622×1156 — the reference
screens are ~1.84:1) and mapped to the device with **one uniform scale** (`Fit.java`): nothing is ever
stretched or squashed, and touch goes through the same transform, so every hit area stays on its art.

- The scale is the largest at which the full art width fits the safe width **and** the screen's must-see
  rows fit the safe height. Safe area = screen minus display cutouts (camera hole, notch, curved edges)
  and any system bars the device keeps showing (`GameView.onApplyWindowInsets`).
  Must-see: Home = coin counter (y 51) … nav bar; Level = HUD top (y 66) … bottom holes.
- **Home:** anchored to the safe bottom, so title → beaver → tagline → PLAY → nav keep the exact reference
  arrangement; coin counter + gear pinned to the top (just below a cutout). Taller screens show more sky
  between them (`bg_full.png` has 400 painted sky rows).
- **Level 1:** anchored to the top, HUD and scene exactly as in the reference; the HUD moves down only if a
  cutout reaches it (`bg.png` has 160 sky rows above). Taller screens show more ground below the bottom
  holes (400 painted rows); the bottom bush/flowers are a foreground layer on the screen's bottom edge.
- Shorter/wider screens (16:9, split screen, foldable inner displays) scale everything down together;
  beyond the painted side padding a soft, darkened copy of the scene fills the sides.
- On a 20:9 phone (1080×2400) the scale is the reference's own width fit (1.72 / 1.74).

## How to build and run

Open the folder in Android Studio (Ladybug or newer, JDK 21) and run the `app` configuration, or:

    ./gradlew assembleDebug          # app/build/outputs/apk/debug/app-debug.apk
    ./gradlew testDebugUnitTest      # render + gameplay tests, PNGs in app/build/renders/
    python3 design-pipeline/compare_renders.py app/build/renders   # compare with the reference

The build copies the art from `app-assets/` (+ the font) into the APK (`syncArtAssets` in
`app/build.gradle`); nothing is duplicated under `app/src/main/assets`.

## Verification (what has and has not been checked)

- `ScreenRenderTest` draws both screens with Android's real graphics stack (Robolectric native graphics,
  SDK 35) on 14 configurations: the two reference shapes, 720×1280 and 1080×1920 (16:9), 1080×2160
  (18:9), 1080×2280 notch, 1080×2340 punch-hole, 1080×2400 with and without a punch-hole, 1440×3200,
  1080×2520 (21:9), system bars visible, curved-edge insets, a foldable inner screen. On each it checks
  that the must-see content lies inside the safe area, taps every Home control and all six characters
  at their on-screen positions (greens score, red/yellow don't, a tap above PLAY doesn't
  count), pause freezes the round, and the round ends at 0 s.
- `compare_renders.py` warps the reference into each render with the layout's own transform and
  compares pixel by pixel. Result (mean difference / pixels differing by more than 40 of 255):
  Home 0.9/255, 0.3 % (coin counter, + and gear pixel-identical); Level 1.9/255, 0.7 % — the same on
  every configuration. What remains is the live digits (Lilita One vs. the original lettering) and the
  faint glow the characters cast on the ground in the reference.
- Levels 3 and 6: rendered on the same 14 configurations plus their reference shape in the reference
  moment (`LevelScreen.referenceMoment`), compared inside the reference phone's bezel: Level 3
  1.4–1.5/255, Level 6 1.8/255 on every configuration. Tests tap every character of the opening wave
  (targets count with the combo multiplier, others don't, the Level 6 bomb costs 3 s), pause, time up,
  and a bot plays Levels 1, 3 and 6 to the end (each win unlocks the next level).
- An APK is built and signed with the plain SDK tools (aapt2/dx/apksigner).

## Code (`app/src/main/java/com/colorpop/game/`)
- `MainActivity` — portrait, immersive, edge-to-edge (`layoutInDisplayCutoutMode` short edges).
- `GameView` — frame loop, fade between screens, safe insets, touch routing.
- `Fit` — the responsive layout rule and the background drawing (padding, mirror, soft side fill).
- `HomeScreen` — sprites + controls: PLAY → the first level not won yet; gear → Settings (sound / vibration toggles,
  saved); + and the nav tabs → "COMING SOON!" until those screens exist; the coin counter is display only.
- `LevelScreen` — every level, from its `level.json` (Level 1 keeps its own format and constants;
  new levels carry `rules`: duration, goal, points, combo, swipe, bomb penalty, pop-up mix and pacing).
  Characters have a role (target / distractor / bomb) and optionally an additive light layer (Level 6
  stars); combo badge = word sprite + live "Nx". Level 3 (`rules.fire`): a tap launches a shot (a
  purple gem with a golden trail, drawn in code) that follows the character to its body and strikes it
  when it lands (0.12–0.3 s; the character waits for it); the purple burst (white-hot core, magenta
  rays, ring, sparkles, orbs), the flash-and-pop of the struck purple and the demonstration hand
  (the reference's glove, cut alone and rebuilt at 2x by `levels/level3_fire.py`) replace the static
  hint and flash pictures. Level 1: opening wave in the reference pose (so 00:28 looks like the reference), then
  random pop-ups (60 % green / 20 % red / 20 % yellow, faster over the round); tap green = pop burst,
  +10, one target less; red/yellow wobble and never count; 30 s; pause freezes everything; round over
  (time up or all 12 greens) → "PLAY AGAIN" / "HOME" (placeholder until the Level Complete screen is
  designed). Characters are clipped at the real, bumpy front edge of each rim (per-column, `level.json`).
- `OutlineText`, `SpriteButton`, `Ui` (placeholder panels in the HUD's navy/cyan style), `Sfx`, `Prefs`, `Art`.

## Art (`app-assets/`) and how it is made (`design-pipeline/`)

`reference/` — `color_pop_reference.png` (original upload); `home_crop.png` (628×1157) and `lvl_crop.png`
(622×1156), the two phone screens cropped inside the bezel. **All coordinates are in these crop pixels.**

`app-assets/home/` — `bg_full.png` (controls, fake status bar and bezel removed; sky extension; art origin at
(`pad_side`, `pad_top`) of `_meta.json`) and the control sprites; `_meta.json` gives each sprite's position and
touch rectangle: coin pill (204,57)-(465,135); plus (400,64)-(461,129); gear centre (564.5,101.5) r40;
PLAY (50,901)-(568,1045); Missions (14,1051)-(157,1149); Shop (163,1051)-(299,1149);
Rewards (306,1051)-(450,1149); Profile (457,1051)-(606,1149).

`app-assets/level/` — `bg.png` (empty holes, live numbers erased, 160 sky rows above, 400 ground rows
below, 32 px each side), `fg_bottom.png` (bush/flowers/grass foreground), `pause.png`,
`characters/char_c1..c6.png` (body extended 34 px below the rim so they can bounce), and `level.json`: hole
openings + per-column front edges, character positions, pause hit circle, live-number boxes and their
calibrated lettering. `_lvl_geom.json` / `_lvl_masks.npz` are the reviewed source measurements.
`app-assets/sfx/` — synthesised sound effects.

`design-pipeline/` (Python 3 + numpy, scipy, Pillow, opencv-contrib-python-headless):
- `build_level.sh` rebuilds all Level 1 art in ~2.5 min, byte-for-byte reproducible:
  `lvl_build.py` (clean base, character sprites) → `lvl_holes.py` (empty holes: rebuilt back rims, real brick
  tops under the characters) → `lvl_hud.py` (pause sprite, numbers erased, lettering calibration) →
  `lvl_ground.py` (foreground, painted ground/sky, side padding) → `lvl_export.py` (`level.json`) → `sfx.py`.
- `lvl_geom.py` — hole geometry shared by the scripts (opening fit, per-column front edge).
- `home1.py`, `home2.py` — Home art; `lvl_seg2.py` — the character masks (reviewed; not re-run);
  `icon.py` — launcher icons from the reference beaver; `compare_renders.py` — see above.
- `fonts/LilitaOne-Regular.ttf` is SIL OFL (`OFL.txt`) and ships in the app.

`app-assets/level3/`, `level6/`, `level8/` — made by `design-pipeline/levels/level3.py` / `level6.py` / `level8.py`
(shared tools: `screen_art.py`, `levels/export.py`): `bg.png` (empty holes rebuilt from a clean donor hole
in ring coordinates, everything else by patch fill + Poisson merge; the reference phone's bezel, corners and
home bar removed; 24 px blurred side padding), character sprites (difference mattes against the rebuilt
background, so sprites over the background give back the reference), light layers, combo word, pause,
`level.json`. Each script prints how far the rebuilt reference is from the reference.
`levels/set_rules.py <level>` writes a script's RULES into its level.json without rebuilding the art.

Character sharpness: the new levels' characters are exported at twice the art resolution
(`"scale": 2` in level.json) so they are as crisp as Level 1's on a phone. `design-pipeline/sr.py`
reconstructs them: no higher-resolution original exists (the owner's uploads are enlargements of
the 1441x1536 JPEG sheet, where the Level 8 phone is 362 px wide; Level 1's original is 622), so the
blur is first inverted (Richardson-Lucy, ~1 art px for characters in focus, 2-2.5 px for the ones the
mockup paints out of focus, per character in the level scripts), then Real-ESRGAN (x4plus, CPU via
`pip install ncnn`; models in `design-pipeline/_models/`, not committed, from the Real-ESRGAN ncnn
release) upscales them, keeping the enlargement's own shapes, colours and lighting.
(Superseded for Level 8 by its new design, below; still used for Levels 3 and 6.)
**Approved by the owner (build 0.5): keep this reconstruction as it is.** The four characters the Level 8
mockup paints out of focus (yellow and brown-hat decoys, the two far gold miners) stay as reconstructed:
they must not be redrawn, recoloured or given invented detail; the owner prefers the original artwork.
No further character-art changes without the owner's request. Each character's alpha is tight around it, so no background is
carried along when it pops up in another hole, and a far-away character is not blown up in a front
hole (at most 1.3x, `LevelScreen.pick`).

### Level 8: new high-resolution design (approved by the owner, build 0.6)
The sheet's Level 8 was too small to become as crisp as Level 1, so the owner approved a new design of
its own: a gold mine at night (starry sky, mine entrance with a cart of gold, head-frame tower, lantern
lights), eight holes with rounded stone rims, gold miners (targets: polished gold, lamp lit, glowing)
and two look-alike decoys (lemon-yellow and brown, lamps off). It is modelled and rendered in 3D with
Blender (Cycles) at twice the art resolution, the HUD redrawn in the Color Pop style. Gameplay and
rules are unchanged. The approved mockup is `reference/level8_new/mockup.png` (and
`reference/screens/level8_new.png`, which the render comparison uses).
- `design-pipeline/level8_3d/`: `scene.py` (scene, camera, lights), `miner.py` (characters), `sky.py`,
  `compose.py` (HUD, mockup), `portrait.py`, `render_assets.py` (renders: background without
  characters, each character alone, rim ids for the front edges, hole geometry), `export.py` (writes
  `app-assets/level8/`: 2x background with the fixed HUD, character sprites, the gold miners' light
  layers measured from the mockup render, pause, banner, `level.json`).
- Blender: `python3 -m venv V && V/bin/pip install bpy==4.4.0 "numpy<2"`; then
  `V/bin/python render_assets.py -- OUT 128` (about 25 min on 4 CPU cores) and
  `python3 export.py OUT portrait.png full_render.png`.
- The app draws a level's background, sprites, pause button and glow layers from 2x art when
  level.json says `"scale": 2`.
- `levels/level8.py` (the sheet version) is kept for reference only and writes elsewhere.

Level 3 in high resolution: the sheet's Level 3 (a ~355 px wide screen) could not become as crisp as
Level 1 -- even deblurring and a neural upscale stay soft -- so it was rebuilt in 3D the same way,
keeping its own design (owner-approved): the reference's capped round critters (purple targets with a
tuft and dark eye patches, pink and red decoys with knobs), its seven holes (the camera is fitted to
their places and sizes), the dirt yard with rounded clay-brick rims, grass strip, fence with a pale
lower rail, sunlit hedge and trees under a blue sky, leaves and flowers; the HUD in Level 3's layout
(score on the left, the tilted 3x COMBO! on the right) drawn crisply. Gameplay and rules (tap-and-fire,
the demonstration, combo, purple burst) are unchanged. Reference: `reference/level3_new/mockup.png`
(and `reference/screens/level3_new.png`, the reference moment with the demonstration's glove).
- `design-pipeline/level3_3d/`: `scene.py`, `critter.py` (characters), `sky.py`, `compose.py` (HUD:
  fixed part, live slots, combo badge; mockup), `portrait.py` (the panel icon), `render_assets.py`
  (as Level 8's; `--extra` renders two pop-up-only decoy looks for the big holes), `export.py`
  (writes `app-assets/level3/` and the reference images; keeps the demonstration's glove `hand.png`).
- A character with `"spawn_only": true` in level.json only pops up (it is not in the opening wave).
- `levels/level3.py` and `levels/level3_fire.py` (the sheet version) are kept for reference only and
  write to `app-assets/level3_sheet/`.

## Remaining work
1. Level 10, Level Complete and Worlds screens (second sheet), coins.
2. Tune the pop-up pacing and the sound/vibration feel on real phones.
