"""Draw sagittal traction geometry using Vita01evt URDF joints and STL outlines."""

import argparse
import math
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.font_manager import FontProperties
from matplotlib.patches import Arc, Circle, FancyArrowPatch, Polygon


INK = "#172d44"
SECONDARY = "#465b70"
TEAL = "#267985"
ORANGE = "#b84a13"
BLUE = "#245fa4"
PURPLE = "#783d8b"
TERRAIN = "#e5edf2"
LEG_DISTANCE = 0.46
BASE_HEIGHT = 0.32
PERSON_HEIGHT = 1.70
HAND_HEIGHT = 0.90
HAND_TO_STANCE = 0.28
ROPE_LENGTH = 2.00
FIRST_RISER_X = 0.16
STAIR_RISE = 0.15
STAIR_RUN = 0.30
SLOPE = math.radians(15)


def rotation(angle):
    c, s = math.cos(angle), math.sin(angle)
    return np.array([[c, -s], [s, c]])


def outline(vertices):
    """Use the convex outline of each projected visual mesh."""
    points = sorted(set(map(tuple, vertices.round(decimals=5))))

    def chain(sequence):
        side = []
        for x, z in sequence:
            while len(side) > 1:
                (ax, az), (bx, bz) = side[-2:]
                if (bx - ax) * (z - az) - (bz - az) * (x - ax) > 0:
                    break
                side.pop()
            side.append((x, z))
        return side

    return np.asarray(chain(points)[:-1] + chain(reversed(points))[:-1])


class VitaSideView:
    def __init__(self, urdf):
        self.model = ET.parse(urdf).getroot()
        self.joints = {}
        self.bounds = {}
        self.profiles = {}
        links = ["base", "head_yaw", "head_pitch"]
        links += [f"{leg}_{part}" for leg in ("FR", "RR") for part in ("hip", "thigh", "calf", "foot")]
        for link in links:
            visual = self.model.find(f"link[@name='{link}']/visual")
            origin = visual.find("origin")
            origin_xz = self.xz(origin.get("xyz"))
            assert np.allclose(np.fromstring(origin.get("rpy"), sep=" "), 0)
            mesh = visual.find("geometry/mesh")
            record_dtype = np.dtype([("normal", "<f4", 3), ("vertices", "<f4", (3, 3)), ("attribute", "<u2")])
            triangles = np.fromfile(urdf.parent / mesh.get("filename"), dtype=record_dtype, offset=84)
            scale = np.fromstring(mesh.get("scale", "1 1 1"), sep=" ")
            vertices = triangles["vertices"].reshape(-1, 3) * scale
            self.profiles[link] = outline(vertices[:, [0, 2]] + origin_xz)
            if link != "base":
                joint = self.model.find(f"joint[@name='{link}_joint']")
                origin = joint.find("origin")
                assert np.allclose(np.fromstring(origin.get("rpy"), sep=" "), 0)
                self.joints[link] = self.xz(origin.get("xyz"))
                limits = joint.find("limit")
                if joint.get("type") == "revolute":
                    self.bounds[link] = (float(limits.get("lower")), float(limits.get("upper")))
        foot = self.model.find("link[@name='FR_foot']/collision/geometry/sphere")
        self.foot_radius = float(foot.get("radius"))
        self.pull_offset = np.array([self.joints["head_yaw"][0], 0.0])

    @staticmethod
    def xz(text):
        return np.fromstring(text, sep=" ")[[0, 2]]

    def draw(self, ax, base, pitch, feet):
        def draw_link(link, position, angle, color, layer):
            vertices = self.profiles[link] @ rotation(angle).T + position
            ax.add_patch(Polygon(vertices, closed=True, facecolor=color, edgecolor="#233b52",
                                 lw=0.85, joinstyle="round", zorder=layer))

        body_rotation = rotation(pitch)
        for leg, foot in zip(("RR", "FR"), feet):
            hip = base + body_rotation @ self.joints[f"{leg}_hip"]
            thigh = hip + body_rotation @ self.joints[f"{leg}_thigh"]
            upper = -self.joints[f"{leg}_calf"][1]
            lower = -self.joints[f"{leg}_foot"][1]
            delta = foot - thigh
            reach = np.linalg.norm(delta)
            bend = math.acos((reach**2 - upper**2 - lower**2) / (2 * upper * lower))
            angle = math.atan2(delta[0], -delta[1]) - math.atan2(lower * math.sin(bend), upper + lower * math.cos(bend))
            knee = thigh + rotation(angle) @ self.joints[f"{leg}_calf"]
            assert np.allclose(knee + rotation(angle + bend) @ self.joints[f"{leg}_foot"], foot)
            for link, urdf_angle in ((f"{leg}_thigh", pitch - angle), (f"{leg}_calf", -bend)):
                lo, hi = self.bounds[link]
                assert lo <= urdf_angle <= hi, (link, urdf_angle)
            draw_link(f"{leg}_foot", foot, angle + bend, "#263b51", 4)
            draw_link(f"{leg}_calf", knee, angle + bend, "#a9bac9", 5)
            draw_link(f"{leg}_thigh", thigh, angle, "#758ca2", 6)
            draw_link(f"{leg}_hip", hip, pitch, "#637c93", 7)
        draw_link("base", base, pitch, "#758da4", 8)
        head_yaw = base + body_rotation @ self.joints["head_yaw"]
        draw_link("head_yaw", head_yaw, pitch, "#8da5b8", 9)
        draw_link("head_pitch", head_yaw + body_rotation @ self.joints["head_pitch"], pitch, "#c0cdd8", 10)
        return base + body_rotation @ self.pull_offset


@dataclass(frozen=True)
class Scene:
    key: str
    title: str
    detail: str

    def height(self, x):
        if self.key == "stairs":
            return STAIR_RISE * np.maximum(0, np.floor((x - FIRST_RISER_X) / STAIR_RUN) + 1)
        if self.key == "slope":
            return np.tan(SLOPE) * x
        return np.zeros_like(x)

    def surface(self, x0, x1):
        if self.key == "stairs":
            edges = np.arange(FIRST_RISER_X, x1, STAIR_RUN)
            xs = np.array([x0, *np.repeat(edges, 2), x1])
            zs = STAIR_RISE * np.repeat(np.arange(len(edges) + 1), 2)
            return xs, zs
        xs = np.array([x0, x1])
        return xs, self.height(xs)


def hand_position(scene, pull):
    """Intersect the 2 m rope circle with the hand-height locus."""
    if scene.key == "stairs":
        max_step = math.floor((pull[1] + ROPE_LENGTH - HAND_HEIGHT) / STAIR_RISE)
        hands = []
        for step in range(max_step + 1):
            z = step * STAIR_RISE + HAND_HEIGHT
            dx = math.sqrt(max(0.0, ROPE_LENGTH**2 - (z - pull[1])**2))
            x = pull[0] + dx
            if math.isclose(z, float(scene.height(x + HAND_TO_STANCE)) + HAND_HEIGHT):
                hands.append(np.array([x, z]))
        if len(hands) != 1:
            raise ValueError("The chosen stair pose needs one feasible taut-rope position.")
        return hands[0]

    grade = math.tan(SLOPE) if scene.key == "slope" else 0.0
    dz_at_pull_x = HAND_HEIGHT + grade * (pull[0] + HAND_TO_STANCE) - pull[1]
    dx = (math.sqrt((1 + grade**2) * ROPE_LENGTH**2 - dz_at_pull_x**2) - grade * dz_at_pull_x) / (1 + grade**2)
    return np.array([pull[0] + dx, pull[1] + dz_at_pull_x + grade * dx])


def draw_person(ax, scene, hand):
    x = hand[0] + HAND_TO_STANCE
    ground = float(scene.height(x))
    shoulder = (x + 0.02, ground + 1.37)
    hip = (x + 0.04, ground + 0.86)
    # Keep both shoes on the selected 30 cm tread in the stair example.
    foot_offsets = (-0.11, 0.008) if scene.key == "stairs" else (-0.08, 0.10)
    ankles = [(x + dx, float(scene.height(x + dx)) + 0.035) for dx in foot_offsets]
    if scene.key == "stairs":
        for ankle_x, _ in ankles:
            assert math.isclose(float(scene.height(ankle_x - 0.043)), ground)
            assert math.isclose(float(scene.height(ankle_x + 0.027)), ground)
    for ankle, knee, color in ((ankles[1], (x + 0.13, ground + 0.42), "#a1b1bf"),
                               (ankles[0], (x - 0.06, ground + 0.46), "#3b5269")):
        ax.plot(*zip(hip, knee, ankle), lw=7, color=color, solid_capstyle="round", zorder=3)
        ax.plot([ankle[0] - 0.043, ankle[0] + 0.027], [ankle[1] - 0.013] * 2,
                lw=4.0, color=color, solid_capstyle="round", zorder=4)
    ax.plot(*zip(hip, shoulder), lw=12, color="#3b5269", solid_capstyle="round", zorder=4)
    head_radius = 0.081
    ax.add_patch(Circle((x + 0.027, ground + PERSON_HEIGHT - head_radius), head_radius,
                        fc="#3b5269", ec="none", zorder=4))
    elbow = (x - 0.14, ground + 1.10)
    ax.plot(*zip(shoulder, elbow, hand), lw=5.5, color="#3b5269", solid_capstyle="round", zorder=5)


def draw_dimensions(ax, scene, font):
    if scene.key == "stairs":
        dim = dict(arrowstyle="<->", lw=0.9, color=TEAL, shrinkA=0, shrinkB=0)
        x = FIRST_RISER_X + STAIR_RUN
        ax.annotate("", (x + STAIR_RUN, 0.205), (x, 0.205), arrowprops=dim)
        ax.text(x + STAIR_RUN / 2, 0.174, "30 cm", ha="center", va="top", color=TEAL, fontsize=11)
        x = FIRST_RISER_X + 4 * STAIR_RUN + 0.04
        ax.annotate("", (x, 0.75), (x, 0.60), arrowprops=dim)
        ax.text(x + 0.06, 0.67, "15 cm", va="center", color=TEAL, fontsize=11)
    elif scene.key == "slope":
        x = 1.20
        z = float(scene.height(x))
        ax.plot([x, x + 0.45], [z, z], "--", color=TEAL, lw=1.0)
        ax.add_patch(Arc((x, z), .65, .65, theta1=0, theta2=15, ec=TEAL, lw=1.1))
        ax.text(x + 0.36, z + .025, "15°", color=TEAL, va="bottom", fontsize=11, fontproperties=font)


def draw_angle_guides(ax, pull, alpha, beta):
    def ray(angle_deg, length):
        angle = math.radians(angle_deg)
        return pull + length * np.array([math.cos(angle), math.sin(angle)])

    def arc(start, end, radius, label, color):
        ax.add_patch(Arc(pull, 2 * radius, 2 * radius, theta1=start, theta2=end,
                         ec=color, lw=1.35, zorder=13))
        ax.text(*ray((start + end) / 2, radius + 0.07), label,
                color=color, ha="center", va="center", fontsize=14, zorder=14)

    body_tip = ray(beta, 0.87)
    ax.plot(*zip(pull, ray(0, 1.12)), "--", color=TEAL, lw=1.25, zorder=11)
    ax.add_patch(FancyArrowPatch(pull, body_tip, arrowstyle="-|>", mutation_scale=13,
                                 shrinkA=0, shrinkB=0, color=BLUE, lw=1.65, zorder=12))
    ax.text(body_tip[0] + 0.025, body_tip[1] + (0.037 if beta else -0.055), r"$+x_b$",
            fontsize=13, color=BLUE, ha="left", va="bottom" if beta else "top", zorder=14)
    if beta == 0:
        arc(0, alpha, 0.61, r"$\alpha=\gamma$", ORANGE)
    else:
        arc(0, alpha, 0.65, r"$\alpha$", ORANGE)
        arc(0, beta, 0.28, r"$\beta$", BLUE)
        arc(beta, alpha, 0.42, r"$\gamma$", PURPLE)


def draw_scene(ax, scene, robot, font):
    x0, x1 = -0.52, 2.65
    surface_x, surface_z = scene.surface(x0, x1)
    ax.fill_between(surface_x, -0.18, surface_z, color=TERRAIN, zorder=0)
    ax.plot(surface_x, surface_z, lw=1.7, color="#6e8295", zorder=1)
    draw_dimensions(ax, scene, font)

    feet_x = LEG_DISTANCE * np.array([-0.5, 0.5])
    feet_ground = scene.height(feet_x)
    pitch = math.atan2(float(np.diff(feet_ground)[0]), LEG_DISTANCE)
    radius_z = robot.foot_radius / math.cos(SLOPE) if scene.key == "slope" else robot.foot_radius
    feet = np.column_stack((feet_x, feet_ground + radius_z))
    base = np.array([0, np.mean(feet_ground) + BASE_HEIGHT])
    pull = robot.draw(ax, base, pitch, feet)
    hand = hand_position(scene, pull)
    draw_person(ax, scene, hand)

    delta = hand - pull
    assert math.isclose(np.linalg.norm(delta), ROPE_LENGTH)
    alpha = math.degrees(math.atan2(delta[1], delta[0]))
    beta = math.degrees(pitch)
    gamma = alpha - beta
    ax.plot(*zip(pull, hand), color=ORANGE, lw=1.65, zorder=11)
    arrow_tip = pull + 0.51 * delta / np.linalg.norm(delta)
    ax.add_patch(FancyArrowPatch(pull, arrow_tip, arrowstyle="-|>", mutation_scale=17,
                                 shrinkA=0, shrinkB=0, color=ORANGE, lw=2.3, zorder=12))
    draw_angle_guides(ax, pull, alpha, beta)
    ax.scatter([pull[0], hand[0]], [pull[1], hand[1]], s=[20, 18], facecolor=ORANGE,
               edgecolor="white", linewidth=0.7, zorder=15)
    ax.text(arrow_tip[0] - 0.028, arrow_tip[1] + 0.07, r"$\mathbf{F}$",
            color=ORANGE, ha="right", va="bottom", fontsize=14, zorder=13)
    ax.text(pull[0] + 0.032, pull[1] - 0.049, r"$P$", color=ORANGE, fontsize=12, va="top", zorder=13)
    ax.text(hand[0] - 0.04, hand[1] + 0.037, r"$H$", color=ORANGE, fontsize=12, ha="right")
    ax.text(x0 + 0.025, 2.67, scene.title, fontsize=20, fontproperties=font, color=INK, va="top")
    ax.text(x0 + 0.025, 2.36, scene.detail, fontsize=11.5, fontproperties=font, color=SECONDARY, va="top")
    metrics = (
        ("水平仰角", "alpha", alpha, ORANGE),
        ("机身俯仰", "beta", beta, BLUE),
        ("相对机身", "gamma", gamma, PURPLE),
    )
    for row, (label, symbol, value, color) in enumerate(metrics):
        y = 2.10 - 0.25 * row
        ax.text(x0 + 0.035, y, label, fontsize=13.4, fontproperties=font, color=INK, va="center")
        ax.text(x0 + 0.91, y, rf"$\{symbol}={value:.1f}^\circ$", fontsize=17, color=color, va="center")
    ax.text(x0 + 0.035, 1.43, rf"$\Delta x={delta[0]:.2f}\,\mathrm{{m}},\quad\Delta z={delta[1]:.2f}\,\mathrm{{m}}$",
            fontsize=11.5, color=SECONDARY, va="top")
    ax.set(xlim=(x0, x1), ylim=(-0.17, 2.83), aspect="equal")
    ax.axis("off")
    print(f"{scene.key}: alpha={alpha:.4f}°, beta={beta:.4f}°, gamma={gamma:.4f}°")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("urdf", type=Path, help="vita01evt_backboard.urdf with relative meshes available")
    parser.add_argument("--font", type=Path, required=True, help="Chinese font file")
    parser.add_argument("--output", type=Path, required=True, help="Output path without a suffix")
    args = parser.parse_args()
    font = FontProperties(fname=args.font)
    matplotlib.rcParams["pdf.fonttype"] = 42
    scenes = (
        Scene("flat", "A  平地牵引", "地面坡度 0°"),
        Scene("stairs", "B  上楼梯牵引", "级高 15 cm  ·  踏面进深 30 cm"),
        Scene("slope", "C  上斜坡牵引", "坡面倾角 15°"),
    )
    robot = VitaSideView(args.urdf)
    fig = plt.figure(figsize=(13.4, 6.46), facecolor="white")
    fig.text(0.04, 0.952, "Vita01evt 三种地形的牵引力方向", fontproperties=font, fontsize=22, color=INK, va="top")
    fig.text(0.04, 0.893, "矢状面示意  ·  橙色为牵引力  ·  青色虚线为世界水平线  ·  蓝色箭头为机身前向轴", fontproperties=font,
             fontsize=12.5, color=SECONDARY, va="top")
    fig.text(0.825, 0.893, r"$\gamma=\alpha-\beta$", fontsize=15, color=PURPLE, va="top")
    for ix, scene in enumerate(scenes):
        ax = fig.add_axes([0.034 + ix * 0.314, 0.155, 0.303, 0.698])
        draw_scene(ax, scene, robot, font)
    fig.text(0.04, 0.099, "成人身高 1.70 m，持绳手 H 距脚下地面 0.90 m。拉直的绳长 2.00 m，机器人牵引点 P 位于机身原点前方 17.287 cm。",
             fontproperties=font, fontsize=11.5, color=SECONDARY)
    fig.text(0.04, 0.053, r"$\alpha=\operatorname{atan2}(z_H-z_P,\ x_H-x_P)$", fontsize=13, color=INK)
    fig.text(0.285, 0.053, "外形和腿部尺寸来自 Vita01evt URDF 与网格。示例前后足水平间距 0.46 m，机身原点高于两足地面均值 0.32 m。",
             fontproperties=font, fontsize=11.5, color=SECONDARY)
    fig.savefig(args.output.with_suffix(".pdf"), metadata={"Title": "Vita01evt traction geometry"})
    fig.savefig(args.output.with_suffix(".png"), dpi=185)


if __name__ == "__main__":
    main()
