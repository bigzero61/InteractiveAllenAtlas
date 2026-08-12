# Interactive Allen Atlas

A PyQt5 desktop viewer for the Allen CCFv3 P56 brain atlas and annotation.
You are now able to view, search, merge and export the brain regions of adult mouse brain quickly and smoothly! 

## Features
<img width="1920" height="1032" alt="Snipaste_2026-08-12_15-49-10" src="https://github.com/user-attachments/assets/0eedeb9f-3f2c-436d-93ff-368bc9413117" />

- Three orthogonal views: sagittal, coronal, and axial.
- **Mosaic view** with axis, start/end anchor, row count, column count, and step.
<img width="1463" height="1009" alt="mosaic" src="https://github.com/user-attachments/assets/d106ae3a-41b3-413c-b929-56b7fbe20516" />
- Brain-region tree with all parent and child structures.
- **Search** by acronym, full name, id, or hierarchy path. Tick the region then the view would quickly reach the optimal slice.
<img width="467" height="737" alt="search" src="https://github.com/user-attachments/assets/88251af0-1118-4cb7-b7d6-c0b5e1a7d29d" />
- **Hemisphere filter**: both, left, or right.
- **Overlay modes**: fill, fill selected, contour labels, contour selected, and combined fill/contour modes. With this feature, you can easily focus only on the parent structures and ignore the child structures.
<img width="504" height="745" alt="fill_selectred" src="https://github.com/user-attachments/assets/9ddb7862-423c-420d-b40f-1b08854d244e" />
<img width="526" height="745" alt="fill_selected_tour" src="https://github.com/user-attachments/assets/3cda0093-7de0-4f6c-bfe1-47627d3e71cc" />
<img width="691" height="780" alt="fill_labeled" src="https://github.com/user-attachments/assets/9b755cb2-72ea-4ec8-922b-e3c51ed2ccc4" />
<img width="509" height="758" alt="fill" src="https://github.com/user-attachments/assets/9e36b486-69e9-40be-90db-e41a68d50e32" />
<img width="695" height="749" alt="contour_labels" src="https://github.com/user-attachments/assets/45d7c1b8-237c-4426-9beb-e6f9ca008820" />
- Custom **merge** groups with one display color per merged group. (Trick: So you can also **change the color** of the region of interest with your preferable color with this feature.)
<img width="1923" height="1029" alt="Snipaste_2026-08-12_15-51-25" src="https://github.com/user-attachments/assets/fad570be-25dc-41bd-b36f-c33e965efdac" />

- Optional display of acronyms (it is always located to the center of the region across slices), orientation labels, XYZ coordinate labels in mm, crosshair, hover lookup, scale bar, and color bar (and yes, you can adjust the contrast of the underlay templates).
- Underlay upload with **perm/flip orientation controls**. (Note: The uploaded images should be registered to the atlas first.)
- PDF export with text labels drawn as **editable PDF text** where possible.

## Included Data

The repository copy in this folder includes the default Allen atlas files in
`data/atlas/`:

- `P56_Atlas.nii.gz`
- `ABA_v3_P56_Annotation_downloaded.nii.gz`
- `ABA_v3_structure_graph.json`

### Coming soon
In the future, other atlas (e.g. human brain) would be tested if they work.

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

Download the .zip file in /Releases. Unzip the file and run "\InteractiveAtlas_Windows_Portable\InteractiveAtlas.exe"

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

## License

The source code in this repository is released under the MIT License.

Bundled Allen Institute atlas data files are not covered by the MIT License.
They remain subject to the Allen Institute Terms of Use and Citation Policy.
Users are responsible for complying with those terms when using or redistributing
the atlas data.
