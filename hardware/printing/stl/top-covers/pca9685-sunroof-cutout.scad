// ============================================================================
// Sesame Robot -- PCA9685 "Sunroof" Cutout for the Enclosed Top Cover
// ============================================================================
// Part of the PCA9685 no-solder fork (docs/pca9685-fork/README.md).
//
// This cuts a rectangular window through the top cover shell so you have
// direct access/clearance for the PCA9685 driver board and its connectors.
//
// USAGE:
//   openscad -o Top-Cover-Enclosed-v117-PCA9685-sunroof.stl pca9685-sunroof-cutout.scad
// or open this file directly in the OpenSCAD GUI, tweak the parameters below,
// and press F6 (render) then export as STL.
//
// ============================================================================
// IMPORTANT AXIS NOTE -- READ THIS BEFORE CHANGING NUMBERS
// ============================================================================
// The raw STL file is stored "lying on its side" relative to the assembled
// robot. In the FILE's own coordinate system:
//   - True vertical (up/down, i.e. where a "sunroof" cut needs to go
//     through) is the FILE's X AXIS, not Z.
//   - The file's Y axis is front-to-back (low Y = front, near the OLED
//     window; high Y = back, near the ear ridges) -- this one matches
//     intuition.
//   - The file's Z axis is left-to-right (width).
// This was confirmed by rotating the mesh -90 degrees about Y and comparing
// against reference photos: that rotation produces a front elevation that
// exactly matches the real robot's face (OLED centered, two ear nubs at top
// corners, small chin tab at bottom) -- confirming file-X = true vertical.
//
// GEOMETRY NOTES (measured directly from Top-Cover-Enclosed-v117.stl,
// casting rays along -X to find the true top/crown surface height at each
// (Y,Z) point):
//   - The crown's flat outer surface sits at X = 65.6, inner surface at
//     X = ~64.4 (thin section here; elsewhere on the shell it's ~2mm).
//   - There is a large, genuinely flat, clear zone on the crown -- in front
//     of the ear-ridge detailing, behind the OLED window -- spanning:
//         Y (front-back): 29 to 41   (12mm)
//         Z (left-right):  -15 to 19  (34mm)
//   - Default cutout below (30 x 10mm, centered in that zone) leaves a
//     couple mm of structural margin on all sides.
//
// IMPORTANT: A real PCA9685 board is roughly 63mm x 25mm, which does NOT
// fit as a full flush cutout in this shell (the flat crown zone tops out at
// ~34x12mm). The internal cavity is tall enough that the board itself sits
// fine INSIDE the shell on the internal frame -- this cutout is a
// wire/connector access + visual "sunroof" window, not a full board
// pass-through. Adjust the parameters below if you want a different size,
// but stay inside the clear zone noted above (or re-verify clearances with
// the ray-casting technique in docs/pca9685-fork/README.md if you don't).
// ============================================================================

// --- Parameters (all in mm, in the FILE's native coordinate system) ---
// NOTE: uses the "-shell-only" STL, not the original file. The original
// Top-Cover-Enclosed-v117.stl is a compound of the main shell PLUS several
// tiny separate solids (magnet slot inserts near the back) that OpenSCAD's
// CGAL backend cannot boolean as a single import (it requires one closed
// manifold). Those tiny parts are unaffected by this cutout anyway -- if you
// want them in your final print, use the pre-merged, ready-to-print
// Top-Cover-Enclosed-v117-PCA9685-sunroof.stl instead of re-rendering this
// script, or manually re-union them back in afterward.
input_stl     = "Top-Cover-Enclosed-v117-shell-only.stl";

y_center      = 35;   // front-back position (clear zone: 29-41)
y_len         = 10;   // depth along front-back (max ~12 before hitting OLED window / ear ridges)
z_center      = 2;    // left-right position (clear zone: -15 to 19)
z_len         = 30;   // width along left-right (max ~34 before hitting the edges)
corner_r      = 2;    // corner rounding radius, for print strength (0 = sharp corners)

x_bottom      = 55;   // well below the inner surface (~64.4) to guarantee a clean through-cut
x_top         = 70;   // well above the outer surface (65.6)

// --- Rounded rectangle helper (2D, drawn in the extrusion's local XY plane) ---
module rounded_rect(l, w, r) {
    if (r <= 0) {
        square([l, w], center = true);
    } else {
        hull() {
            for (sx = [-1, 1]) for (sy = [-1, 1])
                translate([sx * (l/2 - r), sy * (w/2 - r)])
                    circle(r = r, $fn = 32);
        }
    }
}

// --- The cut ---
// Build the rounded rect in the local XY plane (local-X = z_len, local-Y =
// y_len), extrude it along local Z by the cut depth, then rotate 90 about Y
// so the extrusion direction becomes the FILE's true-vertical X axis, local
// X becomes the file's Z axis, and local Y stays the file's Y axis.
difference() {
    import(input_stl, convexity = 10);

    translate([(x_top + x_bottom) / 2, y_center, z_center])
        rotate([0, 90, 0])
            linear_extrude(height = x_top - x_bottom, center = true)
                rounded_rect(z_len, y_len, corner_r);
}
