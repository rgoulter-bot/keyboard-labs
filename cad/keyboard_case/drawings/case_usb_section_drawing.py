#!/usr/bin/env python3
"""
USB mount cross-sections for CNC pykey40 case.

1. YZ cut through USB mid-X — side view (pocket depth vs PCB/USB)
2. XZ cut through USB pocket Y — front-ish view (pocket width vs PCB/USB)

Stacked panels on A4; each cropped to the USB-pocket ROI.
Same case solid as manufacturing port; PCB + USB preview solids overlaid.
Orthographic: mirrored drawing solid; FRONT USB page-right.
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
    PCB_USB_CONNECTOR_MID_X,
    USB_CONNECTOR_CUTOUT_LENGTH,
    USB_CONNECTOR_HEIGHT,
    USB_CONNECTOR_HOLE_HEIGHT,
    USB_CONNECTOR_HOLE_WIDTH,
    derived_dims,
    make_cnc_pykey40_case,
)
from case_pykey40_constants import PCB_DIM

OUT_DIR = Path(__file__).resolve().parent
OUT_SVG = OUT_DIR / "cnc_pykey40_usb_sections_a4.svg"
OUT_PNG = OUT_DIR / "cnc_pykey40_usb_sections_a4.png"

PCB_THICKNESS = 1.6
PCB_CORNER_R = 2.25
USB_LIP_W = 11.0
SCALE = 3.6
SLAB_T = 0.05
MARGIN = 12.0
# ROI half-extents around USB pocket (mm, case coords)
ROI_Y_HALF = 22.0  # side view: depth into case from front
ROI_X_HALF = 28.0  # front view: width around USB mid-X
ROI_Z_PAD = 4.0


def make_pcb(z_bottom: float) -> Part:
    w, l = PCB_DIM
    with BuildPart() as bp:
        with BuildSketch():
            RectangleRounded(w, l, PCB_CORNER_R, align=(Align.MIN, Align.MIN))
            with Locations((PCB_USB_CONNECTOR_MID_X, 0)):
                Rectangle(USB_LIP_W, 4.0, align=(Align.CENTER, Align.CENTER))
        extrude(amount=PCB_THICKNESS)
    return Pos(0, 0, z_bottom) * bp.part


def make_usb_connector(z_pcb_bottom: float) -> Part:
    """Simplified USB box (OpenSCAD preview extents)."""
    ax = PCB_USB_CONNECTOR_MID_X
    ay = -3.0
    az = z_pcb_bottom - 2.0
    return Pos(ax, ay + 7.0 / 2, az) * Box(
        9.0, 7.0, 4.0, align=(Align.CENTER, Align.CENTER, Align.CENTER)
    )


def main() -> None:
    d = derived_dims()
    ow, ol, oh = d["case_outer"]
    pcb_xy = d["case_pcb_position"]
    z_pcb = CASE_BOTTOM_HEIGHT + CASE_LOWER_CAVITY_HEIGHT
    usb_case_x = pcb_xy[0] + PCB_USB_CONNECTOR_MID_X
    # Front-ish XZ cut: through USB pocket and PCB lip (case Y).
    usb_cut_y = 5.0  # within pocket (0..7) and PCB lip (~3.9..7.9)

    case = make_cnc_pykey40_case(
        cutout_usb_connector=True,
        cutout_feet_holes=False,
        cutout_bumpon_guides=False,
        chamfer_edges=False,
    )
    pcb = Pos(pcb_xy[0], pcb_xy[1], 0) * make_pcb(z_pcb)
    usb = Pos(pcb_xy[0], pcb_xy[1], 0) * make_usb_connector(z_pcb)

    # --- YZ section at USB mid-X (side): crop Y around pocket, full Z ---
    yz_cy = usb_cut_y  # pocket / lip region
    yz_size = (SLAB_T, 2 * ROI_Y_HALF, oh + 2 * ROI_Z_PAD)
    yz_center = (usb_case_x, yz_cy, oh / 2)
    yz_case = thin_slab_section(case, center=yz_center, size=yz_size)
    yz_pcb = thin_slab_section(pcb, center=yz_center, size=yz_size)
    yz_usb = thin_slab_section(usb, center=yz_center, size=yz_size)

    # --- XZ section at USB pocket Y (front): crop X around mid-X, full Z ---
    xz_size = (2 * ROI_X_HALF, SLAB_T, oh + 2 * ROI_Z_PAD)
    xz_center = (usb_case_x, usb_cut_y, oh / 2)
    xz_case = thin_slab_section(case, center=xz_center, size=xz_size)
    xz_pcb = thin_slab_section(pcb, center=xz_center, size=xz_size)
    xz_usb = thin_slab_section(usb, center=xz_center, size=xz_size)

    def center_all(p: Part) -> Part | None:
        if p is None or p.volume == 0:
            return None
        return Pos(-ow / 2, -ol / 2, -oh / 2) * p

    def mirror_all(p: Part) -> Part | None:
        c = center_all(p)
        if c is None:
            return None
        return mirror(c, about=Plane.YZ)

    border = TechnicalDrawing(
        designed_by="rgoulter",
        design_date=date.today(),
        page_size=PageSize.A4,
        title="CNC pykey40 USB mount",
        sub_title="cross-sections (pocket ROI)",
        drawing_number="KL-CNC-PY40-USB",
        sheet_number=1,
        drawing_scale=1,
        nominal_text_size=4.0,
    )
    faces_by_area = sorted(border.faces(), key=lambda f: -f.area)
    frame_bb = faces_by_area[0].bounding_box()
    title_bb = faces_by_area[1].bounding_box()

    # Cameras:
    # Side (YZ cut): look from +X — after YZ mirror, USB toward front
    # Front-ish (XZ cut): look from -Y — USB page-right
    CAM_SIDE = ((200, 0, 0), (0, 0, 1))
    CAM_FRONT = ((0, -200, 0), (0, 0, 1))

    layers_side = [
        (n, c, s)
        for n, c, s in [
            ("Case", (0x20, 0x20, 0x20), mirror_all(yz_case)),
            ("PCB", (0xC0, 0x20, 0x20), mirror_all(yz_pcb)),
            ("USB", (0x40, 0x40, 0xA0), mirror_all(yz_usb)),
        ]
        if s is not None
    ]
    layers_front = [
        (n, c, s)
        for n, c, s in [
            ("CaseF", (0x20, 0x20, 0x20), mirror_all(xz_case)),
            ("PCBF", (0xC0, 0x20, 0x20), mirror_all(xz_pcb)),
            ("USBF", (0x40, 0x40, 0xA0), mirror_all(xz_usb)),
        ]
        if s is not None
    ]

    def probe(layers, cam):
        edges = []
        for _n, _c, solid in layers:
            vis, _ = project_to_2d(solid, cam[0], cam[1], (0, 0), SCALE)
            edges.extend(vis)
        return Curve(edges).bounding_box() if edges else None

    bb_s = probe(layers_side, CAM_SIDE)
    bb_f = probe(layers_front, CAM_FRONT)
    if bb_s is None or bb_f is None:
        raise RuntimeError("USB section probe produced empty geometry")

    usable_left = frame_bb.min.X + MARGIN
    usable_right = frame_bb.max.X - MARGIN
    usable_top = frame_bb.max.Y - MARGIN
    usable_bot = max(frame_bb.min.Y + MARGIN, title_bb.max.Y + 8.0)
    usable_h = usable_top - usable_bot
    usable_w = usable_right - usable_left
    mid_y = usable_bot + usable_h / 2.0
    cx = (usable_left + usable_right) / 2.0

    # Stacked panels: SIDE top half, FRONT bottom half
    panel_gap = 6.0
    side_top = usable_top - 2.0
    side_bot = mid_y + panel_gap / 2.0
    front_top = mid_y - panel_gap / 2.0
    front_bot = usable_bot + 18.0  # room for legend

    side_cy = (side_top + side_bot) / 2.0 - 4.0
    front_cy = (front_top + front_bot) / 2.0 - 2.0

    origin_side = (cx - bb_s.center().X, side_cy - bb_s.center().Y)
    origin_front = (cx - bb_f.center().X, front_cy - bb_f.center().Y)

    # Panel divider / frames
    side_frame = Pos(cx, (side_top + side_bot) / 2.0) * Rectangle(
        usable_w - 4, side_top - side_bot - 2
    )
    front_frame = Pos(cx, (front_top + front_bot) / 2.0) * Rectangle(
        usable_w - 4, front_top - front_bot - 2
    )
    divider = Edge.make_line(
        (usable_left + 2, mid_y, 0), (usable_right - 2, mid_y, 0)
    )

    exporter = ExportSVG(unit=Unit.MM)
    labels: list = []

    for name, color, solid in layers_side:
        exporter.add_layer(name, line_color=color, line_weight=0.35)
        vis, _ = project_to_2d(solid, *CAM_SIDE, origin_side, SCALE)
        if vis:
            exporter.add_shape(list(vis), layer=name)

    for name, color, solid in layers_front:
        exporter.add_layer(name, line_color=color, line_weight=0.35)
        vis, _ = project_to_2d(solid, *CAM_FRONT, origin_front, SCALE)
        if vis:
            exporter.add_shape(list(vis), layer=name)

    exporter.add_layer("Frames", line_color=(0x90, 0x90, 0x90), line_weight=0.30)
    exporter.add_shape(list(side_frame.edges()) + list(front_frame.edges()) + [divider], layer="Frames")

    t1 = Text("SIDE — YZ cut @ USB mid-X (pocket ROI)", 3.6)
    t1.position = Vector(usable_left + 4, side_top - 6)
    labels.append(t1)
    t1b = Text(
        f"cut X={usb_case_x:.2f} (case)  |  Y ROI ±{ROI_Y_HALF:.0f} around Y≈{yz_cy:.0f}",
        2.5,
    )
    t1b.position = Vector(usable_left + 4, side_top - 13)
    labels.append(t1b)

    t2 = Text("FRONT — XZ cut @ USB pocket Y (pocket ROI)", 3.6)
    t2.position = Vector(usable_left + 4, front_top - 6)
    labels.append(t2)
    t2b = Text(
        f"cut Y={usb_cut_y:.2f}  |  X ROI ±{ROI_X_HALF:.0f} around USB mid-X  |  "
        f"pocket {USB_CONNECTOR_HOLE_WIDTH:.0f}×{USB_CONNECTOR_CUTOUT_LENGTH:.0f}",
        2.5,
    )
    t2b.position = Vector(usable_left + 4, front_top - 13)
    labels.append(t2b)

    pocket_h_top = (
        CASE_BOTTOM_HEIGHT
        + CASE_LOWER_CAVITY_HEIGHT
        + (USB_CONNECTOR_HOLE_HEIGHT / 2 - USB_CONNECTOR_HEIGHT / 2)
    )
    legend = Text(
        f"Legend: case black / PCB red / USB blue    |    "
        f"pocket {USB_CONNECTOR_HOLE_WIDTH:.0f}×{USB_CONNECTOR_CUTOUT_LENGTH:.0f}    |    "
        f"PCB Z={z_pcb:.0f}    |    cut X={usb_case_x:.2f}  Y={usb_cut_y:.2f}    |    "
        f"pocket H to {pocket_h_top:.1f}",
        2.3,
    )
    legend.position = Vector(usable_left + 2, usable_bot + 8)
    labels.append(legend)

    note2 = Text(
        "USB page-right on front cut (mirrored solid). Side looks from +X. "
        f"Scale ≈{SCALE:.1f}× (cropped ROI).",
        2.1,
    )
    note2.position = Vector(usable_left + 2, usable_bot + 1)
    labels.append(note2)

    exporter.add_layer("Annotations", fill_color=(0, 0, 0), line_color=(0, 0, 0))
    exporter.add_shape(border.edges(), layer="Case")
    glyph_faces = [f for f in border.faces() if f.area < 20]
    if glyph_faces:
        exporter.add_shape(glyph_faces, layer="Annotations")
    exporter.add_shape(labels, layer="Annotations")
    exporter.write(str(OUT_SVG))
    print(f"Wrote {OUT_SVG}")
    svg_to_png(OUT_SVG, OUT_PNG)


if __name__ == "__main__":
    main()
