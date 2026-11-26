"""Shared everyday human (rpm_player.glb) loader, Zero-Spring Bullet Active Ragdoll,
and 52-ARKit facial expression animator for all 5 viral 3D physics templates.
"""

from __future__ import annotations

import math
from typing import Callable, Dict, List, Optional, Tuple

import bpy
from mathutils import Euler, Quaternion, Vector

from core.scene_core import ASSETS, clamp, clamp01, lerp, smoothstep

LIMB_SPECS = [
    ("Hips", None, 14.0, 0.16, None),
    ("Spine2", "Hips", 18.0, 0.17, ((-28, 32), (-20, 20), (-25, 25))),
    ("Head", "Spine2", 5.0, 0.11, ((-32, 32), (-25, 25), (-28, 28))),
    ("LeftArm", "Spine2", 3.0, 0.075, ((-85, 85), (-45, 45), (-85, 85))),
    ("LeftForeArm", "LeftArm", 2.0, 0.06, ((-10, 125), (-15, 15), (-20, 20))),
    ("RightArm", "Spine2", 3.0, 0.075, ((-85, 85), (-45, 45), (-85, 85))),
    ("RightForeArm", "RightArm", 2.0, 0.06, ((-10, 125), (-15, 15), (-20, 20))),
    ("LeftUpLeg", "Hips", 8.0, 0.095, ((-75, 85), (-25, 25), (-45, 45))),
    ("LeftLeg", "LeftUpLeg", 5.0, 0.075, ((-125, 8), (-12, 12), (-12, 12))),
    ("RightUpLeg", "Hips", 8.0, 0.095, ((-75, 85), (-25, 25), (-45, 45))),
    ("RightLeg", "RightUpLeg", 5.0, 0.075, ((-125, 8), (-12, 12), (-12, 12))),
]

ACTIVE_BONES = [
    "Spine", "Spine1", "Spine2", "Neck", "Head",
    "LeftShoulder", "RightShoulder", "LeftArm", "RightArm",
    "LeftForeArm", "RightForeArm", "LeftHand", "RightHand",
    "LeftUpLeg", "RightUpLeg", "LeftLeg", "RightLeg",
    "LeftFoot", "RightFoot",
]

FACE_KEYS = (
    "jawOpen", "mouthFunnel", "mouthStretchLeft", "mouthStretchRight",
    "mouthLowerDownLeft", "mouthLowerDownRight", "mouthFrownLeft", "mouthFrownRight",
    "eyeWideLeft", "eyeWideRight", "browInnerUp", "browOuterUpLeft", "browOuterUpRight",
)


def import_human_grounded(
    scene: bpy.types.Scene,
    *,
    location: Tuple[float, float, float] = (0.0, 0.0, 0.0),
    yaw_deg: float = 0.0,
    pitch_deg: float = 0.0,
    ground_flush: bool = True,
) -> Dict[str, object]:
    """Import everyday businessman (rpm_player.glb) with clean XYZ orientation & grounding."""
    before = set(bpy.data.objects)
    bpy.ops.import_scene.gltf(filepath=ASSETS["human"])
    new_objs = [o for o in bpy.data.objects if o not in before]

    arm: Optional[bpy.types.Object] = None
    shaped_meshes: List[bpy.types.Object] = []
    foot_objs: List[bpy.types.Object] = []
    for o in new_objs:
        if o.type == "ARMATURE":
            arm = o
        elif o.name.startswith("Icosphere"):
            bpy.data.objects.remove(o, do_unlink=True)
        elif o.type == "MESH":
            if o.data.shape_keys:
                shaped_meshes.append(o)
            if "Footwear" in o.name:
                foot_objs.append(o)
    assert arm is not None, "Expected Armature in rpm_player.glb"

    arm.location = location
    arm.rotation_mode = "XYZ"
    arm.rotation_euler = (0.0, math.radians(pitch_deg), math.radians(yaw_deg))
    bpy.context.view_layer.update()

    if ground_flush and foot_objs:
        min_z = min((fo.matrix_world @ Vector(c)).z for fo in foot_objs for c in fo.bound_box)
        arm.location.z += (location[2] - min_z)
        bpy.context.view_layer.update()

    for bn in ACTIVE_BONES:
        pb = arm.pose.bones.get(bn)
        if pb is not None:
            pb.rotation_mode = "QUATERNION"

    return {"arm": arm, "shaped_meshes": shaped_meshes}


def attach_zero_spring_ragdoll(
    scene: bpy.types.Scene,
    human: Dict[str, object],
    *,
    release_frame: int = 45,
    total_frames: int = 150,
    hips_ang_damping: float = 0.65,
    limb_ang_damping: float = 0.04,
) -> Dict[str, object]:
    """Build 11 zero-spring Bullet RBs wired ONLY at Hips via COPY_LOCATION + COPY_ROTATION."""
    arm: bpy.types.Object = human["arm"]
    rb_map: Dict[str, bpy.types.Object] = {}
    bind_hips: Optional[bpy.types.Object] = None
    bpy.context.view_layer.update()

    for bname, parent_name, mass, rad, limits in LIMB_SPECS:
        pb = arm.pose.bones[bname]
        head_w = arm.matrix_world @ pb.head
        tail_w = arm.matrix_world @ pb.tail
        bone_len = max(0.12, (tail_w - head_w).length)
        mid_w = (head_w + tail_w) * 0.5
        rot_q = (arm.matrix_world @ pb.matrix).to_quaternion().normalized()

        bpy.ops.mesh.primitive_cylinder_add(
            vertices=12, radius=rad, depth=bone_len,
            location=(0.0, 0.0, 0.0), rotation=(math.pi * 0.5, 0.0, 0.0),
        )
        rb_obj = bpy.context.active_object
        rb_obj.name = f"RB_{bname}"
        bpy.ops.object.transform_apply(location=False, rotation=True, scale=False)
        rb_obj.location = mid_w
        rb_obj.rotation_mode = "QUATERNION"
        rb_obj.rotation_quaternion = rot_q

        bpy.ops.object.select_all(action="DESELECT")
        rb_obj.select_set(True)
        bpy.context.view_layer.objects.active = rb_obj
        bpy.ops.rigidbody.object_add(type="ACTIVE")
        rb_obj.rigid_body.collision_shape = "CAPSULE"
        rb_obj.rigid_body.mass = mass
        rb_obj.rigid_body.linear_damping = 0.03 if bname == "Hips" else 0.015
        rb_obj.rigid_body.angular_damping = hips_ang_damping if bname == "Hips" else limb_ang_damping
        rb_obj.rigid_body.friction = 0.45
        rb_obj.rigid_body.restitution = 0.25
        rb_obj.hide_render = True
        rb_obj.hide_viewport = True  # Strictly AFTER rigidbody.object_add

        if bname == "Hips":
            bind_hips = bpy.data.objects.new("Bind_Hips", None)
            scene.collection.objects.link(bind_hips)
            bind_hips.parent = rb_obj
            bind_hips.location = Vector((0.0, -0.5 * bone_len, 0.0))
            bind_hips.rotation_euler = (0.0, 0.0, 0.0)

        rb_map[bname] = rb_obj

        if parent_name is not None and limits is not None:
            c_emp = bpy.data.objects.new(f"Joint_{bname}", None)
            scene.collection.objects.link(c_emp)
            c_emp.location = head_w
            c_emp.rotation_mode = "QUATERNION"
            c_emp.rotation_quaternion = rot_q
            bpy.ops.object.select_all(action="DESELECT")
            c_emp.select_set(True)
            bpy.context.view_layer.objects.active = c_emp
            bpy.ops.rigidbody.constraint_add(type="GENERIC_SPRING")
            rbc = c_emp.rigid_body_constraint
            rbc.object1 = rb_map[parent_name]
            rbc.object2 = rb_obj
            rbc.disable_collisions = True
            for attr in ("use_limit_lin_x", "use_limit_lin_y", "use_limit_lin_z"):
                setattr(rbc, attr, True)
            for attr in (
                "limit_lin_x_lower", "limit_lin_x_upper",
                "limit_lin_y_lower", "limit_lin_y_upper",
                "limit_lin_z_lower", "limit_lin_z_upper",
            ):
                setattr(rbc, attr, 0.0)
            (lx0, lx1), (ly0, ly1), (lz0, lz1) = limits
            rbc.use_limit_ang_x = True
            rbc.limit_ang_x_lower = math.radians(lx0)
            rbc.limit_ang_x_upper = math.radians(lx1)
            rbc.use_limit_ang_y = True
            rbc.limit_ang_y_lower = math.radians(ly0)
            rbc.limit_ang_y_upper = math.radians(ly1)
            rbc.use_limit_ang_z = True
            rbc.limit_ang_z_lower = math.radians(lz0)
            rbc.limit_ang_z_upper = math.radians(lz1)
            for ax in ("x", "y", "z"):
                setattr(rbc, f"use_spring_ang_{ax}", False)

    assert bind_hips is not None
    hips_pb = arm.pose.bones["Hips"]
    cl = hips_pb.constraints.new("COPY_LOCATION")
    cl.target = bind_hips
    cl.target_space = "WORLD"
    cl.owner_space = "WORLD"
    cr = hips_pb.constraints.new("COPY_ROTATION")
    cr.target = bind_hips
    cr.target_space = "WORLD"
    cr.owner_space = "WORLD"
    cr.mix_mode = "REPLACE"

    for rb_obj in rb_map.values():
        rb_obj.rigid_body.kinematic = True
        rb_obj.rigid_body.keyframe_insert(data_path="kinematic", frame=1)
        rb_obj.rigid_body.keyframe_insert(data_path="kinematic", frame=max(1, release_frame - 1))
        rb_obj.rigid_body.kinematic = False
        rb_obj.rigid_body.keyframe_insert(data_path="kinematic", frame=release_frame)

    return {**human, "rb_map": rb_map, "hips_rb": rb_map["Hips"]}


def active_panic_euler_deg(f: int, start_f: int, damp_after_f: Optional[int] = None) -> Dict[str, Tuple[float, float, float]]:
    if f < start_f:
        return {}
    t = max(0.0, (f - start_f) / 30.0)
    w = 10.5
    whiplash = math.sin(clamp01((f - start_f) / 14.0) * math.pi)
    damp = (1.0 - 0.55 * smoothstep(float(damp_after_f), float(damp_after_f + 35), float(f))) if damp_after_f else 1.0
    return {
        "Spine": (10.0 + 6.0 * math.sin(w * t), 8.0 * math.sin(0.8 * w * t), 6.0 * math.cos(0.7 * w * t)),
        "Spine1": (12.0 + 7.0 * math.sin(w * t + 0.4), 10.0 * math.sin(0.9 * w * t), 7.0 * math.sin(0.6 * w * t)),
        "Spine2": (10.0 + 6.0 * math.cos(w * t), 12.0 * math.sin(0.85 * w * t + 0.7), 8.0 * math.cos(0.75 * w * t)),
        "Neck": (-18.0 * whiplash + 10.0 * math.sin(1.2 * w * t), 14.0 * math.sin(0.9 * w * t), 10.0 * math.cos(1.1 * w * t)),
        "Head": (-16.0 * whiplash + 8.0 * math.cos(1.3 * w * t), 18.0 * math.sin(0.8 * w * t + 0.5), 12.0 * math.sin(1.0 * w * t)),
        "LeftShoulder": (0.0, 0.0, 15.0 + 10.0 * math.sin(1.5 * w * t) * damp),
        "RightShoulder": (0.0, 0.0, -15.0 - 10.0 * math.sin(1.5 * w * t + 2.4) * damp),
        "LeftArm": (-56.0 + 26.0 * math.sin(1.6 * w * t) * damp, 18.0 * math.cos(1.4 * w * t) * damp, 50.0 + 26.0 * math.cos(1.6 * w * t) * damp),
        "RightArm": (-56.0 + 26.0 * math.sin(1.6 * w * t + 2.7) * damp, -18.0 * math.cos(1.4 * w * t + 2.7) * damp, -50.0 - 26.0 * math.cos(1.6 * w * t + 2.7) * damp),
        "LeftForeArm": (10.0 + 12.0 * math.sin(1.8 * w * t), 0.0, 66.0 + 22.0 * math.sin(1.9 * w * t + 0.8) * damp),
        "RightForeArm": (10.0 + 12.0 * math.sin(1.8 * w * t + 2.5), 0.0, -66.0 - 22.0 * math.sin(1.9 * w * t + 3.3) * damp),
        "LeftHand": (22.0 * math.sin(2.4 * w * t), 0.0, 24.0 * math.cos(2.2 * w * t)),
        "RightHand": (22.0 * math.sin(2.4 * w * t + 2.3), 0.0, -24.0 * math.cos(2.2 * w * t + 2.3)),
        "LeftUpLeg": (58.0 + 30.0 * math.sin(1.7 * w * t) * damp, 10.0 * math.sin(w * t), 16.0 + 10.0 * math.cos(1.1 * w * t)),
        "RightUpLeg": (58.0 + 30.0 * math.sin(1.7 * w * t + 3.14) * damp, -10.0 * math.sin(w * t), -16.0 - 10.0 * math.cos(1.1 * w * t)),
        "LeftLeg": (-84.0 - 26.0 * math.sin(1.7 * w * t + 0.7) * damp, 0.0, 0.0),
        "RightLeg": (-84.0 - 26.0 * math.sin(1.7 * w * t + 3.84) * damp, 0.0, 0.0),
        "LeftFoot": (22.0 * math.sin(1.7 * w * t + 1.2), 0.0, 0.0),
        "RightFoot": (22.0 * math.sin(1.7 * w * t + 4.34), 0.0, 0.0),
    }


def apply_face_weights(shaped_meshes: List[bpy.types.Object], frame: int, face_vals: Dict[str, float]) -> None:
    for m_obj in shaped_meshes:
        sk = m_obj.data.shape_keys
        if sk is None:
            continue
        for k in FACE_KEYS:
            kb = sk.key_blocks.get(k)
            if kb is not None:
                kb.value = clamp01(face_vals.get(k, 0.0))
                kb.keyframe_insert(data_path="value", frame=frame)


def apply_pose_euler_dict(arm: bpy.types.Object, frame: int, pose_deg: Dict[str, Tuple[float, float, float]]) -> None:
    for bn in ACTIVE_BONES:
        pb = arm.pose.bones.get(bn)
        if pb is None:
            continue
        ax, ay, az = pose_deg.get(bn, (0.0, 0.0, 0.0))
        pb.rotation_mode = "QUATERNION"
        pb.rotation_quaternion = Euler((math.radians(ax), math.radians(ay), math.radians(az)), "XYZ").to_quaternion().normalized()
        pb.keyframe_insert(data_path="rotation_quaternion", frame=frame)


def compose_hybrid_active_ragdoll(
    scene: bpy.types.Scene,
    rag: Dict[str, object],
    *,
    release_frame: int,
    total_frames: int,
    prelaunch_fn: Callable[[int], Dict[str, Tuple[float, float, float]]],
    alarm_start_frame: int = 20,
    damp_after_f: Optional[int] = None,
) -> Tuple[Dict[int, Vector], Dict[int, Quaternion]]:
    arm: bpy.types.Object = rag["arm"]
    rb_map: Dict[str, bpy.types.Object] = rag["rb_map"]
    shaped_meshes: List[bpy.types.Object] = rag["shaped_meshes"]
    rb_parent = {bname: pname for bname, pname, *_ in LIMB_SPECS if pname is not None}

    scene.frame_set(1)
    q_rb_rest = {bn: rb.matrix_world.to_quaternion().normalized() for bn, rb in rb_map.items()}
    pre_end = prelaunch_fn(max(1, release_frame - 1))

    hips_pos: Dict[int, Vector] = {}
    hips_rot: Dict[int, Quaternion] = {}

    for f in range(1, total_frames + 1):
        scene.frame_set(f)
        hips_pos[f] = rb_map["Hips"].matrix_world.translation.copy()
        hips_rot[f] = rb_map["Hips"].matrix_world.to_quaternion().normalized()
        q_rb_now = {bn: rb.matrix_world.to_quaternion().normalized() for bn, rb in rb_map.items()}

        phys_w = lerp(0.60, 0.35, smoothstep(float(release_frame + 12), float(release_frame + 20), float(f))) if f >= release_frame else 0.0
        pre_deg = prelaunch_fn(f)
        act_deg = active_panic_euler_deg(f, release_frame, damp_after_f)
        t_blend = smoothstep(float(release_frame - 1), float(release_frame + 9), float(f)) if f >= release_frame else 0.0

        for bn in ACTIVE_BONES:
            pb = arm.pose.bones.get(bn)
            if pb is None:
                continue
            if f < release_frame:
                ax, ay, az = pre_deg.get(bn, (0.0, 0.0, 0.0))
            elif f < release_frame + 10:
                sx, sy, sz = pre_end.get(bn, (0.0, 0.0, 0.0))
                px, py, pz = act_deg.get(bn, (0.0, 0.0, 0.0))
                ax, ay, az = lerp(sx, px, t_blend), lerp(sy, py, t_blend), lerp(sz, pz, t_blend)
            else:
                ax, ay, az = act_deg.get(bn, (0.0, 0.0, 0.0))

            q_act = Euler((math.radians(ax), math.radians(ay), math.radians(az)), "XYZ").to_quaternion().normalized()
            if bn in rb_parent and phys_w > 0.0:
                pn = rb_parent[bn]
                q_rel_rest = (q_rb_rest[pn].inverted() @ q_rb_rest[bn]).normalized()
                q_rel_now = (q_rb_now[pn].inverted() @ q_rb_now[bn]).normalized()
                q_delta = (q_rel_rest.inverted() @ q_rel_now).normalized()
                if q_delta.w < 0.0:
                    q_delta.negate()
                q_comb = (Quaternion((1.0, 0.0, 0.0, 0.0)).slerp(q_delta, phys_w) @ q_act).normalized()
            else:
                q_comb = q_act

            if f >= release_frame + 6:
                e = q_comb.to_euler("XYZ")
                ch = False
                if bn in ("LeftLeg", "RightLeg"):
                    cx = clamp(e.x, math.radians(-125.0), math.radians(-15.0))
                    if abs(cx - e.x) > 1e-5:
                        e.x = cx
                        ch = True
                elif bn == "LeftForeArm":
                    cz = clamp(e.z, math.radians(25.0), math.radians(125.0))
                    if abs(cz - e.z) > 1e-5:
                        e.z = cz
                        ch = True
                elif bn == "RightForeArm":
                    cz = clamp(e.z, math.radians(-125.0), math.radians(-25.0))
                    if abs(cz - e.z) > 1e-5:
                        e.z = cz
                        ch = True
                if ch:
                    q_comb = e.to_quaternion().normalized()

            pb.rotation_mode = "QUATERNION"
            pb.rotation_quaternion = q_comb
            pb.keyframe_insert(data_path="rotation_quaternion", frame=f)

        alarm = smoothstep(float(alarm_start_frame), float(max(alarm_start_frame + 1, release_frame - 1)), float(f))
        scream = smoothstep(float(release_frame), float(release_frame + 6), float(f)) if f >= release_frame else 0.0
        ts = max(0.0, (f - release_frame) / 30.0)
        apply_face_weights(shaped_meshes, f, {
            "jawOpen": lerp(lerp(0.04, 0.35, alarm), 0.78 + 0.16 * math.sin(ts * 9.0), scream),
            "mouthFunnel": scream * (0.32 + 0.12 * math.cos(ts * 7.0)),
            "mouthStretchLeft": scream * 0.48,
            "mouthStretchRight": scream * 0.48,
            "mouthLowerDownLeft": scream * 0.45,
            "mouthLowerDownRight": scream * 0.45,
            "mouthFrownLeft": scream * 0.35,
            "mouthFrownRight": scream * 0.35,
            "eyeWideLeft": lerp(lerp(0.0, 0.65, alarm), 0.95, scream),
            "eyeWideRight": lerp(lerp(0.0, 0.65, alarm), 0.95, scream),
            "browInnerUp": lerp(lerp(0.15, 0.70, alarm), 0.92, scream),
            "browOuterUpLeft": lerp(lerp(0.0, 0.45, alarm), 0.65, scream),
            "browOuterUpRight": lerp(lerp(0.0, 0.45, alarm), 0.65, scream),
        })

    return hips_pos, hips_rot


def print_ragdoll_diagnostics(scene: bpy.types.Scene, arm: bpy.types.Object, sample_frames: Tuple[int, ...]) -> None:
    print("\n=== ACTIVE RAGDOLL JOINT DIAGNOSTICS ===", flush=True)
    bones = ["Spine2", "Head", "LeftArm", "LeftForeArm", "RightArm", "RightForeArm", "LeftUpLeg", "LeftLeg", "RightUpLeg", "RightLeg"]
    rb_hips = bpy.data.objects.get("RB_Hips")
    for f in sample_frames:
        scene.frame_set(f)
        deps = bpy.context.evaluated_depsgraph_get()
        arm_ev = arm.evaluated_get(deps)
        parts = [f"{bn}:{math.degrees(arm_ev.pose.bones[bn].rotation_quaternion.angle):.0f}°" for bn in bones if bn in arm_ev.pose.bones]
        pos_s = ""
        if rb_hips:
            p = rb_hips.evaluated_get(deps).matrix_world.translation
            pos_s = f" | Hips=({p.x:.1f},{p.y:.1f},{p.z:.1f})"
        print(f"F{f:03d}: " + " ".join(parts) + pos_s, flush=True)
