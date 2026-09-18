/**
 * Modern Board - Administrator Dashboard
 * Features: User Management (Role toggle, Account freeze, Delete), Post Management, System Health Metrics
 */

async function loadAdminData() {
    if (!state.user || state.user.role !== 'admin') {
        showToast('관리자 권한이 필요합니다.', 'warning');
        return;
    }
    await Promise.all([
        loadAdminStats(),
        loadAdminUsers(),
        loadAdminPosts()
    ]);
}

// 관리자 통계 요약 로드
async function loadAdminStats() {
    try {
        const res = await fetch(`${API_BASE}/admin/stats`, {
            headers: getAuthHeaders(true)
        });
        const data = await res.json();
        if (!res.ok) throw new Error(data.error || '통계 로드 실패');

        document.getElementById('admin-stat-users').textContent = data.users.total;
        document.getElementById('admin-stat-admins').textContent = data.users.admins;
        document.getElementById('admin-stat-posts').textContent = data.posts.total;
        document.getElementById('admin-stat-comments').textContent = data.comments.total;
    } catch (err) {
        console.error('관리자 통계 오류:', err);
    }
}

// 사용자 목록 로드
async function loadAdminUsers() {
    const tbody = document.getElementById('admin-users-tbody');
    if (!tbody) return;
    tbody.innerHTML = `<tr><td colspan="6" class="text-center py-6 text-slate-500 text-xs"><i class="fas fa-spinner fa-spin mr-2"></i>회원 정보 로드 중...</td></tr>`;

    try {
        const res = await fetch(`${API_BASE}/admin/users`, {
            headers: getAuthHeaders(true)
        });
        const data = await res.json();
        if (!res.ok) throw new Error(data.error || '회원 목록 로드 실패');

        tbody.innerHTML = '';
        data.users.forEach(u => {
            const tr = document.createElement('tr');
            tr.className = 'border-b border-slate-800/60 hover:bg-slate-800/30 transition-colors text-xs text-slate-300';

            let roleBadge = '';
            if (u.role === 'admin') {
                roleBadge = '<span class="px-2 py-0.5 rounded text-[10px] font-semibold bg-rose-500/15 text-rose-400 border border-rose-500/30 font-mono-code">관리자 (ADMIN)</span>';
            } else if (u.role === 'gold') {
                roleBadge = '<span class="px-2 py-0.5 rounded text-[10px] font-semibold bg-amber-500/15 text-amber-300 border border-amber-500/30 font-mono-code">골드 (GOLD)</span>';
            } else {
                roleBadge = '<span class="px-2 py-0.5 rounded text-[10px] font-medium bg-slate-800 text-slate-300 border border-slate-700 font-mono-code">일반 (USER)</span>';
            }

            const statusBadge = u.is_active
                ? '<span class="px-2 py-0.5 rounded-full text-[10px] font-semibold bg-emerald-500/20 text-emerald-400 border border-emerald-500/30">정상 가동</span>'
                : '<span class="px-2 py-0.5 rounded-full text-[10px] font-semibold bg-rose-500/20 text-rose-400 border border-rose-500/30">계정 정지</span>';

            const displayName = u.nickname ? `${escapeHtml(u.nickname)} <span class="text-slate-400 text-[11px] font-normal font-mono">(${escapeHtml(u.username)})</span>` : escapeHtml(u.username);

            tr.innerHTML = `
                <td class="py-3 px-3 text-slate-500 font-mono">#${u.id}</td>
                <td class="py-3 px-3 font-bold text-slate-100">${displayName}</td>
                <td class="py-3 px-3 text-slate-400 font-mono text-[11px]">${escapeHtml(u.email || '-')}</td>
                <td class="py-3 px-3">${roleBadge}</td>
                <td class="py-3 px-3">${statusBadge}</td>
                <td class="py-3 px-3 text-slate-400 text-[11px] font-mono">${u.created_at || '-'}</td>
                <td class="py-3 px-3">
                    <div class="flex items-center gap-1.5">
                        <button onclick="toggleUserRole(${u.id}, '${u.role}')" class="px-2 py-1 rounded bg-indigo-900/40 text-indigo-300 hover:bg-indigo-800/50 border border-indigo-700/40 text-[10px] font-semibold transition-all">
                            권한 변경
                        </button>
                        <button onclick="toggleUserStatus(${u.id})" class="px-2 py-1 rounded ${u.is_active ? 'bg-amber-900/30 text-amber-300 hover:bg-amber-800/40 border border-amber-700/40' : 'bg-emerald-900/30 text-emerald-300 hover:bg-emerald-800/40 border border-emerald-700/40'} text-[10px] font-semibold transition-all">
                            ${u.is_active ? '계정 정지' : '계정 활성'}
                        </button>
                        <button onclick="deleteUser(${u.id}, '${escapeHtml(u.username)}')" class="px-2 py-1 rounded bg-rose-900/30 text-rose-300 hover:bg-rose-800/40 border border-rose-700/40 text-[10px] font-semibold transition-all">
                            삭제
                        </button>
                    </div>
                </td>
            `;
            tbody.appendChild(tr);
        });
    } catch (err) {
        console.error(err);
        tbody.innerHTML = `<tr><td colspan="7" class="text-center py-6 text-rose-400 text-xs">회원 목록 로드 실패: ${err.message}</td></tr>`;
    }
}

// 사용자 권한 순환 변경 (user -> gold -> admin -> user)
async function toggleUserRole(userId, currentRole) {
    const roleCycle = { 'user': 'gold', 'gold': 'admin', 'admin': 'user' };
    const nextRole = roleCycle[currentRole] || 'user';
    const roleNames = { 'user': '일반회원 (USER)', 'gold': '골드회원 (GOLD)', 'admin': '관리자 (ADMIN)' };

    if (!confirm(`이 회원의 역할을 [${roleNames[nextRole]}]로 변경하시겠습니까?\n(클릭할 때마다 일반 → 골드 → 관리자 순으로 순환 변경됩니다)`)) return;

    try {
        const res = await fetch(`${API_BASE}/admin/users/${userId}/role`, {
            method: 'PATCH',
            headers: getAuthHeaders(true),
            body: JSON.stringify({ role: nextRole })
        });
        const data = await res.json();
        if (!res.ok) throw new Error(data.error || '권한 변경 실패');

        showToast(data.message, 'success');
        loadAdminUsers();
        loadAdminStats();
    } catch (err) {
        showToast(err.message || '오류 발생', 'error');
    }
}

// 계정 정지/활성화 토글
async function toggleUserStatus(userId) {
    try {
        const res = await fetch(`${API_BASE}/admin/users/${userId}/status`, {
            method: 'PATCH',
            headers: getAuthHeaders(true)
        });
        const data = await res.json();
        if (!res.ok) throw new Error(data.error || '상태 변경 실패');

        showToast(data.message, 'info');
        loadAdminUsers();
    } catch (err) {
        showToast(err.message || '오류 발생', 'error');
    }
}

// 회원 삭제
async function deleteUser(userId, username) {
    if (!confirm(`[주의] ${username} 회원 계정과 작성된 모든 글/댓글이 완전히 삭제됩니다. 계속하시겠습니까?`)) return;

    try {
        const res = await fetch(`${API_BASE}/admin/users/${userId}`, {
            method: 'DELETE',
            headers: getAuthHeaders(true)
        });
        const data = await res.json();
        if (!res.ok) throw new Error(data.error || '삭제 실패');

        showToast(data.message, 'success');
        loadAdminUsers();
        loadAdminStats();
        if (window.loadPosts) window.loadPosts(true);
    } catch (err) {
        showToast(err.message || '오류 발생', 'error');
    }
}

// 전체 게시글 관리 목록 로드
async function loadAdminPosts() {
    const tbody = document.getElementById('admin-posts-tbody');
    if (!tbody) return;
    tbody.innerHTML = `<tr><td colspan="6" class="text-center py-6 text-slate-500 text-xs"><i class="fas fa-spinner fa-spin mr-2"></i>게시글 로드 중...</td></tr>`;

    try {
        const res = await fetch(`${API_BASE}/admin/posts`, {
            headers: getAuthHeaders(true)
        });
        const data = await res.json();
        if (!res.ok) throw new Error(data.error || '게시글 목록 로드 실패');

        tbody.innerHTML = '';
        data.posts.forEach(p => {
            const tr = document.createElement('tr');
            tr.className = 'border-b border-slate-800/60 hover:bg-slate-800/30 transition-colors text-xs text-slate-300';
            tr.innerHTML = `
                <td class="py-3 px-3 text-slate-500 font-mono">#${p.id}</td>
                <td class="py-3 px-3 font-semibold text-slate-100">${escapeHtml(p.title)}</td>
                <td class="py-3 px-3 text-slate-400">${escapeHtml(p.category)}</td>
                <td class="py-3 px-3 text-slate-300">${escapeHtml(p.author_name)}</td>
                <td class="py-3 px-3 text-slate-400 text-[11px]">${p.created_at || '-'}</td>
                <td class="py-3 px-3">
                    <button onclick="adminDeletePost(${p.id})" class="px-2.5 py-1 rounded bg-rose-500/20 text-rose-300 hover:bg-rose-500/30 border border-rose-500/30 text-[11px] font-semibold transition-all">
                        <i class="fas fa-trash-alt mr-1"></i> 강제 삭제
                    </button>
                </td>
            `;
            tbody.appendChild(tr);
        });
    } catch (err) {
        console.error(err);
        tbody.innerHTML = `<tr><td colspan="6" class="text-center py-6 text-rose-400 text-xs">게시글 로드 실패</td></tr>`;
    }
}

// 관리자 게시글 강제 삭제
async function adminDeletePost(postId) {
    if (!confirm(`게시글 #${postId}을 관리자 권한으로 강제 삭제하시겠습니까?`)) return;

    try {
        const res = await fetch(`${API_BASE}/posts/${postId}`, {
            method: 'DELETE',
            headers: getAuthHeaders(true)
        });
        const data = await res.json();
        if (!res.ok) throw new Error(data.error || '삭제 실패');

        showToast('게시글이 관리자에 의해 강제 삭제되었습니다.', 'info');
        loadAdminPosts();
        loadAdminStats();
        if (window.loadPosts) window.loadPosts(true);
    } catch (err) {
        showToast(err.message || '오류 발생', 'error');
    }
}

// 이상권한 탐지 및 회수 봇 즉시 실행 (Graylog + n8n 연동)
async function runPrivilegeRevokeBot() {
    showToast('🤖 이상권한 탐지 및 회수 봇(Graylog + n8n)을 실행 중입니다...', 'info');
    try {
        const res = await fetch(`${API_BASE}/n8n/run-revoke-bot`, {
            method: 'POST',
            headers: getAuthHeaders(true)
        });
        const data = await res.json();
        if (res.ok && data.success) {
            showToast('✅ 이상권한 자동 탐지 & n8n 회수 워크플로우 완료!', 'success');
            if (data.output) {
                console.log('[Privilege Revoke Bot Output]\n', data.output);
            }
            await loadAdminData();
        } else {
            showToast(`오류: ${data.error || '봇 실행 중 오류 발생'}`, 'error');
        }
    } catch (err) {
        showToast(`네트워크 오류: ${err.message}`, 'error');
    }
}

// 전역 노출
window.loadAdminData = loadAdminData;
window.toggleUserRole = toggleUserRole;
window.toggleUserStatus = toggleUserStatus;
window.deleteUser = deleteUser;
window.adminDeletePost = adminDeletePost;
window.runPrivilegeRevokeBot = runPrivilegeRevokeBot;
