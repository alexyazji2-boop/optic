"""Render Scout, Pulse's mascot, as transparent 3D frames.

Concept 03 ("Scout") from the user's snowman sheet, built as a signed-distance
scene and ray-marched in numpy: two ivory snowballs with a matte clay grain,
the Optic aperture inset as each eye (a gold metal rim, a dark glossy floor,
the logo's chart line raised on it), a carved smile, a muted gold scarf with a
flying tail, stub hands and feet. One key light, one fill, a hemisphere sky,
soft shadows and ambient occlusion, identical for every frame, so a blink or a
tilt changes only the pose.

There is no Blender on the machine this was made on and the app has no build
step, so the renderer is this file and its output is committed:

    static/scout/scout-full@{2x,3x}.webp        the 22 poses in FRAMES, one row (288x380 at 3x)
    static/scout/scout-compact@{2x,3x}.webp     the same poses as a bust (144x156 at 3x)
    static/scout/scout-{full,compact}-tail@*.webp  the scarf's tail, WIND phases, drawn under the pose
    static/scout/frames.json                    the frame order, which components/scout.js copies
    static/scout/scout.png                      the resting pose with its tail, for reference

Run from the repository root (about 25 minutes with everything):
    .venv/bin/python optic-brand/scout/render_scout.py [--no-tail] [--no-hero]
"""

from __future__ import annotations

import json
import math
import os
import sys
from multiprocessing import Pool

import numpy as np
from PIL import Image

OUT = os.path.join(os.path.dirname(__file__), "..", "..", "static", "scout")

# ------------------------------------------------------------------ helpers


def nrm(v):
    return v / np.linalg.norm(v, axis=-1, keepdims=True)


def rot_z(p, pivot, ang):
    c, s = math.cos(ang), math.sin(ang)
    q = p - pivot
    return np.stack([q[:, 0] * c - q[:, 1] * s, q[:, 0] * s + q[:, 1] * c, q[:, 2]], 1) + pivot


def rot_x(q, ang):
    c, s = math.cos(ang), math.sin(ang)
    return np.stack([q[:, 0], q[:, 1] * c - q[:, 2] * s, q[:, 1] * s + q[:, 2] * c], 1)


def sd_ellipsoid(p, c, r):
    q = (p - c) / r
    k0 = np.linalg.norm(q, axis=1)
    k1 = np.linalg.norm(q / r, axis=1)
    return k0 * (k0 - 1.0) / np.maximum(k1, 1e-9)


def sd_box(p, c, h, r=0.0):
    """Distance to a box of half-extents `h` about `c`, corners rounded by `r`."""
    q = np.abs(p - c) - (h - r)
    return np.linalg.norm(np.maximum(q, 0), axis=1) + np.minimum(q.max(1), 0) - r


def sd_capsule(p, a, b, r):
    ab = b - a
    t = np.clip(((p - a) @ ab) / (ab @ ab), 0, 1)
    return np.linalg.norm(p - a - t[:, None] * ab, axis=1) - r


def sd_cyl(p, c, r, hh):
    """A cylinder standing on the y axis."""
    d = np.stack([np.hypot(p[:, 0] - c[0], p[:, 2] - c[2]) - r, np.abs(p[:, 1] - c[1]) - hh], 1)
    return np.minimum(d.max(1), 0) + np.linalg.norm(np.maximum(d, 0), axis=1)


def rot_x_at(p, pivot, ang):
    """Rotate points about the x axis through `pivot`. Passing +ang tests a shape
    whose world pose leans back (its top away from the camera) by ang."""
    c, s = math.cos(ang), math.sin(ang)
    y, z = p[:, 1] - pivot[1], p[:, 2] - pivot[2]
    return np.stack([p[:, 0], pivot[1] + y * c - z * s, pivot[2] + y * s + z * c], 1)


def poly2(u, v, pts):
    """Distance in a plane to a polyline."""
    best = None
    for (x0, y0), (x1, y1) in zip(pts, pts[1:]):
        dx, dy = x1 - x0, y1 - y0
        t = np.clip(((u - x0) * dx + (v - y0) * dy) / (dx * dx + dy * dy), 0, 1)
        d = np.hypot(u - x0 - t * dx, v - y0 - t * dy)
        best = d if best is None else np.minimum(best, d)
    return best


def smin(a, b, k):
    h = np.clip(0.5 + 0.5 * (b - a) / k, 0, 1)
    return b * (1 - h) + a * h - k * h * (1 - h)


def hash3(i, j, k):
    n = np.sin(i * 127.1 + j * 311.7 + k * 74.7) * 43758.5453
    return n - np.floor(n)


def vnoise(p):
    f = np.floor(p)
    t = p - f
    t = t * t * (3 - 2 * t)
    i, j, k = f[:, 0], f[:, 1], f[:, 2]
    out = 0
    for dx in (0, 1):
        for dy in (0, 1):
            for dz in (0, 1):
                w = ((t[:, 0] if dx else 1 - t[:, 0]) * (t[:, 1] if dy else 1 - t[:, 1])
                     * (t[:, 2] if dz else 1 - t[:, 2]))
                out = out + w * hash3(i + dx, j + dy, k + dz)
    return out


# ------------------------------------------------------------- the figure

BODY_C, BODY_R = np.array([0.0, 0.80, 0.0]), np.array([0.72, 0.68, 0.64])
HEAD_C, HEAD_R = np.array([-0.02, 1.99, 0.04]), np.array([0.69, 0.60, 0.62])
NECK = np.array([0.0, 1.42, 0.0])
# "optic", two Optic-lens eyes and a smile, is the face the app ships: the
# owner tried the Pulse mark as the whole face (07e91b3, SCOUT_FACE=pulse)
# and asked for the two eyes back.
FACE_STYLE = os.environ.get("SCOUT_FACE", "optic")
SHOULDER = np.array([0.52, 0.98, 0.20])
SHOULDER_L = np.array([-0.52, 0.98, 0.20])
HAND_R = np.array([0.70, 0.74, 0.27])
HAND_L = np.array([-0.60, 0.88, 0.38])
HAND_SIZE = np.array([0.175, 0.22, 0.17])
DEPTH = 0.034          # how far the eye floor sits below the head's surface

# The logo's chart line, in its 32-unit space with y down (opticMarkHTML).
TRACE32 = [(7.4, 20.2), (11.4, 15.6), (14.6, 17.8), (18.6, 11.6), (21.6, 14.0), (23.9, 11.4)]
# The Pulse mark's heartbeat, same space (pulseMarkHTML: a circle of radius
# 11.2 round the centre, and this trace across it).
PULSE32 = [(7.6, 16), (10.8, 16), (12.8, 11.4), (15.8, 21.4), (18.0, 15.4), (19.4, 18.2), (23.8, 18.2)]


def surface_frame(yaw, pitch, tilt):
    d = np.array([math.sin(yaw) * math.cos(pitch), math.sin(pitch), math.cos(yaw) * math.cos(pitch)])
    t = 1.0 / np.linalg.norm(d / HEAD_R)
    s = HEAD_C + t * d
    n = (s - HEAD_C) / HEAD_R ** 2
    n /= np.linalg.norm(n)
    u = np.cross([0.0, 1.0, 0.0], n)
    u /= np.linalg.norm(u)
    v = np.cross(n, u)
    c, sn = math.cos(tilt), math.sin(tilt)
    return s, c * u + sn * v, -sn * u + c * v


class Eye:
    def __init__(self, yaw, pitch, tilt, width, closure, slant=0.0, ring=False):
        self.s, self.u, self.v = surface_frame(math.radians(yaw), math.radians(pitch), math.radians(tilt))
        self.ring = ring          # the Pulse mark's circle instead of the Optic lens
        if ring:
            a = b = width / 2
            self.a, self.b, self.h = a, b, 2 * b
            self.R, self.c = a, 0.0
        else:
            a, b = width / 2, width * 0.68 / 2      # the logo lens is 26.8 x 21.2, flatter here so it reads as an eye
            self.a, self.b, self.h = a, b, 2 * b
            self.R = (a * a + b * b) / (2 * b)
            self.c = self.R - b
        self.closure = closure
        self.slant = slant        # + lifts the lid's inner end: the worried look
        sc = width / (22.4 if ring else 26.8)
        self.trace = [((x - 16) * sc, -(y - 16) * sc) for x, y in (PULSE32 if ring else TRACE32)]
        self.rim = width * 0.068
        self.tr = width * 0.045

    def uv(self, p):
        d = p - self.s
        return d @ self.u, d @ self.v

    def lens(self, eu, ev):
        """Exact distance to the lens (a vesica with its points left and
        right). The max of the two circles is exact inside but too small past
        the points, which thinned the gold rim to a gap at each tip."""
        if self.ring:
            return np.hypot(eu, ev) - self.R
        x, y = np.abs(ev), np.abs(eu)
        b, d = self.a, self.c
        tip = (y - b) * d > x * b
        return np.where(tip, np.hypot(x, y - b), np.hypot(x + d, y) - self.R)

    def lid_edge(self, eu):
        low = self.c - np.sqrt(np.maximum(self.R ** 2 - eu ** 2, 0))
        if self.ring:
            # One lid over one ring: worry lowers it at both sides alike, so
            # the face reads as concerned rather than raising one brow.
            low = -np.sqrt(np.maximum(self.R ** 2 - eu ** 2, 0))
            return low + self.h * (1 - self.closure) - abs(self.slant) * np.abs(eu)
        # The slant fades out over the last 40% of the closure: a fully closed
        # eye is the plain lash line, since a slanted one runs out of the lens
        # at one tip and left a broken lid on the concerned blink.
        return low + self.h * (1 - self.closure) + self.slant * min(1.0, (1 - self.closure) / 0.4) * eu

    def trace_dist(self, eu, ev):
        best = None
        for (x0, y0), (x1, y1) in zip(self.trace, self.trace[1:]):
            dx, dy = x1 - x0, y1 - y0
            t = np.clip(((eu - x0) * dx + (ev - y0) * dy) / (dx * dx + dy * dy), 0, 1)
            d = np.hypot(eu - x0 - t * dx, ev - y0 - t * dy)
            best = d if best is None else np.minimum(best, d)
        return best


def rot_y_m(a):
    c, s = math.cos(a), math.sin(a)
    return np.array([[c, 0, s], [0, 1, 0], [-s, 0, c]])


def rot_x_m(a):
    c, s = math.cos(a), math.sin(a)
    return np.array([[1, 0, 0], [0, c, -s], [0, s, c]])


def rot_z_m(a):
    c, s = math.cos(a), math.sin(a)
    return np.array([[c, -s, 0], [s, c, 0], [0, 0, 1]])


class Pose:
    """One frame's pose. Angles in degrees.

    tilt   head roll, + leans the top of the head to the viewer's right
    yaw    head turn, + looks to the viewer's right
    pitch  head nod, + tips the face down
    wave   right arm raised from the shoulder
    worry  0..1, the concerned face: lids lowered at the outer corners and a
           flatter, smaller mouth (never a frown)"""

    def __init__(self, tilt=0.0, yaw=0.0, pitch=0.0, cl=0.0, cr=0.0, wide=False,
                 wave=0.0, worry=0.0, tail=True, face=None, wind=0.0, tail_only=False,
                 prop=None, type_=0.0, pen=0.0):
        # world = H (local - neck) + neck; points are mapped back with H's transpose.
        self.H = rot_y_m(math.radians(yaw)) @ rot_x_m(math.radians(pitch)) @ rot_z_m(-math.radians(tilt))
        self.wave = math.radians(wave)
        self.tail = tail or tail_only
        self.wind = wind            # 0..1, the phase of the scarf tail's flutter
        self.tail_only = tail_only  # render the tail alone, the body held out
        k = 0.42 * worry
        cl = max(cl, 0.30 * worry)
        cr = max(cr, 0.30 * worry)
        face = face or FACE_STYLE
        self.smile = face != "pulse"
        if face == "pulse":
            # The Pulse mark as the whole face: its ring and heartbeat. Tried
            # and set aside for the two eyes (2026-10-11); kept to reproduce
            # 07e91b3. The curious look opens the ring a little wider.
            self.eyes = [Eye(9, -1, 0, 0.62 * (1.08 if wide else 1.0), max(cl, cr), slant=k * 0.8, ring=True)]
        else:
            self.eyes = [Eye(-20, 6, -10, 0.46, cl, slant=k),
                         Eye(28, 9, -15, 0.40 * (1.16 if wide else 1.0), cr, slant=-k)]
        # The thing he is working with, and where that puts his hands. None keeps the standing figure
        # exactly as it was: the 22 frames the app already ships march the same scene they always did.
        self.prop = prop
        self.pen = pen
        self.hand_l, self.hand_r = HAND_L, HAND_R
        if prop == "desk":
            lift = 0.024 * math.sin(math.pi * type_)
            self.hand_l = np.array([-0.13, DESK_Y + 0.135 + lift, 1.14])
            self.hand_r = np.array([0.46, DESK_Y + 0.135 + (0.024 - lift), 1.14])
        elif prop == "tablet":
            self.hand_l = np.array([-0.29, 0.97, 1.10])
            self.hand_r = np.array([0.55, 0.97, 1.10])
        elif prop == "write":
            self.hand_l = np.array([-0.36, DESK_Y + 0.115, 1.16])
            self.hand_r = np.array([0.30 + 0.11 * pen, DESK_Y + 0.21, 1.16 - 0.04 * pen])
        self.mouth = surface_frame(math.radians(8), math.radians(-23), math.radians(-4))
        self.smile_w = 0.10 - 0.025 * worry
        self.smile_d = 0.042 - 0.030 * worry


# --------------------------------------------------------------- what he works with
#
# Three worked scenes for Milo's activity states (docs/milo/MILO_CHARACTER_DESIGN.md): a desk with a dark
# laptop and two books, a tablet held in both hands, and the same desk with an open notebook, a pencil and a
# cup. He stands behind the desk rather than sitting at it: the desk crosses him at scarf height and hides
# everything below, which is the composition the reference sheet has and which keeps the body, the arms and
# the whole light rig identical to every other frame.
#
# Materials: 8 shell (laptop, tablet, cup), 9 desk, 10 paper, 11 book cloth. Gold reuses 2 and 3.
# The camera is almost level with him (it has to be: every frame shares one rig), so anything lying flat is
# foreshortened to a few pixels and disappears. Everything here therefore stands up, and the desk is a narrow
# table with its ends and legs in frame rather than a slab running off both edges, which in a sprite with a
# transparent background would read as a black bar rather than as furniture.
DESK_Y = 0.95                                    # the top surface
DESK_C, DESK_H = np.array([0.10, DESK_Y - 0.046, 0.66]), np.array([1.05, 0.046, 0.46])
LEG_X, LEG_Z = (-0.90, 1.10), 0.96
HINGE = np.array([0.0, DESK_Y + 0.044, 0.62])    # the laptop's, at the back of its base
LID_C, LID_H, LID_LEAN = np.array([0.14, DESK_Y + 0.240, 0.62]), np.array([0.34, 0.210, 0.014]), math.radians(13)
TAB_C, TAB_H, TAB_LEAN = np.array([0.13, 1.00, 0.94]), np.array([0.35, 0.235, 0.019]), math.radians(36)
NOTE_P, NOTE_H, NOTE_LEAN = np.array([0.02, DESK_Y + 0.016, 0.98]), np.array([0.44, 0.26, 0.014]), math.radians(48)
# The chart on the tablet, and the Optic trace inside the laptop's aperture: the logo's own line, set by hand
# in each plane rather than scaled from TRACE32, because both are far smaller than an eye.
TAB_TRACE = [(-0.23, -0.09), (-0.10, 0.05), (0.01, -0.04), (0.12, 0.11), (0.23, 0.02)]
LID_TRACE = [(-0.036, -0.011), (-0.011, 0.016), (0.008, -0.004), (0.036, 0.023)]


def props(p, P):
    """Distance to the prop, and its material. Nothing is built for a pose that has no prop."""
    far = np.full(len(p), 9.0)
    if not P.prop:
        return far, None
    kind = P.prop
    d = far.copy()
    m = np.zeros(len(p), np.int8)

    def add(dist, mat):
        nonlocal d, m
        m = np.where(dist < d, mat, m).astype(np.int8)
        d = np.minimum(d, dist)

    if kind in ("desk", "write"):
        add(sd_box(p, DESK_C, DESK_H, 0.012), 9)
        for lx in LEG_X:
            add(sd_box(p, np.array([lx, (DESK_Y - 0.076 - 0.16) / 2, LEG_Z]),
                       np.array([0.042, (DESK_Y - 0.076 + 0.16) / 2, 0.042]), 0.012), 12)

    if kind == "desk":
        add(sd_box(p, np.array([0.14, DESK_Y + 0.020, 0.90]), np.array([0.34, 0.020, 0.28]), 0.010), 8)
        q = rot_x_at(p, HINGE, LID_LEAN)
        add(sd_box(q, LID_C, LID_H, 0.013), 8)
        # The aperture on the lid's back: the ring, and the logo's line inside it.
        mu, mv, mz = q[:, 0] - LID_C[0], q[:, 1] - LID_C[1], q[:, 2] - (LID_C[2] + LID_H[2])
        add(np.hypot(np.hypot(mu, mv) - 0.062, mz) - 0.0105, 2)
        add(np.hypot(poly2(mu, mv, LID_TRACE), mz) - 0.0072, 3)
        # Two books stacked at his left, each with a gold band so they read at card size.
        for c, h in ((np.array([-0.60, DESK_Y + 0.062, 0.84]), np.array([0.26, 0.062, 0.19])),
                     (np.array([-0.56, DESK_Y + 0.178, 0.87]), np.array([0.23, 0.054, 0.17]))):
            add(sd_box(p, c, h, 0.009), 11)
            add(sd_box(p, c + np.array([0.0, 0.0, h[2]]), np.array([h[0] * 0.96, h[1] * 0.28, 0.005])), 2)

    if kind == "tablet":
        q = rot_x_at(p, TAB_C, TAB_LEAN)
        add(sd_box(q, TAB_C, TAB_H, 0.028), 8)
        tu, tv = q[:, 0] - TAB_C[0], q[:, 1] - TAB_C[1]
        add(np.hypot(poly2(tu, tv, TAB_TRACE), q[:, 2] - (TAB_C[2] + TAB_H[2])) - 0.013, 3)

    if kind == "write":
        q = rot_x_at(p, NOTE_P, NOTE_LEAN)
        nc = NOTE_P + np.array([0.0, 0.20, 0.0])
        add(sd_box(q, nc, NOTE_H + np.array([0.034, 0.034, 0.004]), 0.014), 8)
        pages = nc + np.array([0.0, 0.0, 0.014])
        add(sd_box(q, pages, NOTE_H, 0.010), 10)
        nc, face = pages, np.abs(q[:, 2] - (pages[2] + NOTE_H[2])) - 0.005
        # The spine down the middle, and the lines he has written so far on the right page.
        add(np.maximum(np.maximum(np.abs(q[:, 0] - nc[0]) - 0.008,
                                  np.abs(q[:, 1] - nc[1]) - 0.23), face), 9)
        for k, w in ((0.0, 0.13), (-0.075, 0.115), (-0.15, 0.06 + 0.055 * P.pen)):
            add(np.maximum(np.maximum(np.abs(q[:, 0] - (nc[0] + 0.045 + w)) - w,
                                      np.abs(q[:, 1] - (nc[1] + 0.085 + k)) - 0.0075), face), 9)
        # The pencil runs right through his hand and well past it at both ends: his hands are mitts, and a
        # pencil the length of a real one vanishes inside one (first render, 2026-11-03).
        grip = np.array([0.30 + 0.11 * P.pen, DESK_Y + 0.21, 1.16 - 0.04 * P.pen])
        pa = grip + np.array([-0.21, -0.28, 0.02])
        add(sd_capsule(p, pa, pa + np.array([0.52, 0.72, -0.13]), 0.030), 2)
        cup = np.array([0.88, DESK_Y + 0.105, 0.78])
        add(sd_cyl(p, cup, 0.115, 0.105), 8)
        add(np.hypot(np.hypot(p[:, 0] - cup[0], p[:, 2] - cup[2]) - 0.115, p[:, 1] - (cup[1] + 0.105)) - 0.012, 2)

    return d, m


def scene(p, P, mats=False):
    """Distance to Scout from each point; with mats, also a material id.

    0 snow  1 lid  2 gold metal  3 gold trace  4 eye floor  5 smile  6 scarf"""
    # Snow: body, feet, hands.
    body = sd_ellipsoid(p, BODY_C, BODY_R)
    feet = np.minimum(sd_ellipsoid(p, np.array([-0.30, 0.13, 0.22]), np.array([0.25, 0.13, 0.27])),
                      sd_ellipsoid(p, np.array([0.31, 0.13, 0.20]), np.array([0.25, 0.13, 0.27])))
    # Hands sized and placed to stand off the body, not melt into it: asked
    # for "a little more visible" after the first renders.
    hl = rot_z(p, P.hand_l, math.radians(-25))
    hand_l = sd_ellipsoid(hl, P.hand_l, HAND_SIZE)
    # The left hand rests against the body in the standing frames and needs no arm. Reaching for a keyboard,
    # a tablet or a page it would float, so a prop gives it the same capsule the right one has always had.
    if P.prop:
        hand_l = smin(hand_l, sd_capsule(p, SHOULDER_L, P.hand_l, 0.085), 0.05)
    # The right arm swings from the shoulder: a short capsule from inside the
    # body to the hand, so a raised hand stays joined to him instead of
    # floating free, and nothing on the body stretches.
    pw = rot_z(p, SHOULDER, -P.wave)
    hr = rot_z(pw, P.hand_r, math.radians(28))
    hand_r = sd_ellipsoid(hr, P.hand_r, HAND_SIZE)
    ba = P.hand_r - SHOULDER
    pa = pw - SHOULDER
    h = np.clip((pa @ ba) / (ba @ ba), 0, 1)
    arm = np.linalg.norm(pa - h[:, None] * ba, axis=1) - 0.085
    arm_r = smin(hand_r, arm, 0.05)
    snow = smin(smin(body, hand_l, 0.03), arm_r, 0.03)
    snow = np.minimum(snow, feet)

    # Head, in its own tilted frame.
    q = (p - NECK) @ P.H + NECK
    head0 = sd_ellipsoid(q, HEAD_C, HEAD_R)
    head = head0
    gold = np.full(len(p), 9.0)
    trace = np.full(len(p), 9.0)
    lens_in = np.full(len(p), 9.0)
    open_in = np.full(len(p), 9.0)
    for e in P.eyes:
        eu, ev = e.uv(q)
        lens = e.lens(eu, ev)
        edge = e.lid_edge(eu)
        opn = np.maximum(lens, ev - edge)
        # The lid is a soft swelling over the covered part of the lens, so a
        # half-closed eye has an eyelid rather than a missing top half.
        if e.closure > 0.02:
            puff = 0.016 * np.clip(-lens / 0.03, 0, 1) * np.clip((ev - edge) / 0.03, 0, 1)
            head = head - puff
        head = np.maximum(head, -np.maximum(opn, -(head0 + DEPTH)))
        # The rim only where the eye is open, plus the lower arc: a closed eye
        # is a gold lash line, not an empty ring.
        ring = np.hypot(lens, head0) - e.rim
        if e.closure > 0.02:
            ring = np.maximum(ring, ev - edge - e.rim * 0.5)
            lash = np.hypot(ev - edge, head0 + 0.008) - e.rim * 0.7
            ring = np.minimum(ring, np.maximum(lash, lens - e.rim * 0.3))
        gold = np.minimum(gold, ring)
        trace = np.minimum(trace, np.hypot(e.trace_dist(eu, ev), head0 + DEPTH) - e.tr)
        lens_in = np.minimum(lens_in, lens)
        open_in = np.minimum(open_in, opn)
    # The smile, carved.
    ms, mu, mv = P.mouth
    d = q - ms
    su, sv = d @ mu, d @ mv
    sw, sd = P.smile_w, P.smile_d
    uc = np.clip(su, -sw, sw)
    curve = sd * (uc / sw) ** 2
    smile = np.hypot(np.hypot(su - uc, sv - curve), head0) - 0.019
    if not P.smile:
        smile = np.full(len(p), 9.0)
    head = np.maximum(head, -smile)

    # Scarf: a ring round the neck, a knot, and a tail flying to the right.
    sq = rot_x(p - np.array([0.0, 1.43, 0.03]), math.radians(-10))
    ang = np.arctan2(sq[:, 0], sq[:, 2])
    ar = 0.14 * (1 + 0.05 * np.sin(5 * ang))
    rho = np.hypot(sq[:, 0], sq[:, 2]) - 0.335
    scarf = (np.hypot(rho / ar, sq[:, 1] / 0.085) - 1) * 0.085
    knot = sd_ellipsoid(p, np.array([0.27, 1.37, 0.33]), np.array([0.11, 0.10, 0.08]))
    scarf = smin(scarf, knot, 0.04)
    tail = np.full(len(p), 9.0)
    if P.tail:
        # The tail in the wind: a wave travelling from the knot to the tip,
        # growing toward the free end, one cycle per `wind` 0..1 so the
        # frames loop without a seam.
        ph = 2 * math.pi * P.wind
        x0, x1 = 0.28, 1.10 + 0.025 * math.sin(ph)
        t = np.clip((p[:, 0] - x0) / (x1 - x0), 0, 1)
        cy = 1.36 - 0.06 * t + (0.02 + 0.06 * t) * np.sin(t * 2 * math.pi * 1.25 - ph)
        cz = 0.30 - 0.32 * t + 0.035 * t * np.sin(t * 2 * math.pi * 0.9 - ph + 1.0)
        hw = 0.075 * (1 + 0.55 * t) * (1 + 0.07 * np.sin(t * 2 * math.pi - ph))
        ht = 0.022
        dy = np.abs(p[:, 1] - cy) - hw
        dz = np.abs(p[:, 2] - cz) - ht
        rib = np.minimum(np.maximum(dy, dz), 0) + np.hypot(np.maximum(dy, 0), np.maximum(dz, 0)) - 0.012
        ends = np.maximum(x0 - p[:, 0], p[:, 0] - x1 + 0.03 * np.sin(p[:, 1] * 60))
        tail = np.maximum(rib, ends) * 0.6
        scarf = smin(scarf, tail, 0.03)

    prop_d, prop_m = props(p, P)
    dist = np.minimum.reduce([snow, head, gold, trace, scarf])
    if not mats:
        return np.minimum(dist, prop_d)
    # Where each surface point sits on its own part, so the clay grain moves
    # with the head and the arm instead of sliding across them between frames.
    local = p.copy()
    on_head = head <= np.minimum(snow, scarf)
    local[on_head] = q[on_head]
    on_arm = (arm_r < body) & ~on_head
    local[on_arm] = pw[on_arm]
    m = np.zeros(len(p), np.int8)
    m[(head <= snow) & (lens_in < 0)] = 1
    m[(head <= snow) & (open_in < 0.004) & (head0 < -DEPTH * 0.5)] = 4
    m[(head <= snow) & (smile < 0.012)] = 5
    m[scarf <= dist + 1e-4] = 6
    m[gold <= dist + 1e-4] = 2
    m[trace <= dist + 1e-4] = 3
    m[(tail <= dist + 1e-4) & (m == 6)] = 7     # the tail: scarf cloth, its own layer
    if prop_m is not None:
        sel = prop_d < dist
        m[sel] = prop_m[sel]
        local[sel] = p[sel]
        dist = np.minimum(dist, prop_d)
    return dist, m, local


# ----------------------------------------------------------------- render

KEY = nrm(np.array([-0.55, 0.85, 0.62]))
FILL = nrm(np.array([0.75, 0.15, 0.45]))
CAM = np.array([0.10, 1.75, 14.0])


def normal(p, P):
    e = 6e-4
    ex = np.array([e, 0, 0]); ey = np.array([0, e, 0]); ez = np.array([0, 0, e])
    n = np.stack([scene(p + ex, P) - scene(p - ex, P),
                  scene(p + ey, P) - scene(p - ey, P),
                  scene(p + ez, P) - scene(p - ez, P)], 1)
    return nrm(n)


def soft_shadow(p, P, k=9.0):
    res = np.ones(len(p))
    t = np.full(len(p), 0.02)
    for _ in range(48):
        h = scene(p + KEY * t[:, None], P)
        res = np.minimum(res, k * h / t)
        t += np.clip(h, 0.01, 0.2)
    return np.clip(res, 0, 1)


def occlusion(p, n, P):
    occ = np.zeros(len(p))
    w = 1.0
    for i in range(1, 6):
        h = 0.03 * i
        occ += w * (h - scene(p + n * h, P))
        w *= 0.7
    return np.clip(1 - 2.2 * occ, 0, 1)


def tonemap(c):
    c = c * 1.05
    c = (c * (2.51 * c + 0.03)) / (c * (2.43 * c + 0.59) + 0.14)
    return np.clip(c, 0, 1) ** (1 / 2.2)


def shade(p, P):
    n0 = normal(p, P)
    _, m, loc = scene(p, P, mats=True)
    # Matte clay grain on the snow and the scarf: a little bump, no gloss.
    g = 18.0
    base = vnoise(loc * g)
    grad = np.stack([vnoise((loc + [0.004, 0, 0]) * g) - base,
                     vnoise((loc + [0, 0.004, 0]) * g) - base,
                     vnoise((loc + [0, 0, 0.004]) * g) - base], 1)
    soft = (m == 0) | (m == 1) | (m == 6)
    n = n0.copy()
    n[soft] = nrm(n0[soft] - grad[soft] * 1.25)
    grain = vnoise(loc * 70.0)

    v = nrm(CAM - p)
    sh = soft_shadow(p + n0 * 0.004, P)
    ao = occlusion(p, n0, P)
    ndl = (n * KEY).sum(1)
    hk = nrm(KEY + v)
    ndh = np.clip((n * hk).sum(1), 0, 1)
    ndv = np.clip((n * v).sum(1), 0, 1)
    sky = np.array([0.56, 0.58, 0.64]) * (0.5 + 0.5 * n[:, 1:2]) + np.array([0.22, 0.19, 0.16]) * (0.5 - 0.5 * n[:, 1:2])
    amb = sky * ao[:, None] * 0.62
    keycol = np.array([1.0, 0.95, 0.87]) * 0.96
    fill = np.clip((n * FILL).sum(1), 0, 1)[:, None] * np.array([0.78, 0.84, 0.95]) * 0.30
    rim = ((1 - ndv) ** 3)[:, None] * np.array([1.0, 0.92, 0.8]) * 0.22 * ao[:, None]
    refl = 2 * ndv[:, None] * n - v
    env = 0.08 + 0.85 * np.clip((refl[:, 1:2] + 0.15) / 0.9, 0, 1)

    col = np.zeros((len(p), 3))
    # Albedos are linear (sRGB values raised to 2.2), or the gamma at the end
    # washes the ivory out to white and the scarf to cream.
    # snow and lid
    wrap = (np.clip((ndl + 0.3) / 1.3, 0, 1) * sh)[:, None]
    alb = np.array([0.86, 0.77, 0.60]) * (0.97 + 0.04 * grain)[:, None]
    alb[m == 1] *= 0.93
    snowc = alb * (wrap * keycol + fill + amb) + rim + (0.06 * sh * ndh ** 20)[:, None] \
        + alb * np.array([1.0, 0.85, 0.7]) * 0.05 * (1 - ndv)[:, None]
    # gold metal: tinted reflections, one tight highlight
    G = np.array([0.95, 0.62, 0.14])
    lam = (np.clip(ndl, 0, 1) * sh)[:, None]
    metal = G * (0.22 * (lam * keycol + amb)) + G * env * 0.5 * ao[:, None] \
        + G * (1.25 * sh * ndh ** 60)[:, None] + (0.35 * sh * ndh ** 320)[:, None]
    tracec = metal * 0.9 + G * 0.42
    # eye floor: near black glass with a catchlight
    floor = np.array([0.045, 0.038, 0.028]) * (lam * keycol + amb) + (0.95 * sh * ndh ** 150)[:, None] \
        + 0.05 * env * ao[:, None]
    smilec = np.array([0.05, 0.03, 0.018]) * (wrap * keycol + amb)
    # scarf: muted gold cloth, a restrained sheen
    S = np.array([0.35, 0.225, 0.065]) * (0.95 + 0.1 * grain)[:, None]
    scarfc = S * (wrap * keycol * 0.95 + fill + amb) + G * (0.30 * sh * ndh ** 28)[:, None] \
        + G * env * 0.06 * ao[:, None] + rim * 0.5

    # What he works with: matte shells, a matte desk, paper and cloth, under the same rig, so they sit in his
    # world rather than being pasted onto it.
    def matte(alb, spec=0.0, power=40):
        c = alb * (wrap * keycol + fill + amb)
        return c + (spec * sh * ndh ** power)[:, None] if spec else c
    shell = matte(np.array([0.021, 0.024, 0.028]), 0.22, 60) + rim * 0.35
    deskc = matte(np.array([0.042, 0.034, 0.029]), 0.05, 30)
    paperc = matte(np.array([0.80, 0.76, 0.68]) * (0.98 + 0.03 * grain)[:, None])
    bookc = matte(np.array([0.110, 0.082, 0.056]) * (0.96 + 0.08 * grain)[:, None], 0.04, 24)
    legc = matte(np.array([0.026, 0.021, 0.018]), 0.04, 30)

    for mid, c in ((0, snowc), (1, snowc), (2, metal), (3, tracec), (4, floor), (5, smilec), (6, scarfc),
                   (7, scarfc), (8, shell), (9, deskc), (10, paperc), (11, bookc), (12, legc)):
        sel = m == mid
        col[sel] = c[sel]
    return tonemap(col)


def trace_rays(P, d):
    t = (CAM[2] - 1.25) / -d[:, 2]
    hit = np.zeros(len(d), bool)
    alive = np.arange(len(d))
    for _ in range(220):
        if not len(alive):
            break
        p = CAM + d[alive] * t[alive, None]
        dist = scene(p, P)
        done = dist < 4e-4
        hit[alive[done]] = True
        t[alive] += dist * 0.8
        far = t[alive] > CAM[2] + 1.6
        alive = alive[~done & ~far]
    rgba = np.zeros((len(d), 4))
    idx = np.nonzero(hit)[0]
    if P.tail_only and len(idx):
        # Only rays whose first surface is the tail; the body, lit and
        # shadowing as usual, is held out (it is the other layer).
        p = CAM + d[idx] * t[idx, None]
        idx = idx[scene(p, P, mats=True)[1] == 7]
    if len(idx):
        p = CAM + d[idx] * t[idx, None]
        rgba[idx, :3] = shade(p, P)
        rgba[idx, 3] = 1
    if P.tail_only:
        return rgba
    # A soft contact shadow on an invisible floor, so he stands on something.
    miss = np.nonzero(~hit & (d[:, 1] < 0))[0]
    if len(miss):
        tg = -CAM[1] / d[miss, 1]
        g = CAM + d[miss] * tg[:, None]
        near = np.hypot(g[:, 0], g[:, 2] - 0.15) < 1.3
        g, mi = g[near], miss[near]
        if len(g):
            s = soft_shadow(g + [0, 0.002, 0], P, k=5.0)
            c = np.clip(scene(g, P) / 0.32, 0, 1)
            dark = 1 - np.minimum(s, c ** 0.8)
            fade = np.clip(1 - (np.hypot(g[:, 0], g[:, 2] - 0.15) - 0.55) / 0.7, 0, 1)
            rgba[mi, 3] = 0.42 * dark * fade
    return rgba


def render(P, window, size, ss, chunk=200000):
    """Premultiplied RGBA at `size`, from `ss` x `ss` rays per pixel. Rays are
    marched in chunks: a whole 3x frame at once holds a few GB of temporaries
    per worker, and ten workers on a 16 GB machine stalled in swap."""
    (x0, x1, y0, y1), (w, h) = window, size
    W, H = w * ss, h * ss
    xs = x0 + (np.arange(W) + 0.5) / W * (x1 - x0)
    ys = y1 - (np.arange(H) + 0.5) / H * (y1 - y0)
    gx, gy = np.meshgrid(xs, ys)
    target = np.stack([gx.ravel(), gy.ravel(), np.zeros(gx.size)], 1)
    rgba = np.zeros((len(target), 4))
    for c0 in range(0, len(target), chunk):
        rgba[c0:c0 + chunk] = trace_rays(P, nrm(target[c0:c0 + chunk] - CAM))
    img = rgba.reshape(H, W, 4)
    img[..., :3] *= img[..., 3:4]          # premultiply, then box-filter down
    return img.reshape(h, ss, w, ss, 4).mean((1, 3))


# Frame order is a contract with static/components/scout.js (FRAME) and
# tests/test_pulse_scout.py, which reads static/scout/frames.json. Add new
# frames at the end.
FRAMES = [
    ("idle", dict()), ("idle-half", dict(cl=0.5, cr=0.5)), ("idle-closed", dict(cl=1.0, cr=1.0)),
    ("lean", dict(tilt=2.5)),
    ("tilt", dict(tilt=5)), ("tilt-half", dict(tilt=5, cl=0.5, cr=0.5)), ("tilt-closed", dict(tilt=5, cl=1.0, cr=1.0)),
    ("curious", dict(tilt=8, wide=True)), ("curious-half", dict(tilt=8, wide=True, cl=0.5, cr=0.5)),
    ("curious-closed", dict(tilt=8, wide=True, cl=1.0, cr=1.0)),
    ("arm-1", dict(wave=30)), ("arm-2", dict(wave=65)), ("arm-3", dict(wave=100)),
    ("look-l1", dict(tilt=2.5, yaw=-9)), ("look-l2", dict(tilt=2.5, yaw=-18)),
    ("look-r1", dict(tilt=2.5, yaw=9)), ("look-r2", dict(tilt=2.5, yaw=18)),
    ("nod-1", dict(pitch=6)), ("nod-2", dict(pitch=12)),
    ("concerned", dict(worry=1.0, tilt=-2)), ("concerned-half", dict(worry=1.0, tilt=-2, cl=0.6, cr=0.6)),
    ("concerned-closed", dict(worry=1.0, tilt=-2, cl=1.0, cr=1.0)),
    # The three worked poses, for Milo's activity states. Each has its own half-closed and closed lid so a
    # blink does not change the pose it happens in, and one or two frames of the small motion it loops on.
    ("desk", dict(prop="desk", tilt=1.5, pitch=9)),
    ("desk-half", dict(prop="desk", tilt=1.5, pitch=9, cl=0.5, cr=0.5)),
    ("desk-closed", dict(prop="desk", tilt=1.5, pitch=9, cl=1.0, cr=1.0)),
    ("desk-type", dict(prop="desk", tilt=1.5, pitch=9, type_=1.0)),
    ("tablet", dict(prop="tablet", tilt=3, pitch=13)),
    ("tablet-half", dict(prop="tablet", tilt=3, pitch=13, cl=0.5, cr=0.5)),
    ("tablet-closed", dict(prop="tablet", tilt=3, pitch=13, cl=1.0, cr=1.0)),
    ("tablet-near", dict(prop="tablet", tilt=4, pitch=19)),
    ("write", dict(prop="write", tilt=2, pitch=15)),
    ("write-half", dict(prop="write", tilt=2, pitch=15, cl=0.5, cr=0.5)),
    ("write-closed", dict(prop="write", tilt=2, pitch=15, cl=1.0, cr=1.0)),
    ("write-1", dict(prop="write", tilt=2, pitch=15, pen=0.5)),
    ("write-2", dict(prop="write", tilt=2, pitch=15, pen=1.0)),
    # In-between arm positions, added 2026-11-03. The wave had only arm-1, arm-2 and arm-3 (30, 65 and 100
    # degrees) and cut between them, so the hand jumped 35 degrees at a time, about 580 deg/s at the fast
    # steps: it read as a twitch rather than a wave. These halve every step.
    ("arm-a", dict(wave=15)), ("arm-b", dict(wave=47)), ("arm-c", dict(wave=82)),
]
# (window in world units, size at 3x). The 2x sprite is the 3x one resampled,
# never an upscale: the largest use is the welcome figure at 96 CSS px wide.
FULL = ((-0.92, 1.17, -0.10, 2.66), (288, 380))
# A bust, so the acknowledging wave has an arm to wave with; head ~70% of the
# width so the face reads at 46 CSS px.
COMPACT = ((-0.86, 1.17, 0.46, 2.66), (144, 156))
HERO = ((-0.92, 1.17, -0.10, 2.66), (900, 1188))


# The scarf's tail is its own layer, drawn under the body: WIND phases of one
# flutter cycle, looped in CSS behind every pose. Under, not over, so a hand
# raised in front of it (the wave) covers it as it should.
WIND = 12


def job(args):
    kind, i = args
    if kind == "hero":
        return kind, i, (render(Pose(tail=False), HERO[0], HERO[1], 2),
                         render(Pose(wind=0.0, tail_only=True), HERO[0], HERO[1], 2))
    if kind.endswith("-tail"):
        win, size, ss = (COMPACT[0], COMPACT[1], 6) if kind.startswith("compact") else (FULL[0], FULL[1], 4)
        return kind, i, render(Pose(wind=i / WIND, tail_only=True), win, size, ss)
    spec = dict(FRAMES[i][1], tail=False)
    if kind == "compact":
        return kind, i, render(Pose(**spec), COMPACT[0], COMPACT[1], 6)
    return kind, i, render(Pose(**spec), FULL[0], FULL[1], 4)


def under(top, bottom):
    """Premultiplied 'over': `top` drawn over `bottom`."""
    return top + bottom * (1 - top[..., 3:4])


def to_rgba8(pre):
    a = pre[..., 3:4]
    rgb = np.where(a > 1e-6, pre[..., :3] / np.maximum(a, 1e-6), 0)
    return (np.clip(np.concatenate([rgb, a], -1), 0, 1) * 255 + 0.5).astype(np.uint8)


def resample(pre, w, h):
    """Premultiplied Lanczos, so edges darken or lighten with nothing behind
    them: no halo on either theme."""
    chans = [np.asarray(Image.fromarray(pre[..., k].astype(np.float32)).resize((w, h), Image.LANCZOS))
             for k in range(4)]
    out = np.clip(np.stack(chans, -1), 0, None)
    out[..., 3] = np.clip(out[..., 3], 0, 1)
    out[..., :3] = np.minimum(out[..., :3], out[..., 3:4])
    return out


def fade_bottom(pre, frac=0.16):
    """The bust is cut through the body; fade the last rows so the cut is soft."""
    h = pre.shape[0]
    n = int(h * frac)
    ramp = np.ones(h)
    ramp[h - n:] = np.linspace(1, 0, n) ** 1.4
    return pre * ramp[:, None, None]


def save_strip(frames, name, w, h):
    strip = np.concatenate([to_rgba8(f) for f in frames], 1)
    Image.fromarray(strip).save(os.path.join(OUT, name), quality=90, alpha_quality=100, method=6)
    return strip


def main():
    jobs = [("full", i) for i in range(len(FRAMES))] + [("compact", i) for i in range(len(FRAMES))]
    # The tail layer holds the body out but none of the face, so a change of
    # face alone can keep the committed tail strips: --no-tail.
    if "--no-tail" not in sys.argv:
        jobs += [("full-tail", i) for i in range(WIND)] + [("compact-tail", i) for i in range(WIND)]
    if "--no-hero" not in sys.argv:
        jobs.append(("hero", 0))
    os.makedirs(OUT, exist_ok=True)
    out = {}
    with Pool(6) as pool:
        for kind, i, img in pool.imap_unordered(job, jobs):
            out[(kind, i)] = img
            print("rendered", kind, i, flush=True)
    n = len(FRAMES)
    for kind, (_, (w3, h3)), count in (("full", FULL, n), ("compact", COMPACT, n),
                                       ("full-tail", FULL, WIND), ("compact-tail", COMPACT, WIND)):
        if (kind, 0) not in out:
            continue
        frames3 = [out[(kind, i)] for i in range(count)]
        if kind.startswith("compact"):
            frames3 = [fade_bottom(f) for f in frames3]
        save_strip(frames3, "scout-%s@3x.webp" % kind, w3, h3)
        w2, h2 = round(w3 * 2 / 3), round(h3 * 2 / 3)
        save_strip([resample(f, w2, h2) for f in frames3], "scout-%s@2x.webp" % kind, w2, h2)
    with open(os.path.join(OUT, "frames.json"), "w") as fh:
        json.dump({"frames": [name for name, _ in FRAMES], "wind": WIND,
                   "full": {"3x": list(FULL[1]), "2x": [round(FULL[1][0] * 2 / 3), round(FULL[1][1] * 2 / 3)]},
                   "compact": {"3x": list(COMPACT[1]), "2x": [round(COMPACT[1][0] * 2 / 3), round(COMPACT[1][1] * 2 / 3)]}},
                  fh, indent=1)
    if ("hero", 0) in out:
        body, tail = out[("hero", 0)]
        Image.fromarray(to_rgba8(under(body, tail))).save(os.path.join(OUT, "scout.png"), optimize=True)


if __name__ == "__main__":
    main()
