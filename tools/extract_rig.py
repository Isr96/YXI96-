#!/usr/bin/env python3
"""Split the insect pixel-islands into sprites and a rig description."""

import json
from pathlib import Path

import numpy as np
from PIL import Image
from scipy import ndimage
from scipy.spatial.distance import cdist

ROOT = Path(__file__).resolve().parents[1]
SRC = Path(
    "/home/ubuntu/.cursor/projects/workspace/assets/265822cb-873c-449e-9dda-c0d894eaf6a0.png"
)
PARTS = ROOT / "parts"
PARTS.mkdir(exist_ok=True)

BODY_TAIL = [13, 14, 16, 17, 21, 23, 25]  # parent -> child toward tail
BODY_HEAD = [13, 15, 22, 19]
EXTRAS = [
    # id, parent, kind, open_sign (screen-up is negative y)
    (20, 19, "mandible", -1),
    (24, 20, "mandible", -1),
    (27, 19, "mandible", 1),
    (26, 27, "mandible", 1),
    (18, 22, "palp", -1),
    (29, 22, "palp", 1),
]
LEGS = [
    # body, pair (0 rear .. 3 front), chain proximal -> distal
    (16, 0, [11, 9]),
    (16, 0, [32, 36, 38]),
    (14, 1, [7, 5, 3, 1]),
    (14, 1, [33, 39, 41, 43]),
    (13, 2, [8, 6, 4, 2]),
    (13, 2, [31, 40, 42, 44]),
    (15, 3, [12, 10]),
    (15, 3, [30, 37, 35]),
]


def closest_points(a_pts, b_pts):
    # boundary subsets are small enough
    d = cdist(a_pts, b_pts)
    i, j = np.unravel_index(d.argmin(), d.shape)
    return a_pts[i], b_pts[j], float(d[i, j])


def main():
    im = Image.open(SRC).convert("RGBA")
    arr = np.array(im)
    mask = arr[:, :, 3] > 20
    labeled, n = ndimage.label(mask)
    objs = ndimage.find_objects(labeled)

    parts = {}
    boundaries = {}
    for i, sl in enumerate(objs, start=1):
        if sl is None:
            continue
        area = int((labeled[sl] == i).sum())
        if area < 30:
            continue
        y0, x0 = int(sl[0].start), int(sl[1].start)
        y1, x1 = int(sl[0].stop), int(sl[1].stop)
        sub = arr[y0:y1, x0:x1].copy()
        local = labeled[y0:y1, x0:x1] == i
        sub[:, :, 3] = np.where(local, sub[:, :, 3], 0)
        Image.fromarray(sub).save(PARTS / f"{i}.png")
        ys, xs = np.where(local)
        full = np.stack([xs + x0, ys + y0], axis=1)
        er = ndimage.binary_erosion(local)
        by, bx = np.where(local & ~er)
        if len(bx) < 8:
            boundary = full
        else:
            boundary = np.stack([bx + x0, by + y0], axis=1)
        # cap for cdist
        if len(boundary) > 2500:
            boundary = boundary[:: len(boundary) // 2500]
        boundaries[i] = boundary.astype(np.float64)
        parts[i] = {
            "src": f"parts/{i}.png",
            "crop": [x0, y0, x1 - x0, y1 - y0],
            "area": area,
        }

    def link(a, b):
        pa, pb, dist = closest_points(boundaries[a], boundaries[b])
        return {
            "onParent": [float(pa[0]), float(pa[1])],
            "onChild": [float(pb[0]), float(pb[1])],
            "gap": dist,
        }

    bones = []
    for chain in (BODY_TAIL, BODY_HEAD):
        for parent, child in zip(chain, chain[1:]):
            L = link(parent, child)
            L.update({"id": child, "parent": parent, "kind": "body"})
            bones.append(L)

    extras = []
    for cid, parent, kind, sign in EXTRAS:
        L = link(parent, cid)
        L.update({"id": cid, "parent": parent, "kind": kind, "openSign": sign})
        extras.append(L)

    legs = []
    for body, pair, chain in LEGS:
        L0 = link(body, chain[0])
        segs = []
        # first segment pivot is onChild of body link
        pivots = [np.array(L0["onChild"])]
        for a, b in zip(chain, chain[1:]):
            Lab = link(a, b)
            pivots.append(np.array(Lab["onChild"]))
            segs.append(Lab)
        # tip of last segment: farthest pixel from its pivot
        last = chain[-1]
        last_pivot = pivots[-1]
        sl = objs[last - 1]
        local = labeled[sl] == last
        ys, xs = np.where(local)
        pts = np.stack(
            [xs + sl[1].start, ys + sl[0].start], axis=1
        ).astype(np.float64)
        if len(pts) > 4000:
            pts = pts[:: len(pts) // 4000]
        d2 = ((pts - last_pivot) ** 2).sum(axis=1)
        tip = pts[int(d2.argmax())]
        # side from the tip relative to body axis y=510
        side = -1 if tip[1] < 510 else 1
        segments = []
        points = pivots + [tip]
        for idx, pid in enumerate(chain):
            a = points[idx]
            b = points[idx + 1]
            delta = b - a
            length = float(np.hypot(delta[0], delta[1]))
            angle = float(np.arctan2(delta[1], delta[0]))
            segments.append(
                {
                    "id": pid,
                    "pivot": [float(a[0]), float(a[1])],
                    "length": length,
                    "restAngle": angle,
                }
            )
        # angle limits, looser at the hip
        nseg = len(segments)
        limits = []
        for i in range(nseg):
            if i == 0:
                limits.append(1.15)
            elif i == nseg - 1:
                limits.append(0.85)
            else:
                limits.append(0.95)
        legs.append(
            {
                "body": body,
                "pair": pair,
                "side": side,
                "hipOnBody": L0["onParent"],
                "segments": segments,
                "limits": limits,
                "restFoot": [float(tip[0]), float(tip[1])],
            }
        )

    root_pivot = None
    # root pivot = centroid of part 13
    sl = objs[12]
    local = labeled[sl] == 13
    ys, xs = np.where(local)
    root_pivot = [float(xs.mean() + sl[1].start), float(ys.mean() + sl[0].start)]

    rig = {
        "srcWidth": 1536,
        "srcHeight": 1024,
        "root": 13,
        "rootPivot": root_pivot,
        "parts": {str(k): v for k, v in parts.items()},
        "bones": bones,
        "extras": extras,
        "legs": legs,
    }
    (ROOT / "rig.json").write_text(json.dumps(rig, indent=2))
    print("parts", len(parts), "bones", len(bones), "legs", len(legs))
    print("root", root_pivot)
    for leg in legs:
        ids = [s["id"] for s in leg["segments"]]
        print(
            f"  leg body {leg['body']} pair {leg['pair']} side {leg['side']} {ids} foot {leg['restFoot']}"
        )

    # Rebuild rest pose and diff against the source.
    rebuild = np.zeros_like(arr)
    # paste every sprite at its crop — this is the ground truth assembly
    for i, meta in parts.items():
        x, y, w, h = meta["crop"]
        sprite = np.array(Image.open(PARTS / f"{i}.png"))
        # alpha composite
        sa = sprite[:, :, 3:4].astype(np.float32) / 255.0
        da = rebuild[y : y + h, x : x + w, 3:4].astype(np.float32) / 255.0
        out_a = sa + da * (1 - sa)
        src_rgb = sprite[:, :, :3].astype(np.float32)
        dst_rgb = rebuild[y : y + h, x : x + w, :3].astype(np.float32)
        out_rgb = np.where(out_a > 1e-5, (src_rgb * sa + dst_rgb * da * (1 - sa)) / np.maximum(out_a, 1e-5), 0)
        rebuild[y : y + h, x : x + w, :3] = out_rgb
        rebuild[y : y + h, x : x + w, 3:4] = (out_a * 255).astype(np.uint8)

    # compare alpha coverage
    src_a = arr[:, :, 3] > 20
    reb_a = rebuild[:, :, 3] > 20
    print("coverage src", int(src_a.sum()), "rebuild", int(reb_a.sum()), "xor", int((src_a ^ reb_a).sum()))
    white = np.ones_like(rebuild[:, :, :3]) * 255
    a = rebuild[:, :, 3:4].astype(np.float32) / 255
    comp = (rebuild[:, :, :3] * a + white * (1 - a)).astype(np.uint8)
    Image.fromarray(comp).resize((768, 512), Image.Resampling.BILINEAR).save("/tmp/rest_assembly.png")


if __name__ == "__main__":
    main()
