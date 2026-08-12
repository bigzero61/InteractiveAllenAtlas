# Interactive Allen Atlas

A PyQt5 desktop viewer for the Allen CCFv3 P56 mouse brain atlas and annotation.

Interactive Allen Atlas lets you quickly and smoothly view, search, merge, and export annotated brain regions from the adult mouse brain.

中文版本: [README_zh.md](README_zh.md)

## Highlights

- Three orthogonal views: sagittal, coronal, and axial.
- **Mosaic view** with axis, start/end anchor, row count, column count, and slice step.
- Brain-region tree containing both parent and child structures.
- **Search** by acronym, full name, structure id, or hierarchy path.
- **Hemisphere filter**: both, left, or right.
- **Overlay modes**: fill, fill selected, contour labels, contour selected, and combined fill/contour modes.
- Custom **merge** groups with one display color per merged group. (Trick: With this feature, you can easily change the color of any region(s) as you like.)
- Optional display of acronyms, orientation labels, XYZ coordinates in mm, crosshair, hover lookup, scale bar, and color bar.
- Adjustable underlay contrast.
- Underlay (.nii.gz/.nii format) upload with perm/flip orientation controls. (Note: you should register your underlay image to the atlas first. But the good thing is you don't need to change your image to the same orientation.)
- PDF export with **editable text** labels where possible.

## Screenshots

### Main Workspace

<img width="1920" height="1032" alt="Interactive Allen Atlas main workspace" src="https://github.com/user-attachments/assets/0eedeb9f-3f2c-436d-93ff-368bc9413117" />

### Mosaic View

<img width="1463" height="1009" alt="Mosaic view" src="https://github.com/user-attachments/assets/d106ae3a-41b3-413c-b929-56b7fbe20516" />

### Region Search

Search results can match structure acronyms, full names, ids, or hierarchy paths.
Selecting a region can quickly move the views to that region.

<img width="467" height="737" alt="Region search" src="https://github.com/user-attachments/assets/88251af0-1118-4cb7-b7d6-c0b5e1a7d29d" />

### Overlay Modes

The overlay modes make it easy to focus on selected parent structures, child
structures, merged regions, or contour boundaries.

| Fill selected | Selected contour |
| --- | --- |
| <img width="504" height="745" alt="Fill selected overlay mode" src="https://github.com/user-attachments/assets/9ddb7862-423c-420d-b40f-1b08854d244e" /> | <img width="526" height="745" alt="Selected contour overlay mode" src="https://github.com/user-attachments/assets/3cda0093-7de0-4f6c-bfe1-47627d3e71cc" /> |

| Label fill | Standard fill | Label contours |
| --- | --- | --- |
| <img width="691" height="780" alt="Label fill overlay mode" src="https://github.com/user-attachments/assets/9b755cb2-72ea-4ec8-922b-e3c51ed2ccc4" /> | <img width="509" height="758" alt="Standard fill overlay mode" src="https://github.com/user-attachments/assets/9e36b486-69e9-40be-90db-e41a68d50e32" /> | <img width="695" height="749" alt="Label contours overlay mode" src="https://github.com/user-attachments/assets/45d7c1b8-237c-4426-9beb-e6f9ca008820" /> |

### Merge Groups

Merge groups let you combine multiple structures and display them with one custom
color. This can also be used to recolor a region of interest.

<img width="1923" height="1029" alt="Merge groups" src="https://github.com/user-attachments/assets/fad570be-25dc-41bd-b36f-c33e965efdac" />

## Included Data

This repository includes the default Allen atlas files in `data/atlas/`:

- `P56_Atlas.nii.gz`
- `ABA_v3_P56_Annotation_downloaded.nii.gz`
- `ABA_v3_structure_graph.json`

If you do not want to commit these large data files to GitHub, remove
`data/atlas/*.nii.gz` before publishing and tell users to place the files back
in `data/atlas/`.

## Installation

### Linux

Requirements: Python 3.10 to 3.12 is recommended.

```bash
git clone https://github.com/bigzero61/InteractiveAllenAtlas.git
cd InteractiveAtlas_program_github
bash scripts/install_linux.sh
./run.sh
```

Optional: install a terminal command named `atlas`.

```bash
bash scripts/install_atlas_command.sh
atlas
```

By default, this creates `~/.local/bin/atlas`. Make sure `~/.local/bin` is in
your `PATH`.

### Windows

Requirements: Python 3.10 to 3.12 from <https://www.python.org/downloads/> is
recommended. During Python installation, enable **Add python.exe to PATH**.

Open Command Prompt or PowerShell:

```bat
git clone <your-repo-url>
cd InteractiveAtlas_program_github
scripts\install_windows.bat
run_windows.bat
```

You can also double-click `run_windows.bat` after installation.

### Windows Portable EXE

Download the `.zip` file from the repository's **Releases** page, unzip it, and
run:

```text
InteractiveAtlas_Windows_Portable\InteractiveAtlas.exe
```

No Python installation is required for the portable Windows build.

## Custom Atlas Paths

By default, the app reads data from `data/atlas/`. You can override the default
files with environment variables.

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

The desktop app clears merge and uploaded-underlay state when it starts and when
it closes. Cache files are ignored by Git.

## Roadmap

Other atlas resources, such as human brain atlases, may be tested in future
versions.

## Developer Notes

Run directly from source:

```bash
python3 -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
python main.py
```

Build the portable Windows package on Windows:

```bat
scripts\build_windows_portable.bat
```

## License

The source code in this repository is released under the MIT License.

Bundled Allen Institute atlas data files are not covered by the MIT License.
They remain subject to the Allen Institute Terms of Use and Citation Policy.
Users are responsible for complying with those terms when using or redistributing
the atlas data.
