# Claim 表（claim → 实验 → 阈值）

每条 claim 必须绑定一个可执行实验和一个提前写死的阈值。数字只从 run 目录的 `report.json` 抄录，不手填。

| # | Claim | 实验 | 阈值 / 判死线 | 状态 |
|---|---|---|---|---|
| A1 | 确定性子集上 flip 可复现 | `causeforge demo`（toy workload, n_repro=3） | ≥ 90%，否则停下修 determinism | ✅ **100% (18/18)** toy 上界, 2026-07-29；✅ **100% (15/15)** live 真实开奖（depmig 30 任务, Qwen2.5-7B agent+fixer）, 2026-07-30 → `experiments/results/depmig-7b-qwen7b-fixer7b.json` |
| A2 | 非修复候选不会被误验证 | t09 双候选对照 | 化妆候选必须停留在 SUGGESTED | ✅ 1/1 rejected |
| A3 | 切片剔除非因果原子且不降级 | t06（因果行+化妆行） | 2 atoms → 1 atom，切片后再验证仍 flip | ✅ |
| A4 | EXTERNAL 副作用零真实重放 | t08 + 执行器门控单测 | replay 模式下 0 次真实执行 | ✅ (`test_external_tool_is_mocked_in_replay*`) |
| A5 | 每 validated unit 获取成本可报告 | report.json cost ledger | 数字存在且随规模线性可比 | ✅ ~2.2s/unit（toy, 本机） |
| A6 | prefix 复用节省 replay 成本 | M3 checkpoint placement 实验 | vs 全量重放的加速比 | ⬜ M3 |
| A9 | live agent 下对照支 digest 匹配率（新指标） | M1.5 bench 全量采集 | 报告数值 + 分解不匹配来源；toy 上界 100% | ✅ **100%**（29 unit 对照支，live agent）, 2026-07-30；无不匹配来源可分解 |
| A10 | fixer 产出率随 fixer 强度提升 | 同一 19 失败集（agent 轨迹缓存复现），fixer 7B vs 14B | 原假设：14B > 7B | ✅ **假设被否，发现更好的**：7B 翻 4 任务、14B 翻 3 任务、只重叠 1 个，**并集 6 任务**——异构 fixer 池 ≻ 单一强 fixer（M2 多源筛选的第一个实证论据）；两轮 flip-repro 均 15/15=100%、digest-match 均 100%, 2026-07-30 → `experiments/results/depmig-7b-fixer14b.json` |
| A7 | 预算筛选 beat exhaustive/random | M2 cost-per-unit 曲线（55 池化候选, 4 策略 + 机制消融） | 同预算下 validated units 更多 | ◐ **双结论**, 2026-07-30：(1) **机制层节省 26%**（137→101 replays, 产出相同 9u/6t; 全部来自对照支 memoization）；(2) **策略层 null result**——此规模（55 候选/19 失败/家族翻转率差异小）下 adaptive 与 exhaustive/random 无显著差异，全部收敛 9u/6t@101。放大条件（更大池、更贵验证、家族差异悬殊）留待 M2.5 复验 → `experiments/results/m2_curves{,_nomech}.json` |
| A8 | selective revalidation << 全量 | M4 真实包升级实验 | 重放次数下降 ≥ 5× 且不漏降级 | ⬜ M4 |
| B1 | 已发表管线可在本抽象上短代码复现 | `examples/case_step_dpo.py`：tree-sampling → step-DPO 对 + PRM 标签 | ≤100 行 | ✅ **76 行**, 2026-07-30：19 失败 ep × 3 分支采样 → 46 分支、7 翻转、12 个同状态步级 DPO 对；副产物：重采样翻转 3 个 fixer 池全灭的任务（k02/k06/s02），失败覆盖 6/19→**9/19**——A10 推广为"候选**来源**多样性 ≻ 模型强度"（HER relabel / 第二案例待做） |
| B2 | 训练栈直接可摄入 | `causeforge export --format trl-sft/trl-dpo/verl` | 格式与 TRL/verl 契约一致（含 parquet 回读测试） | ✅ 2026-07-30, 45 tests |
| C1 (RQ1) | causal 数据 beat 零成本修正对 | matched-token 对照训练 | 输了 → 当天转线 regression/freshness（库定位下已降级为加分项） | ⬜ pilot |

## 记录规则

- 每次刷新数字：附 run 目录路径 + workload digest（report.json → provenance.workload_digest）。
- 换 workload / 改 verifier 后，所有 ✅ 状态自动失效为 ⬜，重新跑。
