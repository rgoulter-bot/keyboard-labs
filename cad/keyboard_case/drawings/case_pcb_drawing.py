#!/usr/bin/env python3
"""
Standalone PCB technical drawing for CNC pykey40.

Dims: overall PCB size, mount-hole positions relative to PCB edges / SW_1_1,
USB connector mid-X and lip on the PCB outline.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path

from build123d import *

from helpers import (
    center_mark,
    ensure_case_import_path,
    project_to_2d,
    svg_to_png,
)

ensure_case_import_path()

from case_pykey40 import (
    PCB_SW_1_1_POSITION,
    PCB_USB_CONNECTOR_MID_X,
    SWITCH_GRID_UNIT,
    derived_dims,
    pcb_mounting_hole_positions_on_pcb,
)
from case_pykey40_constants import PCB_DIM

OUT_DIR = Path(__file__).resolve().parent
OUT_SVG = OUT_DIR / "cnc_pykey40_pcb_a4.svg"
OUT_PNG = OUT_DIR / "cnc_pykey40_pcb_a4.png"

PCB_THICKNESS = 1.6
PCB_CORNER_R = 2.25
USB_LIP_W = 11.0  # connector 9 + extraW 2
USB_LIP_H = 4.0
SCALE = 0.85
CENTER_MARK_HALF = 2.0


def make_pcb_part() -> Part:
    w, l = PCB_DIM
    with BuildPart() as bp:
        with BuildSketch():
            RectangleRounded(w, l, PCB_CORNER_R, align=(Align.MIN, Align.MIN))
            with Locations((PCB_USB_CONNECTOR_MID_X, 0)):
                Rectangle(USB_LIP_W, USB_LIP_H, align=(Align.CENTER, Align.CENTER))
        extrude(amount=PCB_THICKNESS)
        for hx, hy in pcb_mounting_hole_positions_on_pcb():
            with Locations((hx, hy, 0)):
                Hole(1.1, depth=PCB_THICKNESS + 0.1)
    return bp.part


def main() -> None:
    w, l = PCB_DIM
    pcb = make_pcb_part()
    # Mirror about YZ so USB lip is top-left after viewport_up X-flip.
    pcb_draw = mirror(Pos(-w / 2, -l / 2, -PCB_THICKNESS / 2) * pcb, about=Plane.YZ)

    holes = pcb_mounting_hole_positions_on_pcb()
    # Page X tracks physical X after YZ-mirror + top viewport (USB / SW_1_1 LHS).
    sw11 = PCB_SW_1_1_POSITION
    usb_x = PCB_USB_CONNECTOR_MID_X
    xs = sorted({round(h[0], 6) for h in holes})
    ys = sorted({round(h[1], 6) for h in holes})

    border = TechnicalDrawing(
        designed_by="rgoulter",
        design_date=date.today(),
        page_size=PageSize.A4,
        title="CNC pykey40 PCB",
        sub_title="outline + mounts + USB lip",
        drawing_number="KL-CNC-PY40-PCB",
        sheet_number=1,
        drawing_scale=1,
        nominal_text_size=4.0,
    )
    page = border.bounding_box().size
    page_origin = (page.X * -0.02, page.Y * 0.10)

    drafting = Draft(
        font_size=3.2,
        decimal_precision=2,
        display_units=False,
        extension_gap=0.8,
        head_type=HeadType.STRAIGHT,
        line_width=0.5,
        arrow_length=2.8,
    )

    vis, hid = project_to_2d(
        pcb_draw, (0, 0, 200), (0, -1, 0), page_origin, SCALE
    )

    def mx(x_phys: float) -> float:
        return page_origin[0] + (x_phys - w / 2) * SCALE

    def my(y: float) -> float:
        return page_origin[1] - (y - l / 2) * SCALE

    annotations: list = []
    labels: list = []
    centerlines: list = []
    dim_edges: list = []

    half = CENTER_MARK_HALF * SCALE
    for hx, hy in holes:
        centerlines.extend(center_mark(mx(hx), my(hy), half))
    centerlines.extend(center_mark(mx(sw11[0]), my(sw11[1]), half))

    bb = Curve(vis).bounding_box()
    front_y, back_y = bb.max.Y, bb.min.Y

    peri = Pos(*bb.center()) * Rectangle(bb.size.X, bb.size.Y)
    annotations.append(
        ExtensionLine(
            border=peri.edges().sort_by(Axis.Y)[0],
            offset=12 * MM,
            draft=drafting,
            label=f"{w:.0f}",
        )
    )
    annotations.append(
        ExtensionLine(
            border=peri.edges().sort_by(Axis.X)[-1],
            offset=12 * MM,
            draft=drafting,
            label=f"{l:.0f}",
        )
    )

    # Page L→R = phys left→right (USB / SW_1_1 on LHS).
    hpx = [mx(x) for x in xs]
    hpy = [my(y) for y in ys]
    hpx_sorted = sorted(hpx)
    pcb_page_left = mx(0)
    feat_y = hpy[0]
    x_offset = -((front_y - feat_y) + 10.0) * MM
    edge_and_holes = sorted([pcb_page_left] + hpx_sorted)
    vals_ltr = [xs[0] - 0.0, xs[1] - xs[0], xs[2] - xs[1], w - xs[2]]
    for (xa, xb), val in zip(
        zip(edge_and_holes[:-1], edge_and_holes[1:]), vals_ltr
    ):
        annotations.append(
            ExtensionLine(
                border=[(xa, feat_y, 0), (xb, feat_y, 0)],
                offset=x_offset,
                draft=drafting,
                label=f"{val:.2f}",
            )
        )

    feat_x = hpx_sorted[0]
    y_dim_x = feat_x - 22.0
    front_edge_y = my(0)
    y_segs = [
        (hpy[2], hpy[1], ys[2] - ys[1]),
        (hpy[1], hpy[0], ys[1] - ys[0]),
        (hpy[0], front_edge_y, ys[0] - 0.0),
    ]
    gap = drafting.extension_gap
    arrow_len = drafting.arrow_length
    arrow_half_w = arrow_len / 3.0
    for y_a, y_b, val in y_segs:
        y_lo, y_hi = (y_a, y_b) if y_a < y_b else (y_b, y_a)
        dim_edges.append(Edge.make_line((feat_x - gap, y_a, 0), (y_dim_x - gap, y_a, 0)))
        dim_edges.append(Edge.make_line((feat_x - gap, y_b, 0), (y_dim_x - gap, y_b, 0)))
        dim_edges.append(Edge.make_line((y_dim_x, y_lo, 0), (y_dim_x, y_hi, 0)))
        for y_end, s in ((y_lo, 1), (y_hi, -1)):
            dim_edges.append(
                Edge.make_line(
                    (y_dim_x, y_end, 0),
                    (y_dim_x - arrow_half_w, y_end + s * arrow_len, 0),
                )
            )
            dim_edges.append(
                Edge.make_line(
                    (y_dim_x, y_end, 0),
                    (y_dim_x + arrow_half_w, y_end + s * arrow_len, 0),
                )
            )
        mid_y = (y_a + y_b) / 2
        lbl = Text(f"{val:.2f}", 3.5)
        lbl.position = Vector(y_dim_x - 9.0, mid_y)
        labels.append(lbl)

    sw_lbl = Text(
        f"SW_1_1 ({PCB_SW_1_1_POSITION[0]:.1f}, {PCB_SW_1_1_POSITION[1]:.1f})",
        3.0,
    )
    sw_lbl.position = Vector(mx(sw11[0]) + 4, my(sw11[1]) + 6)
    labels.append(sw_lbl)

    usb_lbl = Text(
        f"USB mid-X {PCB_USB_CONNECTOR_MID_X:.3f}  "
        f"(= SW_1_1.x + 1.5×{SWITCH_GRID_UNIT})",
        3.0,
    )
    usb_lbl.position = Vector(mx(usb_x) - 35, front_y + 18)
    labels.append(usb_lbl)

    lip_lbl = Text(f"USB lip {USB_LIP_W:.0f}×{USB_LIP_H:.0f} (y=−2..+2)", 2.8)
    lip_lbl.position = Vector(mx(usb_x) - 20, front_y + 10)
    labels.append(lip_lbl)

    title = Text("Top — PCB outline (USB top-left)", 4.0)
    title.position = Vector(page_origin[0], front_y + 28)
    labels.append(title)

    note = Text(
        f"PCB {w:.0f}×{l:.0f}×{PCB_THICKNESS}  |  5× mount ⌀2.2  |  "
        f"mounts from SW_1_1 + grid offsets",
        2.8,
    )
    note.position = Vector(page_origin[0], back_y - 16)
    labels.append(note)

    d = derived_dims()
    note2 = Text(
        f"case_pcb_position {tuple(round(v, 3) for v in d['case_pcb_position'])} "
        f"(placement in case; this sheet is PCB-local)",
        2.4,
    )
    note2.position = Vector(page_origin[0], back_y - 24)
    labels.append(note2)

    exporter = ExportSVG(unit=Unit.MM)
    exporter.add_layer("Visible")
    exporter.add_layer(
        "Hidden", line_color=(0x63, 0x63, 0x63), line_type=LineType.ISO_DOT
    )
    exporter.add_layer(
        "Center", line_color=(0x40, 0x40, 0x40), line_type=LineType.ISO_DASH_DOT
    )
    exporter.add_layer("Annotations", fill_color=(0, 0, 0), line_color=(0, 0, 0))
    exporter.add_layer(
        "DimLines", line_color=(0, 0, 0), line_weight=drafting.line_width
    )
    exporter.add_shape(list(vis), layer="Visible")
    if hid:
        exporter.add_shape(list(hid), layer="Hidden")
    if centerlines:
        exporter.add_shape(centerlines, layer="Center")
    if dim_edges:
        exporter.add_shape(dim_edges, layer="DimLines")
    exporter.add_shape(border.edges(), layer="Visible")
    glyph_faces = [f for f in border.faces() if f.area < 20]
    if glyph_faces:
        exporter.add_shape(glyph_faces, layer="Annotations")
    if annotations:
        exporter.add_shape(annotations, layer="Annotations")
    exporter.add_shape(labels, layer="Annotations")
    exporter.write(str(OUT_SVG))
    print(f"Wrote {OUT_SVG}")
    svg_to_png(OUT_SVG, OUT_PNG)


if __name__ == "__main__":
    main()
