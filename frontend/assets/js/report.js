const app = document.getElementById('app');
    const subtitle = document.getElementById('reportSubtitle');
    const sourceNote = document.getElementById('sourceNote');
    const refreshButton = document.getElementById('refreshButton');

    const fmtNumber = new Intl.NumberFormat('zh-CN');
    const fmtScore = new Intl.NumberFormat('zh-CN', { maximumFractionDigits: 1 });
    let charts = [];
    let unmountRadarHover = null;

    function handleViewportResize() {
      charts.forEach(chart => chart.resize());
    }

    function escapeHtml(value) {
      return String(value ?? '')
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#039;');
    }

    function renderInlineMarkdown(value) {
      return escapeHtml(value)
        .replace(/`([^`]+)`/g, '<code>$1</code>')
        .replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>')
        .replace(/__([^_]+)__/g, '<strong>$1</strong>');
    }

    function normalizeMarkdown(value) {
      const text = String(value ?? '').trim();
      const fenced = text.match(/^```(?:markdown|md)?\s*\n([\s\S]*?)\n```\s*$/i);
      return fenced ? fenced[1].trim() : text;
    }

    function markdownToHtml(value) {
      const markdown = normalizeMarkdown(value);
      if (window.marked?.parse) {
        return window.marked.parse(escapeHtml(markdown), {
          async: false,
          breaks: true,
          gfm: true,
          mangle: false,
          headerIds: false
        }) || '<p>等待分析</p>';
      }

      const lines = markdown.replace(/\r\n?/g, '\n').split('\n');
      const html = [];
      let paragraph = [];
      let listType = '';
      let inCodeBlock = false;
      let codeLines = [];

      const closeParagraph = () => {
        if (!paragraph.length) return;
        html.push(`<p>${renderInlineMarkdown(paragraph.join(' '))}</p>`);
        paragraph = [];
      };

      const closeList = () => {
        if (!listType) return;
        html.push(`</${listType}>`);
        listType = '';
      };

      const openList = type => {
        if (listType === type) return;
        closeList();
        html.push(`<${type}>`);
        listType = type;
      };

      for (const rawLine of lines) {
        const line = rawLine.trimEnd();
        const trimmed = line.trim();

        if (trimmed.startsWith('```')) {
          closeParagraph();
          closeList();
          if (inCodeBlock) {
            html.push(`<pre><code>${escapeHtml(codeLines.join('\n'))}</code></pre>`);
            codeLines = [];
          }
          inCodeBlock = !inCodeBlock;
          continue;
        }

        if (inCodeBlock) {
          codeLines.push(rawLine);
          continue;
        }

        if (!trimmed) {
          closeParagraph();
          closeList();
          continue;
        }

        const heading = trimmed.match(/^(#{1,4})\s+(.+)$/);
        if (heading) {
          closeParagraph();
          closeList();
          const level = heading[1].length;
          html.push(`<h${level}>${renderInlineMarkdown(heading[2])}</h${level}>`);
          continue;
        }

        const unordered = trimmed.match(/^[-*+]\s+(.+)$/);
        if (unordered) {
          closeParagraph();
          openList('ul');
          html.push(`<li>${renderInlineMarkdown(unordered[1])}</li>`);
          continue;
        }

        const ordered = trimmed.match(/^\d+\.\s+(.+)$/);
        if (ordered) {
          closeParagraph();
          openList('ol');
          html.push(`<li>${renderInlineMarkdown(ordered[1])}</li>`);
          continue;
        }

        closeList();
        paragraph.push(trimmed);
      }

      if (inCodeBlock) {
        html.push(`<pre><code>${escapeHtml(codeLines.join('\n'))}</code></pre>`);
      }
      closeParagraph();
      closeList();
      return html.join('') || '<p>等待分析</p>';
    }

    function formatDate(ms) {
      const date = new Date(Number(ms));
      if (Number.isNaN(date.getTime())) return '--';
      const y = date.getFullYear();
      const m = String(date.getMonth() + 1).padStart(2, '0');
      const d = String(date.getDate()).padStart(2, '0');
      return `${y}.${m}.${d}`;
    }

    function percent(value, digits = 1) {
      if (!Number.isFinite(value)) return '--';
      return `${value.toFixed(digits)}%`;
    }

    async function loadReport() {
      if ((location.hostname === '127.0.0.1' || location.hostname === 'localhost') && location.port === '8765') {
        return loadLocalFallback();
      }
      try {
        const res = await fetch('/api/report', { cache: 'no-store' });
        const payload = await res.json().catch(() => null);
        if (!res.ok || !payload?.ok) {
          const message = payload?.error?.message || `/api/report ${res.status}`;
          const details = payload?.error?.details ? `：${JSON.stringify(payload.error.details)}` : '';
          throw new Error(`${message}${details}`);
        }
        return payload.data;
      } catch (error) {
        if (location.hostname === '127.0.0.1' || location.hostname === 'localhost') {
          return loadLocalFallback();
        }
        throw error;
      }
    }

    async function refreshReport() {
      refreshButton.disabled = true;
      const previousText = refreshButton.textContent;
      refreshButton.textContent = '更新中';
      sourceNote.textContent = '正在串行更新上游数据';
      try {
        const res = await fetch('/api/report/refresh', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          cache: 'no-store'
        });
        const payload = await res.json().catch(() => null);
        if (!res.ok || !payload?.ok) {
          const message = payload?.error?.message || `HTTP ${res.status}`;
          const retryAfter = payload?.error?.details?.retry_after_seconds;
          throw new Error(retryAfter ? `${message}，约 ${Math.ceil(retryAfter / 60)} 分钟后可再试` : message);
        }
        await boot();
      } catch (error) {
        sourceNote.textContent = `手动更新失败：${error.message}`;
      } finally {
        refreshButton.textContent = previousText;
        refreshButton.disabled = false;
      }
    }

    async function loadLocalFallback() {
      const [historyRes, reportRes, errorTree] = await Promise.all([
        fetch('live_exercise_history.json', { cache: 'no-store' }).then(res => res.json()),
        fetch('live_user_analysis.json', { cache: 'no-store' }).then(res => res.json()),
        fetch('live_error_keypoint_tree.json', { cache: 'no-store' }).then(res => res.json())
      ]);
      const tikuReport = reportRes.data.tikuReport;
      return {
        summary: {
          userId: tikuReport.userId,
          quiz: tikuReport.userQuiz || {},
          answerCount: tikuReport.answerCount,
          exerciseCount: tikuReport.exerciseCount,
          correctCount: tikuReport.correctCount,
          forecastScore: tikuReport.forecastScore,
          avgForecastScore: tikuReport.avgForecastScore,
          maxForecastScore: tikuReport.maxForecastScore,
          exerciseDay: tikuReport.exerciseDay,
          totalUserCount: tikuReport.totalUserCount,
          scoreRankIndex: tikuReport.scoreRankIndex,
          fullMark: tikuReport.fullMark,
          maxAnswerCount: tikuReport.maxAnswerCount,
          answerCountRankIndex: tikuReport.answerCountRankIndex
        },
        trends: tikuReport.trends || [],
        keypoints: tikuReport.keypoints || [],
        history: {
          cursor: historyRes.data.cursor,
          items: historyRes.data.historyItems || []
        },
        errors: errorTree,
        meta: {
          stale: true,
          fetched_at: new Date().toISOString(),
          source: 'local-fallback'
        }
      };
    }

    function adaptReport(apiReport) {
      const summary = apiReport.summary || {};
      return {
        userId: summary.userId,
        userQuiz: summary.quiz || {},
        answerCount: summary.answerCount,
        exerciseCount: summary.exerciseCount,
        correctCount: summary.correctCount,
        forecastScore: summary.forecastScore,
        avgForecastScore: summary.avgForecastScore,
        maxForecastScore: summary.maxForecastScore,
        exerciseDay: summary.exerciseDay,
        totalUserCount: summary.totalUserCount,
        scoreRankIndex: summary.scoreRankIndex,
        fullMark: summary.fullMark,
        maxAnswerCount: summary.maxAnswerCount,
        answerCountRankIndex: summary.answerCountRankIndex,
        trends: apiReport.trends || [],
        keypoints: apiReport.keypoints || []
      };
    }

    function buildStats(report) {
      const accuracy = report.answerCount ? report.correctCount / report.answerCount * 100 : 0;
      const rankText = report.totalUserCount ? `${fmtNumber.format(report.scoreRankIndex)} / ${fmtNumber.format(report.totalUserCount)}` : '--';
      const answerRankText = report.answerCountRankIndex ? `${fmtNumber.format(report.answerCountRankIndex)} / ${fmtNumber.format(report.totalUserCount || report.maxAnswerCount || 0)}` : '--';
      return `
        <div class="stats">
          <div class="stat">
            <div class="stat-label">预测分</div>
            <div class="stat-value">${fmtScore.format(report.forecastScore)}</div>
            <div class="stat-context">平均 ${fmtScore.format(report.avgForecastScore)} / 满分 ${report.fullMark}</div>
          </div>
          <div class="stat">
            <div class="stat-label">答题正确率</div>
            <div class="stat-value">${percent(accuracy)}</div>
            <div class="stat-context">${fmtNumber.format(report.correctCount)} / ${fmtNumber.format(report.answerCount)} 题</div>
          </div>
          <div class="stat">
            <div class="stat-label">练习规模</div>
            <div class="stat-value">${fmtNumber.format(report.exerciseCount)}</div>
            <div class="stat-context">${fmtNumber.format(report.exerciseDay)} 天练习记录</div>
          </div>
          <div class="stat stat-wide">
            <div class="stat-label">预测分排名</div>
            <div class="stat-value">${rankText}</div>
            <div class="stat-context">答题量排名 ${answerRankText}</div>
            <div class="stat-extra">
              <span>考试类型：${escapeHtml(report.userQuiz?.name || '--')}</span>
              <span>官网预测最高分：${fmtScore.format(report.maxForecastScore)}</span>
            </div>
          </div>
        </div>
      `;
    }
    function trendChart(report) {
      const trends = [...report.trends].sort((a, b) => a.time - b.time);
      if (trends.length < 2) return '<div class="empty">趋势点不足</div>';

      return `
        <div class="chart-wrap surface">
          <div class="echart" id="trendChart" role="img" aria-label="预测分趋势图，纵轴最大值为100"></div>
        </div>
      `;
    }

    function horizontalBars(items, options = {}) {
      const max = options.max ?? Math.max(...items.map(item => item.value), 1);
      const formatter = options.formatter || (value => fmtNumber.format(value));
      return `
        <div class="bar-chart">
          ${items.map(item => `
            <div class="bar-row">
              <div class="bar-label" title="${escapeHtml(item.label)}">${escapeHtml(item.label)}</div>
              <div class="bar-track" aria-label="${escapeHtml(item.label)} ${formatter(item.value)}">
                <div class="bar-fill ${item.alt ? 'alt' : ''}" style="width:${Math.min(item.value / max * 100, 100)}%"></div>
              </div>
              <div class="metric">${formatter(item.value)}</div>
            </div>
          `).join('')}
        </div>
      `;
    }

    function summaryCard(report) {
      const sorted = [...report.keypoints].sort((a, b) => (b.answerCount || 0) - (a.answerCount || 0));
      const weakest = [...report.keypoints].filter(item => item.answerCount > 0).sort((a, b) => a.correctRatio - b.correctRatio)[0];
      const strongest = [...report.keypoints].filter(item => item.answerCount > 0).sort((a, b) => b.correctRatio - a.correctRatio)[0];
      return `
        <div class="summary-card surface">
          <ul class="insight-list">
            <li><span>练习最多模块</span><span class="metric">${escapeHtml(sorted[0]?.name || '--')}</span></li>
            <li><span>当前薄弱模块</span><span class="metric">${escapeHtml(weakest?.name || '--')}</span></li>
            <li><span>当前优势模块</span><span class="metric">${escapeHtml(strongest?.name || '--')}</span></li>
          </ul>
        </div>
      `;
    }
    function topReportBlocks(report) {
      return `
        <section class="section report-main-section">
          <div class="report-charts report-main-grid">
            <div class="report-chart-panel">
              <div class="section-head">
                <h2>能力分析</h2>
              </div>
              <div class="mini-chart surface">
                <div class="echart radar" id="rankChart" role="img" aria-label="能力分析六边形报告表单"></div>
              </div>
            </div>
            <div class="report-chart-panel">
              <div class="section-head">
                <h2>模块正确率</h2>
              </div>
              <div class="mini-chart surface">
                <div class="echart compact" id="correctRatioChart" role="img" aria-label="模块正确率图表"></div>
              </div>
            </div>
            <div class="report-chart-panel">
              <div class="section-head">
                <h2>答题量分布</h2>
              </div>
              <div class="mini-chart surface">
                <div class="echart compact" id="answerCountChart" role="img" aria-label="答题量分布图表"></div>
              </div>
            </div>
          </div>
        </section>
      `;
    }
    function reportCharts(report) {
      return '';
    }
    function overviewPanel(report, historyItems = []) {
      return `
        <section class="panel active" id="panel-overview">
          ${buildStats(report)}
          ${topReportBlocks(report)}
          ${reportCharts(report)}
          <section class="section overview-history-section">
            ${historyBlock(historyItems, { idPrefix: 'overview' })}
          </section>
        </section>
      `;
    }
    function historyPanel(historyItems) {
      const finished = historyItems.filter(item => item.status === 1);
      const pending = historyItems.length - finished.length;
      const totalQuestions = finished.reduce((sum, item) => sum + (item.questionCount || 0), 0);
      const totalCorrect = finished.reduce((sum, item) => sum + (item.correctCount || 0), 0);
      return `
        <section class="panel" id="panel-history">
          <div class="stats">
            <div class="stat">
              <div class="stat-label">历史记录</div>
              <div class="stat-value">${historyItems.length}</div>
              <div class="stat-context">当前接口返回条数</div>
            </div>
            <div class="stat">
              <div class="stat-label">已完成练习</div>
              <div class="stat-value">${finished.length}</div>
              <div class="stat-context">${pending} 条可继续做题</div>
            </div>
            <div class="stat">
              <div class="stat-label">完成题量</div>
              <div class="stat-value">${totalQuestions}</div>
              <div class="stat-context">历史列表内统计</div>
            </div>
            <div class="stat">
              <div class="stat-label">列表正确率</div>
              <div class="stat-value">${percent(totalQuestions ? totalCorrect / totalQuestions * 100 : 0)}</div>
              <div class="stat-context">${totalCorrect} / ${totalQuestions} 题</div>
            </div>
          </div>
          <div class="controls">
            <label for="historyFilter" class="muted">状态</label>
            <select id="historyFilter">
              <option value="all">全部</option>
              <option value="finished">已完成</option>
              <option value="pending">继续做题</option>
            </select>
          </div>
          <div class="history-list" id="historyList"></div>
        </section>
      `;
    }

    function historyBlock(historyItems, options = {}) {
      const idPrefix = options.idPrefix || 'errors';
      const filterId = `${idPrefix}HistoryFilter`;
      const listId = `${idPrefix}HistoryList`;
      const recent = recentHistoryItems(historyItems);
      const finished = recent.filter(item => item.status === 1);
      const totalQuestions = finished.reduce((sum, item) => sum + (item.questionCount || 0), 0);
      const totalCorrect = finished.reduce((sum, item) => sum + (item.correctCount || 0), 0);
      return `
        <div class="section-head history-section-head">
          <h2>最近 10 次练习历史</h2>
          <span class="muted">共 ${historyItems.length} 条，仅展示最近 10 条</span>
        </div>
        <div class="stats compact-stats">
          <div class="stat">
            <div class="stat-label">展示记录</div>
            <div class="stat-value">${recent.length}</div>
            <div class="stat-context">最近练习</div>
          </div>
          <div class="stat">
            <div class="stat-label">已完成练习</div>
            <div class="stat-value">${finished.length}</div>
            <div class="stat-context">最近 10 次内</div>
          </div>
          <div class="stat">
            <div class="stat-label">完成题量</div>
            <div class="stat-value">${totalQuestions}</div>
            <div class="stat-context">最近完成记录</div>
          </div>
          <div class="stat">
            <div class="stat-label">列表正确率</div>
            <div class="stat-value">${percent(totalQuestions ? totalCorrect / totalQuestions * 100 : 0)}</div>
            <div class="stat-context">${totalCorrect} / ${totalQuestions} 题</div>
          </div>
        </div>
        <div class="controls">
          <label for="${filterId}" class="muted">状态</label>
          <select id="${filterId}" data-history-filter="${idPrefix}">
            <option value="all">全部</option>
            <option value="finished">已完成</option>
            <option value="pending">继续做题</option>
          </select>
        </div>
        <div class="history-list" id="${listId}" data-history-list="${idPrefix}"></div>
      `;
    }

    function recentHistoryItems(historyItems) {
      return [...historyItems]
        .sort((a, b) => Number(b.updatedTime || 0) - Number(a.updatedTime || 0))
        .slice(0, 10);
    }

    function renderHistoryList(historyItems, filter = 'all', idPrefix = 'errors') {
      const list = document.querySelector(`[data-history-list="${idPrefix}"]`);
      if (!list) return;
      const items = recentHistoryItems(historyItems).filter(item => {
        if (filter === 'finished') return item.status === 1;
        if (filter === 'pending') return item.status !== 1;
        return true;
      });
      list.innerHTML = items.length ? items.map(item => `
        <article class="history-item">
          <div>
            <div class="history-title">${escapeHtml(item.sheetName || '--')}</div>
            <div class="history-meta">
              <span>难度 ${fmtScore.format(item.difficulty || 0)}</span>
              <span>${formatDate(item.updatedTime)}</span>
              <span>题量 ${item.questionCount || 0}</span>
            </div>
          </div>
          <div>
            ${item.status === 1
              ? `<span class="score-pill">共 ${item.questionCount || 0} 题，答对 <strong>${item.correctCount || 0}</strong> 题</span>`
              : '<span class="status-pill">继续做题</span>'}
          </div>
        </article>
      `).join('') : '<div class="empty">当前筛选下没有练习记录</div>';
    }

    function analysisPanel(historyItems = [], errorTree = []) {
      const provider = localStorage.getItem('aiProvider') || 'relay';
      const scope = analysisScope(historyItems, errorTree);
      return `
        <section class="panel" id="panel-analysis">
          <div class="section-head">
            <h2>AI 分析</h2>
            <span class="muted">服务商：${escapeHtml(provider)}</span>
          </div>
          <div class="ai-analysis surface">
            <div class="ai-toolbar">
              <button type="button" id="startAnalysisButton" class="refresh-action">开始分析当前错题</button>
              <button type="button" class="secondary-action" data-open-settings>切换 AI 服务商</button>
            </div>
            <div id="analysisStatus" class="analysis-status">${analysisStatusText('ready', provider, scope)}</div>
            <div id="analysisOutput" class="analysis-output markdown-body">等待分析</div>
          </div>
        </section>
      `;
    }
    function countQuestions(node) {
      if (!node || typeof node !== 'object') return 0;
      const own = Array.isArray(node.questionIds) ? node.questionIds.length : 0;
      const child = Array.isArray(node.children) ? node.children.reduce((sum, item) => sum + countQuestions(item), 0) : 0;
      return own + child;
    }

    function countChildNodes(node) {
      if (!node || typeof node !== 'object') return 0;
      const children = Array.isArray(node.children) ? node.children : [];
      return children.reduce((sum, child) => sum + 1 + countChildNodes(child), 0);
    }

    function analysisScope(historyItems = [], errorTree = []) {
      const tree = Array.isArray(errorTree) ? errorTree : [];
      const histories = Array.isArray(historyItems) ? historyItems : [];
      const finished = histories.filter(item => item.status === 1);
      const wrongQuestions = tree.reduce((sum, item) => sum + countQuestions(item), 0);
      const knowledgePoints = tree.reduce((sum, item) => sum + 1 + countChildNodes(item), 0);
      const practicedQuestions = finished.reduce((sum, item) => sum + (Number(item.questionCount) || 0), 0);
      return {
        wrongQuestions,
        modules: tree.length,
        knowledgePoints,
        finishedPractices: finished.length,
        practicedQuestions
      };
    }

    function analysisScopeSummary(scope) {
      const parts = [
        `${fmtNumber.format(scope.wrongQuestions)} 道错题`,
        `${fmtNumber.format(scope.modules)} 个一级模块`,
        `${fmtNumber.format(scope.knowledgePoints)} 个知识点`
      ];
      if (scope.finishedPractices) {
        parts.push(`近 ${fmtNumber.format(scope.finishedPractices)} 次已完成练习共 ${fmtNumber.format(scope.practicedQuestions)} 题`);
      }
      return parts.join('，');
    }

    function analysisStatusText(state, provider, scope, progress = {}) {
      const summary = analysisScopeSummary(scope);
      if (state === 'running') {
        const receivedText = progress.receivedChars ? `，已收到 ${fmtNumber.format(progress.receivedChars)} 字分析内容` : '';
        return `分析中：正在调用 ${provider}，本次会结合 ${summary}${receivedText}。`;
      }
      if (state === 'done') {
        const receivedText = progress.receivedChars ? `，生成 ${fmtNumber.format(progress.receivedChars)} 字结果` : '';
        return `分析完成：已完成 ${summary} 的 AI 诊断${receivedText}。`;
      }
      if (state === 'error') {
        return `分析失败：已准备 ${summary}，请检查 AI 服务商配置或后端日志后重试。`;
      }
      return `开始状态：已准备 ${summary}。点击开始后将调用 ${provider} 并流式返回结果。`;
    }

    function childKeypoints(node) {
      return Array.isArray(node?.keypoints) ? node.keypoints : [];
    }

    function correctCountFromRatio(node) {
      const answerCount = Number(node?.answerCount) || 0;
      const ratio = Number(node?.correctRatio) || 0;
      return Math.round(answerCount * ratio / 100);
    }

    function errorNodeByName(errorTree) {
      const map = new Map();
      const walk = node => {
        if (!node || typeof node !== 'object') return;
        map.set(node.name, node);
        (Array.isArray(node.children) ? node.children : []).forEach(walk);
      };
      errorTree.forEach(walk);
      return map;
    }

    function progressClass(ratio, target = 0) {
      if (target && ratio >= target) return 'ok';
      if (target && ratio >= target * .75) return 'warn';
      return '';
    }

    function masteryProgress(item, options = {}) {
      const ratio = Number(item.correctRatio) || 0;
      const target = Number(item.targetCorrectRatio) || 0;
      const cls = options.showTarget ? progressClass(ratio, target) : (ratio >= 80 ? 'ok' : ratio >= 60 ? 'warn' : '');
      const clampedRatio = Math.min(Math.max(ratio, 0), 100);
      const hoverLeft = Math.min(Math.max(clampedRatio, 8), 92);
      return `
        <div class="mastery-progress">
          <div class="progress" aria-label="${escapeHtml(item.name)}正确率 ${percent(ratio)}">
            <div class="bar ${cls}" style="width:${clampedRatio}%"></div>
            <span class="progress-hover-value" style="--hover-left:${hoverLeft}%">${percent(ratio)}</span>
            ${options.showTarget && target ? `<span class="target-marker" style="left:${Math.min(Math.max(target, 0), 100)}%"></span>` : ''}
          </div>
          <div class="progress-meta">
            <span>${fmtNumber.format(correctCountFromRatio(item))} / ${fmtNumber.format(Number(item.answerCount) || 0)} 题 · ${percent(ratio)}</span>
            ${options.showTarget ? `<span>目标 ${target ? percent(target, 0) : '--'}</span>` : ''}
          </div>
        </div>
      `;
    }

    function renderMasteryChild(item, errorsByName, depth = 0) {
      const children = childKeypoints(item);
      const errorTotal = countQuestions(errorsByName.get(item.name));
      const hasChildren = children.length > 0;
      return `
        <details class="mastery-child-detail" style="margin-left:${Math.min(depth, 3) * 14}px">
          <summary class="mastery-child">
            <div>
              <div class="mastery-title">${hasChildren ? '<span class="toggle-mark" aria-hidden="true"></span>' : '<span class="toggle-spacer" aria-hidden="true"></span>'}<span class="mastery-name">${escapeHtml(item.name)}</span></div>
              <div class="mastery-meta">题库 ${fmtNumber.format(item.questionCount || 0)} 题 · 已做 ${fmtNumber.format(item.answerCount || 0)} 题</div>
            </div>
            ${masteryProgress(item)}
            <div class="mastery-count">${fmtNumber.format(errorTotal)} 错题</div>
          </summary>
          ${hasChildren ? `<div class="mastery-grandchildren">${children.map(child => renderMasteryChild(child, errorsByName, depth + 1)).join('')}</div>` : ''}
        </details>
      `;
    }

    function renderMasteryDetail(item, errorsByName) {
      const errorTotal = countQuestions(errorsByName.get(item.name));
      const children = childKeypoints(item);
      return `
        <details class="mastery-detail">
          <summary>
            <div>
              <div class="mastery-title"><span class="toggle-mark" aria-hidden="true"></span><span class="mastery-name">${escapeHtml(item.name)}</span></div>
              <div class="mastery-meta">${children.length} 个二级知识点 · 题库 ${fmtNumber.format(item.questionCount || 0)} 题</div>
            </div>
            ${masteryProgress(item, { showTarget: true })}
            <div class="mastery-count">${fmtNumber.format(errorTotal)} 错题</div>
          </summary>
          <div class="mastery-children">
            ${children.length ? children.map(child => renderMasteryChild(child, errorsByName)).join('') : '<div class="empty">暂无下级知识点</div>'}
          </div>
        </details>
      `;
    }

    function errorsPanel(errorTree, report, historyItems = []) {
      const total = errorTree.reduce((sum, item) => sum + countQuestions(item), 0);
      const errorsByName = errorNodeByName(errorTree);
      const keypoints = report.keypoints || [];
      return `
        <section class="panel" id="panel-errors">
          <div class="stats">
            <div class="stat">
              <div class="stat-label">错题节点</div>
              <div class="stat-value">${errorTree.length}</div>
              <div class="stat-context">一级知识点</div>
            </div>
            <div class="stat">
              <div class="stat-label">错题总量</div>
              <div class="stat-value">${fmtNumber.format(total)}</div>
              <div class="stat-context">含子知识点聚合</div>
            </div>
            <div class="stat">
              <div class="stat-label">错题最多</div>
              <div class="stat-value">${escapeHtml([...errorTree].sort((a, b) => countQuestions(b) - countQuestions(a))[0]?.name || '--')}</div>
              <div class="stat-context">一级模块</div>
            </div>
            <div class="stat">
              <div class="stat-label">数据状态</div>
              <div class="stat-value">已同步</div>
              <div class="stat-context">来自接口响应</div>
            </div>
          </div>
          <div class="section-head">
            <h2>知识点掌握</h2>
            <span class="muted">一级题型含目标线，展开后展示二级知识点正确率</span>
          </div>
          <div class="mastery-tree">
            ${keypoints.length ? keypoints.map(item => renderMasteryDetail(item, errorsByName)).join('') : '<div class="empty">暂无知识点数据</div>'}
          </div>
        </section>
      `;
    }

    function chartColors() {
      const style = getComputedStyle(document.documentElement);
      return {
        text: style.getPropertyValue('--text').trim(),
        muted: style.getPropertyValue('--muted').trim(),
        line: style.getPropertyValue('--line').trim(),
        accent: style.getPropertyValue('--accent').trim(),
        ok: style.getPropertyValue('--ok').trim(),
        warn: style.getPropertyValue('--warn').trim()
      };
    }

    function registerChart(id, option) {
      const el = document.getElementById(id);
      if (!el || !window.echarts) return;
      const chart = echarts.init(el, null, { renderer: 'canvas' });
      chart.setOption(option);
      charts.push(chart);
    }

    function buildPowerRadarOption(report, colors, commonText) {
      const preferredNames = ['政治理论', '资料分析', '判断推理', '数量关系', '言语理解与表达', '常识判断'];
      const keypointByName = new Map(report.keypoints.map(item => [item.name, item]));
      const radarItems = preferredNames.map(name => keypointByName.get(name) || { name, correctRatio: 0, targetCorrectRatio: 0 });
      const myValues = radarItems.map(item => Number((Number(item.correctRatio) || 0).toFixed(1)));
      const targetValues = radarItems.map(item => Number((Number(item.targetCorrectRatio) || 0).toFixed(1)));

      return {
        color: ['#ffbb4d', '#ff7269'],
        tooltip: {
          show: false,
          trigger: 'item',
          backgroundColor: 'rgba(255,255,255,.94)',
          borderWidth: 0,
          padding: [10, 12],
          textStyle: { color: colors.text },
          extraCssText: 'box-shadow:0 0 10px rgba(174,174,174,.55);border-radius:3px;',
          formatter: params => {
            const lines = [`${params.marker}${params.seriesName}`];
            radarItems.forEach((item, index) => {
              lines.push(`${item.name}：${fmtScore.format(params.value[index])}`);
            });
            return lines.join('<br>');
          }
        },
        legend: {
          bottom: 0,
          itemWidth: 10,
          itemHeight: 10,
          icon: 'rect',
          textStyle: { ...commonText, fontSize: 14 },
          data: ['我的', '目标']
        },
        radar: {
          center: ['50%', '44%'],
          radius: '52%',
          startAngle: 90,
          splitNumber: 4,
          indicator: radarItems.map(item => ({ name: item.name, max: 100 })),
          axisName: { ...commonText, color: colors.text, fontSize: 13 },
          axisLine: { lineStyle: { color: 'rgba(255,114,105,.24)' } },
          splitLine: { lineStyle: { color: 'rgba(255,114,105,.28)' } },
          splitArea: { show: false }
        },
        series: [
          {
            name: '我的',
            type: 'radar',
            data: [{ value: myValues, name: '我的' }],
            symbol: 'circle',
            symbolSize: 4,
            areaStyle: { color: 'rgba(255,187,77,.22)' },
            lineStyle: { color: '#ffbb4d', width: 2 },
            itemStyle: { color: '#ffbb4d' }
          },
          {
            name: '目标',
            type: 'radar',
            data: [{ value: targetValues, name: '目标' }],
            symbol: 'circle',
            symbolSize: 4,
            areaStyle: { color: 'rgba(255,114,105,.26)' },
            lineStyle: { color: '#ff7269', width: 2 },
            itemStyle: { color: '#ff7269' }
          }
        ]
      };
    }

    function mountRadarHover(report) {
      const el = document.getElementById('rankChart');
      if (!el) return;
      if (typeof unmountRadarHover === 'function') {
        unmountRadarHover();
        unmountRadarHover = null;
      }

      let tooltipEl = document.getElementById('rankRadarTooltip');
      if (!tooltipEl) {
        tooltipEl = document.createElement('div');
        tooltipEl.id = 'rankRadarTooltip';
        tooltipEl.className = 'radar-hover-tooltip';
        document.body.appendChild(tooltipEl);
      }

      const preferredNames = ['政治理论', '资料分析', '判断推理', '数量关系', '言语理解与表达', '常识判断'];
      const keypointByName = new Map(report.keypoints.map(item => [item.name, item]));
      const radarItems = preferredNames.map(name => keypointByName.get(name) || { name, correctRatio: 0, targetCorrectRatio: 0 });
      const orange = '#ffbb4d';
      const red = '#ff7269';
      const green = '#17a673';

      const showTooltip = event => {
        const rect = el.getBoundingClientRect();
        const centerX = rect.left + rect.width * .5;
        const centerY = rect.top + rect.height * .44;
        const dx = event.clientX - centerX;
        const dy = event.clientY - centerY;
        const distance = Math.hypot(dx, dy);
        const radius = Math.min(rect.width, rect.height) * .26;
        if (distance < 12 || distance > radius) {
          tooltipEl.style.display = 'none';
          return;
        }

        const step = Math.PI * 2 / radarItems.length;
        let angle = Math.atan2(dy, dx);
        const sectorOffset = Math.abs((((Math.PI / 2 - angle) % step) + step) % step - step / 2);
        const edgeDistance = radius * Math.cos(step / 2) / Math.cos(sectorOffset);
        if (distance > edgeDistance) {
          tooltipEl.style.display = 'none';
          return;
        }

        let index = Math.round((Math.PI / 2 - angle) / step);
        index = ((index % radarItems.length) + radarItems.length) % radarItems.length;
        const item = radarItems[index];
        const mine = Number(item.correctRatio) || 0;
        const target = Number(item.targetCorrectRatio) || 0;
        const mineColor = target && mine >= target ? green : orange;

        tooltipEl.innerHTML = `
          <strong>${escapeHtml(item.name)}</strong>
          <div class="radar-tooltip-row" style="color:${mineColor}">
            <span class="radar-tooltip-label"><span class="radar-tooltip-dot"></span>我的</span>
            <span>${fmtScore.format(mine)}</span>
          </div>
          <div class="radar-tooltip-row" style="color:${red}">
            <span class="radar-tooltip-label"><span class="radar-tooltip-dot"></span>目标</span>
            <span>${fmtScore.format(target)}</span>
          </div>
        `;
        tooltipEl.style.display = 'block';
        tooltipEl.style.left = `${event.clientX + 12}px`;
        tooltipEl.style.top = `${event.clientY + 12}px`;
      };

      el.addEventListener('mousemove', showTooltip);
      const hideTooltip = () => {
        tooltipEl.style.display = 'none';
      };
      el.addEventListener('mouseleave', hideTooltip);
      unmountRadarHover = () => {
        el.removeEventListener('mousemove', showTooltip);
        el.removeEventListener('mouseleave', hideTooltip);
        hideTooltip();
      };
    }

    function initCharts(report) {
      charts.forEach(chart => chart.dispose());
      charts = [];
      if (!window.echarts) {
        document.querySelectorAll('.echart').forEach(el => {
          el.innerHTML = '<div class="empty">ECharts 加载失败</div>';
        });
        return;
      }

      const colors = chartColors();
      const trends = [...report.trends].sort((a, b) => a.time - b.time);
      const labels = report.keypoints.map(item => item.name);
      const correctRatios = report.keypoints.map(item => Number(item.correctRatio) || 0);
      const targetRatios = report.keypoints.map(item => Number(item.targetCorrectRatio) || 0);
      const answerCounts = report.keypoints.map(item => Number(item.answerCount) || 0);

      const commonText = {
        color: colors.muted,
        fontFamily: '-apple-system, BlinkMacSystemFont, "Segoe UI", "Microsoft YaHei", sans-serif'
      };
      const grid = { left: 44, right: 24, top: 28, bottom: 36, containLabel: true };
      const axisLine = { lineStyle: { color: colors.line } };
      const splitLine = { lineStyle: { color: colors.line } };
      const tooltip = {
        trigger: 'axis',
        backgroundColor: '#fff',
        borderColor: colors.line,
        textStyle: { color: colors.text }
      };

      registerChart('trendChart', {
        color: [colors.accent, colors.warn],
        tooltip: {
          ...tooltip,
          formatter: params => {
            const point = params[0];
            return `${point.axisValue}<br>${point.marker}预测分：${fmtScore.format(point.data)}`;
          }
        },
        grid,
        xAxis: {
          type: 'category',
          data: trends.map(item => formatDate(item.time)),
          axisLabel: commonText,
          axisLine,
          axisTick: { show: false }
        },
        yAxis: {
          type: 'value',
          min: 0,
          max: 100,
          interval: 25,
          axisLabel: commonText,
          axisLine,
          splitLine
        },
        series: [
          {
            name: '预测分',
            type: 'line',
            data: trends.map(item => Number(item.score.toFixed(2))),
            smooth: false,
            symbolSize: 7,
            markLine: {
              symbol: 'none',
              label: { formatter: `平均 ${fmtScore.format(report.avgForecastScore)}`, color: colors.muted },
              lineStyle: { color: colors.warn, type: 'dashed' },
              data: [{ yAxis: report.avgForecastScore }]
            }
          }
        ]
      });

      registerChart('correctRatioChart', {
        color: [colors.accent, colors.warn],
        tooltip,
        legend: { bottom: 0, textStyle: commonText },
        grid: { left: 28, right: 16, top: 18, bottom: 44, containLabel: true },
        xAxis: { type: 'category', data: labels, axisLabel: { ...commonText, interval: 0, rotate: 22 }, axisLine, axisTick: { show: false } },
        yAxis: { type: 'value', min: 0, max: 100, axisLabel: { ...commonText, formatter: '{value}%' }, splitLine },
        series: [
          { name: '正确率', type: 'bar', data: correctRatios.map(v => Number(v.toFixed(1))), barMaxWidth: 22 },
          { name: '目标', type: 'line', data: targetRatios, symbolSize: 6 }
        ]
      });

      registerChart('answerCountChart', {
        color: [colors.accent],
        tooltip,
        grid: { left: 36, right: 20, top: 18, bottom: 30, containLabel: true },
        xAxis: { type: 'value', axisLabel: commonText, splitLine },
        yAxis: { type: 'category', data: labels, axisLabel: commonText, axisLine, axisTick: { show: false } },
        series: [{ name: '答题数', type: 'bar', data: answerCounts, barMaxWidth: 18 }]
      });

      registerChart('rankChart', buildPowerRadarOption(report, colors, commonText));
      mountRadarHover(report);
    }


    function activatePanel(panelName) {
      document.querySelectorAll('.nav button[data-panel]').forEach(button => {
        button.setAttribute('aria-selected', String(button.dataset.panel === panelName));
      });
      document.querySelectorAll('.panel').forEach(panel => {
        panel.classList.toggle('active', panel.id === `panel-${panelName}`);
      });
      const contentArea = document.querySelector('.content-area');
      if (contentArea) contentArea.scrollTop = 0;
      requestAnimationFrame(() => {
        charts.forEach(chart => chart.resize());
        if (panelName === 'overview') {
          requestAnimationFrame(() => charts.forEach(chart => chart.resize()));
        }
      });
    }

    function extractAnalysisChunk(raw) {
      if (!raw || raw === '[DONE]') return '';
      try {
        const payload = JSON.parse(raw);
        return payload.content || payload.choices?.[0]?.delta?.content || payload.choices?.[0]?.message?.content || '';
      } catch {
        return raw;
      }
    }

    function startAiAnalysis(historyItems = [], errorTree = []) {
      const button = document.getElementById('startAnalysisButton');
      const status = document.getElementById('analysisStatus');
      const output = document.getElementById('analysisOutput');
      if (!button || !status || !output) return;

      const provider = localStorage.getItem('aiProvider') || 'relay';
      const scope = analysisScope(historyItems, errorTree);
      let receivedChars = 0;
      let analysisText = '';
      button.disabled = true;
      status.textContent = analysisStatusText('running', provider, scope);
      output.innerHTML = markdownToHtml('');

      const source = new EventSource(`/api/analysis/stream?provider=${encodeURIComponent(provider)}`);
      source.onmessage = event => {
        if (event.data === '[DONE]') {
          source.close();
          button.disabled = false;
          status.textContent = analysisStatusText('done', provider, scope, { receivedChars });
          return;
        }
        const chunk = extractAnalysisChunk(event.data);
        analysisText += chunk;
        output.innerHTML = markdownToHtml(analysisText);
        receivedChars += chunk.length;
        status.textContent = analysisStatusText('running', provider, scope, { receivedChars });
        output.scrollTop = output.scrollHeight;
      };
      source.onerror = () => {
        source.close();
        button.disabled = false;
        status.textContent = analysisStatusText('error', provider, scope);
      };
    }

    function settingsElements() {
      return {
        modal: document.getElementById('settingsModal'),
        openButton: document.getElementById('settingsButton'),
        closeButton: document.getElementById('settingsCloseButton'),
        statusGrid: document.getElementById('settingsStatusGrid'),
        providerSelect: document.getElementById('settingsProviderSelect'),
        saveProviderButton: document.getElementById('settingsSaveProviderButton'),
        providerHint: document.getElementById('settingsProviderHint'),
        cookieInput: document.getElementById('settingsCookieInput'),
        saveCookieButton: document.getElementById('settingsSaveCookieButton'),
        message: document.getElementById('settingsMessage')
      };
    }

    function setSettingsMessage(text, type = '') {
      const { message } = settingsElements();
      if (!message) return;
      message.hidden = false;
      message.className = `settings-message ${type}`;
      message.textContent = text;
    }

    async function loadSettingsStatus() {
      const { statusGrid } = settingsElements();
      if (!statusGrid) return;
      try {
        const res = await fetch('/api/health', { cache: 'no-store' });
        const payload = await res.json();
        const status = payload.status || {};
        statusGrid.innerHTML = `
          <div class="settings-status-item">
            <div class="label">Cookie</div>
            <div class="value">${payload.cookie?.configured ? '已配置' : '未配置'}</div>
          </div>
          <div class="settings-status-item">
            <div class="label">来源</div>
            <div class="value">${escapeHtml(payload.cookie?.source || '--')}</div>
          </div>
          <div class="settings-status-item">
            <div class="label">最近状态</div>
            <div class="value">${status.ok ? '成功' : escapeHtml(status.last_error?.message || '暂无成功记录')}</div>
          </div>
        `;
      } catch (error) {
        setSettingsMessage(`健康检查失败：${error.message}`, 'error');
      }
    }

    async function loadSettingsProviders() {
      const { providerSelect, providerHint } = settingsElements();
      if (!providerSelect || !providerHint) return;
      try {
        const res = await fetch('/api/analysis/providers', { cache: 'no-store' });
        const payload = await res.json();
        if (!res.ok || !payload.ok) {
          throw new Error(payload.detail?.message || payload.error?.message || `HTTP ${res.status}`);
        }
        const providers = payload.providers || [];
        const defaultProvider = providers.find(provider => provider.default)?.id || providers[0]?.id || 'relay';
        const savedProvider = localStorage.getItem('aiProvider') || defaultProvider;
        providerSelect.innerHTML = providers.map(provider => `
          <option value="${escapeHtml(provider.id)}" ${provider.id === savedProvider ? 'selected' : ''}>
            ${escapeHtml(provider.name)} / ${escapeHtml(provider.model)}${provider.configured ? '' : '（未配置 Key）'}
          </option>
        `).join('');
        providerHint.textContent = providers.length
          ? '这里保存当前浏览器的服务商选择，API Key 仍由后端环境变量配置。'
          : '后端未返回可用 AI 服务商。';
      } catch (error) {
        providerHint.textContent = `服务商读取失败：${error.message}`;
      }
    }

    function openSettingsModal() {
      const { modal, cookieInput } = settingsElements();
      if (!modal) return;
      modal.hidden = false;
      document.body.classList.add('modal-open');
      loadSettingsStatus();
      loadSettingsProviders();
      setTimeout(() => cookieInput?.focus(), 0);
    }

    function closeSettingsModal() {
      const { modal, openButton } = settingsElements();
      if (!modal) return;
      modal.hidden = true;
      document.body.classList.remove('modal-open');
      openButton?.focus();
    }

    function wireSettingsModal() {
      const {
        openButton,
        closeButton,
        modal,
        providerSelect,
        saveProviderButton,
        providerHint,
        cookieInput,
        saveCookieButton
      } = settingsElements();

      openButton?.addEventListener('click', openSettingsModal);
      closeButton?.addEventListener('click', closeSettingsModal);
      modal?.querySelectorAll('[data-close-settings]').forEach(element => {
        element.addEventListener('click', closeSettingsModal);
      });
      document.addEventListener('keydown', event => {
        if (event.key === 'Escape' && modal && !modal.hidden) closeSettingsModal();
      });

      saveProviderButton?.addEventListener('click', () => {
        const provider = providerSelect?.value || 'relay';
        localStorage.setItem('aiProvider', provider);
        if (providerHint) providerHint.textContent = `已保存服务商：${provider}`;
      });

      saveCookieButton?.addEventListener('click', async () => {
        const cookie = cookieInput?.value.trim() || '';
        if (!cookie) {
          setSettingsMessage('Cookie 不能为空', 'error');
          return;
        }
        saveCookieButton.disabled = true;
        setSettingsMessage('正在验证 Cookie，请稍候');
        try {
          const res = await fetch('/api/admin/cookie', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ cookie })
          });
          const payload = await res.json();
          if (!res.ok || !payload.ok) {
            throw new Error(payload.error?.message || `HTTP ${res.status}`);
          }
          cookieInput.value = '';
          setSettingsMessage(`${payload.message || '更新成功'} ${payload.warning || ''}`.trim(), 'ok');
          await loadSettingsStatus();
        } catch (error) {
          setSettingsMessage(`更新失败：${error.message}`, 'error');
        } finally {
          saveCookieButton.disabled = false;
        }
      });
    }

    function wireInteractions(historyItems, errorTree) {
      document.querySelectorAll('.nav button[data-panel]').forEach(button => {
        button.addEventListener('click', () => activatePanel(button.dataset.panel));
      });

      document.querySelectorAll('[data-history-filter]').forEach(filter => {
        filter.addEventListener('change', () => renderHistoryList(historyItems, filter.value, filter.dataset.historyFilter));
        renderHistoryList(historyItems, filter.value, filter.dataset.historyFilter);
      });

      document.getElementById('startAnalysisButton')?.addEventListener('click', () => startAiAnalysis(historyItems, errorTree));
      document.querySelectorAll('[data-open-settings]').forEach(element => {
        element.addEventListener('click', event => {
          event.preventDefault();
          openSettingsModal();
        });
      });
    }

    refreshButton.addEventListener('click', refreshReport);
    wireSettingsModal();
    async function boot() {
      try {
        const apiReport = await loadReport();
        const report = adaptReport(apiReport);
        const historyItems = apiReport.history?.items || [];
        const errorTree = apiReport.errors || [];

        subtitle.textContent = `${report.userQuiz?.name || '行测'} · 用户 ${report.userId}`;
        sourceNote.textContent = `${apiReport.meta?.stale ? '缓存数据' : '动态数据'} · 更新：${new Date(apiReport.meta?.fetched_at || Date.now()).toLocaleString('zh-CN', { hour12: false })}`;
        app.innerHTML = [
          overviewPanel(report, historyItems),
          analysisPanel(historyItems, errorTree),
          errorsPanel(errorTree, report, historyItems)
        ].join('');
        wireInteractions(historyItems, errorTree);
        initCharts(report);
        window.removeEventListener('resize', handleViewportResize);
        window.addEventListener('resize', handleViewportResize);
      } catch (error) {
        subtitle.textContent = '报告数据读取失败';
        sourceNote.textContent = '请检查 Cookie 或服务状态';
        app.innerHTML = `<div class="error">报告数据读取失败：${escapeHtml(error.message)}。<button type="button" class="link-button" data-open-settings>前往 Cookie 设置</button></div>`;
      }
    }

    boot();
