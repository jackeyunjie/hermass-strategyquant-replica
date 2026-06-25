import fs from "node:fs";
import path from "node:path";
import {
  AlignmentType, Document, Footer, Header, HeadingLevel, Packer, PageNumber,
  Paragraph, TextRun, Table, TableRow, TableCell, WidthType, ShadingType,
  convertInchesToTwip, BorderStyle,
} from "docx";

const outputPath = process.argv[2];
if (!outputPath) throw new Error("Usage: node generate_prd.js /absolute/path/output.docx");

const outputDir = path.dirname(outputPath);
fs.mkdirSync(outputDir, { recursive: true });

const font = { name: "Times New Roman", eastAsia: "SimSun" };
const codeFont = { name: "Consolas", eastAsia: "SimSun" };
const run = (text, options = {}) => new TextRun({ text, font, size: 22, ...options });
const codeRun = (text) => new TextRun({ text, font: codeFont, size: 18, color: "333333" });
const para = (children, options = {}) => new Paragraph({
  spacing: { after: 120, line: 280 },
  ...options,
  children: Array.isArray(children) ? children : [children],
});
const p = (text) => para(run(text), { indent: { firstLine: convertInchesToTwip(0.33) } });
const h1 = (text) => para(run(text, { bold: true, size: 32 }), { heading: HeadingLevel.HEADING_1, spacing: { before: 400, after: 200 } });
const h2 = (text) => para(run(text, { bold: true, size: 28 }), { heading: HeadingLevel.HEADING_2, spacing: { before: 300, after: 150 } });
const h3 = (text) => para(run(text, { bold: true, size: 24 }), { heading: HeadingLevel.HEADING_3, spacing: { before: 200, after: 100 } });
const li = (text) => para(run("• " + text), { indent: { left: 720 } });
const ol = (num, text) => para(run(num + ". " + text), { indent: { left: 720 } });
const bq = (text) => para(run(text, { italics: true, color: "555555" }), { indent: { left: 720 } });
const codeP = (text) => para(codeRun(text), {
  shading: { type: ShadingType.CLEAR, fill: "F5F5F5" },
  spacing: { after: 60, line: 240 },
  indent: { left: 360 },
});

const toc = () => {
  return new Paragraph({
    children: [new TextRun({ text: "目录", bold: true, size: 32, font })],
    spacing: { after: 300 },
    alignment: AlignmentType.CENTER,
  });
};

const makeTable = (data) => {
  if (!data || data.length === 0) return null;
  const numCols = data[0].length;
  const colWidth = 9600 / numCols;
  const cell = (text, isHeader = false) => new TableCell({
    children: [para(run(text, { bold: isHeader, size: 18 }), { spacing: { after: 60, line: 240 } })],
    margins: { top: 60, bottom: 60, left: 80, right: 80 },
    shading: isHeader ? { type: ShadingType.CLEAR, fill: "E8EEF2" } : undefined,
    width: { size: colWidth, type: WidthType.DXA },
  });
  return new Table({
    width: { size: 100, type: WidthType.PERCENTAGE },
    columnWidths: Array(numCols).fill(colWidth),
    rows: data.map((row, idx) => new TableRow({
      children: row.map(c => cell(c, idx === 0)),
    })),
  });
};

const children = [];
children.push(toc());
children.push(h1('Hermass StrategyQuant 复刻产品需求文档 (PRD)'));
children.push(bq('版本：v1.0 | 日期：2026-06-24 | 状态：草案'));
children.push(bq('作者：Orchestrator Agent（基于 StrategyQuant X 深度调研）'));
children.push(bq('关联项目：Hermass AI 量化交易平台（A 股多周期共振与收缩突破方向）'));
children.push(p('---'));
children.push(h2('1. 概述'));
children.push(h3('1.1 背景与动机'));
children.push(p('**StrategyQuant X** 是全球领先的量化策略自动发现与验证平台，自 2005 年运营以来，帮助数千名用户无需编程即可构建、回测和优化算法交易策略。其核心模式是：通过遗传编程（Genetic Programming）在指标组合空间中自动搜索，并通过多维稳健性测试过滤过拟合策略，最终导出可直接实盘交易的完整源代码。'));
children.push(p('用户当前正在构建 **Hermass** —— 主攻 A 股市场的 AI 量化交易平台，聚焦多周期共振与收缩突破假设的自动化验证。复刻 StrategyQuant 的核心功能体系，将大幅提升 Hermass 的策略发现能力、策略质量管控能力以及用户可及性（无代码/低代码策略构建）。'));
children.push(p('**调研基础**：基于 StrategyQuant 官方网站（strategyquant.com）的功能页、定价页、用户手册及三大技术调研报告（策略生成引擎、稳健性测试、Web UI 与代码导出）综合分析。'));
children.push(h3('1.2 目标'));
children.push(li('**业务目标**：构建 A 股市场版 StrategyQuant 核心能力，实现无代码策略生成、自动稳健性验证、回测优化、多平台代码导出（Python 优先）、组合管理的闭环。'));
children.push(li('**用户目标**：'));
children.push(li('初级用户：无需编程，通过可视化界面生成可验证的交易策略'));
children.push(li('中级用户：构建自定义指标、策略模板，进行 Walk-Forward 分析'));
children.push(li('高级用户：集成自定义模块、插件系统，进行大规模分布式策略搜索'));
children.push(li('**成功指标**：'));
children.push(li('MVP 阶段：单日内可生成 100+ 策略，通过率（稳健性测试）> 20%'));
children.push(li('完整阶段：支持 5000+ 只 A 股，分钟/日线双级别，日生成 1000+ 稳健策略'));
children.push(li('用户留存：月活用户 > 100，策略导出使用率达 60%'));
children.push(h3('1.3 范围'));
children.push(p('**本期包含（Must + Should）**：'));
children.push(li('策略生成引擎（Builder）：遗传编程 + 随机生成'));
children.push(li('回测引擎：日线/分钟线，A 股规则适配（T+1、涨跌停、停牌、除权）'));
children.push(li('稳健性测试：Monte Carlo 模拟、Walk-Forward 分析、过拟合检测'));
children.push(li('策略优化器：简单优化 + Walk-Forward 优化'));
children.push(li('策略改进器（Improver）：局部优化策略组件'));
children.push(li('无代码策略编辑器（AlgoWizard）：可视化节点编辑器'));
children.push(li('回测结果可视化：资金曲线、统计仪表盘、交易记录'));
children.push(li('代码生成器：导出 Python（Hermass 内部 DSL / vectorbt / backtrader）'));
children.push(li('数据管理：集成 Tushare / A 股行情数据下载'));
children.push(li('组合管理：策略组合构建、相关性分析、组合回测'));
children.push(li('用户系统与权限管理'));
children.push(p("**本期不包含（Won't Have）**："));
children.push(li('跨市场数据（期货、外汇、加密货币）—— 聚焦 A 股，后续扩展'));
children.push(li('实时实盘交易接口（CTP 等）—— 先回测/模拟盘，后续对接'));
children.push(li('完整的 AI 结果分析插件（Results AI）—— 基础版集成，高级 NLP 分析后续版本'));
children.push(li('高级模糊逻辑（Fuzzy Logic）策略生成—— 后续 V2 扩展'));
children.push(li('多目标代码导出（MQL4/5、TradeStation）—— 仅 Python，其他语言后续扩展'));
children.push(li('季节性工具箱（Seasonal Toolbox）—— 后续版本'));
children.push(li('自定义指标市场（MQL Market 模式）—— 商业化后续阶段'));
children.push(p('---'));
children.push(h2('2. 用户画像'));
children.push(h3('2.1 角色定义'));
children.push(makeTable([['角色', '描述', '核心目标', '主要痛点'], ['**量化新手**', '有投资经验，无编程能力，想尝试算法交易', '快速验证交易想法，无需编程生成可执行策略', '不懂编程、不知策略好坏、数据获取困难'], ['**策略研究员**', '有量化基础，会用 Python，追求系统化的策略发现', '大规模搜索策略空间，自动化稳健性验证，系统化筛选', '手动策略发现效率低、过拟合难以识别、回测速度慢'], ['**组合管理者**', '管理多策略组合，关注风险分散和组合绩效', '构建非相关策略组合，动态再平衡，组合层面风险评估', '策略相关性难以量化、组合优化工具缺失、手动组合管理复杂'], ['**系统开发者**', '深入理解量化交易系统，希望扩展平台能力', '自定义指标、插件开发、接口集成、性能优化', '平台可扩展性不足、API 不开放、无法自定义分析逻辑']]));
children.push(p('---'));
children.push(h2('3. 用户故事'));
children.push(h3('3.1 量化新手'));
children.push(ol("", '**作为** 量化新手，**我想要** 通过拖拽节点的方式构建一个"收盘价上穿 20 日均线"的入场策略，**以便** 无需编程即可验证这个交易想法。'));
children.push(ol("", '**作为** 量化新手，**我想要** 一键生成 100 个随机策略并自动排序，**以便** 快速找到历史上表现最好的策略候选。'));
children.push(ol("", '**作为** 量化新手，**我想要** 查看策略的资金曲线和关键指标（胜率、盈亏比、最大回撤），**以便** 直观判断策略是否值得深入研究。'));
children.push(ol("", '**作为** 量化新手，**我想要** 将验证过的策略导出为可直接运行的 Python 代码，**以便** 在本地或云端运行回测和模拟交易。'));
children.push(h3('3.2 策略研究员'));
children.push(ol("", '**作为** 策略研究员，**我想要** 配置遗传编程参数（种群大小、进化代数、交叉率、变异率），**以便** 控制策略生成的搜索范围和收敛速度。'));
children.push(ol("", '**作为** 策略研究员，**我想要** 在策略生成流程中自动运行 Monte Carlo 和 Walk-Forward 稳健性测试，**以便** 只保留统计上稳健的策略。'));
children.push(ol("", '**作为** 策略研究员，**我想要** 对生成的策略进行多 OOS 样本外测试，**以便** 验证策略在不同时期的稳定性。'));
children.push(ol("", '**作为** 策略研究员，**我想要** 使用自定义策略模板（如指定入场必须使用 ATR 过滤，出场必须使用跟踪止损），**以便** 在特定框架内搜索策略。'));
children.push(ol("", '**作为** 策略研究员，**我想要** 对策略的某个部分（如仅入场条件）进行改进优化，**以便** 在保留核心逻辑的前提下提升策略表现。'));
children.push(h3('3.3 组合管理者'));
children.push(ol("", '**作为** 组合管理者，**我想要** 将多个策略组合为一个投资组合，并查看组合层面的资金曲线和统计指标，**以便** 评估分散化效果。'));
children.push(ol("", '**作为** 组合管理者，**我想要** 查看组合内策略的相关性矩阵，**以便** 识别并剔除高相关性策略，降低组合风险。'));
children.push(ol("", '**作为** 组合管理者，**我想要** 进行组合优化（如等权重、风险平价、均值方差优化），**以便** 找到最优的权重分配方案。'));
children.push(ol("", '**作为** 组合管理者，**我想要** 对组合进行 Walk-Forward 组合再平衡测试，**以便** 评估动态再平衡策略的有效性。'));
children.push(h3('3.4 系统开发者'));
children.push(ol("", '**作为** 系统开发者，**我想要** 通过插件系统注册自定义技术指标（如中国版资金流向指标），**以便** 扩展平台的指标库。'));
children.push(ol("", '**作为** 系统开发者，**我想要** 通过自定义分析模块执行 Python 脚本对策略进行深度分析，**以便** 实现平台尚未内置的高级分析功能。'));
children.push(ol("", '**作为** 系统开发者，**我想要** 使用自定义项目（Custom Projects）编排多步骤工作流（生成 → 筛选 → 优化 → 组合），**以便** 实现全自动化的策略研发流水线。'));
children.push(ol("", '**作为** 系统开发者，**我想要** 在分布式计算集群上运行大规模策略生成任务，**以便** 加速策略搜索过程。'));
children.push(p('---'));
children.push(h2('4. 功能需求'));
children.push(h3('4.1 功能清单'));
children.push(p('#### 模块 1：策略生成引擎（Builder）'));
children.push(makeTable([['编号', '功能名称', '所属故事', '功能描述', '输入/输出/交互'], ['F-001', 'GP 策略生成', 'US-2.1', '使用 DEAP 遗传编程框架自动生成策略树', '输入：配置参数、股票池、时间范围；输出：策略个体列表'], ['F-002', '随机策略生成', 'US-1.2', '随机组合指标和参数生成策略', '输入：数量、复杂度限制；输出：策略列表'], ['F-003', '策略模板生成', 'US-2.4', '基于用户自定义模板生成策略（Random Placeholder）', '输入：策略模板 JSON；输出：填充后的策略列表'], ['F-004', '策略语法约束', 'US-2.1', '定义策略树的合法操作集和类型闭包', '输入：原始函数集、终端集；输出：合法策略树'], ['F-005', '多目标适应度', 'US-2.1', '同时优化多个目标（收益、夏普、回撤、胜率）', '输入：策略回测结果；输出：NSGA-II 帕累托前沿'], ['F-006', '多市场/多周期', 'US-2.4', '策略使用多图表输入（不同股票或周期）', '输入：多个 symbol/timeframe；输出：多信号融合策略'], ['F-007', '模糊逻辑策略', '—', '策略条件不要求精确满足，允许部分条件为真', '输入：条件列表、阈值百分比；输出：模糊信号']]));
children.push(p('#### 模块 2：回测引擎'));
children.push(makeTable([['编号', '功能名称', '所属故事', '功能描述', '输入/输出/交互'], ['F-008', '事件驱动回测', 'US-1.3', '逐 K 线处理交易事件，保证因果顺序', '输入：K 线数据、策略信号；输出：交易记录、资金曲线'], ['F-009', '向量化回测', 'US-2.1', '批量计算指标和信号，极速验证', '输入：数据矩阵、参数网格；输出：批量回测结果'], ['F-010', 'A 股规则引擎', 'US-1.1', 'T+1、涨跌停（10%/20%/30%）、停牌、除权', '输入：策略信号、市场规则配置；输出：实际可执行信号'], ['F-011', 'Tick 级别回测', '—', '使用逐笔成交数据精确模拟', '输入：Tick 数据；输出：精确交易记录'], ['F-012', '多资产组合回测', 'US-3.1', '同时回测多个资产的策略组合', '输入：多个策略 + 多个资产；输出：组合层面结果'], ['F-013', '成本模型', 'US-1.3', '佣金、印花税、滑点、冲击成本建模', '输入：交易金额、费率配置；输出：成本-adjusted 收益']]));
children.push(p('#### 模块 3：稳健性测试（Robustness Testing）'));
children.push(makeTable([['编号', '功能名称', '所属故事', '功能描述', '输入/输出/交互'], ['F-014', 'Monte Carlo 模拟', 'US-2.2', '9 种模拟类型（交易顺序、跳过、参数扰动、数据噪声等）', '输入：策略 + 回测结果；输出：1000 次模拟的绩效分布'], ['F-015', 'Walk-Forward 分析', 'US-2.2', '滚动优化 + OOS 验证，计算 WFER', '输入：策略 + 数据 + 窗口配置；输出：各窗口 WFER'], ['F-016', 'Walk-Forward 矩阵', 'US-2.2', '系统遍历 (IS, OOS, step) 组合，聚类分析', '输入：多窗口配置；输出：三维稳健性景观'], ['F-017', '系统参数排列 (SPP)', 'US-2.2', '遍历全参数空间，中位数作为真实绩效估计', '输入：参数网格；输出：参数绩效分布'], ['F-018', '优化轮廓分析', 'US-2.2', '评估优化结果的稳定性（Pardo 五大标准）', '输入：优化结果；输出：轮廓评分'], ['F-019', '多 OOS 测试', 'US-2.3', '等分模式 / 市场制度模式的样本外测试', '输入：策略 + 数据；输出：各 OOS 期绩效一致性'], ['F-020', '过拟合检测', 'US-2.2', 'DSR、PBO、PSR 三大指标 + 多重检验校正', '输入：回测结果；输出：过拟合概率'], ['F-021', '自动稳健性过滤', 'US-2.2', '在生成流程中自动拒绝未通过稳健性测试的策略', '输入：策略 + 测试配置；输出：过滤后的策略列表']]));
children.push(p('#### 模块 4：策略优化器'));
children.push(makeTable([['编号', '功能名称', '所属故事', '功能描述', '输入/输出/交互'], ['F-022', '简单优化器', 'US-2.1', '对策略参数进行单/多目标优化', '输入：策略 + 参数范围；输出：最优参数组合'], ['F-023', 'Walk-Forward 优化', 'US-2.2', '周期再优化，模拟实盘定期调参', '输入：策略 + 窗口配置；输出：各期最优参数 + OOS 绩效'], ['F-024', '3D 优化图表', '—', '可视化 Walk-Forward 矩阵的 3D 结果', '输入：矩阵结果；输出：3D 热力图/散点图'], ['F-025', '参数稳定性分析', 'US-2.2', '参数轨迹的平滑度评估', '输入：WFO 结果；输出：稳定性评分']]));
children.push(p('#### 模块 5：策略改进器（Improver）'));
children.push(makeTable([['编号', '功能名称', '所属故事', '功能描述', '输入/输出/交互'], ['F-026', '局部改进', 'US-2.5', '仅改进策略的某一部分（如仅入场或仅出场）', '输入：原策略 + 改进目标；输出：改进后策略'], ['F-027', '多组件改进', '—', '同时改进多个组件', '输入：原策略 + 组件列表；输出：改进后策略列表']]));
children.push(p('#### 模块 6：无代码策略编辑器（AlgoWizard）'));
children.push(makeTable([['编号', '功能名称', '所属故事', '功能描述', '输入/输出/交互'], ['F-028', '简单向导模式', 'US-1.1', '下拉框 + 条件列表，快速构建策略', '输入：条件选择；输出：策略配置'], ['F-029', '节点编辑器（Full）', 'US-1.1', 'ReactFlow 节点编排，支持复杂逻辑', '输入：节点拖拽 + 连接；输出：策略 DAG'], ['F-030', '类型系统与校验', 'US-1.1', '端口类型兼容检查、DAG 循环检测', '输入：节点连接；输出：校验结果（通过/错误）'], ['F-031', '策略序列化', 'US-1.1', '策略导出/导入为 JSON Schema', '输入：策略图；输出：JSON 文件'], ['F-032', '策略逻辑树展示', 'US-1.1', '将节点图转化为层次化逻辑树', '输入：策略图；输出：可读逻辑树'], ['F-033', '自定义指标注册', 'US-4.1', '用户注册自定义指标节点', '输入：指标公式/函数；输出：新节点类型'], ['F-034', '多周期引用', 'US-2.4', '策略中引用不同周期图表数据', '输入：周期配置；输出：跨周期信号节点'], ['F-035', 'ATM（多出场）', '—', '配置多个出场条件（分级止盈）', '输入：出场规则列表；输出：复合出场策略']]));
children.push(p('#### 模块 7：回测结果可视化'));
children.push(makeTable([['编号', '功能名称', '所属故事', '功能描述', '输入/输出/交互'], ['F-036', '资金曲线图', 'US-1.3', '时间序列权益曲线（Lightweight Charts）', '输入：equity_curve 数据；输出：交互式图表'], ['F-037', 'K 线 + 交易标记', 'US-1.3', '在 K 线图上标记买卖点和指标', '输入：OHLCV + 交易记录 + 指标；输出：复合图表'], ['F-038', '统计仪表盘', 'US-1.3', '综合指标面板（夏普、回撤、胜率、盈亏比等）', '输入：回测结果；输出：KPI 卡片 + 雷达图'], ['F-039', '交易记录表', 'US-1.3', '每笔交易的详细记录表', '输入：trades 数据；输出：可排序/过滤表格'], ['F-040', '收益分布图', 'US-1.3', '单笔盈亏分布、月度收益分布', '输入：trades/returns；输出：直方图/箱线图'], ['F-041', '回撤分析', 'US-1.3', '回撤时段、回撤恢复时间', '输入：drawdown_series；输出：回撤分析图表'], ['F-042', 'MAE/MFE 分析', '—', '最大不利/有利偏移分析', '输入：每笔交易 MAE/MFE；输出：散点图']]));
children.push(p('#### 模块 8：代码生成器'));
children.push(makeTable([['编号', '功能名称', '所属故事', '功能描述', '输入/输出/交互'], ['F-043', 'Python 代码生成', 'US-1.4', '将策略生成可运行 Python 代码', '输入：策略 IR（JSON）；输出：.py 文件'], ['F-044', '代码生成模板', 'US-1.4', 'Jinja2 模板引擎，支持多目标框架', '输入：策略 IR + 模板选择；输出：目标代码'], ['F-045', 'Hermass DSL 生成', 'US-1.4', '生成 Hermass 内部策略框架的 DSL', '输入：策略 IR；输出：Hermass 专用代码'], ['F-046', '代码预览', 'US-1.4', '在 UI 中预览生成的代码', '输入：策略 IR；输出：语法高亮代码']]));
children.push(p('#### 模块 9：组合管理'));
children.push(makeTable([['编号', '功能名称', '所属故事', '功能描述', '输入/输出/交互'], ['F-047', '组合构建', 'US-3.1', '将多个策略组合为投资组合', '输入：策略列表 + 权重；输出：组合配置'], ['F-048', '组合回测', 'US-3.1', '组合层面的回测与统计', '输入：组合 + 数据；输出：组合绩效'], ['F-049', '相关性矩阵', 'US-3.2', '计算策略间的收益相关性', '输入：策略收益序列；输出：相关性热力图'], ['F-050', '组合优化', 'US-3.3', '等权重/风险平价/均值方差优化', '输入：策略列表 + 优化目标；输出：最优权重'], ['F-051', '组合 Walk-Forward', 'US-3.4', '组合层面的 Walk-Forward 再平衡', '输入：组合 + 窗口配置；输出：再平衡绩效'], ['F-052', '组合稳健性测试', '—', '对组合进行 Monte Carlo 和 WFO', '输入：组合；输出：稳健性报告']]));
children.push(p('#### 模块 10：数据管理'));
children.push(makeTable([['编号', '功能名称', '所属故事', '功能描述', '输入/输出/交互'], ['F-053', '数据下载', 'US-1.2', '集成 Tushare 下载 A 股行情数据', '输入：股票列表 + 时间范围 + 周期；输出：下载任务'], ['F-054', '数据存储', 'US-1.2', '时序数据库存储（TimescaleDB / ClickHouse）', '输入：原始数据；输出：持久化存储'], ['F-055', '数据管理面板', 'US-1.2', '查看已下载数据、数据质量、覆盖度', '输入：数据库；输出：管理界面'], ['F-056', '数据复权', '—', '自动前复权/后复权处理', '输入：原始 OHLCV + 复权因子；输出：复权数据'], ['F-057', '数据预览', '—', '在 UI 中预览数据（K 线、指标）', '输入：数据查询；输出：预览图表']]));
children.push(p('#### 模块 11：自定义项目与插件'));
children.push(makeTable([['编号', '功能名称', '所属故事', '功能描述', '输入/输出/交互'], ['F-058', '自定义项目', 'US-4.3', '编排多步骤工作流（生成 → 筛选 → 优化 → 组合）', '输入：工作流步骤配置；输出：自动化流水线'], ['F-059', '插件系统', 'US-4.2', '注册自定义分析模块、指标、代码生成器', '输入：插件代码；输出：扩展功能'], ['F-060', '自定义分析', 'US-4.2', '执行 Python 脚本对策略进行深度分析', '输入：策略 + 脚本；输出：分析结果'], ['F-061', '策略导入', '—', '导入现有策略代码（Python 解析）', '输入：.py 文件；输出：策略 IR']]));
children.push(p('#### 模块 12：系统与基础设施'));
children.push(makeTable([['编号', '功能名称', '所属故事', '功能描述', '输入/输出/交互'], ['F-062', '用户注册/登录', '全局', '邮箱/密码注册，JWT 认证', '输入：凭证；输出：会话 token'], ['F-063', '权限管理', '全局', '角色（管理员/研究员/访客）+ 资源权限', '输入：用户 + 资源；输出：权限判定'], ['F-064', '策略仓库', '全局', '策略的 CRUD、版本管理、标签分类', '输入：策略数据；输出：持久化存储'], ['F-065', '任务调度', '全局', 'Celery + Redis 异步任务调度回测/生成任务', '输入：任务定义；输出：任务执行状态'], ['F-066', '结果缓存', '全局', '缓存回测结果避免重复计算', '输入：策略 + 数据指纹；输出：缓存结果'], ['F-067', '分布式计算', 'US-4.4', 'Ray 集群调度大规模策略搜索', '输入：集群配置；输出：分布式任务执行'], ['F-068', '日志与监控', '全局', '任务日志、系统监控、性能指标', '输入：运行时数据；输出：日志/监控面板']]));
children.push(h3('4.2 非功能需求'));
children.push(makeTable([['维度', '要求', '优先级'], ['**性能**', '单策略回测 < 1s（日线，5 年数据）；批量 100 策略 < 10s', 'Must'], ['**性能**', '支持 5000+ 只股票的分钟级回测', 'Should'], ['**性能**', '策略生成 100 代 × 500 个体 < 2h（单机）', 'Should'], ['**安全**', '用户数据隔离，策略代码不泄露', 'Must'], ['**安全**', 'API 认证（JWT），防注入（参数化查询）', 'Must'], ['**可用性**', '系统可用性 > 99.5%', 'Should'], ['**可扩展性**', '模块化架构，支持插件扩展', 'Must'], ['**可扩展性**', '水平扩展（Ray 分布式）支持', 'Should'], ['**易用性**', '无代码编辑器 30 分钟内完成首个策略构建', 'Must'], ['**易用性**', '中文界面（优先），英文支持（后续）', 'Must'], ['**兼容性**', '支持 Chrome / Edge / Firefox 最新版', 'Must'], ['**兼容性**', '后端支持 Linux / macOS / Windows Server', 'Should']]));
children.push(h3('4.3 功能依赖关系'));
children.push(codeP('[数据管理 F-053~F-057]'));
children.push(codeP('        ↓'));
children.push(codeP('[回测引擎 F-008~F-013]'));
children.push(codeP('        ↓'));
children.push(codeP('[策略生成引擎 F-001~F-007] ← 依赖回测引擎评估适应度'));
children.push(codeP('        ↓'));
children.push(codeP('[稳健性测试 F-014~F-021] ← 依赖回测引擎'));
children.push(codeP('        ↓'));
children.push(codeP('[策略优化器 F-022~F-025] ← 依赖回测引擎'));
children.push(codeP('        ↓'));
children.push(codeP('[策略改进器 F-026~F-027] ← 依赖策略生成 + 回测'));
children.push(codeP('        ↓'));
children.push(codeP('[无代码编辑器 F-028~F-035] ← 可独立但依赖回测验证'));
children.push(codeP('        ↓'));
children.push(codeP('[代码生成器 F-043~F-046] ← 依赖策略 IR 定义'));
children.push(codeP('        ↓'));
children.push(codeP('[组合管理 F-047~F-052] ← 依赖回测引擎 + 策略仓库'));
children.push(codeP('        ↓'));
children.push(codeP('[自定义项目 F-058~F-061] ← 依赖所有上游模块'));
children.push(p('---'));
children.push(h2('5. 优先级（MoSCoW 矩阵）'));
children.push(makeTable([['功能编号', '功能名称', '优先级', '理由'], ['F-008', '事件驱动回测', '**Must**', '核心基础设施，无回测则所有功能失效'], ['F-010', 'A 股规则引擎', '**Must**', 'A 股特殊规则是项目核心定位'], ['F-001', 'GP 策略生成', '**Must**', 'StrategyQuant 核心差异化功能'], ['F-002', '随机策略生成', '**Must**', '快速生成 baseline，支撑 GP 初始种群'], ['F-014', 'Monte Carlo 模拟', '**Must**', '稳健性测试核心，过滤过拟合'], ['F-015', 'Walk-Forward 分析', '**Must**', '参数稳定性验证核心'], ['F-020', '过拟合检测', '**Must**', '策略质量控制最后一道防线'], ['F-028', '简单向导模式', '**Must**', '无代码用户入口'], ['F-029', '节点编辑器', '**Must**', '高级用户可视化策略构建'], ['F-030', '类型系统与校验', '**Must**', '节点编辑器数据正确性保障'], ['F-036', '资金曲线图', '**Must**', '回测结果最核心可视化'], ['F-038', '统计仪表盘', '**Must**', '策略评估核心指标展示'], ['F-043', 'Python 代码生成', '**Must**', '策略落地执行的关键路径'], ['F-045', 'Hermass DSL 生成', '**Must**', '与现有 Hermass 系统对接'], ['F-053', '数据下载', '**Must**', '数据来源基础设施'], ['F-054', '数据存储', '**Must**', '数据持久化基础设施'], ['F-062', '用户注册/登录', '**Must**', '系统安全基础'], ['F-065', '任务调度', '**Must**', '异步回测/生成任务调度'], ['F-004', '策略语法约束', '**Must**', 'GP 策略合法性保障'], ['F-013', '成本模型', '**Should**', '精确回测，但可用简化版替代'], ['F-022', '简单优化器', '**Should**', '提升策略质量，但非上线必需'], ['F-026', '局部改进', '**Should**', '提升策略质量，可手动优化替代'], ['F-031', '策略序列化', '**Should**', '策略持久化，但可暂存内存'], ['F-032', '策略逻辑树展示', '**Should**', '策略可读性，但非功能必需'], ['F-037', 'K 线 + 交易标记', '**Should**', '增强可视化，可用纯资金曲线替代'], ['F-039', '交易记录表', '**Should**', '详细分析，但可用汇总替代'], ['F-047', '组合构建', '**Should**', '组合管理入门，但可先单策略'], ['F-049', '相关性矩阵', '**Should**', '组合分析核心，但可先单策略'], ['F-056', '数据复权', '**Should**', 'A 股精确回测，但可预处理'], ['F-064', '策略仓库', '**Should**', '策略管理，但可先本地存储'], ['F-005', '多目标适应度', '**Could**', '增强搜索效率，但单目标可行'], ['F-006', '多市场/多周期', '**Could**', '策略丰富度，但单周期可运行'], ['F-016', 'Walk-Forward 矩阵', '**Could**', '深度分析，但标准 WFO 足够'], ['F-017', '系统参数排列', '**Could**', '深度稳健性，但 MC 和 WFO 足够'], ['F-018', '优化轮廓分析', '**Could**', '深度优化分析，但简单优化可行'], ['F-019', '多 OOS 测试', '**Could**', '额外验证，但 WFO 已覆盖'], ['F-021', '自动稳健性过滤', '**Could**', '自动化，但可手动筛选'], ['F-023', 'Walk-Forward 优化', '**Could**', '高级优化，但简单优化可行'], ['F-024', '3D 优化图表', '**Could**', '可视化增强，非功能必需'], ['F-033', '自定义指标注册', '**Could**', '扩展性，但内置指标足够起步'], ['F-034', '多周期引用', '**Could**', '多周期策略，可后续扩展'], ['F-035', 'ATM（多出场）', '**Could**', '策略丰富度，但单出场可运行'], ['F-040', '收益分布图', '**Could**', '分析增强，但仪表盘已覆盖'], ['F-041', '回撤分析', '**Could**', '分析增强，但仪表盘已覆盖'], ['F-042', 'MAE/MFE 分析', '**Could**', '专业分析，后续扩展'], ['F-044', '代码生成模板', '**Could**', '多目标代码，但 Python 足够'], ['F-046', '代码预览', '**Could**', '体验增强，但直接下载可行'], ['F-048', '组合回测', '**Could**', '组合功能，但可先单策略'], ['F-050', '组合优化', '**Could**', '高级组合，但等权重可行'], ['F-051', '组合 Walk-Forward', '**Could**', '组合高级功能，后续扩展'], ['F-052', '组合稳健性测试', '**Could**', '组合高级功能，后续扩展'], ['F-055', '数据管理面板', '**Could**', '体验增强，但后台管理可行'], ['F-057', '数据预览', '**Could**', '体验增强，非功能必需'], ['F-058', '自定义项目', "**Won't**", '工作流编排，V2 扩展'], ['F-059', '插件系统', "**Won't**", '扩展机制，V2 扩展'], ['F-060', '自定义分析', "**Won't**", '高级扩展，V2 扩展'], ['F-061', '策略导入', "**Won't**", '逆向工程，V2 扩展'], ['F-007', '模糊逻辑策略', "**Won't**", '高级策略类型，V2 扩展'], ['F-011', 'Tick 级别回测', "**Won't**", '高精度回测，V2 扩展'], ['F-012', '多资产组合回测', "**Won't**", '组合回测，V2 扩展'], ['F-025', '参数稳定性分析', "**Won't**", 'WFO 深度分析，V2 扩展'], ['F-027', '多组件改进', "**Won't**", '改进扩展，V2 扩展'], ['F-063', '权限管理', "**Won't**", '简单单用户即可，后续扩展'], ['F-066', '结果缓存', "**Won't**", '性能优化，后续迭代'], ['F-067', '分布式计算', "**Won't**", '单机可运行，后续扩展'], ['F-068', '日志与监控', "**Won't**", '系统运维，后续扩展'], ['F-009', '向量化回测', "**Won't**", '性能优化，后续用事件驱动优化']]));
children.push(p('---'));
children.push(h2('6. 技术架构'));
children.push(h3('6.1 总体架构'));
children.push(codeP('┌─────────────────────────────────────────────────────────────────────────────┐'));
children.push(codeP('│                              前端层 (Frontend)                                │'));
children.push(codeP('│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐   │'));
children.push(codeP('│  │策略编辑器 │  │回测仪表盘│  │组合管理  │  │数据管理  │  │用户管理  │   │'));
children.push(codeP('│  │(ReactFlow)│  │(ECharts) │  │(AG Grid)│  │(Ant Design)│  │(Auth)   │   │'));
children.push(codeP('│  └──────────┘  └──────────┘  └──────────┘  └──────────┘  └──────────┘   │'));
children.push(codeP('│                    React 18 + TypeScript + Vite + Zustand                     │'));
children.push(codeP('└─────────────────────────────────────────────────────────────────────────────┘'));
children.push(codeP('                                      │ HTTP / WebSocket'));
children.push(codeP('                                      ▼'));
children.push(codeP('┌─────────────────────────────────────────────────────────────────────────────┐'));
children.push(codeP('│                              API 层 (FastAPI)                                 │'));
children.push(codeP('│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐   │'));
children.push(codeP('│  │策略 CRUD │  │回测调度  │  │代码生成  │  │组合分析  │  │数据管理  │   │'));
children.push(codeP('│  │用户 API  │  │任务状态  │  │导出下载  │  │权限控制  │  │文件上传  │   │'));
children.push(codeP('│  └──────────┘  └──────────┘  └──────────┘  └──────────┘  └──────────┘   │'));
children.push(codeP('│                      Pydantic + SQLAlchemy 2.0 async                          │'));
children.push(codeP('└─────────────────────────────────────────────────────────────────────────────┘'));
children.push(codeP('                                      │'));
children.push(codeP('          ┌───────────────────────────┼───────────────────────────┐'));
children.push(codeP('          │                           │                           │'));
children.push(codeP('          ▼                           ▼                           ▼'));
children.push(codeP('┌─────────────────┐    ┌─────────────────────┐    ┌─────────────────┐'));
children.push(codeP('│ 异步任务队列     │    │    数据持久化层       │    │   缓存/消息层    │'));
children.push(codeP('│  (Celery)       │    │  (PostgreSQL +       │    │   (Redis)       │'));
children.push(codeP('│  ┌───────────┐   │    │   TimescaleDB)       │    │  ┌───────────┐  │'));
children.push(codeP('│  │ 回测引擎  │   │    │  ┌───────────────┐   │    │  │ 任务状态  │  │'));
children.push(codeP('│  │ 策略生成  │   │    │  │ 策略元数据     │   │    │  │ 会话缓存  │  │'));
children.push(codeP('│  │ 代码生成  │   │    │  │ 回测结果      │   │    │  │ 实时推送  │  │'));
children.push(codeP('│  │ 组合优化  │   │    │  │ 行情数据      │   │    │  └───────────┘  │'));
children.push(codeP('│  └───────────┘   │    │  └───────────────┘   │    └─────────────────┘'));
children.push(codeP('└─────────────────┘    └─────────────────────┘'));
children.push(h3('6.2 技术选型'));
children.push(makeTable([['层级', '技术选型', '备选方案', '选型理由'], ['**前端框架**', 'React 18 + TypeScript + Vite', 'Vue 3', 'ReactFlow 生态成熟，节点编辑器必需'], ['**UI 组件**', 'Ant Design 5 + shadcn/ui', 'Material-UI', '企业级设计系统，表格/表单能力突出'], ['**状态管理**', 'Zustand', 'Redux', '轻量，适合节点编辑器复杂状态'], ['**图表库**', 'ECharts 5 + Lightweight Charts', 'Recharts / Plotly', 'ECharts 通用，Lightweight Charts 金融专用'], ['**节点编辑器**', 'ReactFlow (@xyflow/react)', 'Rete.js', 'React 原生，文档完善，支持嵌套'], ['**后端框架**', 'FastAPI + SQLAlchemy 2.0 async', 'Flask', '异步原生，自动生成 OpenAPI'], ['**数据库**', 'PostgreSQL 15 + TimescaleDB', 'ClickHouse', 'ACID + 时序扩展，SQL 兼容'], ['**缓存**', 'Redis 7', 'Memcached', 'Pub/Sub + 任务状态 + 会话缓存'], ['**任务队列**', 'Celery + Redis broker', 'RQ', '成熟可靠，监控工具完善'], ['**数据科学**', 'NumPy, Pandas, DEAP, TA-Lib', 'polars', '生态成熟，DEAP 定制性强'], ['**回测引擎**', '自建（事件驱动 + 向量化混合）', 'RQAlpha', '完全可控，A 股规则原生集成'], ['**参数优化**', 'Optuna', 'Ray Tune', 'TPE + 早停剪枝，轻量高效'], ['**代码生成**', 'Jinja2 模板引擎', 'AST 生成', '模板灵活，维护成本低'], ['**部署**', 'Docker + Docker Compose', 'K8s', '快速迭代，适合 MVP']]));
children.push(h3('6.3 核心模块数据流'));
children.push(p('**策略生成流程**：'));
children.push(codeP('用户配置 → 策略生成引擎（DEAP）→ 生成策略树 → 回测引擎评估 → '));
children.push(codeP('适应度计算 → 选择/交叉/变异 → 下一代 → ... → 收敛 → '));
children.push(codeP('稳健性测试（MC + WFO）→ 过滤 → 策略仓库'));
children.push(p('**回测流程**：'));
children.push(codeP('策略 IR (JSON) → 策略编译器 → 信号生成函数 → 事件驱动回测 → '));
children.push(codeP('交易记录 → 绩效计算 → 结果数据结构 → 可视化 / 缓存'));
children.push(p('**代码生成流程**：'));
children.push(codeP('策略 IR (JSON) → IR 解析器 → 模板选择 → Jinja2 渲染 → '));
children.push(codeP('Python 代码 → 代码格式化 → 下载/预览'));
children.push(h3('6.4 预估代码量级'));
children.push(makeTable([['模块', '预估代码量', '说明'], ['前端（React + ReactFlow + 图表）', '25,000 ~ 35,000 行', '含编辑器、仪表盘、组合管理'], ['后端（FastAPI + 业务逻辑）', '15,000 ~ 20,000 行', '含 API、任务调度、数据管理'], ['回测引擎', '8,000 ~ 12,000 行', '含事件驱动、A 股规则、绩效计算'], ['策略生成引擎（DEAP 集成）', '5,000 ~ 8,000 行', '含 GP 定制、适应度函数、约束'], ['稳健性测试', '6,000 ~ 10,000 行', '含 MC、WFO、SPP、过拟合检测'], ['优化器', '3,000 ~ 5,000 行', '含简单优化、WFO 优化'], ['代码生成器', '2,000 ~ 3,000 行', '含模板引擎、多目标生成'], ['数据管理', '3,000 ~ 5,000 行', '含下载、存储、复权'], ['测试', '8,000 ~ 12,000 行', '单元测试 + 集成测试'], ['**总计**', '**75,000 ~ 110,000 行**', '不含依赖库']]));
children.push(p('---'));
children.push(h2('7. 版本规划建议'));
children.push(h3('7.1 MVP（v1.0）— 8-10 周'));
children.push(p('**目标**：跑通核心闭环：策略生成 → 回测 → 稳健性测试 → 代码生成'));
children.push(p('**核心交付**：'));
children.push(li('F-008 事件驱动回测（日线级别）'));
children.push(li('F-010 A 股规则引擎（T+1、涨跌停 10%）'));
children.push(li('F-001 GP 策略生成（单目标，50 个指标）'));
children.push(li('F-002 随机策略生成'));
children.push(li('F-014 Monte Carlo 模拟（3 种核心类型）'));
children.push(li('F-015 Walk-Forward 分析（标准模式）'));
children.push(li('F-020 过拟合检测（基础指标）'));
children.push(li('F-028 简单向导模式'));
children.push(li('F-029 节点编辑器（基础节点类型）'));
children.push(li('F-030 类型系统与校验'));
children.push(li('F-036 资金曲线图'));
children.push(li('F-038 统计仪表盘'));
children.push(li('F-043 Python 代码生成'));
children.push(li('F-045 Hermass DSL 生成'));
children.push(li('F-053 数据下载（Tushare 集成）'));
children.push(li('F-054 数据存储（TimescaleDB）'));
children.push(li('F-062 用户注册/登录'));
children.push(li('F-065 任务调度（Celery）'));
children.push(h3('7.2 v1.1 — +6-8 周'));
children.push(p('**目标**：完善核心功能，提升用户体验'));
children.push(p('**新增交付**：'));
children.push(li('F-013 成本模型（佣金、印花税、滑点）'));
children.push(li('F-022 简单优化器'));
children.push(li('F-026 局部改进'));
children.push(li('F-031 策略序列化'));
children.push(li('F-032 策略逻辑树展示'));
children.push(li('F-037 K 线 + 交易标记'));
children.push(li('F-039 交易记录表'));
children.push(li('F-047 组合构建'));
children.push(li('F-049 相关性矩阵'));
children.push(li('F-056 数据复权'));
children.push(li('F-064 策略仓库（版本管理）'));
children.push(h3('7.3 v2.0 — +8-10 周'));
children.push(p('**目标**：高级功能、扩展性、分布式'));
children.push(p('**新增交付**：'));
children.push(li('F-005 多目标适应度'));
children.push(li('F-006 多市场/多周期'));
children.push(li('F-016 Walk-Forward 矩阵'));
children.push(li('F-017 系统参数排列'));
children.push(li('F-018 优化轮廓分析'));
children.push(li('F-021 自动稳健性过滤'));
children.push(li('F-023 Walk-Forward 优化'));
children.push(li('F-033 自定义指标注册'));
children.push(li('F-034 多周期引用'));
children.push(li('F-048 组合回测'));
children.push(li('F-050 组合优化'));
children.push(li('F-058 自定义项目'));
children.push(li('F-059 插件系统'));
children.push(li('F-067 分布式计算（Ray）'));
children.push(h3('7.4 v3.0 — +10-12 周'));
children.push(p('**目标**：生产级、跨市场、商业化'));
children.push(p('**新增交付**：'));
children.push(li('F-007 模糊逻辑策略'));
children.push(li('F-011 Tick 级别回测'));
children.push(li('F-012 多资产组合回测'));
children.push(li('F-035 ATM（多出场）'));
children.push(li('F-051 组合 Walk-Forward'));
children.push(li('F-052 组合稳健性测试'));
children.push(li('F-060 自定义分析'));
children.push(li('F-061 策略导入'));
children.push(li('跨市场数据（港股、期货）'));
children.push(li('商业化功能（付费、配额、订阅）'));
children.push(p('---'));
children.push(h2('8. 验收标准'));
children.push(h3('8.1 核心功能验收标准'));
children.push(li('AC-F008-01: 正常回测'));
children.push(li('Given 用户已配置一个简单策略（MA 交叉）和 5 年日线数据'));
children.push(li('When 系统执行回测'));
children.push(li('Then 回测在 1 秒内完成，返回资金曲线和交易记录'));
children.push(li('AC-F008-02: 防未来函数'));
children.push(li('Given 策略中使用了当前 K 线的收盘价作为信号'));
children.push(li('When 系统执行回测'));
children.push(li('Then 信号仅在下一根 K 线开盘价执行，不会出现使用未来数据的情况'));
children.push(li('AC-F008-03: 边界条件'));
children.push(li('Given 数据存在停牌、除权除息等边界情况'));
children.push(li('When 系统执行回测'));
children.push(li('Then 回测正确处理停牌（无法交易）、除权（价格复权），不报错'));
children.push(li('AC-F010-01: T+1 规则'));
children.push(li('Given 策略在 Day 1 发出买入信号'));
children.push(li('When 系统执行回测'));
children.push(li('Then Day 1 持仓买入，Day 1 无法卖出；Day 2 可卖出'));
children.push(li('AC-F010-02: 涨跌停限制'));
children.push(li('Given 股票在 Day 1 涨停（涨幅 >= 10%）'));
children.push(li('When 策略发出买入信号'));
children.push(li('Then 买入信号无法成交（价格不可达到），回测记录为未成交'));
children.push(li('AC-F010-03: ST 股票限制'));
children.push(li('Given 股票标记为 ST（5% 涨跌停）'));
children.push(li('When 策略执行回测'));
children.push(li('Then 涨跌停限制为 5%，而非 10%'));
children.push(li('AC-F001-01: 策略生成'));
children.push(li('Given 用户配置 50 个指标、种群大小 100、进化 50 代'));
children.push(li('When 系统运行 GP 生成'));
children.push(li('Then 在 2 小时内生成并评估 5000 个策略，返回适应度排序后的策略列表'));
children.push(li('AC-F001-02: 策略合法性'));
children.push(li('Given GP 生成过程中产生策略树'));
children.push(li('When 系统评估策略'));
children.push(li('Then 所有策略树均通过语法约束检查，无非法操作（如除零、越界）'));
children.push(li('AC-F001-03: 收敛性'));
children.push(li('Given 运行 50 代 GP'));
children.push(li('When 观察每代最优适应度'));
children.push(li('Then 最优适应度在 30 代后趋于稳定（变化 < 5%）'));
children.push(li('AC-F014-01: 交易顺序随机化'));
children.push(li('Given 一个已回测策略（10 笔交易，净利润 1000 元）'));
children.push(li('When 运行 1000 次交易顺序随机化 Monte Carlo 模拟'));
children.push(li('Then 返回 1000 次模拟的净利润分布，中位数接近 1000 元，标准差 < 500 元'));
children.push(li('AC-F014-02: 参数扰动'));
children.push(li('Given 一个策略（MA 周期 = 20）'));
children.push(li('When 运行参数随机扰动（±10%）的 1000 次模拟'));
children.push(li('Then 80% 以上的模拟保持盈利（净利润 > 0）'));
children.push(li('AC-F014-03: 稳健性判定'));
children.push(li('Given 1000 次 Monte Carlo 模拟结果'));
children.push(li('When 系统评估稳健性'));
children.push(li('Then 盈利模拟比例 >= 80% 时判定为"通过"，否则"不通过"'));
children.push(li('AC-F015-01: 标准 WFO'));
children.push(li('Given 一个策略和 5 年数据，配置 IS=2 年、OOS=1 年、step=6 个月'));
children.push(li('When 运行 Walk-Forward 分析'));
children.push(li('Then 返回 5 个窗口的 WFER，每个窗口均有 IS 和 OOS 绩效'));
children.push(li('AC-F015-02: WFER 计算'));
children.push(li('Given 某窗口 IS 夏普 = 1.5，OOS 夏普 = 1.2'));
children.push(li('When 计算 WFER'));
children.push(li('Then WFER = 1.2 / 1.5 = 0.8'));
children.push(li('AC-F015-03: 参数稳定性'));
children.push(li('Given 多窗口 WFO 结果，参数轨迹变化 < 20%'));
children.push(li('When 评估参数稳定性'));
children.push(li('Then 参数稳定性评分 >= 0.8'));
children.push(li('AC-F029-01: 节点拖拽'));
children.push(li('Given 用户在节点面板选择一个技术指标节点（MA）'));
children.push(li('When 拖拽到画布并释放'));
children.push(li('Then 画布上生成 MA 节点，可配置参数（周期 = 20）'));
children.push(li('AC-F029-02: 节点连接'));
children.push(li('Given 画布上有两个节点（MA 输出、比较器输入）'));
children.push(li('When 用户从 MA 输出端口拖拽到比较器输入端口'));
children.push(li('Then 建立连接，比较器可读取 MA 输出序列'));
children.push(li('AC-F029-03: 类型校验'));
children.push(li('Given 用户尝试将一个布尔输出连接到一个数值输入'));
children.push(li('When 系统执行连接校验'));
children.push(li('Then 连接被拒绝，显示错误提示"类型不匹配：boolean 无法连接到 number"'));
children.push(li('AC-F029-04: 循环检测'));
children.push(li('Given 用户尝试创建循环连接（A→B→C→A）'));
children.push(li('When 系统执行连接校验'));
children.push(li('Then 连接被拒绝，显示错误提示"检测到循环依赖，策略图必须是 DAG"'));
children.push(li('AC-F043-01: 代码生成'));
children.push(li('Given 用户在节点编辑器中构建了一个策略（MA 交叉 + ATR 止损）'));
children.push(li('When 用户点击"生成代码"'));
children.push(li('Then 系统生成可直接运行的 Python 代码，包含数据加载、指标计算、信号生成、回测逻辑'));
children.push(li('AC-F043-02: 代码可执行性'));
children.push(li('Given 生成的 Python 代码文件'));
children.push(li('When 在本地 Python 环境运行（已安装依赖）'));
children.push(li('Then 代码无语法错误，运行结果与 Web 回测结果一致（收益差异 < 1%）'));
children.push(li('AC-F043-03: Hermass DSL 生成'));
children.push(li('Given 策略 IR 中包含 Hermass 特定标记'));
children.push(li('When 选择"Hermass DSL"模板'));
children.push(li('Then 生成符合 Hermass 策略框架语法规范的代码'));
children.push(p('---'));
children.push(h2('9. 假设与约束'));
children.push(h3('9.1 假设'));
children.push(li('用户具备基础的量化交易知识（理解均线、夏普比率等概念），但无需编程能力'));
children.push(li('A 股行情数据可通过 Tushare Pro 接口获取（需用户自备 API Key）'));
children.push(li('初期以单用户/小团队模式运行，暂不涉及多租户隔离'));
children.push(li('回测精度以日线为主，分钟线为辅，Tick 级别后续扩展'));
children.push(li('服务器资源配置：至少 8 核 CPU、32GB 内存、500GB SSD 存储'));
children.push(h3('9.2 约束'));
children.push(li('**技术约束**：Python 是主要后端语言，JavaScript/TypeScript 是主要前端语言；所有代码模块和架构命名保持英文，技术文档和复盘报告使用中文'));
children.push(li('**业务约束**：A 股市场特性（T+1、涨跌停）必须精确实现，否则策略回测结果无效'));
children.push(li('**数据约束**：A 股历史数据完整性受限于数据源，需处理停牌、退市等缺失数据情况'));
children.push(li('**合规约束**：不涉及实盘交易接口，仅提供回测和模拟交易功能；代码生成仅用于研究目的，用户自行承担实盘风险'));
children.push(li('**时间约束**：MVP 阶段目标 8-10 周，需合理控制功能范围'));
children.push(h3('9.3 风险'));
children.push(makeTable([['风险', '影响', '概率', '缓解措施'], ['GP 过拟合严重', '高', '高', '强制复杂度惩罚 + 训练/测试隔离 + 滚动回测 + 稳健性测试'], ['未来函数（Look-Ahead Bias）', '高', '中', '事件驱动架构 + 数据延迟注入 + 代码审计'], ['性能瓶颈（大规模回测慢）', '高', '中', '向量化计算 + 缓存 + 异步任务 + 后续 Ray 分布式'], ['数据质量问题（缺失、错误）', '中', '中', '数据质量检测 + 预处理管道 + 用户可手动修正'], ['策略 IR 设计不足导致后续扩展困难', '高', '中', '设计阶段充分评审 + 预留扩展字段 + 版本兼容'], ['用户学习曲线陡峭', '中', '高', '引导式教程 + 模板策略 + 交互式帮助'], ['开源依赖库弃用', '低', '中', '锁定版本 + 定期评估 + 备选方案']]));
children.push(p('---'));
children.push(h2('10. 开放问题'));
children.push(p('---'));
children.push(h2('11. 附录'));
children.push(h3('11.1 术语表'));
children.push(makeTable([['术语', '解释'], ['GP', 'Genetic Programming（遗传编程），一种进化算法，通过树形结构表示策略，通过交叉和变异操作进化'], ['NSGA-II', 'Non-dominated Sorting Genetic Algorithm II，多目标遗传算法，用于同时优化多个冲突目标'], ['WFO', 'Walk-Forward Optimization，滚动优化 + 样本外验证，模拟实盘定期调参'], ['WFER', 'Walk-Forward Efficiency Ratio，WFO 效率比 = OOS 绩效 / IS 绩效，衡量参数稳定性'], ['SPP', 'System Parameter Permutation，系统参数排列，遍历全参数空间评估策略稳定性'], ['MC', 'Monte Carlo，蒙特卡洛模拟，通过随机扰动测试策略稳健性'], ['OOS', 'Out-of-Sample，样本外测试，使用未参与训练的数据验证策略'], ['IR', 'Intermediate Representation，中间表示，策略的统一数据结构，用于序列化和代码生成'], ['ATR', 'Average True Range，平均真实波动范围，常用 volatility 指标'], ['MAE/MFE', 'Maximum Adverse/ Favorable Excursion，最大不利/有利偏移，分析交易执行质量'], ['DAG', 'Directed Acyclic Graph，有向无环图，策略节点编辑器的数据结构约束'], ['T+1', 'A 股交易规则，当日买入次日才能卖出'], ['Hermass', '用户当前构建的 AI 量化交易平台项目名称']]));
children.push(h3('11.2 参考文档链接'));
children.push(li('StrategyQuant 官网：https://strategyquant.com/'));
children.push(li('StrategyQuant 功能页：https://strategyquant.com/features/'));
children.push(li('DEAP 文档：https://deap.readthedocs.io/'));
children.push(li('Optuna 文档：https://optuna.readthedocs.io/'));
children.push(li('ReactFlow 文档：https://reactflow.dev/'));
children.push(li('FastAPI 文档：https://fastapi.tiangolo.com/'));
children.push(li('TimescaleDB 文档：https://docs.timescale.com/'));
children.push(li('Tushare 文档：https://tushare.pro/document/2'));
children.push(h3('11.3 调研报告引用'));
children.push(makeTable([['报告', '路径', '核心内容'], ['策略生成引擎技术调研', '`strategy_builder_tech_research.md`', 'DEAP 框架、回测引擎选型、A 股规则适配、性能优化'], ['稳健性测试技术调研', '`research/robustness_testing_report.md`', 'MC 9 种模拟、WFO 矩阵、SPP、过拟合检测（DSR/PBO/PSR）'], ['Web UI 与代码导出技术调研', '`technical_research_report.md`', 'ReactFlow 架构、代码生成、数据库设计、API 设计']]));

const doc = new Document({
  features: { updateFields: true },
  sections: [{
    properties: {
      page: {
        margin: { top: 1440, right: 1440, bottom: 1440, left: 1440 },
      }
    },
    headers: {
      default: new Header({
        children: [para(run("Hermass StrategyQuant 复刻 - 产品需求文档", { bold: true, size: 18 }), { alignment: AlignmentType.CENTER })]
      })
    },
    footers: {
      default: new Footer({
        children: [para(
          new TextRun({ children: [PageNumber.CURRENT], font, size: 18 }),
          { alignment: AlignmentType.CENTER }
        )]
      })
    },
    children,
  }],
});

fs.writeFileSync(outputPath, await Packer.toBuffer(doc));
console.log("Generated:", outputPath);
