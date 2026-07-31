# Claim 表（claim → 实验 → 阈值）

每条 claim 必须绑定一个可执行实验和一个提前写死的阈值。数字只从 run 目录的 `report.json` 抄录，不手填。

| # | Claim | 实验 | 阈值 / 判死线 | 状态 |
|---|---|---|---|---|
| A1 | 确定性子集上 flip 可复现 | `causeforge demo`（toy workload, n_repro=3） | ≥ 90%，否则停下修 determinism | ✅ **100% (18/18)** toy 上界, 2026-07-29；✅ **100% (15/15)** live 真实开奖（depmig 30 任务, Qwen2.5-7B agent+fixer）, 2026-07-30 → `experiments/results/depmig-7b-qwen7b-fixer7b.json`；✅ **100% (9/9 + 6/6)** pandas 家族（跨解释器 py3.11 底座）；✅ **100% (6/6)** 14B-agent 配置；✅ **100% (3/3 + 18/18)** 扩容 16 任务双 fixer 配置；✅ **100% (69/69)** 全量 52 任务最大异构池（14B fixer + resample 一等源, 110 候选→23 MINIMAL 单轮）—— 判死线在 **8 种配置**下全部成立 → `experiments/results/depmig-*.json` |
| A11 | agent 强度与失败画像 | 同一 36 任务, 7B vs 14B agent | 观察性结论 | ✅ 2026-07-31：14B 解 27/36 vs 7B 13/36；**14B 失败集 ⊂ 7B 失败集**（无 14B-only 失败）→ agent 多样性非覆盖杠杆（与 fixer 来源多样性相反），"采集用中档模型"决策获反向验证；9 个双双失败任务为 bench 硬核（含全部存活 T3） |
| A2 | 非修复候选不会被误验证 | t09 双候选对照 | 化妆候选必须停留在 SUGGESTED | ✅ 1/1 rejected |
| A3 | 切片剔除非因果原子且不降级 | t06（因果行+化妆行） | 2 atoms → 1 atom，切片后再验证仍 flip | ✅ |
| A4 | EXTERNAL 副作用零真实重放 | t08 + 执行器门控单测 | replay 模式下 0 次真实执行 | ✅ (`test_external_tool_is_mocked_in_replay*`) |
| A5 | 每 validated unit 获取成本可报告 | report.json cost ledger | 数字存在且随规模线性可比 | ✅ ~2.2s/unit（toy, 本机） |
| A6 | prefix 复用节省 replay 成本 | M3 `causeforge storage-bench`（depmig-7b 真实 run, 9 fork 点 ×3 重复） | vs 全量重放的加速比 | ✅ 2026-07-31：内容寻址 DAG 共享 **2.3×**（186 引用→81 唯一树, 省 56.6% 字节）；fork 加速 **every=298.6× / every_k:2=1.91×** vs from-scratch；稀疏 fork 前缀重执行重建状态与密集 checkpoint **digest 逐字节等价**（正确性内建于 bench）。注：加速倍数随步成本缩放（本 workload 步内含 pytest 子进程），placement 的意义正在于此 → `experiments/results/m3_storage_bench.json` |
| A9 | live agent 下对照支 digest 匹配率（新指标） | M1.5 bench 全量采集 | 报告数值 + 分解不匹配来源；toy 上界 100% | ✅ **100%**（29 unit 对照支，live agent）, 2026-07-30；无不匹配来源可分解 |
| A10 | fixer 产出率随 fixer 强度提升 | 同一失败集，fixer 7B vs 14B（核心 19 失败 + 扩容 12 失败） | 原假设：14B > 7B | ✅ **分层结论**, 2026-07-30/31：核心任务上 7B 翻 4 / 14B 翻 3 / 重叠 1（并集 6 ≻ 任一单源）；**扩容的多点重组任务上 14B 严格占优**（6 任务 ⊋ 7B 的 1）→ 易中难度靠来源多样性、高难度靠 fixer 强度，池化两者通吃；flip-repro 全程 100% → `experiments/results/depmig-7b-{fixer14b,ext,ext-f14b}.json` |
| A7 | 预算筛选 beat exhaustive/random | M2 cost-per-unit 曲线（55 池化候选, 4 策略 + 机制消融） | 同预算下 validated units 更多 | ◐→✅ **三段结论**, 2026-07-30/31：(1) **机制层节省 26%**（137→101 replays, 产出相同）；(2) 55 候选小池上策略层 null（全部收敛）；(3) **295 候选大池复验**（写下的放大条件兑现）：adaptive 在小预算区间领先——@30 replays 4u/4t vs random 最好 3u/3t vs exhaustive 2u/1t（+33%），@120 仍略领先（13u/11t），@240 起全部收敛——**预算越紧 adaptive 越有用，预算充裕时策略无关**（这正是"budgeted"场景该有的形状）；单席位差距温和，不夸大 → `experiments/results/m2_curves{,_nomech,_large}.json` |
| A8 | selective revalidation << 全量 | M4 两次真实版本事件（9 unit 语料, `causeforge revalidate`） | 重放次数下降 ≥ 5× 且不漏降级 | ✅ 2026-07-31：**升级** pydantic 2.7.4→2.11.7：selective 5 vs full 24 replays（**4.8×**），2 单元确认存活并重盖章；**回滚** click 8.1.7→7.1.2：selective 2 vs full 16（**8.0×**），4 个 click 单元被正确降级（control-drift：回滚使原始 bug 消失，反事实对失效）；两事件降级集 selective≡full，零漏报 → `experiments/results/m4_{pydantic_2.11.7,click_7.1.2}.json` |
| A12 | 候选源保真度阶梯：覆盖随源保真度（成本）上升 | 同一 35 失败集，五级源隔离测量 | 各级边际覆盖 > 0 | ✅ 2026-07-31：盲 fixer（7B/14B 一击）→ 温度重采样 → 测试感知 fixer（首破 T3：s06 静默 autocommit）→ **验证在环迭代精修**（60 次尝试翻 4 任务，反馈 = 真实执行的干预支失败输出，只有 replay 引擎给得出）；失败转化 **23/35**；天花板结论后被修正：**全家桶配置**（fixer-tests + resample + refine 同池, 109 候选→29 units 单轮, 87/87）攻破 numpy 钉子户——**n06 NEP50 被 7B 温度重采样翻转**（14B 全阶梯反复失败的任务），"能力天花板"对随机源多孔：抽样方差本身是覆盖手段；失败转化最终 **24/35**，未覆盖 11 任务（json 格式类 T3 为主）；flip-repro 全 11 配置 100% → `experiments/results/depmig-{fixer-tests,refine,kitchen-sink}.json` |
| A13 | 仪器负对照：determinism gate 真的会关 | `tests/test_negative_control.py`（毒任务 CI 断言） | 结局级抖动必须被拒；内容级噪声按设计放行 | ✅ 2026-07-31：快照边界外隐藏状态（外部计数器）→ 对照支失配 → 退回 SUGGESTED 且干预支零支出；报错文本内时间戳（结局稳定）→ 正常验证——仪器工作在 **outcome 粒度**，此为设计属性非缺陷 |
| A14 | 剩余失败的抵抗类型判定 | k=8 加密重采样定点 11 个未覆盖任务 | 采样受限 vs 方法受限分界 | ✅ 2026-07-31：**88 连抽零翻转**——n06 属采样饥饿（多抽即破），这 11 个（json 格式类 T3 为主）系方法/能力受限，对 7B 随机 + 14B 确定性全阶梯免疫；最终失败转化定格 24/35 → `runs/depmig-resample-k8` |
| B1 | 已发表管线可在本抽象上短代码复现 | `examples/case_step_dpo.py`：tree-sampling → step-DPO 对 + PRM 标签 | ≤100 行 | ✅ **76 行**, 2026-07-30：19 失败 ep × 3 分支采样 → 46 分支、7 翻转、12 个同状态步级 DPO 对；副产物：重采样翻转 3 个 fixer 池全灭的任务（k02/k06/s02），失败覆盖 6/19→**9/19**——A10 推广为"候选**来源**多样性 ≻ 模型强度"；**案例 #2** `examples/case_credit_ate.py`（**53 行**, 离线零重放）：CCPO 式反事实步级信用（ATE = P(success\|do(a′)) − P(success\|a)）直接从存储的 paired outcomes 编译，9 单元 → 信用标注轨迹（HER relabel 可作第三案例，非必需） |
| B2 | 训练栈直接可摄入 | `causeforge export --format trl-sft/trl-dpo/verl` | 格式与 TRL/verl 契约一致（含 parquet 回读测试） | ✅ 2026-07-30, 45 tests |
| B3 | HER relabel 可作纯观察性算子表达 | `examples/case_her_relabel.py` | ≤50 行、零重放零 LLM | ✅ **43 行**, 2026-08-01：34 个失败轨迹重标注为"达成之目标"的 OBSERVED 级监督 → `experiments/results/her_sft.jsonl` |
| B4 | 多层 rollout-tree 信用分配（Tree-GRPO 家族核心）可表达 | `examples/case_rollout_tree.py` | ≤100 行、真实执行的树 + 组相对优势 | ✅ **78 行**, 2026-08-01：深度 2 反事实树（L1 温度采样、L2 以**已执行分支的失败输出**为条件精修），12 节点 / 5 成功 / 3 个非零组相对优势 → `experiments/results/tree_credit.jsonl`。**README 五行"已发表家族"对照表至此全部兑现**（step-DPO、tree-credit、ATE、PRM、HER） |
| C1 (RQ1) | causal 数据 beat 零成本修正对 | matched-token LoRA 对照（validated 43 行 vs suggested 38 行, 同配方同种子, 跨家族留出 16 任务） | 输了 → 当天转线（库定位下已降级为加分项） | ◐ **低功率 null**, 2026-08-01：base 6/16、validated 5/16、suggested 5/16，**15/16 任务三臂结局逐一相同**（唯一差异 s04 为双臂同丢, 属小数据 SFT 漂移）；validated 与 suggested **完全打平**——判死线 #2 未触发（要求"输给基线", 实为零可检测效应）。结论：~40 行语料低于 SFT 效应检测阈值；复验条件：语料 ≥10×（~500 units）或改用任务型定向评估；C 链按库定位维持加分项 → `experiments/results/c1/` |

## 记录规则

- 每次刷新数字：附 run 目录路径 + workload digest（report.json → provenance.workload_digest）。
- 换 workload / 改 verifier 后，所有 ✅ 状态自动失效为 ⬜，重新跑。
