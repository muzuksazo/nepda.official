"""문제 장면 템플릿 `spill_diffuser` — Blender 안에서 실행된다 (blender -b -P blender_scene.py -- …).

지나가던 손이 리드 디퓨저를 쳐서 쓰러뜨리고 병 입구에서 액체가 쏟아진다. 84프레임(3.5초, 24fps), 9:16.
병이 넘어지는 동작은 강체 물리, 흐르는 액체는 입자 시뮬레이션이다. assets/ 에 에셋이 있으면 쓰고 없으면 기본 도형으로 만든다.

사용: blender -b -P blender_scene.py -- <프레임 출력 폴더> <assets 폴더> [해상도 %] [시작 프레임] [끝 프레임]
"""
import math
import os
import random
import sys

import bmesh
import bpy
from mathutils import Matrix, Vector

argv = sys.argv[sys.argv.index("--") + 1:]
OUT, ASSETS = argv[0], argv[1]
RES = int(argv[2]) if len(argv) > 2 else 100
F_START = int(argv[3]) if len(argv) > 3 else 1
F_END = int(argv[4]) if len(argv) > 4 else 84
END, HIT = 84, 22
BR, BH = 0.032, 0.085          # 병 반지름, 높이

bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene
D = bpy.data.objects


def interp(kind):
    bpy.context.preferences.edit.keyframe_new_interpolation_type = kind


def asset(*parts):
    p = os.path.join(ASSETS, *parts)
    return p if os.path.exists(p) else None


def link(o):
    scene.collection.objects.link(o)
    return o


def new_mat(name):
    m = bpy.data.materials.new(name)
    try:
        m.use_nodes = True
    except Exception:
        pass
    return m, next(n for n in m.node_tree.nodes if n.type == "BSDF_PRINCIPLED")


def flat_mat(name, color, rough=0.5, **extra):
    m, b = new_mat(name)
    b.inputs["Base Color"].default_value = (*color, 1)
    b.inputs["Roughness"].default_value = rough
    for k, v in extra.items():
        try:
            b.inputs[k].default_value = v
        except Exception as e:
            print("mat input", k, e)
    return m


def texture_mat(name, folder, scale):
    """Poly Haven 텍스처 폴더(diff/rough/nor_gl.jpg)로 PBR 재질을 만든다."""
    m, b = new_mat(name)
    nt = m.node_tree
    tc = nt.nodes.new("ShaderNodeTexCoord")
    mp = nt.nodes.new("ShaderNodeMapping")
    mp.inputs["Scale"].default_value = (scale, scale, scale)
    nt.links.new(tc.outputs["UV"], mp.inputs[0])

    def img(file, non_color):
        n = nt.nodes.new("ShaderNodeTexImage")
        n.image = bpy.data.images.load(os.path.join(folder, file))
        if non_color:
            n.image.colorspace_settings.name = "Non-Color"
        nt.links.new(mp.outputs[0], n.inputs["Vector"])
        return n
    nt.links.new(img("diff.jpg", False).outputs["Color"], b.inputs["Base Color"])
    nt.links.new(img("rough.jpg", True).outputs["Color"], b.inputs["Roughness"])
    nm = nt.nodes.new("ShaderNodeNormalMap")
    nt.links.new(img("nor_gl.jpg", True).outputs["Color"], nm.inputs["Color"])
    nt.links.new(nm.outputs[0], b.inputs["Normal"])
    return m


def revolve(name, prof, n=64):
    bm = bmesh.new()
    rings = [[bm.verts.new((r * math.cos(i * 2 * math.pi / n), r * math.sin(i * 2 * math.pi / n), z)) for i in range(n)] for r, z in prof]
    for k in range(len(prof) - 1):
        for i in range(n):
            j = (i + 1) % n
            bm.faces.new((rings[k][i], rings[k][j], rings[k + 1][j], rings[k + 1][i])).smooth = True
    bm.faces.new(list(reversed(rings[0])))
    bm.faces.new(rings[-1])
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    return link(bpy.data.objects.new(name, me))


def append_objects(blend_path, name_filter=None):
    with bpy.data.libraries.load(blend_path, link=False) as (src, dst):
        dst.objects = [n for n in src.objects if name_filter is None or name_filter(n)]
    out = []
    for o in dst.objects:
        if o is not None and o.type == "MESH":
            out.append(link(o))
        elif o is not None:
            bpy.data.objects.remove(o, do_unlink=True)
    return out


# ---------------- 방: 테이블, 벽, 조명 ----------------
bpy.ops.mesh.primitive_plane_add(size=4)
table = bpy.context.active_object
wood_dir = asset("polyhaven", "table_wood")
table.data.materials.append(texture_mat("TableWood", wood_dir, 3.33) if wood_dir else flat_mat("TableWood", (0.35, 0.20, 0.10), 0.45))
bpy.ops.mesh.primitive_plane_add(size=6, location=(0, 0.9, 0), rotation=(math.radians(90), 0, 0))
bpy.context.active_object.data.materials.append(flat_mat("Wall", (0.70, 0.67, 0.60), 0.9))

world = bpy.data.worlds.new("Room")
scene.world = world
try:
    world.use_nodes = True
except Exception:
    pass
bg = next(n for n in world.node_tree.nodes if n.type == "BACKGROUND")
hdri = asset("polyhaven", "room_hdri", "env.hdr")
if hdri:
    env = world.node_tree.nodes.new("ShaderNodeTexEnvironment")
    env.image = bpy.data.images.load(hdri)
    world.node_tree.links.new(env.outputs["Color"], bg.inputs[0])
    bg.inputs[1].default_value = 1.1
else:
    bg.inputs[0].default_value = (0.25, 0.25, 0.25, 1)


def light(name, loc, target, energy, size):
    d = bpy.data.lights.new(name, "AREA")
    d.energy, d.size = energy, size
    o = link(bpy.data.objects.new(name, d))
    o.location = loc
    o.rotation_euler = (Vector(target) - o.location).to_track_quat("-Z", "Y").to_euler()


light("Key", (-0.5, -0.8, 0.9), (0, 0, 0.05), 38 if hdri else 120, 0.6)
if not hdri:
    light("Fill", (0.8, -0.6, 0.5), (0, 0, 0.05), 40, 1.0)

for name, loc, scale in (("prop_plant", (0.24, 0.36, 0.0), 1.0), ("prop_vase", (-0.27, 0.48, 0.0), 0.8)):
    blend = asset("polyhaven", name, "model.blend")
    if blend:
        for o in append_objects(blend):
            o.location, o.scale = loc, (scale, scale, scale)

# ---------------- 리드 디퓨저 (병 + 라벨 + 막대) ----------------
C_MASS = 0.045                 # 무게중심 높이. 원점이 바닥이면 오뚝이처럼 다시 일어난다.
bottle = revolve("Bottle", [(BR - 0.003, -C_MASS), (BR, 0.004 - C_MASS), (BR, BH * 0.72 - C_MASS), (BR * 0.5, BH * 0.9 - C_MASS),
                            (BR * 0.42, BH - C_MASS), (BR * 0.34, BH - C_MASS)])
bottle.location = (0, 0, C_MASS)
bottle.data.materials.append(flat_mat("Glass", (0.52, 0.23, 0.04), 0.08, **{"Transmission Weight": 0.75, "IOR": 1.45, "Coat Weight": 0.6}))
label = revolve("Label", [(BR + 0.0004, 0.022 - C_MASS), (BR + 0.0004, 0.050 - C_MASS)])
label.data.materials.append(flat_mat("LabelPaper", (0.89, 0.85, 0.75), 0.7))
label.parent = bottle
reed_mat = flat_mat("Reed", (0.60, 0.42, 0.20), 0.8)
random.seed(3)
reeds = []
for i in range(7):
    bpy.ops.mesh.primitive_cylinder_add(vertices=8, radius=0.0016, depth=0.20)
    r = bpy.context.active_object
    r.name = f"Reed{i}"
    r.data.materials.append(reed_mat)
    a = i * 2 * math.pi / 7
    tilt = math.radians(random.uniform(9, 17))
    r.parent = bottle
    r.rotation_euler = (tilt * math.sin(a), tilt * math.cos(a), 0)
    r.location = (0.015 * math.cos(a), -0.015 * math.sin(a), 0.115 - C_MASS)
    reeds.append(r)
hull = bottle.copy()               # 복합 강체에서 병 몸통의 충돌 형태
hull.name = "BottleHull"
link(hull)
hull.parent = bottle
hull.matrix_parent_inverse.identity()
hull.location = (0, 0, 0)
hull.hide_render = True

# ---------------- 팔: 소매 + 손 ----------------
arm = link(bpy.data.objects.new("Arm", None))
bpy.ops.mesh.primitive_cylinder_add(vertices=32, radius=0.034, depth=0.42)
sleeve = bpy.context.active_object
sleeve.name = "Sleeve"
fabric_dir = asset("polyhaven", "sleeve_fabric")
sleeve.data.materials.append(texture_mat("SleeveFabric", fabric_dir, 1.6) if fabric_dir else flat_mat("SleeveFabric", (0.03, 0.08, 0.26), 0.85))
sleeve.parent = arm
sleeve.rotation_euler = (0, math.radians(90), 0)
sleeve.location = (0.27, 0, -0.014)
sleeve.scale = (1.38, 1.38, 1.0)


def skin_material(zmin):
    """손 모델에 색·질감이 없어 절차적으로 입힌다: 얼룩, 손끝 혈색, 모공·주름 요철."""
    m, b = new_mat("Skin")
    nt = m.node_tree
    new, lk = nt.nodes.new, nt.links.new
    tc = new("ShaderNodeTexCoord")
    sep = new("ShaderNodeSeparateXYZ")
    lk(tc.outputs["Object"], sep.inputs[0])

    def noise(scale, detail):
        n = new("ShaderNodeTexNoise")
        n.inputs["Scale"].default_value, n.inputs["Detail"].default_value = scale, detail
        lk(tc.outputs["Object"], n.inputs["Vector"])
        return n.outputs[0]

    def remap(sock, a, bb, lo=0.0, hi=1.0):
        n = new("ShaderNodeMapRange")
        n.clamp = True
        for i, v in zip((1, 2, 3, 4), (a, bb, lo, hi)):
            n.inputs[i].default_value = v
        lk(sock, n.inputs[0])
        return n.outputs[0]

    def mix(a, color, fac):
        n = new("ShaderNodeMix")
        n.data_type = "RGBA"
        if isinstance(a, tuple):
            n.inputs[6].default_value = (*a, 1)
        else:
            lk(a, n.inputs[6])
        n.inputs[7].default_value = (*color, 1)
        lk(fac, n.inputs[0])
        return n.outputs[2]

    col = mix((0.52, 0.30, 0.20), (0.62, 0.42, 0.31), remap(noise(22, 3), 0.35, 0.7))
    col = mix(col, (0.58, 0.24, 0.17), remap(noise(9, 2), 0.45, 0.75, 0.0, 0.45))
    col = mix(col, (0.60, 0.22, 0.17), remap(sep.outputs[2], zmin + 0.085, zmin + 0.005, 0.0, 0.55))
    col = mix(col, (0.38, 0.20, 0.14), remap(noise(140, 2), 0.5, 0.8, 0.0, 0.18))
    lk(col, b.inputs["Base Color"])
    lk(remap(noise(60, 3), 0.3, 0.7, 0.38, 0.58), b.inputs["Roughness"])
    for k, v in (("Subsurface Weight", 0.22), ("Subsurface Radius", (0.010, 0.0035, 0.002)), ("Subsurface Scale", 0.45)):
        try:
            b.inputs[k].default_value = v
        except Exception as e:
            print("skin input", k, e)
    vor = new("ShaderNodeTexVoronoi")
    vor.inputs["Scale"].default_value = 900
    lk(tc.outputs["Object"], vor.inputs["Vector"])
    bump = new("ShaderNodeBump")
    bump.inputs["Strength"].default_value, bump.inputs["Distance"].default_value = 0.10, 0.0004
    lk(vor.outputs[0], bump.inputs["Height"])
    lk(bump.outputs[0], b.inputs["Normal"])
    return m


hand = None
bundle = asset("human_base", "human_base_meshes_bundle.blend")
if bundle:
    found = append_objects(bundle, lambda n: "hand" in n.lower() and "realistic" in n.lower() and not n.startswith("GEO"))
    if found:
        hand = found[0]
        for extra in found[1:]:
            bpy.data.objects.remove(extra, do_unlink=True)
        zs = [v.co.z for v in hand.data.vertices]
        hand.data.materials.clear()
        hand.data.materials.append(skin_material(min(zs)))
        for p in hand.data.polygons:
            p.use_smooth = True
        sub = hand.modifiers.new("Smooth", "SUBSURF")
        sub.levels, sub.render_levels = 1, 2
        hand.parent = arm
        hand.matrix_parent_inverse.identity()
        # 손가락이 -X(휘두르는 방향), 손바닥이 아래를 향하게
        hand.matrix_basis = Matrix.Translation((0.11 - max(zs), 0.0, -0.015)) @ Matrix(((0, 0, 1), (-1, 0, 0), (0, -1, 0))).to_4x4()
if hand is None:
    bpy.ops.mesh.primitive_uv_sphere_add(radius=0.036, segments=32, ring_count=16)
    hand = bpy.context.active_object
    hand.scale = (1.5, 1.0, 0.7)
    hand.data.materials.append(flat_mat("Skin", (0.52, 0.30, 0.20), 0.6))
    for p in hand.data.polygons:
        p.use_smooth = True
    hand.parent = arm
hand.name = "Hand"

# ---------------- 물리 ----------------
bpy.ops.mesh.primitive_cube_add(size=1, location=(0, 0, -0.1))     # 얇은 평면은 막대가 뚫고 지나가서 두꺼운 충돌체를 둔다
floor = bpy.context.active_object
floor.name = "TableCollider"
floor.scale = (4, 4, 0.2)
floor.hide_render = True
bpy.ops.rigidbody.world_add()
rw = scene.rigidbody_world
if rw.collection is None:
    rw.collection = bpy.data.collections.new("RigidBodyWorld")
rw.substeps_per_frame, rw.solver_iterations = 30, 40
rw.point_cache.frame_start, rw.point_cache.frame_end = 1, END


def rigid(o, kind, shape, mass=1.0, friction=0.6, kinematic=False):
    rw.collection.objects.link(o)
    b = o.rigid_body
    b.type, b.collision_shape, b.mass, b.friction, b.restitution = kind, shape, mass, friction, 0.05
    b.use_margin, b.collision_margin, b.kinematic = True, 0.0005, kinematic
    b.linear_damping, b.angular_damping = 0.08, 0.6
    try:
        b.mesh_source = "BASE"
    except Exception:
        pass


rigid(floor, "PASSIVE", "BOX", friction=0.8)
for r in reeds:
    rigid(r, "ACTIVE", "CONVEX_HULL", mass=0.004, friction=0.7)
rigid(hull, "ACTIVE", "CONVEX_HULL", mass=0.3, friction=0.7)
rigid(bottle, "ACTIVE", "COMPOUND", mass=0.32, friction=0.7)
rigid(sleeve, "PASSIVE", "CONVEX_HULL", friction=0.5, kinematic=True)
rigid(hand, "PASSIVE", "CONVEX_HULL", friction=0.5, kinematic=True)

# 입구에서 흘러나오는 액체 방울
oil = flat_mat("Oil", (0.15, 0.04, 0.003), 0.03, **{"Coat Weight": 1.0})
bpy.ops.mesh.primitive_ico_sphere_add(subdivisions=2, radius=1.0, location=(0, 0, -2.0))
drop = bpy.context.active_object
drop.name = "Drop"
for p in drop.data.polygons:
    p.use_smooth = True
drop.data.materials.append(oil)
bm = bmesh.new()
bmesh.ops.create_circle(bm, cap_ends=True, segments=12, radius=0.009)
me = bpy.data.meshes.new("PourEmitter")
bm.to_mesh(me)
bm.free()
emitter = link(bpy.data.objects.new("PourEmitter", me))
emitter.parent = bottle
emitter.location = (0, 0, BH - C_MASS - 0.002)
emitter.hide_render = True
emitter.show_instancer_for_render = False
emitter.modifiers.new("Pour", "PARTICLE_SYSTEM")
ps = emitter.particle_systems[0]
st = ps.settings
st.count, st.frame_start, st.frame_end, st.lifetime = 800, 27, 70, 400
st.emit_from, st.physics_type = "FACE", "NEWTON"
st.normal_factor, st.factor_random = 0.30, 0.10
st.particle_size, st.size_random, st.mass = 0.0058, 0.55, 0.01
st.drag_factor, st.damping, st.subframes = 0.05, 0.03, 5
st.use_size_deflect = True
st.render_type, st.instance_object = "OBJECT", drop
ps.point_cache.frame_start, ps.point_cache.frame_end = 1, END
floor.modifiers.new("Collision", "COLLISION")
floor.collision.damping_factor, floor.collision.friction_factor = 0.6, 0.22

# 팔 경로: 병 윗부분을 쳐서 밀지 않고 쓰러뜨린 뒤 위로 빠진다. 병이 옆으로 눕는 높이를 찾을 때까지 몇 가지를 시도한다.
interp("LINEAR")


def bake_with(zhit, zlift):
    bpy.ops.ptcache.free_bake_all()
    scene.frame_set(1)
    arm.animation_data_clear()
    arm.rotation_euler = (0, math.radians(-6), math.radians(10))
    for f, x, z in ((6, 0.60, zhit + 0.005), (HIT, 0.10, zhit), (HIT + 5, -0.06, zlift), (HIT + 22, -0.80, zlift + 0.12)):
        arm.location = (x, 0.015, z)
        arm.keyframe_insert("location", frame=f)
    bpy.ops.ptcache.bake_all(bake=True)
    scene.frame_set(76)
    m = bottle.matrix_world.copy()
    return m, (m.to_3x3() @ Vector((0, 0, 1))).normalized()


best = None
for zhit, zlift in ((0.135, 0.20), (0.145, 0.22), (0.128, 0.22), (0.150, 0.24), (0.118, 0.20)):
    rest, axis = bake_with(zhit, zlift)
    score = -axis.x - abs(axis.z) - max(0.0, abs(rest.translation.x) - 0.36)
    print(f"arm z {zhit}: rest {[round(v, 3) for v in rest.translation]} axis {[round(v, 2) for v in axis]}")
    if best is None or score > best[0]:
        best = (score, zhit, zlift)
    if axis.x < -0.75 and abs(axis.z) < 0.15 and abs(rest.translation.x) < 0.36:
        break
else:
    rest, axis = bake_with(best[1], best[2])

# 웅덩이: 방울이 떨어진 자리에서 시작해 커진다 (입구에서 흘러나온 것으로 읽히도록)
dg = bpy.context.evaluated_depsgraph_get()
alive = [p for p in emitter.evaluated_get(dg).particle_systems[0].particles if p.alive_state == "ALIVE"]
if alive:
    cx = sum(p.location.x for p in alive) / len(alive)
    cy = sum(p.location.y for p in alive) / len(alive)
else:
    mouth = rest @ Vector((0, 0, BH - C_MASS))
    cx, cy = mouth.x, mouth.y
flat = Vector((axis.x, axis.y, 0)).normalized()
bm = bmesh.new()
bmesh.ops.create_circle(bm, cap_ends=True, segments=48, radius=1)
for v in bm.verts:
    a = math.atan2(v.co.y, v.co.x)
    k = 1 + 0.18 * math.sin(3 * a + 1) + 0.10 * math.sin(5 * a) + 0.07 * math.sin(8 * a + 2)
    v.co.x *= k
    v.co.y *= k * 0.8
me = bpy.data.meshes.new("Puddle")
bm.to_mesh(me)
bm.free()
puddle = link(bpy.data.objects.new("Puddle", me))
puddle.data.materials.append(oil)
puddle.rotation_euler = (0, 0, math.atan2(flat.y, flat.x))
interp("BEZIER")
for f, k in ((31, 0.02), (44, 0.45), (62, 0.85), (END, 1.0)):
    puddle.location = (cx, cy, 0.0012)
    puddle.scale = (0.085 * k, 0.068 * k, 1)
    puddle.keyframe_insert("location", frame=f)
    puddle.keyframe_insert("scale", frame=f)

# ---------------- 카메라: 손에 든 폰처럼 흔들리고, 쓰러진 뒤에는 입구가 보이는 옆쪽으로 ----------------
cd = bpy.data.cameras.new("Cam")
cd.lens = 54
cam = link(bpy.data.objects.new("Cam", cd))
target = link(bpy.data.objects.new("CamTarget", None))
track = cam.constraints.new("TRACK_TO")
track.target, track.track_axis, track.up_axis = target, "TRACK_NEGATIVE_Z", "UP_Y"
random.seed(11)
for f in range(1, END + 1, 4):
    j = 0.004 if f < HIT else 0.010
    cam.location = ((-0.06 if f < HIT else -0.30) + random.uniform(-j, j), -0.62 + random.uniform(-j, j), 0.36 + random.uniform(-j, j))
    cam.keyframe_insert("location", frame=f)
c = rest.translation
for f, p in ((1, (-0.03, 0.0, 0.07)), (HIT, (-0.03, 0.0, 0.07)), (40, (c.x - 0.04, c.y, 0.03)), (END, (c.x - 0.05, c.y, 0.03))):
    target.location = p
    target.keyframe_insert("location", frame=f)
scene.camera = cam

# ---------------- 렌더 ----------------
scene.frame_start, scene.frame_end = F_START, F_END
scene.render.fps = 24
scene.render.resolution_x, scene.render.resolution_y, scene.render.resolution_percentage = 1080, 1920, RES
scene.render.engine = "BLENDER_EEVEE"
for k, v in (("taa_render_samples", 32), ("use_raytracing", True)):
    try:
        setattr(scene.eevee, k, v)
    except Exception as e:
        print("eevee", k, e)
scene.render.use_motion_blur = True
scene.render.motion_blur_shutter = 0.3
scene.render.image_settings.file_format = "JPEG"
scene.render.image_settings.quality = 95
os.makedirs(OUT, exist_ok=True)
scene.render.filepath = os.path.join(OUT, "p_")
scene.render.use_overwrite = False
bpy.ops.render.render(animation=True)
print("SPILL_SCENE_DONE")
