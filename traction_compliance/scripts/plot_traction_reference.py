"""Plot the proposed pure traction reference, using illustrative gains."""

from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import font_manager
from matplotlib.patches import Circle
import numpy as np


FORCE_THRESHOLD = 5.0
DAMPING = 20.0
YAW_GAIN = 0.5
REAR_ANGLE = np.deg2rad(170.0)
TEAL = "#155e75"
ORANGE = "#b45309"
GRAY = "#dce5eb"


def planar_reference(force, lower, upper):
    # Single-axis force slice with all other components zero, at steady state.
    effective = np.sign(force) * np.maximum(np.abs(force) - FORCE_THRESHOLD, 0.0)
    velocity = np.clip(effective / DAMPING, lower, upper)
    return np.where(np.abs(velocity) > 0.05, velocity, 0.0)


def yaw_reference(theta, force_norm):
    speed = np.clip(YAW_GAIN * theta, -1.5, 1.5)
    speed = np.where((force_norm >= FORCE_THRESHOLD) & (np.abs(speed) > 0.05), speed, 0.0)
    # Near the rear axis, the direction depends on previously selected turn direction.
    return np.ma.masked_where((force_norm >= FORCE_THRESHOLD) & (np.abs(theta) >= REAR_ANGLE), speed)


def plot_curve(ax, x, y, color):
    # Split lines at the speed deadband edges instead of interpolating across them.
    edges = np.flatnonzero(np.abs(np.diff(y.filled(np.nan))) > 0.04) + 1
    for indices in np.split(np.arange(x.size), edges):
        ax.plot(x[indices], y[indices], color=color, lw=1.8)


def main():
    chinese_font = Path("/System/Library/Fonts/Supplemental/Arial Unicode.ttf")
    fonts = ["DejaVu Sans"]
    if chinese_font.is_file():
        font_manager.fontManager.addfont(str(chinese_font))
        fonts.insert(0, font_manager.FontProperties(fname=str(chinese_font)).get_name())
    plt.rcParams.update({
        "font.family": fonts, "font.size": 10, "axes.titlesize": 11,
        "axes.spines.top": False, "axes.spines.right": False,
        "axes.unicode_minus": False, "pdf.fonttype": 42,
    })
    fig, axes = plt.subplots(2, 2, figsize=(7.2, 6.3), layout="constrained")
    force = np.linspace(-40, 40, 4001)
    for ax, panel, name, symbol, lower, upper in (
        (axes[0, 0], "a", "前向", "x", -0.5, 1.3),
        (axes[0, 1], "b", "侧向", "y", -0.5, 0.5),
    ):
        ax.axvspan(-FORCE_THRESHOLD, FORCE_THRESHOLD, color=GRAY, alpha=0.65)
        ax.plot(0, 0, marker="o", ms=3, color=TEAL)
        plot_curve(ax, force, np.ma.asarray(planar_reference(force, lower, upper)), TEAL)
        ax.set(
            title=f"({panel}) {name}稳态参考速度",
            xlabel=rf"外力分量 $F_{symbol}^b$ (N)",
            ylabel=rf"$v_{{{symbol},\mathrm{{ref}}}}$ (m/s)",
            xlim=(-40, 40), ylim=(lower - 0.12, upper + 0.12), yticks=[lower, 0, upper],
            xticks=[-40, -20, -5, 0, 5, 20, 40],
        )
        ax.grid(alpha=0.15)

    ax = axes[1, 0]
    grid = np.linspace(-40, 40, 501)
    fx, fy = np.meshgrid(grid, grid)
    yaw = yaw_reference(np.arctan2(fy, fx), np.hypot(fx, fy))
    colors = plt.get_cmap("RdBu_r").with_extremes(bad=GRAY)
    mesh = ax.pcolormesh(fx, fy, yaw, cmap=colors, vmin=-1.5, vmax=1.5, rasterized=True)
    ax.add_patch(Circle((0, 0), FORCE_THRESHOLD, fill=False, color="#596c7a", ls="--"))
    ax.set(
        title="(c) 水平力与偏航参考", xlabel=r"前向外力 $F_x^b$ (N)",
        ylabel=r"侧向外力 $F_y^b$ (N)", xlim=(-40, 40), ylim=(-40, 40),
        xticks=[-40, -20, 0, 20, 40], yticks=[-40, -20, 0, 20, 40], aspect="equal",
    )
    bar = fig.colorbar(mesh, ax=ax, fraction=0.05, pad=0.04, shrink=0.9, ticks=[-1.5, 0, 1.5])
    bar.ax.set_title("rad/s", fontsize=9, pad=7)

    ax = axes[1, 1]
    theta = np.linspace(-np.pi, np.pi, 5001)
    ax.axvspan(-np.pi, -REAR_ANGLE, color=GRAY)
    ax.axvspan(REAR_ANGLE, np.pi, color=GRAY)
    plot_curve(ax, theta, yaw_reference(theta, 30.0), ORANGE)
    ax.set(
        title="(d) 偏航参考速度 (30 N)", xlabel=r"外力方向角 $\theta$ (rad)",
        ylabel=r"$\omega_{z,\mathrm{ref}}$ (rad/s)", xlim=(-np.pi, np.pi), ylim=(-1.65, 1.65),
        xticks=[-np.pi, -np.pi / 2, 0, np.pi / 2, np.pi],
        xticklabels=[r"$-\pi$", r"$-\pi/2$", "0", r"$\pi/2$", r"$\pi$"],
        yticks=[-1.5, -0.75, 0, 0.75, 1.5],
    )
    ax.grid(alpha=0.15)
    destination = Path(__file__).resolve().parents[1] / "figures/traction_reference_map.pdf"
    fig.savefig(destination, dpi=240, bbox_inches="tight", pad_inches=0.06)
    plt.close(fig)


if __name__ == "__main__":
    main()
