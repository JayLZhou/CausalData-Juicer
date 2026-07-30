# M1.5 Mini-Bench 规格：dependency-migration（依赖迁移）

> 状态：spec v1（施工依据）。目标：给判死线一个公平开奖环境——20–50 个确定性、密闭、
> 难度分层的真实 breaking-change 迁移任务，跑出两个真数字：
> **live agent 下的 flip 可复现率**（判死线 #1 真实开奖）与**对照支 digest 匹配率**（新指标，论文素材）。

## 1. 任务形态

每个任务 = 一个小型 Python repo（2–5 个源文件 + 密闭测试套件），代码按**旧版本** API 编写，
但任务环境安装的是**新版本**依赖 → 测试初始失败。Agent 的工作：编辑源码完成迁移，使测试在
新版本下通过。**不允许改测试文件、不允许改依赖版本**（verifier 强制，见 §5）。

这个形态的三个好处：

1. 失败是真实且可复现的（breaking change 是历史事实，不是人造 bug）；
2. 修复有客观标准答案（官方迁移指南），fixer 候选质量可控；
3. 干预天然落在 `write_file`/编辑步上，与 M1 的两种干预类型无缝衔接。

## 2. Breaking-change 家族（5+1）

| 家族 | 旧 pin | 新 pin | 底座解释器 | 典型迁移点 |
|---|---|---|---|---|
| pydantic | 1.10.13 | ≥2.7 | py3.12 | `.dict()→.model_dump()`、`@validator→@field_validator`、`Config→model_config`、`parse_obj→model_validate` |
| numpy | 1.26.4 | ≥2.0 | py3.12 | `np.float_/np.int_` 移除、`np.alltrue` 移除、`copy=False` 语义、`np.core` 私有化 |
| sqlalchemy | 1.4.54 | ≥2.0 | py3.12 | `declarative_base` 迁移、`Query→select()`、`engine.execute` 移除、`autocommit` 移除 |
| click | 7.1.2 | ≥8.1 | py3.12 | `autocompletion→shell_complete`、`get_terminal_size` 移除、`Choice` 大小写、`result.output` 行为 |
| networkx | 2.8.8 | ≥3.2 | py3.12 | `from_numpy_matrix` 移除、`node_connected_component` API、属性访问变更（纯 Python，零编译依赖） |
| pandas（可选） | 1.5.3 | ≥2.2 | **py3.11**（conda 造底座） | `append` 移除、`inplace` 语义、Copy-on-Write、`applymap→map` |

前 5 个家族全部兼容本机唯一的 python3.12；pandas 家族旧版无 cp312 wheel，
需 `conda create -n cf-py311 python=3.11` 提供底座解释器，作为 stretch goal，不阻塞开奖。

## 3. 规模与难度分层

每家族 6 个任务（5 家族 = 30 任务，pandas 就位则 36），按难度：

- **T1 机械替换（每家族 2 个）**：单一 API 改名/移除，单文件单点。预期中档模型高成功率——用于产出成功轨迹（stress 方向 v2 的原料）与低难度失败。
- **T2 多点/结构迁移（每家族 3 个）**：2–4 个迁移点跨 2–3 个文件，或需要结构改写（如 sqlalchemy Query→select）。预期主力失败区——干预数据的主产地。
- **T3 静默语义变更（每家族 1 个）**：不报 ImportError/AttributeError，而是行为悄悄变了、断言值错（numpy 类型提升、pandas CoW、click 输出行为）。最难，测试是唯一暴露途径。

每任务元数据：`{family, tier, migration_points: [...], expected_apis: [...]}`——
后续分析 flip 率、成本按 tier 分桶。

## 4. 密闭性要求（公平开奖的关键）

1. **测试零网络**：测试套件不 import requests/httpx/socket 网络调用；bench 构建时静态扫描强制。
2. **测试确定性**：禁 `time.time()`/无种子随机/依赖 dict 遍历顺序的断言；有随机的一律 `seed=0`。
3. **环境不可变**：任务 venv 由 EnvManager 一次性构建（构建期允许网络装包），episode 与 replay 期间只读。venv 在 workspace **外**，workspace 内只有指针文件 `.causeforge_env.json`（进 snapshot，几十字节）。
4. **依赖锁死**：全部 `==` pin，构建后记录 `pip freeze` 进 bench 的 provenance。
5. **无外部资产**：所有任务 repo 手写自建（README 纪律），迁移点参照各库官方 migration guide；PyMigBench 只作灵感来源，不直接搬代码。

## 5. Verifier 契约

- 判定：任务 venv 的解释器执行 `pytest -q`（经 `.causeforge_env.json` 指针解析），exit 0 且 passed ≥ 1 → success。
- 防作弊，success 还需同时满足：
  - 测试文件内容 digest 与任务定义一致（agent 改测试 = 直接 fail）；
  - `.causeforge_env.json` 未被篡改；
  - 源码中不得出现 `pytest.skip` / `sys.exit` 注入（静态扫描）。
- Outcome 记录 passed/failed 计数 + 规范化摘要（沿用 M1 的 time-free 归一化）。

## 6. Agent 与采集协议

- **Policy**：`LLMPolicy`（OpenAI 兼容端点，temperature=0，响应全量落盘缓存）。工具面 = M1 四工具（read_file / write_file / run_pytest / send_report 不进 bench）。max_steps=12。
- **每任务 episodes**：主采集 1 条/任务（temperature=0 确定性）；预算允许时对失败任务加采 2 条变体（提示词扰动），供 M2 的多候选筛选用。
- **Fixer 候选源**：同一端点、独立 prompt（给出失败观测 + 官方迁移要点），产出 1–3 个候选干预/失败任务；全部缓存，成本入账（这是第一笔真实 LLM 开销的主体）。
- **开奖指标**（写进 report.json，判死线自动判定）：
  1. `flip_repro_rate`（live agent 采集 + n_repro=3）——判死线 #1：< 90% 停下修 determinism；
  2. `control_digest_match_rate`——对照支逐步 digest 匹配率（新指标，M1 已埋点）；
  3. cost-per-validated-unit（token + 秒 + 美元）按 tier 分桶。

## 7. 目录与实现顺序

```text
causeforge/workloads/depmig/
├── families/{pydantic,numpy,sqlalchemy,click,networkx}/   # 每任务一个目录：src/ + tests/ + task.json
├── build.py       # 静态扫描（密闭性）+ EnvManager 构建 + provenance 冻结
└── loader.py      # 产出 ToyTask 同构的 Task 对象（同一 Collector/Replayer 直接吃）
```

施工顺序：EnvManager + 指针解析（已在 M1.5 前置件中）→ pydantic 家族 6 任务打通全链 →
其余 4 家族批量复制模式 → LLMPolicy 接真端点 → 全量采集开奖。

## 8. 待定决策（不阻塞施工）

- **端点与预算**：默认候选是本机 vLLM（零美元）或中档商业 API（Haiku 级）；采集阶段要"会犯真实错误的 agent"，模型不宜过强。粗估：36 任务 × (1 episode + fixer 候选) × ~4k tok ≈ 数百万 token —— 本地 vLLM 免费，商业 API 数十美元。
- pandas 家族是否启用（依赖 conda 底座是否顺利）。
