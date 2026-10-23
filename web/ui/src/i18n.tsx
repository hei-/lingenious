import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from 'react';

export type Lang = 'zh' | 'en';

/** All user-facing strings live here. */
const dict = {
  zh: {
    appName: '零件匠',
    tagline: '参数化 CAD 智能体 · LLM 设计,几何内核裁决',
    newRun: '新建任务',
    history: '历史任务',
    examples: '示例',
    examplesHint: '只读,无需 API Key',
    readOnly: '只读示例',
    noRuns: '还没有任务。描述一个零件,开始第一次运行。',
    loading: '加载中…',
    retry: '重试',
    loadFailed: '加载失败',
    menu: '菜单',
    close: '关闭',
    mockBanner: '演示数据模式(mock):后端不可用或使用了 ?mock=1,下列结果为内置样例回放。',
    language: 'EN', languageSwitch: 'Switch to English',
    loginTitle: '需要访问口令', loginHint: '该服务设置了访问口令,请输入后继续。', loginToken: '访问口令', loginSubmit: '登录', logout: '退出登录', loginBad: '口令不正确。', loginWait: '尝试过于频繁,请稍后再试。', err_401: '需要登录。',
    theme: '主题',
    status_queued: '排队中', status_running: '运行中', status_success: '成功', status_failed: '未通过', status_error: '出错',
    // form
    reqLabel: '零件需求',
    reqPlaceholder: '例如:L 型铝支架,底板 100×60×6mm,立板高 40mm、厚 3mm,底板四角各一个 M6 通孔……',
    material: '材料', process: '工艺',
    mat_6061: '铝 6061', mat_7075: '铝 7075', mat_steel: '钢', mat_304: '不锈钢 304', mat_abs: 'ABS 塑料',
    proc_cnc_milling: 'CNC 铣削', proc_cnc_turning: 'CNC 车削', proc_3_axis: '三轴加工',
    submit: '开始生成', submitting: '提交中…',
    chips: '示例需求',
    llmOff: '服务端未配置 LLM(llm_configured=false),无法创建新任务。',
    llmOffHint: '请先查看左侧“示例”中的真实运行结果,或在服务端 .env 配置 API Key 后重启。',
    demoOff: '在线演示只能查看示例,不能新建任务。',
    demoOffHint: '左侧“示例”是三个真实运行的完整结果。要输入自己的需求,请按 README 用 Docker 自己部署。',
    demoBanner: '在线演示:只读的三个真实示例,无后端。自己部署后可新建任务和修改。',
    reqTooShort: '请至少写一句话描述零件。',
    reqTooLong: '需求过长(上限 {n} 字)。',
    submitFailed: '提交失败',
    welcomeTitle: '描述一个零件',
    welcomeSub: 'LLM 写 CadQuery 脚本,OCCT 几何内核逐条校验 L1 几何有效、L2 需求符合、L3 DFM 可制造性,失败则带数值回传修复,最多 4 轮。',
    // workspace
    version: '版本', request: '需求', tabs_model: '3D 模型', tabs_report: '校验报告', tabs_drawing: '工程图', tabs_code: '脚本', tabs_compare: '版本对比',
    timeline: '迭代时间线', downloads: '下载',
    dl_title: '下载', dl_menu: '更多下载选项', dl_step_short: 'STEP', dl_step_primary: '下载 STEP', dl_zip: '下载全部 (ZIP)', dl_zip_off: '演示模式不提供 ZIP', dl_more: '更多', dl_less: '收起',
    dl_g_manufacturing: '制造文件', dl_g_source: '可编辑源文件', dl_g_records: '记录',
    dl_d_step: '通用 3D 格式,可导入各类 CAD', dl_d_pdf: '三视图,用于打印 / 审阅', dl_d_dxf: '二维图纸,可在 CAD 中编辑',
    dl_d_py: '参数化脚本,改参数后可重新生成', dl_d_json: '规格、每轮脚本与问题', dl_d_log: '迭代日志(纯文本)',
    dl_n_step: 'STEP 模型', dl_n_pdf: '工程图 PDF', dl_n_dxf: '工程图 DXF', dl_n_py: '参数化脚本', dl_n_json: '运行记录', dl_n_log: '日志',
    dl_pending: '生成中…', dl_failed: '生成失败', dl_missing: '无此文件', dl_notPassed: '该版本未通过校验,文件仅供参考。',
    copy: '复制', copied: '已复制', copyFailed: '复制失败', dl_py_btn: '下载 .py',
    dl_step: 'STEP', dl_py: 'part.py', dl_json: 'run.json', dl_pdf: '图纸 PDF', dl_dxf: '图纸 DXF',
    // timeline
    step_parsing: '解析需求', step_spec: '生成规格', step_generating: '生成脚本', step_round: '第 {n} 轮', step_fixing: '修复中(第 {n} 轮)', step_done: '完成',
    passed: '通过', failedRound: '未通过', execFailed: '执行失败', seconds: '{s} 秒',
    done_success: '全部校验通过', done_failed: '结束:仍有未解决问题',
    runError: '运行出错', waiting: '等待服务端事件…', connLost: '事件连接中断,正在重连…',
    usage: '{calls} 次调用 · {p} + {c} tokens',
    issuesCount: '{n} 条问题', noIssues: '无问题', expand: '展开', collapse: '收起',
    codeChanges: '脚本变更', codeFull: '完整脚本', noCode: '此轮未记录脚本。',noCodeWhy: '此轮没有保存脚本:这是较早格式的运行记录(run.json 的 rounds 中没有 code 字段),只保留了最终脚本。',viewFinal: '查看最终脚本',moreRules: '另 {n} 项',versionStatus: '状态', diffNone: '与上一轮脚本相同。', diffGap: '… {n} 行未变 …',
    // report
    reportEmpty: '运行尚未产出校验结果。',
    allPass: '没有未解决的问题', unresolved: '未解决的问题', lastRound: '最后一轮结果',
    measured: '实测', required: '要求', hint: '建议', target: '对象',
    sev_error: '错误', sev_warning: '警告',
    level_L0: 'L0 执行', level_L1: 'L1 几何有效', level_L2: 'L2 需求符合', level_L3: 'L3 可制造性',
    spec: '规格', specEmpty: '规格尚未生成。', partType: '零件类型', features: '特征', assertions: '系统推导的断言', defaults: '采用的默认值', missing: '缺失信息',
    bbox: '包围盒', holeCount: '孔数', holeDiameters: '孔径', tol: '容差',
    // viewer
    v_fit: '适应视图', v_wire: '线框', v_edges: '边线', v_ortho: '正交', v_persp: '透视', v_axes: '坐标轴/网格', v_dims: '尺寸',
    v_fallback: '无 part.glb,显示包围盒示意体', v_loading: '加载模型…', v_noWebgl: '此浏览器不支持 WebGL,无法显示 3D。', v_hint: '拖动旋转 · 滚轮缩放 · 右键平移',
    viewerLabel: '三维模型视图',
    // drawing
    drawingEmpty: '没有可显示的工程图。', zoomIn: '放大', zoomOut: '缩小', reset: '复位', drawingHint: '滚轮缩放 · 拖动平移 · 键盘 + − 方向键',
    // modify
    modifyTitle: '修改当前模型', modifyPlaceholder: '例如:立板厚度改成 4mm', modifySubmit: '生成新版本', modifyOff: '示例为只读,不能修改。', modifyNoLlm: '服务端未配置 LLM,无法修改。',
    modifyFailed: '修改失败', modifyBusy: '当前版本仍在运行,完成后才能修改。',
    // compare
    compareA: '版本 A', compareB: '版本 B', compareNeed: '至少需要两个版本才能对比。', paramDiff: '参数差异', paramSame: '规格参数没有差异。', codeDiff: '脚本差异',
    param: '参数', loadingCode: '读取脚本…',
    err_503: '服务端未配置 LLM API Key。', err_403: '示例是只读的。', err_409: '该任务有版本仍在运行,或还没有成功的版本可供修改。', err_429: '排队任务过多,请稍后再试。', err_422: '输入不合法或过长。',
    done_need_info: '需求信息不足,请补充后重新提交', missingInfo: '缺少的信息', artifactFailed: '产物生成失败', status_need_info: '需补充信息',
    themeAuto: '主题:跟随系统', themeLight: '主题:浅色', themeDark: '主题:深色',
    synthetic: '脚本改参', syntheticTip: '该版本不是 LLM 生成的:由脚本化的参数修改(3→4mm)经真实流水线计算得到。',
    geomRound: '第 {n} 轮几何', backFinal: '回到最终', reconstructed: '还原', reconstructedTip: '该轮当时未保存脚本:由最终脚本还原(去掉后来补上的修正)并重新计算几何与位置,不是运行时的原始记录。', shownIn3d: '显示中', roReadonly: '示例为只读,新建任务后可修改', roNew: '新建任务', finalGeom: '最终',
    compareFix: '对比修正', compareOff: '退出对比', compareLegend: '红色半透明:第 {a} 轮(失败) · 实体:{b}', viewRoundGeom: '在 3D 中查看该轮几何', noRoundGeom: '该轮没有几何(未能执行)',
    locate: '在模型中定位', noLocation: '无位置信息', markerLegend: '问题位置',
    wTitle: '用文字描述零件,几何内核替你校验', wSub: 'LLM 写参数化脚本,OCCT 逐条检查有效性、需求符合与可制造性,不合格就带着数值回去重写。',
    wExamples: '先看看真实运行', wStep1: '描述', wStep1d: '写下尺寸、孔、材料。', wStep2: '校验迭代', wStep2d: '内核判定,失败带数值修复,最多 4 轮。', wStep3: '下载', wStep3d: 'STEP、参数化脚本、三视图工程图。',
    selPicked: '从 {runs} 次真实运行中选取第 {n} 次', selRun: '第 {n} 次', selRounds: '{n} 轮', selPickedMark: '(选中)',
    step_modify: '按修改要求生成:', globalRound: '全局第 {n} 轮(含之前的版本)', syntheticUsage: '脚本改参,未调用 LLM',
    reqEmpty: '先填写零件需求', kbdSubmit: '提交',
    usePrompt: '用这条需求', openExample: '打开示例', tagRounds: '{n} 轮修正后通过', tagFirst: '一次通过', tagNotPassed: '未通过', tagPrompt: '需求示例', usePromptOff: '需先配置 LLM Key', noRunsShort: '还没有任务,可从示例开始。',
    notFound: '找不到这个任务。', backHome: '返回',
  },
  en: {
    appName: 'Lingenious',
    tagline: 'Parametric CAD agent · the LLM designs, the geometry kernel judges',
    newRun: 'New run',
    history: 'History',
    examples: 'Examples',
    examplesHint: 'Read-only, no API key needed',
    readOnly: 'Read-only example',
    noRuns: 'No runs yet. Describe a part to start your first one.',
    loading: 'Loading…',
    retry: 'Retry',
    loadFailed: 'Failed to load',
    menu: 'Menu',
    close: 'Close',
    mockBanner: 'Mock mode: backend unavailable or ?mock=1 was used. Results below are a built-in replay.',
    language: '中', languageSwitch: '切换到中文',
    loginTitle: 'Access token required', loginHint: 'This server is protected by an access token. Enter it to continue.', loginToken: 'Access token', loginSubmit: 'Sign in', logout: 'Sign out', loginBad: 'Invalid token.', loginWait: 'Too many attempts, try again later.', err_401: 'Sign-in required.',
    theme: 'Theme',
    status_queued: 'Queued', status_running: 'Running', status_success: 'Success', status_failed: 'Not passed', status_error: 'Error',
    reqLabel: 'Part requirement',
    reqPlaceholder: 'e.g. L-shaped aluminium bracket, 100×60×6 mm base, 40 mm tall 3 mm wall, an M6 through hole in each base corner…',
    material: 'Material', process: 'Process',
    mat_6061: 'Al 6061', mat_7075: 'Al 7075', mat_steel: 'Steel', mat_304: 'Stainless 304', mat_abs: 'ABS',
    proc_cnc_milling: 'CNC milling', proc_cnc_turning: 'CNC turning', proc_3_axis: '3-axis',
    submit: 'Generate', submitting: 'Submitting…',
    chips: 'Example prompts',
    llmOff: 'The server has no LLM configured (llm_configured=false); new runs are disabled.',
    llmOffHint: 'Browse the real runs under "Examples" on the left, or set an API key in the server .env and restart.',
    demoOff: 'This online demo only shows the examples; new runs are disabled.',
    demoOffHint: 'The "Examples" on the left are three complete real runs. To try your own requirement, self-host with Docker as described in the README.',
    demoBanner: 'Online demo: three real example runs, read-only, no backend. Self-host to create runs and edits.',
    reqTooShort: 'Describe the part in at least one sentence.',
    reqTooLong: 'Requirement too long (max {n} characters).',
    submitFailed: 'Submit failed',
    welcomeTitle: 'Describe a part',
    welcomeSub: 'The LLM writes a CadQuery script; the OCCT kernel checks L1 validity, L2 requirement match and L3 DFM rules. Failures go back with numbers for repair, up to 4 rounds.',
    version: 'Version', request: 'Requirement', tabs_model: '3D model', tabs_report: 'Report', tabs_drawing: 'Drawing', tabs_code: 'Script', tabs_compare: 'Compare',
    timeline: 'Iteration timeline', downloads: 'Downloads',
    dl_title: 'Downloads', dl_menu: 'More download options', dl_step_short: 'STEP', dl_step_primary: 'Download STEP', dl_zip: 'Download all (ZIP)', dl_zip_off: 'ZIP is not available in mock mode', dl_more: 'More', dl_less: 'Less',
    dl_g_manufacturing: 'Manufacturing', dl_g_source: 'Editable source', dl_g_records: 'Records',
    dl_d_step: 'Universal 3D format for any CAD', dl_d_pdf: '3-view drawing for print / review', dl_d_dxf: '2D drawing, editable in CAD',
    dl_d_py: 'Parametric script; edit and rebuild', dl_d_json: 'Spec, scripts and issues per round', dl_d_log: 'Iteration log (plain text)',
    dl_n_step: 'STEP model', dl_n_pdf: 'Drawing PDF', dl_n_dxf: 'Drawing DXF', dl_n_py: 'Parametric script', dl_n_json: 'Run record', dl_n_log: 'Log',
    dl_pending: 'Generating…', dl_failed: 'Failed', dl_missing: 'Not available', dl_notPassed: 'This version did not pass the checks; files are for reference only.',
    copy: 'Copy', copied: 'Copied', copyFailed: 'Copy failed', dl_py_btn: 'Download .py',
    dl_step: 'STEP', dl_py: 'part.py', dl_json: 'run.json', dl_pdf: 'Drawing PDF', dl_dxf: 'Drawing DXF',
    step_parsing: 'Parsing requirement', step_spec: 'Spec derived', step_generating: 'Generating script', step_round: 'Round {n}', step_fixing: 'Fixing (round {n})', step_done: 'Done',
    passed: 'Passed', failedRound: 'Failed', execFailed: 'Execution failed', seconds: '{s} s',
    done_success: 'All checks passed', done_failed: 'Finished with unresolved issues',
    runError: 'Run error', waiting: 'Waiting for server events…', connLost: 'Event stream lost, reconnecting…',
    usage: '{calls} calls · {p} + {c} tokens',
    issuesCount: '{n} issues', noIssues: 'No issues', expand: 'Expand', collapse: 'Collapse',
    codeChanges: 'Script changes', codeFull: 'Full script', noCode: 'No script recorded for this round.',noCodeWhy: 'No script was saved for this round: this run uses an older format (rounds in run.json have no code field), so only the final script was kept.',viewFinal: 'View final script',moreRules: '+{n} more',versionStatus: 'Status', diffNone: 'Identical to the previous round.', diffGap: '… {n} unchanged lines …',
    reportEmpty: 'The run has not produced check results yet.',
    allPass: 'No unresolved issues', unresolved: 'Unresolved issues', lastRound: 'Last round result',
    measured: 'Measured', required: 'Required', hint: 'Hint', target: 'Target',
    sev_error: 'Error', sev_warning: 'Warning',
    level_L0: 'L0 Execution', level_L1: 'L1 Valid geometry', level_L2: 'L2 Requirement match', level_L3: 'L3 Manufacturability',
    spec: 'Spec', specEmpty: 'Spec not available yet.', partType: 'Part type', features: 'Features', assertions: 'Assertions derived by the system', defaults: 'Defaults used', missing: 'Missing information',
    bbox: 'Bounding box', holeCount: 'Hole count', holeDiameters: 'Hole diameters', tol: 'tolerance',
    v_fit: 'Fit view', v_wire: 'Wireframe', v_edges: 'Edges', v_ortho: 'Ortho', v_persp: 'Persp', v_axes: 'Axes / grid', v_dims: 'Dimensions',
    v_fallback: 'No part.glb; showing a bounding-box placeholder', v_loading: 'Loading model…', v_noWebgl: 'WebGL is unavailable in this browser.', v_hint: 'Drag to orbit · scroll to zoom · right-drag to pan',
    viewerLabel: '3D model viewer',
    drawingEmpty: 'No drawing available.', zoomIn: 'Zoom in', zoomOut: 'Zoom out', reset: 'Reset', drawingHint: 'Scroll to zoom · drag to pan · keys + − arrows',
    modifyTitle: 'Modify this model', modifyPlaceholder: 'e.g. make the wall 4 mm thick', modifySubmit: 'Create new version', modifyOff: 'Examples are read-only.', modifyNoLlm: 'The server has no LLM configured.',
    modifyFailed: 'Modify failed', modifyBusy: 'This version is still running.',
    compareA: 'Version A', compareB: 'Version B', compareNeed: 'Need at least two versions to compare.', paramDiff: 'Parameter differences', paramSame: 'No spec parameter differences.', codeDiff: 'Script diff',
    param: 'Parameter', loadingCode: 'Loading script…',
    err_503: 'The server has no LLM API key configured.', err_403: 'Examples are read-only.', err_409: 'A version of this run is still running, or there is no successful version to modify.', err_429: 'Too many queued runs, try again later.', err_422: 'Invalid or too long input.',
    done_need_info: 'More information needed; refine the requirement and resubmit', missingInfo: 'Missing information', artifactFailed: 'Artifact failed', status_need_info: 'Needs info',
    themeAuto: 'Theme: system', themeLight: 'Theme: light', themeDark: 'Theme: dark',
    synthetic: 'scripted edit', syntheticTip: 'Not generated by the LLM: a scripted parameter edit run through the real pipeline.',
    geomRound: 'Round {n} geometry', backFinal: 'Back to final', reconstructed: 'Reconstructed', reconstructedTip: 'The script of this round was not saved at the time: it was reconstructed from the final script (removing the later fix) and its geometry recomputed; not a run-time record.', shownIn3d: 'In 3D', roReadonly: 'Examples are read-only; create a new run to modify', roNew: 'New run', finalGeom: 'final',
    compareFix: 'Compare fix', compareOff: 'Exit compare', compareLegend: 'Translucent red: round {a} (failed) · solid: {b}', viewRoundGeom: 'View this round in 3D', noRoundGeom: 'No geometry for this round (it failed to execute)',
    locate: 'Locate on model', noLocation: 'No location', markerLegend: 'Issue locations',
    wTitle: 'Describe a part; the geometry kernel checks it', wSub: 'An LLM writes a parametric script; OCCT checks validity, requirement match and manufacturability, and failures go back with numbers.',
    wExamples: 'See real runs first', wStep1: 'Describe', wStep1d: 'Dimensions, holes, material.', wStep2: 'Check & iterate', wStep2d: 'Kernel verdicts; failures are repaired with numbers, up to 4 rounds.', wStep3: 'Download', wStep3d: 'STEP, parametric script, 3-view drawing.',
    selPicked: 'Picked run {n} of {runs} real runs', selRun: 'Run {n}', selRounds: '{n} rounds', selPickedMark: '(picked)',
    step_modify: 'Generate from the change:', globalRound: 'Overall round {n} (counting earlier versions)', syntheticUsage: 'Scripted edit, no LLM calls',
    reqEmpty: 'Describe the part first', kbdSubmit: 'to submit',
    usePrompt: 'Use this prompt', openExample: 'Open example', tagRounds: 'Passed after {n} rounds', tagFirst: 'Passed first try', tagNotPassed: 'Not passed', tagPrompt: 'Prompt idea', usePromptOff: 'Needs an LLM key', noRunsShort: 'No runs yet; start from an example.',
    notFound: 'Run not found.', backHome: 'Back',
  },
} as const;

export type Key = keyof typeof dict.zh;
type Vars = Record<string, string | number>;

interface Ctx { errMsg: (e: unknown) => string; lang: Lang; setLang: (l: Lang) => void; t: (k: Key, v?: Vars) => string; has: (k: string) => boolean; tr: (k: string, fb: string) => string }
const I18n = createContext<Ctx | null>(null);

function initialLang(): Lang {
  try { const s = localStorage.getItem('lang'); if (s === 'zh' || s === 'en') return s; } catch { /* storage blocked */ }
  return 'zh';
}

export function I18nProvider({ children }: { children: ReactNode }) {
  const [lang, setLangState] = useState<Lang>(initialLang);
  const setLang = useCallback((l: Lang) => { setLangState(l); try { localStorage.setItem('lang', l); } catch { /* ignore */ } }, []);
  useEffect(() => { document.documentElement.lang = lang === 'zh' ? 'zh-CN' : 'en'; }, [lang]);
  const value = useMemo<Ctx>(() => {
    const d = dict[lang] as Record<string, string>;
    const t = (k: Key, v?: Vars) => (d[k] ?? k).replace(/\{(\w+)\}/g, (_, n) => String(v?.[n] ?? ''));
    const errMsg = (e: unknown) => { const st = (e as { status?: number })?.status; const k = st ? `err_${st}` : ''; return k in d ? d[k] : (e as Error)?.message ?? String(e); };
    return { errMsg, lang, setLang, t, has: (k) => k in d, tr: (k, fb) => d[k] ?? fb };
  }, [lang, setLang]);
  return <I18n.Provider value={value}>{children}</I18n.Provider>;
}

export function useI18n(): Ctx {
  const c = useContext(I18n);
  if (!c) throw new Error('I18nProvider missing');
  return c;
}

/** Rule ids -> short human labels (fall back to the id). */
export const ruleLabels: Record<Lang, Record<string, string>> = {
  zh: {
    valid_solid: '实体有效', single_solid: '单一实体', positive_volume: '体积为正', bbox_match: '包围盒', hole_count: '孔数', hole_diameter: '孔径',
    hole_position: '孔位', volume_range: '体积范围', min_wall_thickness: '最小壁厚', hole_edge_distance: '孔边距', internal_corner_radius: '内圆角',
    hole_spacing: '孔间距', hole_depth_ratio: '孔深径比', deep_pocket: '深腔', thin_web_height: '薄筋高厚比',
  },
  en: {
    valid_solid: 'Valid solid', single_solid: 'Single solid', positive_volume: 'Positive volume', bbox_match: 'Bounding box', hole_count: 'Hole count', hole_diameter: 'Hole diameter',
    hole_position: 'Hole position', volume_range: 'Volume range', min_wall_thickness: 'Min wall thickness', hole_edge_distance: 'Hole-edge distance', internal_corner_radius: 'Internal corner radius',
    hole_spacing: 'Hole spacing', hole_depth_ratio: 'Hole depth/diameter', deep_pocket: 'Deep pocket', thin_web_height: 'Thin web height',
  },
};

export const EXAMPLE_PROMPTS: Record<Lang, string[]> = {
  zh: [
    'L 型铝支架:底板 100×60×6mm,立板沿长边,高 40mm、厚 3mm,底板四角各一个 M6 通孔,立板中间一个直径 20 的圆孔。',
    '矩形安装板 120×80×8mm,四角各一个 M8 通孔,中心一个直径 30 的圆孔,四周倒角 R3。',
    'U 型支架:宽 50mm,长 80mm,高 35mm,壁厚 4mm,两侧壁各一个直径 8 的孔。',
  ],
  en: [
    'L-shaped aluminium bracket: 100×60×6 mm base, 40 mm tall 3 mm wall along the long edge, M6 through holes in the four base corners, a 20 mm hole in the middle of the wall.',
    'Rectangular mounting plate 120×80×8 mm, M8 through holes in the four corners, a 30 mm hole at the centre, R3 corner fillets.',
    'U-bracket: 50 mm wide, 80 mm long, 35 mm tall, 4 mm wall, one 8 mm hole in each side wall.',
  ],
};
