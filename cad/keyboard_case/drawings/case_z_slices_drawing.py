#!/usr/bin/env python3
"""
Horizontal Z-slices of the CNC pykey40 case (thin-slab intersect).

Three panels on one A3 sheet:
  - bottom plate (Z through bottom height)
  - lower cavity (mount posts visible)
  - upper cavity

Annotates the Z height used for each cut.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path

from build123d import *

from helpers import (
    ensure_case_import_path,
    project_to_2d,
    svg_to_png,
    thin_slab_section,
)

ensure_case_import_path()

from case_pykey40 import (
    CASE_BOTTOM_HEIGHT,
    CASE_LOWER_CAVITY_HEIGHT,
    CASE_LOW_PROFILE_MX_UPPER_CAVITY_HEIGHT,
    derived_dims,
    make_cnc_pykey40_case,
    mount_hole_positions_case,
)

OUT_DIR = Path(__file__).resolve().parent
OUT_SVG = OUT_DIR / "cnc_pykey40_z_slices_a3.svg"
OUT_PNG = OUT_DIR / "cnc_pykey40_z_slices_a3.png"

SCALE = 0.42
SLAB_T = 0.05
MARGIN = 18.0


def main() -> None:
    d = derived_dims()
    ow, ol, oh = d["case_outer"]
    bottom_h = CASE_BOTTOM_HEIGHT
    lower_h = CASE_LOWER_CAVITY_HEIGHT
    upper_h = CASE_LOW_PROFILE_MX_UPPER_CAVITY_HEIGHT

    z_bottom = bottom_h / 2.0  # 1.0 — through bottom plate
    z_lower = bottom_h + lower_h / 2.0  # 4.0 — lower cavity + posts
    z_upper = bottom_h + lower_h + upper_h / 2.0  # 9.0 — upper cavity

    case = make_cnc_pykey40_case(
        cutout_usb_connector=True,
        cutout_feet_holes=False,
        cutout_bumpon_guides=False,
        chamfer_edges=False,
    )

    slices = [
        ("Bottom plate", z_bottom, f"Z={z_bottom:.1f} (through bottom h={bottom_h:.0f})"),
        ("Lower cavity", z_lower, f"Z={z_lower:.1f} (lower cavity + mount posts)"),
        ("Upper cavity", z_upper, f"Z={z_upper:.1f} (upper cavity)"),
    ]

    border = TechnicalDrawing(
        designed_by="rgoulter",
        design_date=date.today(),
        page_size=PageSize.A3,
        title="CNC pykey40 case",
        sub_title="horizontal Z-slices",
        drawing_number="KL-CNC-PY40-ZS",
        sheet_number=1,
        drawing_scale=1,
        nominal_text_size=4.0,
    )
    faces_by_area = sorted(border.faces(), key=lambda f: -f.area)
    frame_bb = faces_by_area[0].bounding_box()
    title_bb = faces_by_area[1].bounding_box()

    visible: list = []
    hidden: list = []
    labels: list = []

    # Layout: three panels stacked vertically, clear of title block
    usable_top = frame_bb.max.Y - MARGIN
    usable_bot = max(frame_bb.min.Y + MARGIN, title_bb.max.Y + 8.0)
    usable_left = frame_bb.min.X + MARGIN
    usable_right = frame_bb.max.X - MARGIN
    panel_h = (usable_top - usable_bot) / 3.0
    cx = (usable_left + usable_right) / 2.0

    for i, (name, z_cut, note) in enumerate(slices):
        sec = thin_slab_section(
            case,
            center=(ow / 2, ol / 2, z_cut),
            size=(ow + 20, ol + 20, SLAB_T),
        )
        # Center on cut Z so projection sits in XY
        centered = Pos(-ow / 2, -ol / 2, -z_cut) * sec
        draw = mirror(centered, about=Plane.YZ)

        # Probe bbox at origin to place panel
        vis0, hid0 = project_to_2d(draw, (0, 0, 200), (0, -1, 0), (0, 0), SCALE)
        bb0 = Curve(vis0).bounding_box()
        panel_top = usable_top - i * panel_h
        panel_bot = panel_top - panel_h
        panel_cy = (panel_top + panel_bot) / 2.0
        # Shift so section centre lands on panel centre
        origin = (cx - bb0.center().X, panel_cy - bb0.center().Y)
        vis, hid = project_to_2d(draw, (0, 0, 200), (0, -1, 0), origin, SCALE)
        visible.extend(vis)
        if hid:
            hidden.extend(hid)

        bb = Curve(vis).bounding_box()
        t1 = Text(f"{name} — {note}", 3.5)
        t1.position = Vector(bb.min.X, bb.max.Y + 6)
        labels.append(t1)

    legend = Text(
        "Top views of horizontal sections (USB top-left). "
        f"Outer {ow:.0f}×{ol:.0f}×{oh:.0f}. Thin-slab intersect ±{SLAB_T/2:.3f} mm.",
        2.8,
    )
    legend.position = Vector(usable_left, usable_bot + 4)
    labels.append(legend)

    holes = mount_hole_positions_case()
    n_posts = Text(f"Mount posts at Z={z_lower:.1f}: {len(holes)}× ⌀6 (pilots omitted in section flags)", 2.4)
    n_posts.position = Vector(usable_left, usable_bot - 4)
    labels.append(n_posts)

    exporter = ExportSVG(unit=Unit.MM)
    exporter.add_layer("Visible")
    exporter.add_layer(
        "Hidden", line_color=(0x63, 0x63, 0x63), line_type=LineType.ISO_DOT
    )
    exporter.add_layer("Annotations", fill_color=(0, 0, 0), line_color=(0, 0, 0))
    exporter.add_shape(visible, layer="Visible")
    if hidden:
        exporter.add_shape(hidden, layer="Hidden")
    exporter.add_shape(border.edges(), layer="Visible")
    glyph_faces = [f for f in border.faces() if f.area < 20]
    if glyph_faces:
        exporter.add_shape(glyph_faces, layer="Annotations")
    exporter.add_shape(labels, layer="Annotations")
    exporter.write(str(OUT_SVG))
    print(f"Wrote {OUT_SVG}")
    svg_to_png(OUT_SVG, OUT_PNG, dpi=120)


if __name__ == "__main__":
    main()
