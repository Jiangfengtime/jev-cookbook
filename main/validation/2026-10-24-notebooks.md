# 全量 Notebook 验证记录 · 2026-10-24

已检查 37 本正式教程：37 本语法通过，34 本按当前运行条件执行到末尾，3 本因明确缺少前置条件停止。**执行到末尾不代表可选训练、对话和数据生成步骤全部执行**，逐本范围见下表。

25 本核心教程均从新内核访问 `main/.env` 配置的阿里云原生 System One 服务，模型为 `decision-model-preview`，共 225 次成功 SDK 请求，零离线回退。验证时故意注入旧进程的本机地址、模型和密钥，确认文件配置仍然生效。三本评测分别覆盖 231 个不同题目，所有结果为 `ok`，没有把提前停止的 `unattempted` 结果算作通过。未启动本地 Laya，未验证双模型对比。

验证环境为 Python 3.11、typesafe-sdk 0.7.0，使用 `main/.venv/bin/python`。Python 回归测试 17 项、DSH TypeScript 构建及 Node 测试 27 项通过；Notebook 迁移脚本重复执行修改数为 0。Python 回归在独立源码副本中清空执行输出后运行，避免用户保存的输出影响结构检查。所有执行副本均与当前 Notebook 源码逐格对齐（仅插入验证探针、替代重复安装单元格）。没有覆盖用户已保存的运行输出。

## 本次修复

- 扩展教程从仓库标记定位根目录，统一加载 `main/.env`，向子进程传递配置；修正目录重组后失效的应用、数据和外部项目路径。
- 智能家居先启动服务再请求，只清理本内核启动的进程；评测在独立临时目录转换并汇总仓库内题库，不覆盖旧实验。
- 评测适配器改用官方 SDK 传送嵌套 state；修正端点和模型传递、长题 token 预留，增加题目覆盖和逐题成功检查。
- Pi/DSH 支持配置的 System One 地址；DSH 接受缺失或 null 的输出 token 用量，保留为未知值。
- Jev-Mem 遇到服务端单次最多 16 题的限制时按问题分批，保留完整 state、候选和问题 ID；显式注入客户端，防止内部建图仍走旧客户端。模型及输出路径提示改为实际配置值。
- 训练开始前检查 CUDA；数据缺失时给出明确的跳过提示，不再启动必然失败的筛选子进程。

## 逐本结果

| Notebook | 执行状态 | 实际覆盖与限制 |
|---|---|---|
| [01_认识Jev/01_认识Jev.ipynb](../01_认识Jev/01_认识Jev.ipynb) | 真实 API 通过 | 6 次成功请求；零离线回退。 |
| [02_核心概念/01_SystemOne.ipynb](../02_核心概念/01_SystemOne.ipynb) | 真实 API 通过 | 3 次成功请求；零离线回退。 |
| [02_核心概念/02_状态.ipynb](../02_核心概念/02_状态.ipynb) | 真实 API 通过 | 6 次成功请求；零离线回退。 |
| [02_核心概念/03_原语.ipynb](../02_核心概念/03_原语.ipynb) | 真实 API 通过 | 27 次成功请求；零离线回退。 |
| [02_核心概念/04_置信度.ipynb](../02_核心概念/04_置信度.ipynb) | 真实 API 通过 | 24 次成功请求；零离线回退。 |
| [02_核心概念/05_应用构建.ipynb](../02_核心概念/05_应用构建.ipynb) | 真实 API 通过 | 13 次成功请求；零离线回退。 |
| [03_架构模式/01_架构模式.ipynb](../03_架构模式/01_架构模式.ipynb) | 真实 API 通过 | 20 次成功请求；零离线回退。 |
| [04_实战指南/01_自一致性Noul.ipynb](../04_实战指南/01_自一致性Noul.ipynb) | 真实 API 通过 | 6 次成功请求；零离线回退。 |
| [04_实战指南/02_自一致性Choice.ipynb](../04_实战指南/02_自一致性Choice.ipynb) | 真实 API 通过 | 6 次成功请求；零离线回退。 |
| [04_实战指南/03_并行提问.ipynb](../04_实战指南/03_并行提问.ipynb) | 真实 API 通过 | 6 次成功请求；零离线回退。 |
| [04_实战指南/04_重排序.ipynb](../04_实战指南/04_重排序.ipynb) | 真实 API 通过 | 5 次成功请求；零离线回退。 |
| [04_实战指南/05_逐行语义搜索.ipynb](../04_实战指南/05_逐行语义搜索.ipynb) | 真实 API 通过 | 5 次成功请求；零离线回退。 |
| [04_实战指南/06_结构恢复.ipynb](../04_实战指南/06_结构恢复.ipynb) | 真实 API 通过 | 5 次成功请求；零离线回退。 |
| [04_实战指南/07_函数调用.ipynb](../04_实战指南/07_函数调用.ipynb) | 真实 API 通过 | 2 次成功请求；零离线回退。 |
| [04_实战指南/08_技能推荐.ipynb](../04_实战指南/08_技能推荐.ipynb) | 真实 API 通过 | 6 次成功请求；零离线回退。 |
| [04_实战指南/09_实体对齐.ipynb](../04_实战指南/09_实体对齐.ipynb) | 真实 API 通过 | 5 次成功请求；零离线回退。 |
| [04_实战指南/10_RAG段落分类.ipynb](../04_实战指南/10_RAG段落分类.ipynb) | 真实 API 通过 | 7 次成功请求；零离线回退。 |
| [04_实战指南/11_引用核查.ipynb](../04_实战指南/11_引用核查.ipynb) | 真实 API 通过 | 5 次成功请求；零离线回退。 |
| [04_实战指南/12_LLM防护栏.ipynb](../04_实战指南/12_LLM防护栏.ipynb) | 真实 API 通过 | 13 次成功请求；零离线回退。 |
| [04_实战指南/13_SDE级联.ipynb](../04_实战指南/13_SDE级联.ipynb) | 真实 API 通过 | 4 次成功请求；零离线回退。 |
| [04_实战指南/14_日期抽取.ipynb](../04_实战指南/14_日期抽取.ipynb) | 真实 API 通过 | 5 次成功请求；零离线回退。 |
| [04_实战指南/15_预解析值抽取.ipynb](../04_实战指南/15_预解析值抽取.ipynb) | 真实 API 通过 | 9 次成功请求；零离线回退。 |
| [04_实战指南/16_层级分类.ipynb](../04_实战指南/16_层级分类.ipynb) | 真实 API 通过 | 25 次成功请求；零离线回退。 |
| [04_实战指南/17_自动研究特征发现.ipynb](../04_实战指南/17_自动研究特征发现.ipynb) | 真实 API 通过 | 6 次成功请求；零离线回退。 |
| [04_实战指南/18_基于置信度的分类.ipynb](../04_实战指南/18_基于置信度的分类.ipynb) | 真实 API 通过 | 6 次成功请求；零离线回退。 |
| [05_智能家居实验/01_智能家居实验.ipynb](../05_智能家居实验/01_智能家居实验.ipynb) | 执行结束 | 真实 Jev 文本决策通过；未配置 StepFun，未验证语音与聊天。 |
| [06_模型评测/01_模型评测.ipynb](../06_模型评测/01_模型评测.ipynb) | 执行结束 | 配置的 Jev 服务完成 231 道不同题目，全部 ok；本地 Laya 服务未启动，未做双模型对比。 |
| [06_模型评测/benchmark/notebooks/laya_vs_jev.ipynb](../06_模型评测/benchmark/notebooks/laya_vs_jev.ipynb) | 执行结束 | 配置的 Jev 服务完成 231 道不同题目，全部 ok；本地 Laya 服务未启动，未做双模型对比。 |
| [06_模型评测/llm_eval/notebooks/jevbench_intro.ipynb](../06_模型评测/llm_eval/notebooks/jevbench_intro.ipynb) | 执行结束 | 配置的 Jev 服务完成 231 道不同题目，全部 ok；本地 Laya 服务未启动，未做双模型对比。 |
| [07_实战应用/app/smart-home/smart_home_walkthrough.ipynb](../07_实战应用/app/smart-home/smart_home_walkthrough.ipynb) | 执行结束 | 真实 Jev 文本决策通过；未配置 StepFun，未验证语音与聊天。 |
| [08_前沿研究/jev_mem/jev_mem_scaling.ipynb](../08_前沿研究/jev_mem/jev_mem_scaling.ipynb) | 前置条件不足 | 缺少 DEEPSEEK_API_KEY / OPENAI_API_KEY；已修复路径、配置和分批逻辑，缩放实验未执行。 |
| [08_前沿研究/jev_mem/jev_mem_walkthrough.ipynb](../08_前沿研究/jev_mem/jev_mem_walkthrough.ipynb) | 执行结束 | 真实 Jev 建图和检索通过，审计无决策兜底；没有聊天模型 Key，跳过答案生成及评审对比。 |
| [09_Agent集成/01_Pi集成实验.ipynb](../09_Agent集成/01_Pi集成实验.ipynb) | 执行结束 | 用单独安装的 Pi CLI 验证三个实时决策命令；不代表自由对话 Agent 完整会话已验证。 |
| [09_Agent集成/02_DSH决策协作.ipynb](../09_Agent集成/02_DSH决策协作.ipynb) | 执行结束 | 原语与路由使用真实 Jev；对话案例按设计重放归档并运行测试，没有新跑对话模型。 |
| [10_本地模型/notebooks/full_v2_finetuning.ipynb](../10_本地模型/notebooks/full_v2_finetuning.ipynb) | 前置条件不足 | 本机无 CUDA GPU，前置检查明确停止；未下载训练权重或执行训练。 |
| [10_本地模型/notebooks/zh_dataset_construction.ipynb](../10_本地模型/notebooks/zh_dataset_construction.ipynb) | 执行结束 | 默认流程执行结束；原始 ShareGPT 数据缺失，API 生成和标注开关关闭，相关步骤明确跳过。 |
| [10_本地模型/notebooks/zh_head_finetuning.ipynb](../10_本地模型/notebooks/zh_head_finetuning.ipynb) | 前置条件不足 | 本机无 CUDA GPU，前置检查明确停止；未下载训练权重或执行训练。 |

## 还需要的条件

- 两本微调教程：NVIDIA CUDA GPU 及相应训练环境。当前机器不具备，未执行训练。
- `jev_mem_scaling`：在 `main/.env` 配置可用的 `DEEPSEEK_API_KEY`，或 `OPENAI_API_KEY` 与对应的 `OPENAI_BASE_URL`、`ANSWER_MODEL`。同样用于走读教程的答案生成与评审，Jev 决策密钥不能代替聊天模型密钥。
- Jev-Mem：安装外部项目并设置 `JEV_MEM_ROOT`；本次使用修订 `7ab0c73c6d8f4f611ad252c1e6ba8083f8df0e44`，未把外部源码提交进本仓库。Pi 另需可执行 CLI，并通过进程环境 `PI_EXE` 指定。本次用单独的临时安装验证，并未修改全局 CLI。
- 语音、聊天、本地 Laya 对比及真实数据标注按需提供各自服务、原始语料与密钥；本次没有把这些跳过步骤计为已实测。

## 复查方法

以下命令从仓库根目录执行；真实执行会使用服务额度。安装单元格在验证时跳过，应先准备依赖。

```bash
main/.venv/bin/python -m pip install -r main/requirements-extended.txt
main/.venv/bin/python main/generators/update_extended_notebooks.py
main/.venv/bin/python main/generators/validate_notebooks.py --scope all
main/.venv/bin/python main/generators/validate_notebooks.py --scope core --execute --test-stale-env --output /tmp/jev-core-validation
# 设置 JEV_MEM_ROOT、PI_EXE，按 DSH 工程说明安装并编译 Node 依赖后：
main/.venv/bin/python main/generators/validate_notebooks.py --scope all --execute --output /tmp/jev-full-validation
```

验证器将执行副本及 `results.json` 写入输出目录。`blocked_prerequisite` 需单独检查，不能当作完整通过。核心教程额外核对真实请求、服务地址、密钥来源及是否回退；评测额外核对题目 ID、数量和每题状态。其他扩展的可选步骤仍须结合逐本输出判断。

知识库镜像（`main/11_知识库`）、生成的验证预览、Notebook 模板和 checkpoint 不纳入这 37 本正式教程。

[机器可读记录](2026-10-24-notebooks.json)保存每本源码及执行产物摘要、评测覆盖和研究审计摘要。完整执行副本保留在本机 `/private/tmp/jev-full-validation-20261024`，不把包含大段运行结果的副本重新提交为教材源码。
