# CauseForge 设计文档（M0/M1）

> A Budgeted Interventional Data Engine for Agent Improvement
> 本文是 README 主张的展开：抽象定义、闭环各阶段的语义、以及 M1 实现的落地决策。

## 1. 问题与主张

Agent trace 是观察性数据：它只记录 agent 恰好尝试过的那一条路径。要得到"如果第 k 步换一个动作，结局是否翻转"这样的因果结论，必须做干预实验。干预实验昂贵（fork 环境、重放、验证），因此系统的核心不是"能不能做反事实"，而是**在预算内最大化每美元/每分钟产出的已验证因果单元数**。

三个设计支柱：

1. **成对反事实重放**（paired counterfactual replay）：同一 snapshot fork 两支——原始支（determinism 对照）与干预支。只有对照支复现原始失败、干预支成功，才算一次有效 flip。
2. **证据阶梯**：数据单元的可信度是显式状态机，任何弱化（环境漂移）会降级，任何强化（复现实验、切片再验证、训练验证）才能升级。
3. **全程记账**：每次 LLM 调用、工具执行、重放都入账。成本是论文横轴。

## 2. 核心抽象（sdk/schemas.py）

| 抽象 | 语义 |
|---|---|
| `Episode` | 一次任务执行：步骤序列（动作 + 观测 + 观测摘要 digest + 缓存的 LLM 交互）+ 最终 `Outcome` + 成本账本 |
| `Snapshot` | step 边界处的状态：文件系统树（content-addressed digest）+ 显式声明状态。不承诺进程级恢复 |
| `Intervention` | 对某一步动作的修改：`ACTION_REPLACE`（整体替换工具调用）或 `TOOL_ARGUMENT_EDIT`（参数编辑，可分解为 set / per-line patch 原子） |
| `Outcome` | verifier 判定：success + passed/failed 计数 + 摘要。M1 verifier = pytest |
| `CausalUnit` | 终端资产：episode + 干预 + 双臂结局 + flip 判定 + 复现记录 + 最小切片 + 证据等级 + provenance + 成本 |

### 证据阶梯

```text
OBSERVED                 原始轨迹里出现过
SUGGESTED                screener 提出的候选（或验证失败退回）
COUNTERFACTUAL_VALIDATED 一次 paired replay 确认 flip
REPRODUCIBLE             n/n 次独立 fork 重放全部 flip
MINIMAL                  ddmin 切片后仍 flip，且切片后再验证通过
TRAINING_VALIDATED       下游训练实验证实增益（RQ1，M1 不涉及）
```

规则：所有导出行都带 `evidence_tier` 字段；编译器只导出 `COUNTERFACTUAL_VALIDATED` 及以上。

## 3. 闭环各阶段

### 3.1 采集（runtime/collector.py）

Collector 驱动一个 `Policy`（M1：`ScriptedPolicy`，确定性 mock-LLM，走与真 LLM 相同的记录接口）。每一步：

1. 在执行动作**之前**对 workspace 做 snapshot（这是 fork 点）；
2. 执行工具调用，记录观测与规范化观测 digest；
3. 缓存 LLM prompt/response/token 数（重放永不重新询问模型）。

episode 结束后由 pytest verifier 给出 `Outcome`。

### 3.2 筛选（acquisition/screener.py）

M1 版本：只选失败 episode，从 `CandidateSource` 收集候选干预，按 effect-signature（干预内容的 digest）去重。M1 的 source 是 workload 自带的修复表（模拟已缓存的 fixer-LLM，零 live token——账本如实记录为零）。M2 在同一接口上换上多保真筛选与 sequential stopping。

### 3.3 重放（replay/replayer.py）

- **Recorded replay**：从 snapshot 重放记录的动作序列，逐步比对观测 digest + 最终 outcome signature → determinism 判定。
- **Paired replay**：
  1. 对照支（原始动作）必须 `deterministic_match`，否则该候选直接退回 `SUGGESTED`（不许在不确定的地基上宣称因果）；
  2. 干预支在目标步应用干预，其余步骤按记录执行；
  3. flip := 原始失败 ∧ 干预成功；
  4. 再做 n−1 次独立 fork 重放，n/n 全 flip → `REPRODUCIBLE`。

副作用门控在执行器层强制：replay 模式下 `EXTERNAL_SIDE_EFFECT` 工具一律 dry-run mock，且其观测 digest 在 live/replay 两模式下规范化为同一占位符，不污染 determinism 判定。

### 3.4 切片（slicing/ddmin.py）

把干预分解为原子（每个 ArgEdit；patch_lines 进一步按行拆），经典 ddmin 找仍然 flip 的最小子集，最后整体再验证一次。每次探测都是真实重放并计入该 unit 的账本——切片成本是获取成本的一部分。`ACTION_REPLACE` 视为原子，单次确认后即 `MINIMAL`。

### 3.5 编译（compiler/exports.py）

四种视图，均为 JSONL、逐行带 `evidence_tier`：

- `sft.jsonl`：干预前上下文 → 修正动作；
- `dpo.jsonl`：同一 prompt 下 chosen（修正）/ rejected（原始）；
- `memory.jsonl`：失败→恢复单元（含 rationale）；
- `regression.jsonl` + 生成的 `test_regression.py`：可执行反事实用例——从 run 目录重新 fork snapshot、重放对照支与干预支、断言 flip 仍复现。

### 3.6 维护（maintenance/provenance.py）

每个 unit 打上环境指纹（causeforge 版本、python、平台、工具注册表 digest、workload digest）。`needs_revalidation(unit, current_env)` 返回漂移分量清单——M4 的 selective revalidation 在此钩子上展开。

## 4. 存储（store/blob.py、run_store.py）

Snapshot 树以确定性 tree digest 做 content addressing，相同树只存一份（M1 规模下 shared-prefix 复用免费获得；真正的 trace DAG 与 checkpoint placement 属 M3）。run 目录自包含：episodes/snapshots/units 的 JSONL + blobs + exports + report，`RunStore` 可从磁盘完整重建重放。

## 5. M1 workload（workloads/toy.py）

9 个确定性 "implement the function" 任务，覆盖全部机制路径：

| 任务 | 情形 | 干预 |
|---|---|---|
| t01/t03/t07 | 成功基线 | — |
| t02_fib | off-by-one bug | ACTION_REPLACE |
| t04_reverse_words | 字符反转≠词反转 | TOOL_ARGUMENT_EDIT set(content) |
| t05_wrong_path | 内容对、路径错 | TOOL_ARGUMENT_EDIT set(path) |
| t06_prime | 因果行 + 化妆行 | patch_lines ×2 → ddmin 应删掉化妆原子 |
| t08_report | bug + EXTERNAL 工具调用 | ACTION_REPLACE（重放中 send_report 被 mock） |
| t09_abs | 双候选 | 化妆非修复（必须验证失败）+ 真修复（必须 flip） |

## 6. M1 实测结果（判死线 #1）

```text
episodes 9 (6 failed) / candidates 7 / units: 6 MINIMAL + 1 SUGGESTED(rejected)
determinism control: OK
flip repro rate: 18/18 = 100%   (kill line ≥ 90% — PASS)
slicing: 7 atoms → 6 atoms      (t06 化妆原子被正确剔除)
```

该断言以 CI 形式固化在 `tests/test_e2e_demo.py`。

## 7. 明确不做（第一版）

进程级 snapshot（CRIU）、多框架 adapter、Web UI、PostgreSQL、OpenTelemetry、remote workers、非 pytest verifier、live LLM 分支策略（留给 M2 的预算机制成熟之后）。
