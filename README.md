# 技术文档

[牵引引导与全身柔顺控制](traction_compliance/main.pdf)

包含问题定义、Cerebrix H6 代码分析、相关论文方案和评价协议。LaTeX 源码与参考文献位于 `traction_compliance/`。

## 编译

安装包含 CTeX/Fandol 字体的 XeLaTeX 与 latexmk，或安装 Tectonic，并将编译工具加入 `PATH`。在仓库根目录运行

```bash
sh traction_compliance/build.sh
```

脚本优先使用 XeLaTeX 与 latexmk，也支持 Tectonic。当前中文稿为 `main.tex`，编译生成同目录下的 `main.pdf`。添加 `main_cn.tex` 后，脚本会同时生成 `main_cn.pdf`。辅助产物统一保存在论文目录下的 `tmp/`，该目录不纳入版本控制。

Tectonic 使用固定的 `tlextras-2022.0r0` 包快照，首次运行需要联网获取 TeX 包。可通过 `TECTONIC_BUNDLE` 环境变量指定本地包或镜像。现有图表可直接用于编译。重新生成解析图时，使用安装了 `numpy` 和 `matplotlib` 的 Python 运行

```bash
python3 traction_compliance/scripts/plot_reference.py
```

文档以代码提交 `57a05ee00d229da6fd6f10defcc51e947247d6c6` 为依据，检索日期为 2026-11-13。图表由公式生成，文中实验矩阵为待执行方案。
