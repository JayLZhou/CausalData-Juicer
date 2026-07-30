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
| A10 | fixer 产出率随 fixer 强度提升 | 同一 29 失败集，fixer 7B vs 14B | 14B 翻转数 > 5/29（当前 7B：click 2 / networkx 2 / pydantic 1，numpy·sqlalchemy·T3 为 0） | ⬜ 进行中 |
| A7 | 预算筛选 beat exhaustive/random | M2 cost-per-unit 曲线 | 同预算下 validated units 更多 | ⬜ M2 |
| A8 | selective revalidation << 全量 | M4 真实包升级实验 | 重放次数下降 ≥ 5× 且不漏降级 | ⬜ M4 |
| B1 (RQ1) | causal 数据 beat 零成本修正对 | matched-token 二组对照训练 | 输了 → 当天转线 regression/freshness | ⬜ pilot |

## 记录规则

- 每次刷新数字：附 run 目录路径 + workload digest（report.json → provenance.workload_digest）。
- 换 workload / 改 verifier 后，所有 ✅ 状态自动失效为 ⬜，重新跑。
