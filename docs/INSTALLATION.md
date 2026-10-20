# 运行环境与安装

## 支持范围

- 标准 64 位 CPython 3.11、3.12、3.13、3.14。
- Windows、macOS、Linux 桌面环境及现代浏览器；具体已执行的组合以 [Clean installation 工作流](https://github.com/threek-1/xrd-workbench/actions/workflows/compatibility.yml) 的绿色结果为准。
- 安装时需能访问 Python 包索引。项目提供源码与依赖声明，不附带 Python 解释器和离线依赖全集。
- 暂不支持 Python 3.10 及更早版本、3.15 及更新版本、32 位 Python、PyPy 或自由线程构建。Windows ARM、Linux ARM、旧系统和其他架构不能直接从 x64/Apple Silicon 的测试结果推断兼容。

这不是“任何电脑均可运行”的保证。系统架构、依赖轮子是否可用、网络和文件权限都会影响安装。安装脚本要求二进制依赖包可用，避免普通用户意外进入 C/C++ 编译流程。

## 安装入口

在完整解压或克隆的项目目录运行 `python3 install.py`（macOS/Linux）或 `py install.py`（Windows）。也可以指定解释器：

```text
python install.py --python /path/to/python --check
```

`--check` 只检查解释器，不安装。默认创建项目内的 `.venv`，也可通过 `--venv` 指定其他目录。安装结束后使用它打印的启动命令。若没有任何 Python 命令，先从 [Python 官方网站](https://www.python.org/downloads/) 安装标准 64 位发行版。

依赖声明在 `pyproject.toml`，包括 NumPy、SciPy、Matplotlib、pandas、Streamlit 和 PyMuPDF。pip 根据 Python 和操作系统解析兼容依赖。无需 Conda、模型 API 或 Nature Skills；可选的额外绘图审查工具不属于运行依赖。

## 隔离测试

工作流在 GitHub 提供的独立运行器上执行，不挂载开发者电脑、不复用其 Python 环境，也不读取私人数据或技能目录。每个组合分别：

1. 将公开源码复制到带空格和中文的目录，通过安装脚本创建无系统包继承的虚拟环境。
2. 从项目目录以外启动，执行 CLI 分析、两类图四种格式导出、校验和检查及原始数据复现。
3. 用 Streamlit AppTest 检查表单、分析结果和报告，实际启动 HTTP 服务并检查健康端点。
4. 执行回归测试，构建源码包和 wheel。
5. 在另一个全新环境中只安装 wheel 及声明依赖，移除源码副本，再重复运行检查。

测试使用仓库内的合成示例，包含中文文件名。每个任务保存依赖清单、运行结果、示例输出和服务日志，供排错下载。工作流会在有测试失败时显示失败；配置了某个组合不等于该组合已经通过。

HTTP 健康检查和 AppTest 不等于真实浏览器对所有交互的全面验证，也不验证真实物相鉴定准确度。图形导出检查覆盖 PDF 文字尺寸、重叠和页面边界，实际用于论文前仍需检查最终尺寸输出。
