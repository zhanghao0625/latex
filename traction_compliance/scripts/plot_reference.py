"""Plot the repository's force mapping and an analytical dynamics example.

Run with the Python environment containing torch, numpy and matplotlib:
    python scripts/plot_reference.py --source-repo /path/to/cts-moe-him

The mapping is evaluated from the unchanged source functions, with parameters
returned by the actual H6 teacher-aligned baseline recipe. No policy rollout
or measured robot velocity is used.
"""
from __future__ import annotations

import argparse
import ast
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
from types import SimpleNamespace

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import font_manager
from matplotlib.patches import Circle
import numpy as np
import torch

ROOT = Path(__file__).resolve().parents[1]
INK = "#16324F"
TEAL = "#155e75"
ORANGE = "#b45309"


def load_source(repo: Path):
    """Load just the tensor module and isolated, unchanged source AST bodies."""
    directory = repo / "source/cerebrix/cerebrix/rl/traction"
    tensor_path = directory / "tensors.py"
    spec = importlib.util.spec_from_file_location("traction_plot_source_tensors", tensor_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    parameters = json.loads((directory / "reference/source_recipe_parameters.json").read_text())
    scales = json.loads((directory / "reference/reward_scales.json").read_text())
    recipe_path = directory / "teacher_aligned.py"
    tree = ast.parse(recipe_path.read_text())
    names = {"TEACHER_RECIPE_ID", "FORWARD_TARGET"}
    selected = [
        node for node in tree.body
        if (isinstance(node, ast.Assign)
            and any(isinstance(target, ast.Name) and target.id in names for target in node.targets))
        or (isinstance(node, ast.FunctionDef) and node.name == "training_recipe")
    ]
    namespace = {"SOURCE_PARAMETERS": parameters, "SOURCE_REWARD_SCALES": scales}
    exec(compile(ast.Module(body=selected, type_ignores=[]), str(recipe_path), "exec"), namespace)
    recipe = namespace["training_recipe"]()
    reference_path = directory / "reference/reward_methods.py"
    tree = ast.parse(reference_path.read_text())
    owner = next(node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == "SourceRewardMethods")
    method = next(node for node in owner.body if isinstance(node, ast.FunctionDef) and node.name == "_get_force_to_vel")
    namespace = {"torch": torch}
    exec(compile(ast.Module(body=[method], type_ignores=[]), str(reference_path), "exec"), namespace)
    try:
        revision = subprocess.check_output(["git", "-C", str(repo), "rev-parse", "HEAD"], text=True).strip()
    except subprocess.CalledProcessError:
        revision = "unknown"
    metadata = {
        "source_repository": str(repo), "source_revision": revision,
        "recipe": recipe,
        "source_files_sha256": {
            str(path.relative_to(repo)): hashlib.sha256(path.read_bytes()).hexdigest()
            for path in (tensor_path, recipe_path, reference_path, directory / "reference/source_recipe_parameters.json")
        },
    }
    return module.source_force_to_velocity, namespace["_get_force_to_vel"], parameters, recipe, metadata


def tensor_kwargs(commands):
    return dict(
        alpha=commands["force_cmd_alpha"], beta=commands["force_cmd_beta"],
        max_x=commands["force_cmd_max_vel_x"], min_x=commands["force_cmd_min_vel_x"],
        max_y=commands["force_cmd_max_vel_y"], max_yaw=commands["force_cmd_max_vel_yaw"],
        yaw_alpha=commands["force_cmd_yaw_alpha"], yaw_beta=commands["force_cmd_yaw_beta"],
    )


def formula(force, params):
    """Independent evaluation of the manuscript's equations for comparison."""
    result = np.zeros_like(force)
    for axis, lower, upper in ((0, params["min_x"], params["max_x"]), (1, -params["max_y"], params["max_y"])):
        component = force[:, axis]
        mask = np.abs(component) > params["alpha"]
        result[mask, axis] = np.clip(
            (component[mask] + params["alpha"] * np.sign(component[mask])) / params["beta"], lower, upper
        )
    theta = np.arctan2(force[:, 1], force[:, 0])
    mask = (np.linalg.norm(force[:, :2], axis=1) > params["alpha"]) & (np.abs(theta) > params["yaw_alpha"])
    result[mask, 2] = np.clip(
        (theta[mask] + params["yaw_alpha"] * np.sign(theta[mask])) / params["yaw_beta"],
        -params["max_yaw"], params["max_yaw"],
    )
    return result


def configure_style():
    chinese_font = Path("/System/Library/Fonts/Supplemental/Arial Unicode.ttf")
    fonts = ["DejaVu Sans"]
    if chinese_font.is_file():
        font_manager.fontManager.addfont(str(chinese_font))
        fonts.insert(0, font_manager.FontProperties(fname=str(chinese_font)).get_name())
    plt.rcParams.update({
        "font.family": fonts, "font.size": 9, "axes.titlesize": 10,
        "axes.labelsize": 10, "axes.spines.top": False, "axes.spines.right": False,
        "axes.unicode_minus": False, "pdf.fonttype": 42, "savefig.facecolor": "white",
        "text.color": "#222222", "axes.labelcolor": "#222222",
        "axes.titlepad": 10, "axes.labelpad": 5,
    })


def disconnected_line(ax, x, y, **kwargs):
    # Do not draw a fictitious sloping segment across a jump discontinuity.
    jumps = np.flatnonzero(np.abs(np.diff(y)) > 0.1) + 1
    for part in np.split(np.arange(len(x)), jumps):
        if len(part):
            ax.plot(x[part], y[part], **kwargs)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-repo", type=Path, default=ROOT.parent.parent / "cts-moe-him")
    parser.add_argument("--map-only", action="store_true", help="Keep the existing dynamics illustration unchanged")
    args = parser.parse_args()
    source, reference, original, recipe, metadata = load_source(args.source_repo.resolve())
    commands = recipe["force_commands"]
    params = tensor_kwargs(commands)

    def evaluate(force, *, source_params=params):
        force = np.asarray(force, dtype=np.float64)
        with torch.inference_mode():
            return source(torch.from_numpy(force), **source_params).numpy()

    # Check both source implementations, equations, threshold equality, and Fz independence.
    rng = np.random.default_rng(20261114)
    random_force = rng.uniform([-50, -50, -10], [50, 50, 10], size=(10000, 3))
    edge = np.array([-50, -18, -17.500001, -17.5, -10, 0, 10, 17.5, 17.500001, 18, 50.0])
    probes = np.concatenate([
        np.column_stack([edge, np.zeros_like(edge), np.zeros_like(edge)]),
        np.column_stack([np.zeros_like(edge), edge, np.zeros_like(edge)]),
    ])
    all_force = np.concatenate([random_force, probes])
    output = evaluate(all_force)
    formula_output = formula(all_force, params)
    np.testing.assert_allclose(output, formula_output, rtol=0, atol=1e-12)
    for label, config in (("h6_baseline", commands), ("original_recipe", original["commands"])):
        state = SimpleNamespace(
            cfg=SimpleNamespace(domain_rand=SimpleNamespace(disturbance_coord="LOCAL_SPACE")),
            disturbance=torch.tensor(all_force[:, None, :], dtype=torch.float64),
            force_cmd=torch.zeros(len(all_force), 3, dtype=torch.float64),
        )
        reference(state, **{key.removeprefix("force_cmd_"): value for key, value in config.items() if key.startswith("force_cmd_")})
        np.testing.assert_allclose(evaluate(all_force, source_params=tensor_kwargs(config)), state.force_cmd.numpy(), rtol=0, atol=0)
        metadata[f"{label}_source_implementations_match"] = True
    at_threshold = evaluate([[params["alpha"], 0, 0], [-params["alpha"], 0, 0], [0, params["alpha"], 0]])
    np.testing.assert_array_equal(at_threshold, np.zeros((3, 3)))
    without_fz = all_force.copy()
    without_fz[:, 2] = 0
    np.testing.assert_array_equal(output, evaluate(without_fz))
    metadata.update(
        samples_compared=len(all_force), max_equation_absolute_error=float(np.max(np.abs(output - formula_output))),
        threshold_equality_returns_zero=True, force_z_does_not_change_reference=True,
        example_force_N=probes.tolist(), example_reference=output[-len(probes):].tolist(),
        quantity="reference velocity correction from sampled force labels; not measured policy output",
    )
    validation = ROOT / "tmp/reference_map_validation.json"
    validation.parent.mkdir(exist_ok=True)
    validation.write_text(json.dumps(metadata, indent=2, ensure_ascii=False) + "\n")

    configure_style()
    fig, axes = plt.subplots(2, 2, figsize=(7.2, 6.6))
    fig.subplots_adjust(left=.105, right=.965, bottom=.085, top=.945, wspace=.38, hspace=.40)
    force = np.linspace(-50, 50, 4001)
    for axis, name, symbol, lower, upper in ((0, "前向", "x", params["min_x"], params["max_x"]),
                                            (1, "侧向", "y", -params["max_y"], params["max_y"])):
        ax = axes[0, axis]
        inputs = np.zeros((len(force), 3))
        inputs[:, axis] = force
        values = evaluate(inputs)[:, axis]
        disconnected_line(ax, force, values, color=TEAL, lw=1.8)
        ax.axvspan(-params["alpha"], params["alpha"], color="#dce5eb", alpha=.55, zorder=-2)
        for threshold in (-params["alpha"], params["alpha"]):
            ax.axvline(threshold, color="#7a8996", ls="--", lw=.9)
        ax.scatter([-params["alpha"], params["alpha"]], [0, 0], color=TEAL, s=23, zorder=5)
        ax.scatter([-params["alpha"], params["alpha"]], [lower, upper], facecolors="white", edgecolors=TEAL, s=27, linewidths=1.2, zorder=5)
        ax.set(title=f"({'a' if axis == 0 else 'b'}) {name}参考速度修正", xlabel=rf"外力分量 $F_{symbol}$ (N)",
               ylabel=rf"$\delta_{{{symbol},\mathrm{{ref}}}}$ (m/s)", xlim=(-50, 50),
               ylim=(lower-.18, upper+.20), xticks=[-50, -params["alpha"], 0, params["alpha"], 50],
               xticklabels=["-50", f"{-params['alpha']:g}", "0", f"{params['alpha']:g}", "50"],
               yticks=[lower, 0, upper])
        ax.grid(alpha=.15)

    ax = axes[1, 0]
    grid = np.linspace(-50, 50, 401)
    fx, fy = np.meshgrid(grid, grid)
    inputs = np.column_stack([fx.ravel(), fy.ravel(), np.zeros(fx.size)])
    yaw = evaluate(inputs)[:, 2].reshape(fx.shape)
    mesh = ax.pcolormesh(fx, fy, yaw, shading="nearest", cmap="RdBu_r", vmin=-params["max_yaw"], vmax=params["max_yaw"], rasterized=True)
    ax.add_patch(Circle((0, 0), params["alpha"], fill=False, color="#596c7a", ls="--", lw=1.1))
    for sign in (-1, 1):
        theta = sign * params["yaw_alpha"]
        ax.plot([0, 50], [0, 50*np.tan(theta)], color="#596c7a", ls="--", lw=1)
    ax.set(title="(c) 偏航参考速度修正", xlabel=r"前向外力 $F_x$ (N)", ylabel=r"侧向外力 $F_y$ (N)",
           xlim=(-50, 50), ylim=(-50, 50), xticks=[-50, 0, 50], yticks=[-50, 0, 50])
    ax.set_aspect("equal", adjustable="box")
    bar = fig.colorbar(mesh, ax=ax, fraction=.045, pad=.035, ticks=[-.8, 0, .8])
    bar.ax.set_title("rad/s", fontsize=9, pad=7)

    ax = axes[1, 1]
    theta = np.linspace(-np.pi, np.pi, 5001)
    magnitude = 30.0
    yaw = evaluate(np.column_stack([magnitude*np.cos(theta), magnitude*np.sin(theta), np.zeros_like(theta)]))[:, 2]
    disconnected_line(ax, theta, yaw, color=ORANGE, lw=1.8)
    ax.axvspan(-params["yaw_alpha"], params["yaw_alpha"], color="#dce5eb", alpha=.55, zorder=-2)
    threshold = params["yaw_alpha"]
    onset = min(2*threshold/params["yaw_beta"], params["max_yaw"])
    ax.scatter([-threshold, threshold], [0, 0], color=ORANGE, s=23, zorder=5)
    ax.scatter([-threshold, threshold], [-onset, onset], facecolors="white", edgecolors=ORANGE, s=27, linewidths=1.2, zorder=5)
    for sign in (-1, 1):
        ax.axvline(sign*threshold, color="#7a8996", ls="--", lw=.9)
    ax.set(title="(d) 偏航参考速度修正（30 N）", xlabel=r"外力方向角 $\theta$ (rad)",
           ylabel=r"$\delta_{\omega,\mathrm{ref}}$ (rad/s)", xlim=(-np.pi, np.pi), ylim=(-1.0, 1.0),
           xticks=[-np.pi, -threshold, 0, threshold, np.pi],
           xticklabels=[r"$-\pi$", f"{-threshold:g}", "0", f"{threshold:g}", r"$\pi$"],
           yticks=[-.8, -.6, 0, .6, .8])
    ax.grid(alpha=.15)
    destination = ROOT / "figures/reference_map"
    fig.savefig(destination.with_suffix(".pdf"), bbox_inches="tight", pad_inches=.06)
    fig.savefig(destination.with_suffix(".png"), dpi=300, bbox_inches="tight", pad_inches=.06)
    plt.close(fig)

    if not args.map_only:
        dt = .02
        t = np.arange(0, 6+dt/2, dt)
        force_t = np.where((t >= 1) & (t < 3), 20., 0.)
        reference_t = np.zeros_like(t)
        mass, damping = 10., 20.
        decay = np.exp(-damping*dt/mass)
        for k in range(len(t)-1):
            reference_t[k+1] = decay*reference_t[k] + (1-decay)*force_t[k]/damping
        current = evaluate(np.column_stack([force_t, np.zeros_like(t), np.zeros_like(t)]))[:, 0]
        fig, ax = plt.subplots(figsize=(10, 3), layout="constrained")
        ax.step(t, current, where="post", lw=2, color=ORANGE, label="当前代数参考速度修正")
        ax.plot(t, reference_t, lw=2, color=TEAL, label="质量--阻尼参考速度修正")
        ax.set(xlabel="时间 (s)", ylabel="参考速度修正 (m/s)", xlim=(0, 6))
        ax.legend(frameon=False, loc="upper right")
        ax.grid(alpha=.15)
        fig.savefig(ROOT / "figures/reference_dynamics.pdf")
        plt.close(fig)
    print(json.dumps({"samples_compared": len(all_force), "max_equation_absolute_error": metadata["max_equation_absolute_error"],
                      "source_implementations_match": True, "figure": str(destination.with_suffix('.png'))}, ensure_ascii=False))


if __name__ == "__main__":
    main()
