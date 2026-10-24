# Desktop raster assets

DejaVu Sans and DejaVu Sans Mono, version 2.37, acquired from the installed
Debian `fonts-dejavu-core` 2.37-8 package. The TTF hashes in `receipt.json` are
measured artifact pins, not independently authenticated upstream checksums.
Upstream: <https://dejavu-fonts.github.io/>. Copyright and permission notices
are preserved in `DejaVu-LICENSE.txt`; the Debian packaging license section
does not describe the font files. No Debian packaging code is included.

`scripts/build-desktop-fonts.py` uses Pillow/FreeType to produce bounded ASCII
coverage for 16×16 and 24×24 cells. The receipt records the Pillow version and
each decoded coverage hash. Native builds consume the committed generated
`.in` masks and need no host font installation, font parser, Python or FreeType
at runtime. Reproduction/checking needs Pillow 12.3.0 as recorded:

```sh
python3 scripts/build-desktop-fonts.py --check
```

Masks are packed count/coverage pairs in native arrays and decoded into the
existing 16-pixel tables plus two bounded 24-pixel tables. The encoded payload
is 53,104 bytes. No boot/heap limit was increased. UI glyphs are fitted inside their rounded FreeType advances. The desktop
profile uses10/15-pixel terminal cells and13/19-pixel baselines at2x/3x. The
legacy bitmap profile and protected clients retain their existing metrics. These are rasterized assets, not a new typeface design or Unicode shaper.
The legacy bitmap faces remain available for existing protected SCI clients,
fallback and the established stress profile. Desktop text roles select the new
rasters at the supported 2×/3× sizes. Larger typography/layout changes remain
part of the full desktop goal.
