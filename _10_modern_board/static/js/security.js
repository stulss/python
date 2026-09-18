/**
 * Modern Board - Security Dashboard & Monitoring
 * Features: Metrics Cards, Threat Level Indicator, Chart.js Visualizations, Audit Log Table, Live Threat Simulator
 */

let timelineChart = null;
let doughnutChart = null;

async function loadSecurityData() {
    await Promise.all([
        loadSecurityStats(),
        loadSecurityLogs(),
        loadSecurityEvents()
    ]);
}

// 보안 통계 및 차트 데이터 로드
async function loadSecurityStats() {
    try {
        const res = await fetch(`${API_BASE}/security/stats`, {
            headers: getAuthHeaders(true)
        });
        const data = await res.json();
        if (!res.ok) {
            if (res.status === 401 || res.status === 403) {
                showToast(data.error || '보안 대시보드는 골드(Gold) 등급 이상부터 열람 가능합니다.', 'warning');
            }
            throw new Error(data.error || '보안 통계 로드 실패');
        }

        // 지표 카드 갱신
        document.getElementById('sec-stat-total').textContent = data.total_events || 0;
        document.getElementById('sec-stat-critical').textContent = data.severity_distribution.CRITICAL || 0;
        document.getElementById('sec-stat-warning').textContent = data.severity_distribution.WARNING || 0;
        document.getElementById('sec-stat-info').textContent = data.severity_distribution.INFO || 0;

        // 위협 레벨 배지 갱신 (한국어화)
        const threatLevelEl = document.getElementById('sec-threat-level');
        if (threatLevelEl) {
            const levelMap = {
                'SECURE': '안전 (SECURE)',
                'ELEVATED': '주의 (ELEVATED)',
                'HIGH': '경고 (HIGH)',
                'CRITICAL': '심각 (CRITICAL)'
            };
            threatLevelEl.textContent = levelMap[data.threat_level] || data.threat_level;
            const colors = {
                'SECURE': 'bg-emerald-500/20 text-emerald-400 border-emerald-500/40 glow-emerald',
                'ELEVATED': 'bg-amber-500/20 text-amber-400 border-amber-500/40',
                'HIGH': 'bg-orange-500/20 text-orange-400 border-orange-500/40',
                'CRITICAL': 'bg-rose-500/20 text-rose-400 border-rose-500/40 glow-rose animate-pulse'
            };
            threatLevelEl.className = `px-3.5 py-1 text-xs font-extrabold rounded-full border tracking-widest ${colors[data.threat_level] || colors.SECURE}`;
        }


        // Chart.js 렌더링
        renderTimelineChart(data.chart_series);
        renderDoughnutChart(data.event_types);
    } catch (err) {
        console.error('보안 통계 로드 오류:', err);
    }
}

// 7일간 추이 차트
function renderTimelineChart(series) {
    const ctx = document.getElementById('chart-security-timeline');
    if (!ctx) return;

    if (timelineChart) {
        timelineChart.destroy();
    }

    timelineChart = new Chart(ctx, {
        type: 'line',
        data: {
            labels: series.labels,
            datasets: [
                {
                    label: 'Critical/High 위협',
                    data: series.critical,
                    borderColor: '#f43f5e',
                    backgroundColor: 'rgba(244, 63, 94, 0.1)',
                    tension: 0.35,
                    fill: true,
                    borderWidth: 2,
                    pointRadius: 4,
                    pointBackgroundColor: '#f43f5e'
                },
                {
                    label: 'Warning 경고',
                    data: series.warning,
                    borderColor: '#f59e0b',
                    backgroundColor: 'rgba(245, 158, 11, 0.05)',
                    tension: 0.35,
                    fill: true,
                    borderWidth: 2,
                    pointRadius: 3,
                    pointBackgroundColor: '#f59e0b'
                },
                {
                    label: '정상/Info 이벤트',
                    data: series.normal,
                    borderColor: '#6366f1',
                    backgroundColor: 'rgba(99, 102, 241, 0.05)',
                    tension: 0.35,
                    fill: true,
                    borderWidth: 2,
                    pointRadius: 3,
                    pointBackgroundColor: '#6366f1'
                }
            ]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: {
                    position: 'top',
                    labels: { color: '#94a3b8', font: { family: 'Plus Jakarta Sans', size: 11 } }
                },
                tooltip: {
                    backgroundColor: '#1e293b',
                    titleColor: '#f8fafc',
                    bodyColor: '#cbd5e1',
                    borderColor: '#334155',
                    borderWidth: 1
                }
            },
            scales: {
                x: {
                    grid: { color: 'rgba(51, 65, 85, 0.2)' },
                    ticks: { color: '#64748b', font: { size: 10 } }
                },
                y: {
                    beginAtZero: true,
                    grid: { color: 'rgba(51, 65, 85, 0.2)' },
                    ticks: { color: '#64748b', font: { size: 10 }, stepSize: 1 }
                }
            }
        }
    });
}

// 이벤트 유형 분포 도넛 차트
function renderDoughnutChart(eventTypes) {
    const ctx = document.getElementById('chart-security-doughnut');
    if (!ctx) return;

    if (doughnutChart) {
        doughnutChart.destroy();
    }

    const labels = Object.keys(eventTypes);
    const counts = Object.values(eventTypes);

    const palette = [
        '#6366f1', '#f43f5e', '#f59e0b', '#10b981', '#06b6d4', '#8b5cf6', '#ec4899'
    ];

    doughnutChart = new Chart(ctx, {
        type: 'doughnut',
        data: {
            labels: labels.length ? labels : ['이벤트 없음'],
            datasets: [{
                data: counts.length ? counts : [1],
                backgroundColor: labels.length ? palette.slice(0, labels.length) : ['#334155'],
                borderColor: '#0f172a',
                borderWidth: 3
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            cutout: '70%',
            plugins: {
                legend: {
                    position: 'bottom',
                    labels: { color: '#94a3b8', font: { family: 'Plus Jakarta Sans', size: 11 }, boxWidth: 12 }
                }
            }
        }
    });
}

// 보안 로그 목록 로드
async function loadSecurityLogs() {
    const tableBody = document.getElementById('security-logs-tbody');
    const severityFilter = document.getElementById('sec-filter-severity')?.value || 'ALL';

    if (!tableBody) return;
    tableBody.innerHTML = `<tr><td colspan="6" class="text-center py-6 text-slate-500 text-xs"><i class="fas fa-spinner fa-spin mr-2"></i>로그 불러오는 중...</td></tr>`;

    try {
        const url = `${API_BASE}/security/logs?limit=40${severityFilter !== 'ALL' ? `&severity=${severityFilter}` : ''}`;
        const res = await fetch(url, {
            headers: getAuthHeaders(true)
        });
        const data = await res.json();

        if (!res.ok) {
            tableBody.innerHTML = `<tr><td colspan="6" class="text-center py-8 text-amber-400 text-xs"><i class="fas fa-lock mr-1.5"></i>${data.error || '보안 로그 접근 권한이 없습니다. (골드 이상)'}</td></tr>`;
            return;
        }

        if (!data.logs || data.logs.length === 0) {
            tableBody.innerHTML = `<tr><td colspan="6" class="text-center py-8 text-slate-500 text-xs">기록된 보안 로그가 없습니다.</td></tr>`;
            return;
        }

        tableBody.innerHTML = '';
        data.logs.forEach(log => {
            const tr = document.createElement('tr');
            tr.className = 'border-b border-slate-800/60 hover:bg-slate-800/30 transition-colors text-xs text-slate-300';

            const severityBadge = {
                'INFO': '<span class="px-2 py-0.5 rounded-md text-[10px] font-bold bg-slate-800 text-slate-300 border border-slate-700">정보 (INFO)</span>',
                'WARNING': '<span class="px-2 py-0.5 rounded-md text-[10px] font-bold bg-amber-500/15 text-amber-300 border border-amber-500/30">경고 (WARN)</span>',
                'HIGH': '<span class="px-2 py-0.5 rounded-md text-[10px] font-bold bg-orange-500/15 text-orange-300 border border-orange-500/30">위험 (HIGH)</span>',
                'CRITICAL': '<span class="px-2 py-0.5 rounded-md text-[10px] font-bold bg-rose-500/25 text-rose-300 border border-rose-500/40 animate-pulse">심각 (CRIT)</span>'
            }[log.severity] || log.severity;


            const eventTypeNames = {
                'LOGIN_SUCCESS': '로그인 성공',
                'LOGIN_FAIL': '로그인 실패',
                'SQLI_DETECT': 'SQL 인젝션 탐지',
                'BRUTE_FORCE': '무차별 대입 공격',
                'UNAUTHORIZED_ACCESS': '비인가 접근 (401)',
                'UNAUTHORIZED_ADMIN_ACCESS': '관리자 무단 접근 (403)',
                'UNAUTHORIZED_SECURITY_ACCESS': '보안콘솔 비인가 접근 (403)',
                'XSS_DETECT': 'XSS 스크립트 감지',
                'PRIVILEGE_ESC': '권한 상승 시도',
                'USER_REGISTER': '신규 회원가입'
            };
            const eventNameKr = eventTypeNames[log.event_type] || log.event_type;

            tr.innerHTML = `
                <td class="py-3 px-3 text-slate-500 font-mono">#${log.id}</td>
                <td class="py-3 px-3 whitespace-nowrap text-[11px] text-slate-400 font-mono">${log.created_at}</td>
                <td class="py-3 px-3">${severityBadge}</td>
                <td class="py-3 px-3 font-semibold text-slate-200">
                    <div>${eventNameKr}</div>
                    <span class="text-[10px] text-slate-500 font-mono">${escapeHtml(log.event_type)}</span>
                </td>
                <td class="py-3 px-3 font-mono text-[11px] text-slate-400">${escapeHtml(log.ip_address)}</td>
                <td class="py-3 px-3 text-slate-300 font-mono text-[11px]">
                    <span class="text-slate-500 mr-1 font-bold">${log.method || 'GET'}</span>
                    <span class="text-indigo-400">${escapeHtml(log.endpoint || '-')}</span>
                    <div class="text-slate-400 text-xs mt-0.5">${escapeHtml(log.details || '')}</div>
                </td>
            `;

            tableBody.appendChild(tr);
        });
    } catch (err) {
        console.error('보안 로그 로드 오류:', err);
        tableBody.innerHTML = `<tr><td colspan="6" class="text-center py-6 text-rose-400 text-xs">로그를 불러오는 데 실패했습니다: ${err.message}</td></tr>`;
    }
}

// 모의 위협 시뮬레이션 발생
async function triggerSecuritySimulation(attackType) {
    try {
        const res = await fetch(`${API_BASE}/security/simulate`, {
            method: 'POST',
            headers: getAuthHeaders(true),
            body: JSON.stringify({ attack_type: attackType })
        });
        const data = await res.json();
        if (res.ok) {
            showToast(`[${attackType}] 공격 시뮬레이션 이벤트가 성공적으로 로깅되었습니다!`, 'warning');
            loadSecurityData(); // 대시보드 즉시 갱신
        } else {
            showToast(data.error || '시뮬레이션 권한이 없습니다.', 'error');
        }
    } catch (err) {
        console.error(err);
        showToast('시뮬레이션 전송 중 오류 발생', 'error');
    }
}

// 로그 초기화
async function clearAllSecurityLogs() {
    if (!confirm('모든 보안 로그를 초기화하시겠습니까?')) return;
    try {
        const res = await fetch(`${API_BASE}/security/clear`, {
            method: 'POST',
            headers: getAuthHeaders(true)
        });
        const data = await res.json();
        if (res.ok) {
            showToast('보안 로그가 초기화되었습니다.', 'info');
            loadSecurityData();
        } else {
            showToast(data.error || '초기화 권한이 없습니다.', 'error');
        }
    } catch (err) {
        showToast('초기화 실패', 'error');
    }
}

// 이벤트 리스너 등록
document.addEventListener('DOMContentLoaded', () => {
    // 심각도 필터 변경
    document.getElementById('sec-filter-severity')?.addEventListener('change', loadSecurityLogs);

    // 시뮬레이션 버튼들
    document.querySelectorAll('.btn-simulate-attack').forEach(btn => {
        btn.addEventListener('click', (e) => {
            const attackType = e.currentTarget.dataset.type;
            triggerSecuritySimulation(attackType);
        });
    });

// n8n 실시간 웹훅 트리거 테스트
async function triggerN8nTest(type = 'security') {
    try {
        showToast('n8n 보안관제 웹훅으로 이벤트를 발송 중입니다...', 'info');
        const res = await fetch(`${API_BASE}/n8n/trigger`, {
            method: 'POST',
            headers: getAuthHeaders(true),
            body: JSON.stringify({
                type: type,
                student: '보안관제_운영자',
                src_ip: '203.0.113.88',
                level: 3,
                rule: 'BRUTE_FORCE_SOAR',
                fail_count: 5,
                decision: 'deny',
                severity: 'High',
                reason: 'n8n SOAR 보안 자동화 연동 실시간 테스트'
            })
        });
        const data = await res.json();
        if (!res.ok) throw new Error(data.error || 'n8n 웹훅 발송 실패');

        showToast('✅ n8n 보안관제 웹훅 전송 성공! (디스코드/슬랙/텔레그램 및 게시판 자동 연동)', 'success');
        setTimeout(loadSecurityData, 1500);
    } catch (err) {
        showToast(`n8n 웹훅 오류: ${err.message}`, 'error');
    }
}

// n8n 모던커뮤니티 보안관제 워크플로우 전용 트리거
async function triggerN8nCustomTest(level = 12, expectedDecision = 'deny') {
    try {
        const desc = expectedDecision === 'deny' ? '거부 (Level 12 침입 감지)' : '허용 (Level 5 정상 접근)';
        showToast(`n8n 모던커뮤니티 보안관제 [${desc}] 이벤트를 발송합니다...`, 'info');

        const randomIp = `203.0.113.${Math.floor(Math.random() * 200) + 20}`;
        const res = await fetch(`${API_BASE}/n8n/trigger`, {
            method: 'POST',
            headers: getAuthHeaders(true),
            body: JSON.stringify({
                type: 'security',
                student: '모던보안관제_운영자',
                alerts: [
                    {
                        ip: randomIp,
                        level: level,
                        rule: level >= 10 ? 'RULE_BRUTE_FORCE_1001' : 'RULE_NORMAL_AUTH_1002'
                    }
                ]
            })
        });
        const data = await res.json();
        if (!res.ok) throw new Error(data.error || 'n8n 웹훅 발송 실패');

        showToast(`✅ n8n 모던커뮤니티 보안관제 실행 완료! (${expectedDecision.toUpperCase()} 판정 -> Discord/Slack/Telegram 전송 및 게시판 연동)`, 'success');
        setTimeout(() => {
            loadSecurityData();
            // 메인 피드나 보안글 목록 갱신
            if (typeof loadPosts === 'function') loadPosts(true);
        }, 1500);
    } catch (err) {
        showToast(`n8n 웹훅 오류: ${err.message}`, 'error');
    }
}

// n8n SOAR 보안 이벤트(SecurityEvent) 목록 및 요약 로드
async function loadSecurityEvents() {
    const tbody = document.getElementById('security-events-tbody');
    const decisionFilter = document.getElementById('sec-event-filter-decision')?.value || '';

    // 요약 정보 로드 (/api/security/events/summary)
    try {
        const sRes = await fetch(`${API_BASE}/security/events/summary`);
        const sData = await sRes.json();
        const deny = sData.by_decision?.deny || 0;
        const allow = sData.by_decision?.allow || 0;
        if (document.getElementById('soar-stat-total')) document.getElementById('soar-stat-total').textContent = deny + allow;
        if (document.getElementById('soar-stat-deny')) document.getElementById('soar-stat-deny').textContent = deny;
        if (document.getElementById('soar-stat-allow')) document.getElementById('soar-stat-allow').textContent = allow;
        const topIp = (sData.top_deny_ips && sData.top_deny_ips.length) ? `${sData.top_deny_ips[0].src_ip} (${sData.top_deny_ips[0].fails}회)` : '-';
        if (document.getElementById('soar-stat-top-ip')) document.getElementById('soar-stat-top-ip').textContent = topIp;
    } catch (err) {
        console.warn('SOAR 요약 로드 실패:', err);
    }

    if (!tbody) return;
    tbody.innerHTML = `<tr><td colspan="8" class="text-center py-4 text-slate-500 text-xs"><i class="fas fa-spinner fa-spin mr-1.5"></i>SOAR 이벤트 불러오는 중...</td></tr>`;

    try {
        const url = `${API_BASE}/security/events?limit=50${decisionFilter ? `&decision=${decisionFilter}` : ''}`;
        const res = await fetch(url);
        const data = await res.json();
        const events = data.events || [];

        if (events.length === 0) {
            tbody.innerHTML = `<tr><td colspan="8" class="text-center py-6 text-slate-500 text-xs">기록된 SOAR 이벤트가 없습니다.</td></tr>`;
            return;
        }

        tbody.innerHTML = events.map(e => {
            const isDeny = e.decision === 'deny';
            const badge = isDeny
                ? '<span class="px-2 py-0.5 rounded-full text-[10px] font-bold bg-rose-500/20 text-rose-400 border border-rose-500/30">🚫 거부</span>'
                : '<span class="px-2 py-0.5 rounded-full text-[10px] font-bold bg-emerald-500/20 text-emerald-400 border border-emerald-500/30">✅ 허용</span>';
            const sevColor = e.severity === 'High' ? 'text-rose-400' : (e.severity === 'Medium' ? 'text-amber-400' : 'text-slate-400');
            const target = e.student || e.users || 'SYSTEM';
            const reason = typeof escapeHtml === 'function' ? escapeHtml(e.reason || '-') : (e.reason || '-');
            const timeStr = (e.created_at || '').replace('T', ' ').slice(0, 19) || (e.generated_at || '-');

            return `
                <tr class="border-b border-slate-800/60 hover:bg-slate-800/30 transition-colors text-xs text-slate-300">
                    <td class="py-2.5 px-3 font-mono text-slate-500">#${e.id}</td>
                    <td class="py-2.5 px-3 font-semibold text-slate-200">${typeof escapeHtml === 'function' ? escapeHtml(target) : target}</td>
                    <td class="py-2.5 px-3 font-mono text-indigo-300">${typeof escapeHtml === 'function' ? escapeHtml(e.src_ip || '-') : (e.src_ip || '-')}</td>
                    <td class="py-2.5 px-3">${badge}</td>
                    <td class="py-2.5 px-3 font-mono font-bold ${sevColor}">${typeof escapeHtml === 'function' ? escapeHtml(e.severity || 'Normal') : (e.severity || 'Normal')}</td>
                    <td class="py-2.5 px-3 font-mono text-slate-400">${e.fail_count || 0}</td>
                    <td class="py-2.5 px-3 text-slate-300 max-w-xs truncate" title="${reason}">${reason}</td>
                    <td class="py-2.5 px-3 font-mono text-[11px] text-slate-500">${timeStr}</td>
                </tr>
            `;
        }).join('');
    } catch (err) {
        tbody.innerHTML = `<tr><td colspan="8" class="text-center py-6 text-rose-400 text-xs">SOAR 이벤트 로드 실패: ${err.message}</td></tr>`;
    }
}

// 전역 노출
window.loadSecurityData = loadSecurityData;
window.loadSecurityEvents = loadSecurityEvents;
window.triggerN8nTest = triggerN8nTest;
window.triggerN8nCustomTest = triggerN8nCustomTest;
