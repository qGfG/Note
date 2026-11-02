# 桌面便笺

参照 Windows 便笺的小窗口布局：淡黄色纸张、顶部操作栏、底部格式栏。每张便笺独立显示，支持始终置顶。

点击便笺后，上下工具栏会滑入；点击其他应用或桌面后，工具栏自动滑出，只显示纸张和正文。正文位置保持不动，置顶状态也保持不变。

双击 `启动便笺.pyw`，或执行 `python app.py`。需要 Python 3.10+（含 Tkinter），无第三方依赖。

- 顶部 **＋** 新建；**图钉** 切换始终置顶（金色实心表示开启）；**···** 打开颜色、其他便笺和退出菜单；**×** 保存并关闭当前窗口。
- 拖动顶部空白区域移动；拖动左右边调整宽度、上下边调整高度、四个角同时调整宽高。工具栏隐藏时也能缩放。窗口位置、大小及置顶状态会保留。
- 底部 **B / I / U / ab** 为选中文字切换加粗、斜体、下划线、删除线。
- 底部 **≡** 为当前行或选中行切换项目符号。列表内回车自动继续，空列表项回车结束列表。
- 底部图片按钮插入 PNG / GIF 图片，图片会复制到数据文件夹，不依赖原文件位置。
- 自动保存正文、格式和图片。关闭窗口不删除便笺，再次启动只恢复最后关闭的那一张。其他便笺可通过“··· → 打开便笺”打开。“退出所有便笺”时，下次恢复退出前正在使用的那一张。

快捷键：`Ctrl+N` 新建、`Ctrl+P` 切换置顶、`Ctrl+S` 保存。正文支持复制、粘贴及文字撤销；格式修改不参与文字撤销。

数据在 `EXE 所在文件夹（源码运行时为项目文件夹）`，其中 `notes.db` 存储便笺，`images` 存储插图。备份前退出所有便笺，再复制整个文件夹。旧版标题和正文会合并显示，已有内容保留。请避免同时重复运行多个应用实例编辑同一条便笺。

第一次从旧版升级时，由于还没有关闭记录，会选择一张最近编辑过且有内容的便笺。此后严格按最后关闭的便笺恢复，即使它是空白便笺。移动窗口、缩放及置顶只保存窗口设置，不会重写未编辑的正文。

自定义数据目录：`python app.py --data-dir .\my-notes`。

验证：`python -m unittest discover -s tests -v`。


## EXE portable build

Run dist/StickyNotes.exe directly; Python is not required. notes.db and images/ are stored alongside the EXE. On first launch, existing AppData/Local/NoteZxh data is copied automatically if no local notes.db exists. Keep the entire folder together when moving or backing up. Use a writable folder. Only one instance per data folder is allowed.
