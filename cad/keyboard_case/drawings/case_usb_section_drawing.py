#!/usr/bin/env python3
"""
USB mount cross-sections for CNC pykey40 case.

1. YZ cut through USB mid-X — side view (pocket depth vs PCB/USB)
2. XZ cut through USB pocket Y — front-ish view (pocket width vs PCB/USB)

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
SCALE = 1.6
SLAB_T = 0.05
MARGIN = 14.0


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
    # Pocket is Y=0..CUTOUT_LENGTH; PCB lip sits near Y=pcb_xy[1].
    usb_cut_y = 5.0  # within pocket (0..7) and PCB lip (~3.9..7.9)

    case = make_cnc_pykey40_case(
        cutout_usb_connector=True,
        cutout_feet_holes=False,
        cutout_bumpon_guides=False,
        chamfer_edges=False,
    )
    pcb = Pos(pcb_xy[0], pcb_xy[1], 0) * make_pcb(z_pcb)
    usb = Pos(pcb_xy[0], pcb_xy[1], 0) * make_usb_connector(z_pcb)

    # --- YZ section at USB mid-X (side view of pocket) ---
    yz_case = thin_slab_section(
        case, center=(usb_case_x, ol / 2, oh / 2), size=(SLAB_T, ol + 40, oh + 20)
    )
    yz_pcb = thin_slab_section(
        pcb, center=(usb_case_x, ol / 2, oh / 2), size=(SLAB_T, ol + 40, oh + 20)
    )
    yz_usb = thin_slab_section(
        usb, center=(usb_case_x, ol / 2, oh / 2), size=(SLAB_T, ol + 40, oh + 20)
    )

    # --- XZ section at USB pocket Y (front-ish: pocket width) ---
    xz_case = thin_slab_section(
        case, center=(ow / 2, usb_cut_y, oh / 2), size=(ow + 40, SLAB_T, oh + 20)
    )
    xz_pcb = thin_slab_section(
        pcb, center=(ow / 2, usb_cut_y, oh / 2), size=(ow + 40, SLAB_T, oh + 20)
    )
    xz_usb = thin_slab_section(
        usb, center=(ow / 2, usb_cut_y, oh / 2), size=(ow + 40, SLAB_T, oh + 20)
    )

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
        sub_title="cross-sections",
        drawing_number="KL-CNC-PY40-USB",
        sheet_number=1,
        drawing_scale=1,
        nominal_text_size=4.0,
    )
    faces_by_area = sorted(border.faces(), key=lambda f: -f.area)
    frame_bb = faces_by_area[0].bounding_box()
    title_bb = faces_by_area[1].bounding_box()

    # Cameras:
    # Side (YZ cut): look from +X (cam +200,0,0) — after YZ mirror, USB toward front
    # Front-ish (XZ cut): look from -Y (cam 0,-200,0) — USB page-right
    CAM_SIDE = ((200, 0, 0), (0, 0, 1))
    CAM_FRONT = ((0, -200, 0), (0, 0, 1))

    layers_side = [
        (n, c, s)
        for n, c, s in [
            ("Case", (0x40, 0x40, 0x40), mirror_all(yz_case)),
            ("PCB", (0xC0, 0x20, 0x20), mirror_all(yz_pcb)),
            ("USB", (0x40, 0x40, 0xA0), mirror_all(yz_usb)),
        ]
        if s is not None
    ]
    layers_front = [
        (n, c, s)
        for n, c, s in [
            ("CaseF", (0x40, 0x40, 0x40), mirror_all(xz_case)),
            ("PCBF", (0xC0, 0x20, 0x20), mirror_all(xz_pcb)),
            ("USBF", (0x40, 0x40, 0xA0), mirror_all(xz_usb)),
        ]
        if s is not None
    ]

    # Probe sizes
    def probe(layers, cam):
        edges = []
        for _n, _c, solid in layers:
            vis, _ = project_to_2d(solid, cam[0], cam[1], (0, 0), SCALE)
            edges.extend(vis)
        return Curve(edges).bounding_box() if edges else None

    bb_s = probe(layers_side, CAM_SIDE)
    bb_f = probe(layers_front, CAM_FRONT)

    usable_left = frame_bb.min.X + MARGIN
    usable_right = frame_bb.max.X - MARGIN
    usable_top = frame_bb.max.Y - MARGIN
    usable_bot = max(frame_bb.min.Y + MARGIN, title_bb.max.Y + 10.0)
    mid_x = (usable_left + usable_right) / 2.0
    # Side panel left half; front panel right half
    side_cx = usable_left + (mid_x - usable_left) / 2.0
    front_cx = mid_x + (usable_right - mid_x) / 2.0
    cy = (usable_top + usable_bot) / 2.0 + 8.0

    origin_side = (side_cx - bb_s.center().X, cy - bb_s.center().Y)
    origin_front = (front_cx - bb_f.center().X, cy - bb_f.center().Y)

    exporter = ExportSVG(unit=Unit.MM)
    labels: list = []

    for name, color, solid in layers_side:
        exporter.add_layer(name, line_color=color, line_weight=0.25)
        vis, _ = project_to_2d(solid, *CAM_SIDE, origin_side, SCALE)
        if vis:
            exporter.add_shape(list(vis), layer=name)

    for name, color, solid in layers_front:
        exporter.add_layer(name, line_color=color, line_weight=0.25)
        vis, _ = project_to_2d(solid, *CAM_FRONT, origin_front, SCALE)
        if vis:
            exporter.add_shape(list(vis), layer=name)

    t1 = Text("Side — YZ @ USB mid-X", 3.5)
    t1.position = Vector(side_cx - 35, usable_top - 4)
    labels.append(t1)
    t1b = Text(f"X={usb_case_x:.2f} (case)", 2.6)
    t1b.position = Vector(side_cx - 25, usable_top - 12)
    labels.append(t1b)

    t2 = Text("Front — XZ @ USB pocket Y", 3.5)
    t2.position = Vector(front_cx - 40, usable_top - 4)
    labels.append(t2)
    t2b = Text(f"Y={usb_cut_y:.2f}  pocket {USB_CONNECTOR_HOLE_WIDTH:.0f}×{USB_CONNECTOR_CUTOUT_LENGTH:.0f}", 2.6)
    t2b.position = Vector(front_cx - 45, usable_top - 12)
    labels.append(t2b)

    note = Text(
        f"case black / PCB red / USB blue  |  PCB Z={z_pcb:.0f}  |  "
        f"pocket H to {CASE_BOTTOM_HEIGHT + CASE_LOWER_CAVITY_HEIGHT + (USB_CONNECTOR_HOLE_HEIGHT/2 - USB_CONNECTOR_HEIGHT/2):.1f}",
        2.4,
    )
    note.position = Vector(usable_left, usable_bot + 2)
    labels.append(note)

    note2 = Text(
        "USB page-right on front cut (mirrored solid). Side looks from +X.",
        2.2,
    )
    note2.position = Vector(usable_left, usable_bot - 6)
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
