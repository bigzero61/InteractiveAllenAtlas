# Interactive Allen Atlas Program

A PyQt5 desktop viewer for the Allen CCFv3 P56 brain atlas and annotation.

The app renders locally in the Python process, so slice scrolling, search,
crosshair lookup, mosaic refresh, region merges, and PDF export do not require a
browser or a web server.

## Features

- Three orthogonal views: sagittal, coronal, and axial.
- Mosaic view with axis, start/end anchor, row count, column count, and step.
- Brain-region tree with all parent and child structures.
- Search by acronym, full name, id, or hierarchy path.
- Hemisphere filter: both, left, or right.
- Overlay modes: fill, fill selected, contour labels, contour selected, and combined fill/contour modes.
- Custom merge groups with one display color per merged group.
- Optional acronyms, orientation labels, XYZ coordinate labels in mm, crosshair, hover lookup, scale bar, and color bar.
- Underlay upload with perm/flip orientation controls.
- PDF export with text labels drawn as editable PDF text where possible.

## Included Data

The repository copy in this folder includes the default Allen atlas files in
`data/atlas/`:

- `P56_Atlas.nii.gz`
- `ABA_v3_P56_Annotation_downloaded.nii.gz`
- `ABA_v3_structure_graph.json`

If you do not want to commit these large data files to GitHub, remove
`data/atlas/*.nii.gz` before publishing and tell users to place the files back
in `data/atlas/`.

## Linux Install

Requirements: Python 3.10 to 3.12 is recommended.

```bash
git clone <your-repo-url>
cd InteractiveAtlas_program_github
bash scripts/install_linux.sh
./run.sh
```

Optional: install a terminal command named `atlas`.

```bash
bash scripts/install_atlas_command.sh
atlas
```

By default this creates `~/.local/bin/atlas`. Make sure `~/.local/bin` is in
your `PATH`.

## Windows Install

Requirements: Python 3.10 to 3.12 from <https://www.python.org/downloads/> is recommended.
During Python installation, enable "Add python.exe to PATH".

Open Command Prompt or PowerShell:

```bat
git clone <your-repo-url>
cd InteractiveAtlas_program_github
scripts\install_windows.bat
run_windows.bat
```

You can also double-click `run_windows.bat` after installation.

## Windows Portable EXE

Build the portable package on Windows:

```bat
scripts\build_windows_portable.bat
```

Or with PowerShell:

```powershell
.\scripts\build_windows_portable.ps1
```

The build creates:

```text
release\InteractiveAtlas_Windows_Portable.zip
```

Share this zip file with Windows users. They only need to unzip it and
double-click `InteractiveAtlas.exe`; Python does not need to be installed on the
target computer.

Build note: PyInstaller Windows executables should be built on Windows. A Linux
machine can prepare the source project, but it usually cannot reliably produce a
native Windows `.exe` for PyQt5, SciPy, scikit-image, matplotlib, and nibabel.

## Custom Atlas Paths

By default the app reads data from `data/atlas/`. You can override the default
files with environment variables:

Linux:

```bash
export ALLEN_ATLAS_ROOT=/path/to/ALLEN_atlas
export ATLAS_BASE_NII=/path/to/P56_Atlas.nii.gz
export ATLAS_ANNOTATION_NII=/path/to/ABA_v3_P56_Annotation_downloaded.nii.gz
export ATLAS_STRUCTURE_GRAPH_JSON=/path/to/ABA_v3_structure_graph.json
./run.sh
```

Windows PowerShell:

```powershell
$env:ALLEN_ATLAS_ROOT = "D:\Atlas\ALLEN_atlas"
$env:ATLAS_BASE_NII = "D:\Atlas\ALLEN_atlas\P56_Atlas.nii.gz"
$env:ATLAS_ANNOTATION_NII = "D:\Atlas\ALLEN_atlas\ABA_v3_P56_Annotation_downloaded.nii.gz"
$env:ATLAS_STRUCTURE_GRAPH_JSON = "D:\Atlas\ALLEN_atlas\ABA_v3_structure_graph.json"
.\run_windows.bat
```

## Runtime Files

The app creates runtime files under `data/`:

- `data/cache/`: generated atlas cache.
- `data/uploads/`: uploaded underlay files.
- `data/merges.json`: merge groups for the current run.
- `data/underlay.json`: uploaded underlay state.

The desktop app clears merge and uploaded-underlay state when it starts and
when it closes. Cache files are ignored by Git.

## Developer Notes

Run directly from source:

```bash
python3 -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
python main.py
```
