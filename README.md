# 技术文档

[牵引引导与全身柔顺控制](traction_compliance/output/pdf/traction_compliance_review.pdf)

包含问题定义、Cerebrix H6 代码分析、相关论文方案和评价协议。LaTeX 源码与参考文献位于 `traction_compliance/`。

## 编译

安装 Tectonic，或包含 CTeX/Fandol 字体的 XeLaTeX 与 latexmk，然后运行

```bash
cd traction_compliance
./build.sh
```

Tectonic 使用固定的 `tlextras-2022.0r0` 包快照，首次运行需要联网获取 TeX 包。可通过 `TECTONIC_BUNDLE` 环境变量指定本地包或镜像。已提交图表可直接用于编译。重新生成解析图时，使用安装了 `numpy` 和 `matplotlib` 的 Python 运行

```bash
python3 scripts/plot_reference.py
```

输出为 `output/pdf/traction_compliance_review.pdf`。`build/` 和临时文件不纳入版本控制。

文档以代码提交 `57a05ee00d229da6fd6f10defcc51e947247d6c6` 为依据，检索日期为 2026-11-13。图表由公式生成，文中实验矩阵为待执行方案。
