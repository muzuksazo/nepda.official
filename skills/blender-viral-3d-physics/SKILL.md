---
name: blender-viral-3d-physics
description: >-
  Build Zack D. Films-grade 9:16 3D physics hooks and zero-credit simulations in
  Blender 5.1 using real glTF assets, Cloth Pressure, seamless 3D Ocean waves,
  zero-spring Hybrid Active Ragdolls with ARKit expressions, mandatory 4-frame
  Visual Gates, Inworld Korean VO cloning, and PIL-overlay FFmpeg assembly.
  Use whenever rendering 3D physics simulations, ragdoll launches, vehicle
  impacts, or building reusable Blender hook templates.
---

# Blender 5.1 Viral 3D Physics & Active Ragdoll Workflow

Use this workflow whenever generating native Blender 5.1 3D physics shots (launches, impacts, ragdolls, deformation) that must hit high visual detail, anatomical motion, and zero rendering artifacts on macOS (`0` Flow credits).

> **Anti-Reskin Pair**: When sourcing inspiration from third-party viral clips, pair with `principle-only-hook-abstraction` so commercial outputs reuse physical mechanics and timing, never third-party footage, IP, or brand likenesses.

---

## 1. Blender 5.1 Render & Modifier Standards (macOS Verified)

1. **Fast Film-Grade Render Setup (`BLENDER_EEVEE`, `~1.6–2.2s/frame` vs Cycles Metal `>2m/f`)**:
   - `scene.render.engine = "BLENDER_EEVEE"`
   - `taa_render_samples = 32`, `use_raytracing = True`, `motion_blur_steps = 3`, `shadow_ray_count = 2`
   - `scene.render.use_motion_blur = True`, `scene.render.motion_blur_shutter = 0.26` (sharp face, crisp limb streaks)
   - `scene.view_settings.view_transform = "AgX"`, `exposure = 0.12`
   - Compositor (`Blender 5.1` API): build `ng = bpy.data.node_groups.new(..., "CompositorNodeTree")`, set `scene.compositing_node_group = ng`, add output socket via `ng.interface.new_socket(name="Image", in_out="OUTPUT", socket_type="NodeSocketColor")`, wire `RLayers -> Glare (Type='Fog Glow') -> HueSat (Sat=1.15) -> GroupOutput`.
2. **Cloth & Ocean Gotchas**:
   - **Cloth pinning**: use `cloth.settings.vertex_group_mass = "PinBottom"` + `pin_stiffness` (`vertex_group_pin` does not exist in 5.1).
   - **3D Ocean**: `om.spatial_size` MUST be `int` (e.g. `110`), NEVER `float`. Use `repeat_x = 4, repeat_y = 4` centered beneath mid-air trajectories so wide-angle close-ups never expose plane borders.
   - **Water spray droplets**: in EEVEE, avoid near-1.0 transmission (`0.92` renders dark/grey); use sunlit opaque-glossy scatter (`roughness=0.05, coat=1.0, transmission=0.32`).
   - **Live BlenderMCP isolation**: never call `read_factory_settings(use_empty=True)` inside a live BlenderMCP session (disconnects addon); delete objects via `bpy.data.objects.remove(...)`. Keep scale normalization idempotent on `.blend` reload.

---

## 2. Asset Orientation, Grounding & Detail Gate

NEVER trust `.glb`/`.fbx` default transforms by eye. Run this check before baking physics:

1. **glTF Quaternion Trap (`QUATERNION` ignores `rotation_euler`)**:
   - Top-level glTF roots (`RootNode`) import with `rotation_mode = 'QUATERNION'`.
   - ALWAYS set `obj.rotation_mode = "XYZ"` **before** setting `obj.rotation_euler` to orient forward motion along `+X` (or target path vector).
2. **Mandatory Frame-1 World BBox Assertion**:
   - After keyframing `F1` and updating `view_layer`, inspect world bounding boxes of `body` and directional parts (`lights` / `headlights` / nose mesh) relative to the pivot:
     - Assert longitudinal length matches travel axis (e.g., `body_size_x > 4.0`).
     - Assert headlights/front face lead positively along travel direction (e.g., `lights_rel_x > 1.2`). Abort immediately if sideways or reversed.
3. **Flush Grounding & Safe Wheel Spin**:
   - Measure wheel/foot minimum `z` relative to pivot, and place deck/floor top `z` flush with wheel bottom (zero hovering or clipping).
   - Spin wheel meshes ONLY if their local bbox center is within `< 0.10m` of `(0,0,0)` (otherwise rotating orbits the wheel off the car); set `rotation_mode = "XYZ"` and roll `-ds / radius` around the wheel axle.
4. **Minimum Scene Detail Floor**:
   - Platforms/launch decks must use contrasting PBR materials + structural trim (e.g. dark brushed metal + yellow drop-edge hazard curb), never bare grey cubes.

---

## 3. Everyday Human & Hybrid Active Ragdoll Protocol

Pure zero-control Bullet ragdolls with default springs flatten limbs back to rest pose (`4–15°` bends) and spin chaotically mid-air; stiff `COPY_TRANSFORMS` breaks scaled rigs. Use this protocol instead:

1. **Rig & Axis Audit First**:
   - Select an everyday realistic rigged character (e.g., ReadyPlayerMe `.glb` with `52 ARKit` shape keys on head/teeth/eyes; avoid bare armored mannequins).
   - Inspect rest bone axes (`b.matrix_local.to_3x3()`) and verify mesh shape keys before authoring any pose math.
2. **Zero-Spring Bullet World**:
   - Call `rb_obj.hide_viewport = True` strictly **after** `bpy.ops.rigidbody.object_add(type="ACTIVE")`.
   - Use `GENERIC_SPRING` constraints (Blender 5.1 has no `CONE_TWIST`), lock linear limits `0..0`, keep anatomical angular limits, and set **`use_spring_ang_x/y/z = False`** so Bullet never pulls joints back to T-pose.
   - Set `RB_Hips` `angular_damping = 0.65` (prevents unreadable helicopter spin) and child limb `angular_damping = 0.04` (free inertia); tune catapult `RagLaunchPiston` so apex stays `z ≈ 25–45m` above the landing environment, and place `SkyTurbulence` at actual flight altitude (`z ≈ 24m`).
3. **Never T/A-Pose Pre-Launch (`F1..F_launch-1`)**:
   - Lower arms naturally along the torso, add subtle knee/elbow flex, and smoothly crane `Neck`/`Head` (`F15..F_launch-1`) to track the incoming hazard with rising alarm blendshapes before launch. Smoothly blend (`10` frames) into panic flail on launch.
4. **Post-Bake Hybrid Composition (`q_phys_delta @ q_active`)**:
   - Wire ONLY `Hips` to `Bind_Hips` via `COPY_LOCATION` + `COPY_ROTATION` (`WORLD -> WORLD`, NEVER `COPY_TRANSFORMS`).
   - Run `bpy.ops.ptcache.bake_all(bake=True)` first.
   - Then iterate frames `1..end`: extract `q_phys_delta = q_rel_rest.inverted() @ q_rel_now` (normalize and flip if `w < 0` for shortest-path slerp), slerp by physical weight (`0.60` at launch → `0.35` mid-air), multiply onto anatomical mid-air panic-flail poses, clamp hinge axes (`Left/RightLeg` knees `[-125°, -15°]`, forearms `[±25°, ±125°]`), and keyframe pose quaternions + `52-ARKit` screaming face (`jawOpen`, `mouthFunnel`, `mouthStretch`, `eyeWide`, `browInnerUp`).
5. **High-Altitude Front-3/4 Camera**:
   - For mid-air close-ups, compute camera offset from torso `front` blended toward the landing-target ray (`z_dir >= 0.28`), `24mm` wide-angle lens, plus a soft tracking `AREA` fill light so both screaming face/limbs and tiny ground environment below stay in one readable vertical frame.

---

## 4. Mandatory 4-Frame Visual Gate (No Blind Full Renders)

NEVER launch a 150-frame render without passing all three gates:

1. **Numeric Sanity Print**:
   - Forward orientation `assert` passed (`body_size`, `lights_rel`).
   - Print per-shot `Hips` world position + `front` vector and child joint angles (`F045`, `F060`, `F085`, `F100`, `F120`, `F140`). Mid-air close-up knees/elbows MUST read `50–115°` (fail if `< 25°`).
2. **4-Frame `--preview-only` Sheet**:
   - Render 4 key moments (Approach/Drive, Pre-Launch Look-Up + Dive, Impact Launch, Mid-Air Active Ragdoll Close-Up), stitch into a `2x2` preview PNG via Anaconda Python + PIL, and inspect directly via `read_file`.
3. **Baked Cache Reuse**:
   - Save the baked `.blend` cleanly. For full render (or interrupted resume), verify `point_cache.is_baked == True` before rendering frames so physics matches the approved preview identically.

---

## 5. Audio, Korean Captions & Final Verification

- **Inworld TTS Voice Cloning**:
  - Clone via `POST https://api.inworld.ai/voices/v1/voices:clone` (`langCode: "KO_KR"`); synthesize via `POST https://api.inworld.ai/tts/v1/voice` (`modelId: "inworld-tts-2"`). Never persist raw API keys to disk or git.
- **Homebrew FFmpeg Captioning**:
  - When FFmpeg lacks `libass`/`drawtext`, render crisp outlined Korean PNG subtitles via Anaconda PIL (`/System/Library/Fonts/AppleSDGothicNeo.ttc`) and composite with FFmpeg `overlay` + `-14.0 LUFS` 2-pass normalization + synced impact SFX.
- **Final QA**:
  - Verify `ffprobe` streams (`720x1280` or `1440x1280`, `30fps`, `h264 + aac`) and directly inspect the comparison strip and rendered `.mp4` with `read_file` before reporting completion.
