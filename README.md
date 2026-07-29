# CauseForge

> **A Budgeted Interventional Data Engine for Agent Improvement**
> 在明确的执行预算下，主动获取、验证并持续维护关于改写 Agent 任务结果的因果数据。

**状态：M1 立卡片已完成（端到端跑通，首个生死数字达标：flip 可复现率 100%）。** 本 README 是项目的合同：主张、路线、判死线都写在这里。

---

## 快速开始

```bash
python3 -m venv .venv && .venv/bin/pip install -e .
.venv/bin/python -m causeforge demo            # 一条命令端到端 demo
.venv/bin/python -m causeforge report runs/demo
.venv/bin/python -m causeforge regress runs/demo   # 重放导出的反事实回归用例
.venv/bin/python -m pytest tests/
```

Demo 输出（toy workload，9 任务 / 6 失败 / 7 候选干预）：

```text
units by tier       : {'SUGGESTED': 1, 'MINIMAL': 6}
determinism control : OK
FLIP REPRO RATE     : 100.0% (18/18 intervened replays flipped)  [kill line: >= 90%]
causal slicing      : 7 atoms -> 6 atoms
```

## 这是什么

Agent 在执行中产生大量轨迹，但原始 trace 是观察性的、单臂的，不随模型/prompt/工具/环境升级迅速失效。现有系统的共同盲点是**被动处理已经产生的日志**（存储、摘要、召回、导出）。CauseForge 打的是另一件事：

> Experience systems store what agents happened to try;
> **CauseForge actively acquires the causal experience that agents should learn from.**

系统主动决定：在哪条轨迹的哪个状态、施加什么类型的干预、fork 环境后成对反事实重放、验证结果是否真的翻转、最小化到最小因果切片，并物化为四类资产：

| 输出 | 用途 |
|---|---|
| Minimal correction pairs | SFT / 行为克隆 |
| Original/repaired branch pairs | DPO / preference learning |
| Failure-to-recovery units | Agent memory / skill library |
| Executable counterfactual cases | 回归测试 / Agent 版本评估 |

完整设计见 [docs/design.md](docs/design.md)。

## 核心闭环

```text
Agent Execution → Trace Collection → Candidate Screening
    → Snapshot / Fork / Intervention → Paired Counterfactual Replay
    → Effect Validation → Minimal Causal Slicing
    → SFT / DPO / Memory / Regression Views → Version-Aware Revalidation
```

四个核心抽象（`Episode` / `Snapshot` / `Intervention` / `Outcome`），最终数据单位是带证据等级的 `CausalUnit`：

`Observed → Suggested → Counterfactual-Validated → Reproducible → Minimal → Training-Validated`

任何 API 和展示中，证据等级永远随数据可见——不把弱证据包装成因果。

## 怎么证明它有用：三条证据链

| 证据链 | 内容 | 成本 |
|---|---|---|
| **A. 引擎自身高效** | flip 可复现率、每个 validated unit 的获取成本、prefix 复用节省、selective revalidation vs 全量重放 | 机器时间，无训练开销 |
| **B. 数据有价值** | matched-budget 下二组对照的下游效用（含零成本 baseline：不执行任何 replay 的 LLM 修正对） | 训练实验，唯一真正的赌注 |
| **C. 有人真用** | 一条命令 demo、开源、外部项目接入 Import Mode | 工程 + 社区 |

点亮顺序 A → B → C。B 翻车不毁项目：主线从"训练数据引擎"转向"Agent 回归测试与数据保鲜"，证据链 A 与 M4 实验原样保值。

## 路线图

- [x] **M0** 设计文档（[docs/design.md](docs/design.md)）
- [x] **M1 立卡片**：schemas → collector → 本地环境 snapshot/restore → paired replay → pytest verifier → SFT/DPO export → 玩具 demo 端到端跑通。**首个生死数字：flip 可复现率 = 100%（18/18，确定性子集）**
- [ ] **M1.5 workload**：自建 dependency-migration mini-bench（20–50 任务，锚定真实 breaking change：pydantic v2、pandas 2.x、numpy 2.0 等，PyMigBench 作候选来源）+ Docker 环境适配器
- [ ] **M2 获取优化器**：多保真筛选、adaptive singleton、sequential stopping、effect-signature 去重；产出 cost-per-unit 曲线 vs exhaustive/random
- [ ] **M3 存储与调度**：shared-prefix trace DAG、checkpoint placement；产出 replay 加速数据
- [ ] **M4 保鲜维护**：全链路 provenance、selective revalidation、用一次真实包版本升级做实验
- [ ] **训练 pilot（RQ1）**：二组 matched-token 对照，单一底座单一 LoRA 配置
- [ ] 论文骨架与 claim 表随 M1 起步并行推进（`experiments/claims.md`）

## 判死线（提前写死，不许挪动）

1. 纯净子集 flip 可复现率 **< 90%** → 停下修 determinism 或换 workload，不带病前进。**（M1 实测 100%，通过）**
2. RQ1 输给零成本 LLM 修正对 baseline → 当天转线到 regression/freshness 主线。
3. 连续两周没有产出新数字 → 项目跑偏，回到本表。

## 拿铁设计约束

- **只在 step 边界 fork。**Snapshot = 文件系统 + 显式声明状态，不承诺恢复运行中的进程（无 CRIU 依赖）。
- **副作用分级执行。**工具声明 `PURE / IDEMPOTENT / REVERSIBLE / TRANSACTIONAL / EXTERNAL_SIDE_EFFECT`；EXTERNAL 不得进行真实重放，只允许 mock/dry-run。
- **Recorded replay 优先，LLM 响应全量缓存。**Live paired replay 只留给策略分支——这是成本存活机制，不是可选优化。
- **成本记账从第一行代码开始。**token/时间/美元入账，总成本是论文横轴，事后补记等于造假。
- **不依赖任何未经核实的外部资产。**workload 自建或选用公开数据集。

## 第一版范围纪律

**做**：Python SDK、本地/Docker 环境适配器、pytest verifier、`ActionReplace` + `ToolArgumentEdit` 两种干预、paired replay、causal slicing、四种 export、一条命令 demo。

**冻结**（直到证据链亮两条）：Web UI、多框架 adapter、PostgreSQL、OpenTelemetry、remote workers、通用化 API 打磨。

## 仓库结构

```text
causeforge/
├── sdk/            # schemas（四个核心抽象 = 论文 Contribution 1）
├── runtime/        # collector、agent policy、pytest verifier
├── store/          # content-addressed blob store（trace DAG 属 M3）
├── replay/         # sandbox、recorded/paired replay
├── interventions/  # ActionReplace、ToolArgumentEdit + 原子分解
├── acquisition/    # screener（adaptive singleton、stopping 属 M2）
├── slicing/        # ddmin 最小因果切片
├── compiler/       # sft / dpo / memory / regression 四种导出
├── maintenance/    # provenance、selective revalidation 钩子
├── workloads/      # toy workload（M1.5 换 dependency-migration bench）
├── pipeline.py     # 端到端编排
├── run_store.py    # run 目录持久化（自包含、可重执行）
└── cli.py          # demo / report / regress
experiments/        # claims.md（claim → 实验 → 阈值）
docs/               # design.md
tests/              # 24 项单测 + E2E（判死线以 CI 断言形式存在）
```

## 开发环境约定

一切安装发生在项目内（`.venv`），不安装全局。macOS 只做开发机；论文性能数字（replay throughput 等）在 Linux 上测。
