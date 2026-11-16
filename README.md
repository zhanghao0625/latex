# 技术文档

[牵引引导与全身柔顺控制](traction_compliance/main.pdf)

包含问题定义、旧版 Cerebrix H6 基线分析、当前纯牵引方法、相关工作和评估协议。LaTeX 源码与参考文献位于 `traction_compliance/`。

章节源码位于 [`traction_compliance/chapters/`](traction_compliance/chapters/)，包含 6 个正文章节和 1 个附录。各章采用 `序号-英文章节名称.tex` 命名，从 `1` 开始按章节顺序编号，所有 `.tex` 文件直接放在该目录下，由 `traction_compliance/main.tex` 统一加载和编译。

## 编译

安装包含 CTeX/Fandol 字体的 XeLaTeX 与 latexmk，或安装 Tectonic，并将编译工具加入 `PATH`。在仓库根目录运行

```bash
sh traction_compliance/build.sh
```

脚本优先使用 XeLaTeX 与 latexmk，也支持 Tectonic。当前中文稿为 `main.tex`，编译生成同目录下的 `main.pdf`。添加 `main_cn.tex` 后，脚本会同时生成 `main_cn.pdf`。辅助产物统一保存在论文目录下的 `tmp/`，该目录不纳入版本控制。

Tectonic 使用固定的 `tlextras-2022.0r0` 包快照，首次运行需要联网获取 TeX 包。可通过 `TECTONIC_BUNDLE` 环境变量指定本地包或镜像。现有图表可直接用于编译。重建旧版参考图时，使用含 NumPy、Matplotlib 和 PyTorch 的环境，并指定已检出审阅提交的旧代码目录。

```bash
python3 traction_compliance/scripts/plot_reference.py --source-repo /path/to/cts-moe-him
```

旧版 H6 基线依据 `cts-moe-him` 提交 `57a05ee00d229da6fd6f10defcc51e947247d6c6`，当前纯牵引方法和评分协议依据 `vbot` 提交 `1810875`。参考速度图为公式计算结果。
