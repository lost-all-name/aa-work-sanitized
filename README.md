# aa-work-sanitized · Local Count Summary

一个可运行、可测试的 Python 通用计数汇总示例。输入三列 CSV，按组汇总总数与通过数，使用统一的演示阈值比较，输出本地 JSON 和静态 HTML 报告。

本项目的实现、数据格式、页面和测试均独立编写。示例数据为手工构造的虚拟计数，不包含任何公司的连接信息、客户标识、生产样本或专用业务规则。

## 功能

| 能力 | 说明 |
| --- | --- |
| 分组汇总 | 自动合并同组记录，按组名稳定排序 |
| 精确比较 | 使用整数比较判定是否达到统一阈值，不受显示舍入影响 |
| 严格输入 | 检查表头、字段数量、组名和计数范围，错误时不输出报告 |
| 本地报告 | 同时生成机器可读的 JSON 和可直接打开的 HTML |
| 发布检查 | 固定源码清单、合成样本摘要、暂存区检查与可重复打包 |

适合学习数据校验、分组聚合、命令行工具、单元测试和源码发布流程。所有组使用相同规则，演示阈值可由命令行调整。

## 快速运行

需要 Python 3.10 或更新版本，仅使用标准库，无需安装第三方包、Excel、浏览器扩展或账号。

在项目根目录执行：

```powershell
python -m quality_summary
```

默认读取 `examples/synthetic.csv`，在 `build/` 中生成：

- `summary.json`：结构化汇总结果。
- `summary.html`：可在浏览器直接打开的静态报告，无 JavaScript、外部资源或联网链接。

默认示例包含 4 条记录、3 个组，总数 92，通过数 78。`sample_a` 的两条记录会合并，总体通过率按计数加权。

默认运行结果如下，判定阈值为 80%：

| 分组 | 总数 | 通过数 | 通过率 | 判定 |
| --- | ---: | ---: | ---: | --- |
| overall | 92 | 78 | 84.7826% | 达到演示阈值 |
| sample_a | 50 | 43 | 86.0000% | 达到演示阈值 |
| sample_b | 25 | 24 | 96.0000% | 达到演示阈值 |
| sample_c | 17 | 11 | 64.7059% | 低于演示阈值 |

HTML 和 JSON 中的 `pass_rate` 使用 0 到 1 的小数比例，例如 `0.860000` 表示 86%。

## 自定义输入与演示条件

```csv
group,total,passed
sample_a,37,31
sample_b,25,24
sample_c,17,11
sample_a,13,12
```

表头必须依次为 `group,total,passed`。组名仅接受以小写字母开头的小写字母、数字和下划线，长度最多 40；计数为非负整数，满足 `0 <= passed <= total` 且 `total > 0`。每行总数最多为万亿，输入最多 10 万条。

```powershell
python -m quality_summary --input examples/synthetic.csv --output build/strict --minimum-pass-rate 0.9
```

比较标准可以设置为 0 到 1 的数值，最多六位小数。默认 `0.8` 仅为虚构示例条件，不代表生产标准。决策使用精确整数比较，显示比例保留六位小数，不影响边界判定。所有组使用完全相同的逻辑。

自定义输入和报告不会自动脱敏：它们包含你提供的组名和计数。请将私人数据留在本地 `build/` 中，勿放入示例目录或加入发布包。程序不打印输入行和异常中的文件路径。

## 验证与打包

```powershell
python -m unittest discover -s tests -v
python tools/release.py check
python tools/release.py build
```

打包产物位于 `dist/quality-summary-demo.zip`，使用固定文件清单，不递归打包整个工作目录。源码包只含文档、代码、测试和固定摘要的合成示例，并附相对路径和 SHA256 清单。运行结果、虚拟环境、Git 元数据和本机文件不进入包中。

解压后进入 `quality-summary-demo` 文件夹，即可运行上述命令。包内的 `RELEASE_MANIFEST.json` 用于校验文件；它由打包工具生成。

GitHub Actions 配置在 Windows 与 Linux 上运行测试和发布检查。本地整理和打包不会创建 GitHub 仓库或上传文件。

## 结构与许可

- `quality_summary/core.py`：纯数据校验与分组汇总。
- `quality_summary/reports.py`：CSV 输入与本地报告生成。
- `quality_summary/__main__.py`：命令行入口。
- `tests/`：功能与发布边界测试。
- `tools/release.py`：发布检查、确定性打包与完整性验证。

许可：[MIT](LICENSE)。发布内容和运行时数据的边界见 [PRIVACY.md](PRIVACY.md)。
