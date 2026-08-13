<p align="right">
  <a href="README.md"><img src="https://img.shields.io/badge/Language-English-0969DA" alt="English README"></a>
  <a href="README_zh.md"><img src="https://img.shields.io/badge/Language-简体中文-D73A49" alt="简体中文 README"></a>
</p>

# Interactive Allen Atlas

一款用于 Allen CCFv3 P56 小鼠脑图谱及注释可视化的 PyQt5 桌面应用。

Interactive Allen Atlas 可以帮助你快速、流畅地浏览、搜索、合并并导出标注脑区。

## 主要功能

- 三视图：矢状位、冠状位和轴位。
- **Mosaic 视图**：支持方向、起始/结束层面、行数、列数和切片步长设置。
- 脑区树：包含所有父级与子级结构。
- **脑区搜索**：支持简称、全称、结构 ID 和层级路径搜索。
- **半球筛选**：可选择双侧、左侧或右侧。
- **Overlay 模式**：填充、仅填充所选、轮廓、仅轮廓所选，以及填充/轮廓组合模式。
- 自定义 **merge** 组：每个合并组可使用统一颜色显示。
- 可选显示脑区简称、方向标识、以 mm 为单位的 XYZ 坐标、十字线、悬停识别、比例尺和 color bar。
- 可调节 underlay 对比度。
- 支持上传 underlay，并提供 perm/flip 方向控制。
- PDF 导出：在可能的情况下，文字以可编辑文本形式输出。

## 截图

### 主界面

<img width="1920" height="1032" alt="Interactive Allen Atlas main workspace" src="https://github.com/user-attachments/assets/0eedeb9f-3f2c-436d-93ff-368bc9413117" />

### Mosaic 视图

<img width="1463" height="1009" alt="Mosaic view" src="https://github.com/user-attachments/assets/d106ae3a-41b3-413c-b929-56b7fbe20516" />

### 脑区搜索

搜索结果可匹配结构简称、全称、ID 或层级路径。选中脑区后，可以快速跳转到该脑区对应的视图位置。

<img width="467" height="737" alt="Region search" src="https://github.com/user-attachments/assets/88251af0-1118-4cb7-b7d6-c0b5e1a7d29d" />

### Overlay 模式

这些 overlay 模式适合聚焦查看所选父级结构、子结构、合并区域或轮廓边界。

| 仅填充所选 | 仅轮廓所选 |
| --- | --- |
| <img width="504" height="745" alt="Fill selected overlay mode" src="https://github.com/user-attachments/assets/9ddb7862-423c-420d-b40f-1b08854d244e" /> | <img width="526" height="745" alt="Selected contour overlay mode" src="https://github.com/user-attachments/assets/3cda0093-7de0-4f6c-bfe1-47627d3e71cc" /> |

| 简称填充 | 普通填充 | 简称轮廓 |
| --- | --- | --- |
| <img width="691" height="780" alt="Label fill overlay mode" src="https://github.com/user-attachments/assets/9b755cb2-72ea-4ec8-922b-e3c51ed2ccc4" /> | <img width="509" height="758" alt="Standard fill overlay mode" src="https://github.com/user-attachments/assets/9e36b486-69e9-40be-90db-e41a68d50e32" /> | <img width="695" height="749" alt="Label contours overlay mode" src="https://github.com/user-attachments/assets/45d7c1b8-237c-4426-9beb-e6f9ca008820" /> |

### Merge 组

Merge 组可将多个结构合并，并以同一种自定义颜色显示，也可用于重新赋色感兴趣区域。

<img width="1923" height="1029" alt="Merge groups" src="https://github.com/user-attachments/assets/fad570be-25dc-41bd-b36f-c33e965efdac" />

## 附带数据

仓库中已包含默认 Allen 图谱数据，位于 `data/atlas/`：

- `P56_Atlas.nii.gz`
- `ABA_v3_P56_Annotation_downloaded.nii.gz`
- `ABA_v3_structure_graph.json`

如果你不想将这些较大的数据文件提交到 GitHub，可以在发布前移除
`data/atlas/*.nii.gz`，并告知用户自行放回 `data/atlas/` 目录。

## 安装方式

### Linux

要求：推荐 Python 3.10 到 3.12。

```bash
git clone <your-repo-url>
cd InteractiveAtlas_program_github
bash scripts/install_linux.sh
./run.sh
```

可选：安装一个名为 `atlas` 的终端命令。

```bash
bash scripts/install_atlas_command.sh
atlas
```

默认会创建 `~/.local/bin/atlas`。请确保 `~/.local/bin` 已加入你的 `PATH`。

### Windows

要求：推荐 Python 3.10 到 3.12，下载地址：<https://www.python.org/downloads/>。安装 Python 时请勾选 **Add python.exe to PATH**。

在命令提示符或 PowerShell 中执行：

```bat
git clone <your-repo-url>
cd InteractiveAtlas_program_github
scripts\install_windows.bat
run_windows.bat
```

安装完成后，也可以直接双击 `run_windows.bat` 启动。

### Windows 便携版 EXE

下载仓库 **Releases** 页面中的 `.zip` 文件，解压后运行：

```text
InteractiveAtlas_Windows_Portable\InteractiveAtlas.exe
```

便携版在目标电脑上不需要安装 Python。

## 自定义图谱路径

默认情况下，程序会从 `data/atlas/` 读取数据。你也可以通过环境变量覆盖默认路径。

Linux：

```bash
export ALLEN_ATLAS_ROOT=/path/to/ALLEN_atlas
export ATLAS_BASE_NII=/path/to/P56_Atlas.nii.gz
export ATLAS_ANNOTATION_NII=/path/to/ABA_v3_P56_Annotation_downloaded.nii.gz
export ATLAS_STRUCTURE_GRAPH_JSON=/path/to/ABA_v3_structure_graph.json
./run.sh
```

Windows PowerShell：

```powershell
$env:ALLEN_ATLAS_ROOT = "D:\Atlas\ALLEN_atlas"
$env:ATLAS_BASE_NII = "D:\Atlas\ALLEN_atlas\P56_Atlas.nii.gz"
$env:ATLAS_ANNOTATION_NII = "D:\Atlas\ALLEN_atlas\ABA_v3_P56_Annotation_downloaded.nii.gz"
$env:ATLAS_STRUCTURE_GRAPH_JSON = "D:\Atlas\ALLEN_atlas\ABA_v3_structure_graph.json"
.\run_windows.bat
```

## 运行时文件

程序会在 `data/` 下生成运行时文件：

- `data/cache/`：自动生成的图谱缓存。
- `data/uploads/`：上传的 underlay 文件。
- `data/merges.json`：当前运行的合并组。
- `data/underlay.json`：上传 underlay 的状态。

桌面版会在启动和关闭时清空 merge 与 uploaded-underlay 状态。缓存文件会被 Git 忽略。

## 规划

未来可能会尝试其它图谱资源，例如 human brain atlas。

## 开发说明

从源码直接运行：

```bash
python3 -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
python main.py
```

在 Windows 上构建便携版：

```bat
scripts\build_windows_portable.bat
```

## 许可证

本仓库中的源代码采用 MIT License。

随仓库附带的 Allen Institute 图谱数据不受 MIT License 约束，
仍受 Allen Institute Terms of Use 和 Citation Policy 的约束。使用或再分发
这些图谱数据时，请遵守相关条款。
