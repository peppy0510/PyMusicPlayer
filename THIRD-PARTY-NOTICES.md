# Third-Party Notices

The MIT licence in [`LICENSE`](LICENSE) covers the code written for this project — `source/`,
excluding `source/pybass/`. It does **not** cover the third-party binaries and assets vendored
in this repository. Those remain under their own terms, held by their own copyright holders,
and are listed below.

If you fork or redistribute PyMusicPlayer, these terms travel with the files. The MIT licence
grants you no rights over them.

---

## `assets/dlls/bass_vst.dll` — BASS_VST

Copyright (c) Bjoern Petersen Software Design and Development.
Licensed under the **GNU Lesser General Public License, version 3**.

- Licence text: [`licenses/BASS_VST/lgpl-3.0.txt`](licenses/BASS_VST/lgpl-3.0.txt) and
  [`licenses/BASS_VST/gpl-3.0.txt`](licenses/BASS_VST/gpl-3.0.txt). LGPL-3.0 incorporates the
  terms of GPL-3.0 by reference, so both texts are required.
- Source code: <https://github.com/r10s/BASS_VST>
- Included **unmodified**, as a separate shared library. You may replace `bass_vst.dll` with
  your own build of BASS_VST and PyMusicPlayer will use it.

VST PlugIn Interface Technology by Steinberg Media Technologies GmbH.

## `assets/dlls/bass.dll`, `bass_fx.dll`, `bassmidi.dll`, `bassmix.dll`, `tags.dll` — BASS

Copyright (c) Un4seen Developments Ltd. — <https://www.un4seen.com>

Used in PyMusicPlayer under a commercial licence purchased from Un4seen Developments.
**That licence covers this application only; it is not sublicensed to you.** BASS is free for
non-commercial use. Any other use requires your own licence from Un4seen.

## `assets/dlls/LoudMax.dll`, `LoudMax64.dll`, `LoudMaxLite.dll`, `LoudMaxLite64.dll` — LoudMax

Copyright (c) 2019 Thomas Mundt — <https://loudmax.blogspot.com>

LoudMax is freeware. The author's stated terms:

> LoudMax is freeware and not commercial in any mean. However, you may not distribute and/or
> modify LoudMax without having an explicit permission from me.

Please obtain LoudMax from the author's site above.

## `assets/fonts/unifont.ttf` — GNU Unifont

Copyright (c) Roman Czyborra, Paul Hardy, and contributors. Build dated 2013-10-20.
Licensed under the **GNU General Public License, version 2 or later**, with the GNU font
embedding exception:

> These font files are licensed under the GNU General Public License, either Version 2 or (at
> your option) a later version, with the exception that embedding the font in a document does
> not in itself constitute a violation of the GNU GPL.

- Licence text: [`licenses/Unifont/gpl-2.0.txt`](licenses/Unifont/gpl-2.0.txt)
- Upstream: <https://unifoundry.com/unifont/>

Unifont releases from version 13.0.04 onward are additionally available under the SIL Open
Font License 1.1. The build vendored here predates that, so GPL-2.0-or-later applies.

## `source/pybass/` — pybass

Copyright (c) Maxim Kolosov. pybass 0.5.5, BSD licence.

The licence lives in the per-file headers of `source/pybass/pybass*.py` — do not strip them.
`source/pybass/bass.py` and `source/pybass/__init__.py` are this project's own loaders and are
covered by the MIT licence.

---

## Runtime dependencies

The packages in [`requirements.pip`](requirements.pip) are installed with pip and are **not**
vendored here, so this repository does not redistribute them. Binary builds produced by
`makebuild.py` / PyInstaller **do** bundle them, and their terms apply to that artefact.

Notably, **mutagen is licensed GPL-2.0-or-later**. Anyone shipping a bundled binary of
PyMusicPlayer should review the full dependency set before distributing it.
