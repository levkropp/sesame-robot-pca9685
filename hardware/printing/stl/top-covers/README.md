# Top Cover Styles

## Enclosed v100
Current modern version of sesame top cover, includes 5mm x 2mm magnet slots for hats! Front display wires are covered, supports multicolor details.

## Cat v100
Modern Version of the enclosed top cover with cat ears instead of stubby ears! Updated with all current features with magnet support for hats, and multicolor details.

## No Ears v100
Template for designing your own ears for Sesame. The areas right next to where the ears ussually go is a little thin so this version is only really meant for desiging ears onto. (Includes all previously mentioned features)

## Enclosed v117 -- PCA9685 Sunroof (PCA9685 fork)

`Top-Cover-Enclosed-v117-PCA9685-sunroof.stl` is a variant of Enclosed v117 with a
30 x 10mm rounded-corner window cut into the crown (top), giving direct access/clearance
for the PCA9685 driver board and its wiring. Print this instead of the plain
`Top-Cover-Enclosed-v117.stl` if you're building the [PCA9685 no-solder fork](../../../docs/pca9685-fork/README.md).

![Top cover with PCA9685 sunroof cutout](../../../docs/pca9685-fork/assets/top-cover-sunroof-preview.png)

The cutout sits in a genuinely clear, flat zone on the true crown of the head --
well clear of the existing OLED window (front face) and the ear ridges (back).

> [!IMPORTANT]
> **Axis gotcha:** the raw STL file is stored "lying on its side" relative to the
> assembled robot -- the file's **X axis is true vertical** (up/down), not Z. Z is
> actually left-right width, and Y is front-back depth (that one matches intuition).
> This was confirmed by rotating the mesh and matching it against reference photos
> of the assembled robot. If you're measuring your own clear zones on this file,
> cast rays along -X to find the true top surface, not -Z.

The internal cavity is tall enough that the PCA9685 board itself sits fine inside on
the internal frame; this window is for connector/wire access and visual clearance,
not a full board pass-through (a real PCA9685 board, ~63x25mm, is larger than the
shell's available flat area on the crown).

Want a different size or position? Edit `pca9685-sunroof-cutout.scad` (parameters
documented at the top of the file) and re-render with OpenSCAD:

```bash
openscad -o Top-Cover-Enclosed-v117-PCA9685-sunroof.stl pca9685-sunroof-cutout.scad
```

That script imports `Top-Cover-Enclosed-v117-shell-only.stl` (a pre-cleaned,
single-solid version of the shell -- OpenSCAD's CGAL backend can't boolean the
original file directly, since it's a compound of the main shell plus several tiny
separate solids for the hat magnet slots). If you want those magnet-slot pieces
included in your final custom cut, re-union them back in afterward, or just use the
pre-built `Top-Cover-Enclosed-v117-PCA9685-sunroof.stl` as-is.

