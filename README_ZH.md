# CauseForge

> **A Budgeted Interventional Data Engine for Agent Improvement**
> 在有限执行预算下，主动获取、验证并持续维护真正改变 Agent 任务结果的因果数据。
> English front page: [README.md](README.md) · License: Apache-2.0

**状态：M1–M4 + B 链完成，证据链 A 全部点亮（A1–A10）。** 48 项测试全绿；live agent（Qwen2.5-7B on vLLM）真实开奖：flip 可复现率 100%（15/15）、对照支 digest 匹配率 100%、机制层省 26% replay、selective revalidation 省 4.8–8.0× 且零漏降级、fork 加速 298×；两个 ≤80 行案例复现已发表管线家族；TRL/verl 导出直通。详细数字与出处见 [experiments/claims.md](experiments/claims.md)。本 README 是项目的合同：主张、路线、判死线都写在这里。

## 快速开始

```bash
python3 -m venv .venv && .venv/bin/pip install -e .
.venv/bin/python -m causeforge demo             # 一条命令端到端 demo
.venv/bin/python -m causeforge report runs/demo
.venv/bin/python -m causeforge regress runs/demo  # 重放导出的反事实回归用例
.venv/bin/python -m pytest tests/
```

## 这是什么

Agent 在执行中产生大量轨迹，但原始 trace 是观察性的、冗余的，且随模型/prompt/工具/环境升级迅速失效。现有系统的共同点是**被动处理已经产生的日志**（存储、打分、切分、导出）。CauseForge 做的是另一件事：

> Experience systems store what agents happened to try;
> **CauseForge actively acquires the causal experience that agents should learn from.**

系统主动决定：在哪条轨迹的哪个状态、施加什么类型的干预、fork 环境做成对反事实重放、验证结果是否真的翻转、提取最小因果单元，并物化为四类资产：

| 输出 | 用途 |
|---|---|
| Minimal correction pairs | SFT / 行为克隆 |
| Original/repaired branch pairs | DPO / preference learning |
| Failure-to-recovery units | Agent memory / skill library |
| Executable counterfactual cases | 回归测试 / Agent 版本评估 |

完整设计见 [docs/design.md](docs/design.md)。

## 生态位：一个"因果版 Data-Juicer"？

电梯稿可以这么讲，但精确的定位是站在 Data-Juicer 一族没有的那根轴上：

> Data-Juicer refines the data you already have;
> **CauseForge decides which executions to run to create the data you're missing — and proves each unit actually changed the outcome.**

| | Data-Juicer 家族（DJ 2.0 / Sandbox / Trinity-RFT） | CauseForge |
|---|---|---|
| 输入 | 已存在的语料 / 经验数据 | 可重放的 Agent 执行环境 |
| 核心动作 | 算子变换：清洗、过滤、去重、合成 | fork / 干预 / 成对反事实重放 |
| 质量信号 | 启发式统计、模型打分、训练反馈（池粒度、观察性） | verifier 结果翻转（unit 粒度、干预性、可复现） |
| 环境在闭环里 | 否 | **是——这是本质分界线** |
| 数据失效 | 重新跑一遍处理 | provenance 驱动的选择性重验证 |

- **生态策略**：不与 DJ 竞争，站它上游——validated causal units 可直接作为 DJ / Trinity-RFT 管线的高置信输入源。
- **时间压力**：Trinity-RFT 已把 DJ 接进 agent 经验管线（带优先级的 experience replay）。反事实验证和版本化失效的空位还在，但不会永远空着。
- **Related work 必引**：Data-Juicer 2.0（NeurIPS'25 D&B）、DJ Sandbox（ICML'25）、Trinity-RFT、AgentTrek。

## 干预性算子：把算子抽象从观察性推进到因果

核心设计（也是论文 Contribution 1 的新表述）：**扩展算子的类型签名**。

```text
DJ 算子:          Dataset → Dataset                # 纯变换，花 CPU/GPU 时间
CauseForge 算子:  (Units, Env, Budget) → Units'    # 可花真实执行预算，可提升证据等级
```

Budget 分两层，这是库的核心卖点（tree-search 造数据家族的头号痛点就是 rollout 成本）：

- **机制层（永远在线）**：成本记账、shared-prefix 复用、LLM 全量缓存、sequential stopping、多保真漏斗——用户跑任何策略都免费获得省钱层；
- **策略层（可插拔）**：我们的 acquisition optimizer 是默认调度策略之一，用户可自带策略（MCTS 展开、随机、穷举）在同一记账系统上运行——评估因此可以和已发表方法的真实策略同台比 cost-per-unit。

三类算子构成完整代数：

| 算子类 | 成员 | 环境 | 预算 | 证据等级效果 |
|---|---|---|---|---|
| 观察性（DJ 同款语义） | screen / rank / signature-dedup / 启发式切片 | 不需要 | 零 | 封顶 Suggested |
| **干预性（新物种）** | propose / fork+paired-replay / minimize / revalidate | 需要 | 真实执行成本 | 推进至 Counterfactual-Validated / Reproducible / Minimal |
| 编译 | sft / dpo / memory / regression | 不需要 | 零 | 不变，随视图携带 |

由此获得三个免费的统一：

- **三级接入模式 = 算子集合的三个子集 + 证据等级天花板。**Import Mode 只有观察性+编译算子；Tool Replay Mode 增加局部干预算子；Snapshot Mode 全量开放。
- **Acquisition optimizer = 配方调度器。**决定数据池中多大流量通过哪个贵算子——多保真漏斗成为配方语言的一等公民。
- **方向对称：repair 与 stress 是同一台机器。**干预算子无方向，目标函数有方向——repair 方向在失败轨迹上搜索 fail→pass 翻转（恢复数据）；stress 方向在成功轨迹上搜索 pass→fail 的最小扰动（鲁棒性报告、加强版回归测试、对抗课程 / hard negatives）。机制共享，只换目标符号。stress 方向为 v2；对外文案统一用 perturbation / stress-testing，不用 "attack"。
- **通用性边界**：任何领域只要提供可重放环境 + verifier，全部算子即可用；给不出的领域降级至 Import Mode。

实现边界：语义上与 DJ 兼容（units 可导出进 DJ/Trinity 管线），实现上不寄生——不在 data-juicer 代码库上开发，只做导出适配器。

## 库定位：N 篇论文的手搓循环 → 一个公共底座

2024–2026 已成型一个方法家族：从分支 / 反事实 rollout 造训练信号（MCTS→step-level DPO 对、TreeRL / Tree-GRPO / ARPO、rollout-tree 信用分配 RTMC / AT2PO、CCPO 的 SCM+ATE 信用、CriticSearch……）。每篇都在手搓同一个循环：**分支 → rollout → 比较 → 步级信号 → 编译**。CauseForge 的库主张：这个家族共享一个底座，我们把它做成库。

| 已发表方法家族 | 在 CauseForge 中的表达 |
|---|---|
| MCTS → step-level DPO 对 | fork + paired replay + DPO 编译算子 |
| Rollout-tree 信用分配（Tree-GRPO / RTMC / AT2PO） | shared-prefix trace DAG + paired outcomes |
| 反事实信用（CCPO 的 ATE） | paired replay 效应估计 $\widehat{\Delta}$ |
| Process reward 数据 | process-reward 视图编译算子 |
| HER 式 relabel | ObservationEdit / relabel 观察性算子 |

这个定位卸掉了 RQ1 赌局：方法有效性已由各原论文证明，我们的主张是底座——评估变为 (1) 表达力案例研究（≤100 行复现 2–3 个已发表方法的数据管线）、(2) 效率（DAG/缓存/预算调度 vs 各自的 naive 循环）、(3) 独有能力（证据等级、副作用安全、版本化保鲜）。

**Adoption 硬条件**：导出 verl / TRL 兼容格式；无状态环境（数学/推理任务的从前缀重采样）作为零成本特例支持——这是家族里最大的用户群，snapshot 在此退化为 prompt 前缀。有状态工具环境的 snapshot/fork/副作用管理是护城河，留给 code agent 场景。

## 核心闭环

```text
Agent Execution → Trace Collection → Candidate Screening
    → Snapshot / Fork / Intervention → Paired Counterfactual Replay
    → Effect Validation → Minimal Causal Slicing
    → SFT / DPO / Memory / Regression Views → Version-Aware Revalidation
```

四个核心抽象：`Episode` / `Snapshot` / `Intervention` / `Outcome`，最终数据单位是带证据等级的 `CausalUnit`：

`Observed → Suggested → Counterfactual-Validated → Reproducible → Minimal → Training-Validated`

任何 API 和展示中，证据等级永远随数据可见——不把弱证据包装成因果。

## 怎么证明它有用：证据链

| 证据链 | 内容 | 成本 |
|---|---|---|
| **A. 引擎自身高效** | flip 可复现率、每个 validated unit 的获取成本、prefix 复用节省、selective revalidation vs 全量重放 | 机器时间，无训练开销 |
| **B. 表达力** | 用算子抽象 ≤100 行复现 2–3 个已发表方法的数据管线（MCTS-DPO、rollout-tree 信用分配、HER relabel） | 工程，无训练开销 |
| **C. 数据有价值（加分项）** | matched-budget 下五组对照的下游效用（含零成本 baseline：不执行任何 replay 的 LLM 修正对） | 训练实验；库定位下已非生死赌局 |
| **D. 有人真用** | 一条命令 demo、开源、verl/TRL/DJ 导出适配、外部项目接入 Import Mode。宣传时机：A+B 数字亮了再出去说话；主渠道是 integration PR（verl/TRL 导入、awesome-list、DJ 适配器），不是发帖 | 工程 + 社区 |

点亮顺序 A → B → D，C 择机做。C 翻车不毁项目：库的价值主张由 A+B+D 支撑，训练主张降级为其中一个应用；A 与 M4 实验原样保值。

## 路线图

- [x] **M0** 设计文档（[docs/design.md](docs/design.md)）
- [x] **M1 竖切面**：schemas → collector → 本地环境 snapshot/restore → paired replay → pytest verifier → 四种 export → 玩具 demo 端到端跑通。实测：flip 可复现率 18/18 = 100%（玩具上界）、9 episodes、7→6 causal atoms（ddmin 切片）、cost ~2.2s/unit、判死线进 CI（`tests/test_e2e_demo.py`）。M1.5 需补报：live agent 下的对照支 digest 匹配率
- [x] **M1.5 workload**：depmig mini-bench 30 任务 / 5 家族（pydantic、numpy、sqlalchemy、click、networkx），pass-old/fail-new 双向认证 30/30（`causeforge bench-build`）；live 采集（7B agent + 异构 fixer 池）flip 可复现率 **100% (15/15)**、digest 匹配率 **100%**、agent 解题 11/30 零作弊。发现：候选**来源**多样性 ≻ 模型强度（失败转化 6/19→9/19）。Docker 缺席，venv 隔离降级方案落地；pandas 家族（py3.11 底座）为 stretch
- [x] **M2 预算层 + 获取优化器**：机制层（对照支 memoization + 复现早停）实测省 **26%** replay；策略层（exhaustive/random/adaptive 可插拔 + matched-budget 曲线 `causeforge acquire-eval`）在 55 候选规模下为诚实 null（全部收敛，放大条件已记录）
- [x] **M3 存储与调度**：内容寻址隐式 trace DAG（共享 **2.3×**、省 56.6% 字节）；checkpoint placement（every/every_k/first）+ 前缀重执行 fork（状态重建 digest 等价）；fork 加速 **298.6×** vs 全量重放（`causeforge storage-bench`）
- [x] **M4 保鲜维护**：按家族依赖声明的 provenance + selective revalidation（`causeforge revalidate`）；两次真实版本事件：pydantic 升级 **4.8×**、click 回滚 **8.0×** 节省，降级集 selective≡full 零漏报（回滚事件演示 control-drift 失效类）
- [x] **案例研究（证据链 B）**：`examples/case_step_dpo.py`（**76 行**：tree-sampling→步级 DPO+PRM，live 跑通）、`examples/case_credit_ate.py`（**53 行**：CCPO 式反事实步级信用，离线零重放）；TRL-SFT/TRL-DPO/verl-parquet 导出（`causeforge export`）
- [ ] **训练 pilot（RQ1，加分项）**：五组 matched-token 对照，同一基座同一 LoRA 配置
- [ ] **(v2) CauseForge Sandbox**：小成本下游代理信号（LoRA 探针 / memory 命中率 / regression 通过率）反馈校准 acquisition optimizer——把 TransferEstimate 从静态启发式变成自校准闭环。与 DJ Sandbox 平行："他们 co-develop 数据配方与模型，我们 co-develop 干预策略与 Agent"。依赖 M1–M4 全部就位，v1 冻结
- [ ] 论文骨架与 claim 表随 M1 起步并行推进（[experiments/claims.md](experiments/claims.md)）

## 判死线（提前写死，不许恋战）

1. 纯净子集 flip 可复现率 **< 90%** → 停下修 determinism 或换 workload，不带病前进。
2. RQ1 输给零成本 LLM 修正对 baseline → 当天转线到 regression/freshness 主线。
3. 连续两周没有产出新数字 → 项目跑偏，回到本表。

## 承重设计约束

- **只在 step 边界 fork。**Snapshot = 文件系统 + 显式声明状态，不承诺恢复进行中的进程（无 CRIU 依赖）。
- **副作用分级执行。**工具声明 `PURE / IDEMPOTENT / REVERSIBLE / TRANSACTIONAL / EXTERNAL_SIDE_EFFECT`；EXTERNAL 一律禁止真实重放，只允许 mock/dry-run。
- **Recorded replay 优先，LLM 响应全量缓存。**Live paired replay 只留给过筛候选——这是成本活命机制，不是可选优化。
- **成本记账从第一行代码开始。**token/时间/美元入账，总成本是论文横轴，事后补记等于重跑。
- **不依赖任何未经核实的外部资产。**workload 自建或采用公开数据集。

## 第一版范围纪律

**做**：Python SDK、本地/Docker 环境适配器、pytest verifier、`ActionReplace` + `ToolArgumentEdit` 两种干预、paired replay、causal slicing、四种 export、一条命令 demo。

**冻结**（直到证据链亮两条）：Web UI、多框架 adapter、PostgreSQL、OpenTelemetry、remote workers、通用化 API 打磨。

## 规划的仓库结构

```text
causeforge/
├── sdk/            # schemas（四个核心抽象 = 论文 Contribution 1）
├── runtime/        # collector、agent adapter
├── store/          # trace DAG、blob store、checkpoint policy   (M3)
├── replay/         # sandbox、recorded/paired replay
├── interventions/  # ActionReplace、ToolArgumentEdit、…
├── acquisition/    # screener、adaptive singleton、stopping     (M2)
├── slicing/        # delta debug、minimal context
├── compiler/       # sft / dpo / memory / regression
├── maintenance/    # provenance、selective replay               (M4)
└── cli.py
experiments/        # claims.md（claim → 实验 → 阈值）、pilot 脚本
docs/               # design.md
```

## 开发环境约定

一切安装圈定在项目内（`.venv`），不做全局安装。macOS 只作开发机；论文性能数字（replay throughput 等）在 Linux 上测。
