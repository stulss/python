/**
 * Modern Board - Core Application & State Management
 */

const state = {
    token: localStorage.getItem('mb_token') || null,
    user: JSON.parse(localStorage.getItem('mb_user') || 'null'),
    activeTab: 'board', // 'board', 'security', 'admin'
};

// API Base URL
const API_BASE = '/api';

// 인증 헤더 헬퍼
function getAuthHeaders(isJson = true) {
    const headers = {};
    if (isJson) headers['Content-Type'] = 'application/json';
    if (state.token) headers['Authorization'] = `Bearer ${state.token}`;
    return headers;
}

// 토스트 메시지 렌더링
function showToast(message, type = 'info') {
    const container = document.getElementById('toast-container');
    if (!container) return;

    const toast = document.createElement('div');
    const colors = {
        success: 'bg-emerald-600 text-white border-emerald-500',
        error: 'bg-rose-600 text-white border-rose-500',
        warning: 'bg-amber-600 text-white border-amber-500',
        info: 'bg-indigo-600 text-white border-indigo-500'
    };
    const icons = {
        success: '<i class="fas fa-check-circle mr-2"></i>',
        error: '<i class="fas fa-exclamation-triangle mr-2"></i>',
        warning: '<i class="fas fa-exclamation-circle mr-2"></i>',
        info: '<i class="fas fa-info-circle mr-2"></i>'
    };

    toast.className = `flex items-center px-4 py-3 rounded-xl shadow-2xl border text-sm font-medium transition-all duration-300 transform translate-y-2 opacity-0 ${colors[type] || colors.info}`;
    toast.innerHTML = `${icons[type] || ''}<span>${message}</span>`;
    container.appendChild(toast);

    // Fade in
    requestAnimationFrame(() => {
        toast.classList.remove('translate-y-2', 'opacity-0');
    });

    // Auto remove
    setTimeout(() => {
        toast.classList.add('opacity-0', 'translate-y-2');
        setTimeout(() => toast.remove(), 300);
    }, 3500);
}

// 모달 제어
function openModal(id) {
    const modal = document.getElementById(id);
    if (modal) {
        modal.classList.remove('hidden');
        modal.classList.add('flex');
    }
}

function closeModal(id) {
    const modal = document.getElementById(id);
    if (modal) {
        modal.classList.add('hidden');
        modal.classList.remove('flex');
    }
}

// 전역 탭 전환
function switchTab(tabName) {
    // 보안 대시보드 권한 체크: 골드(Gold) 이상만 가능
    if (tabName === 'security') {
        if (!state.user || !['gold', 'admin'].includes(state.user.role)) {
            showToast('보안 대시보드는 골드(Gold) 등급 이상부터 열람 가능합니다. (골드 또는 관리자로 로그인하세요)', 'warning');
            if (!state.user) {
                openModal('modal-login');
            }
            if (state.activeTab !== 'security') {
                return;
            }
            tabName = 'board';
        }
    }

    // 관리자 콘솔 권한 체크: 관리자만 가능
    if (tabName === 'admin') {
        if (!state.user || state.user.role !== 'admin') {
            showToast('관리자 권한이 필요합니다. 관리자(admin)로 로그인하세요.', 'warning');
            if (state.activeTab !== 'admin') {
                return;
            }
            tabName = 'board';
        }
    }

    state.activeTab = tabName;
    
    // 네비게이션 활성 상태 표시 (스크린샷 세그먼트 버튼 스타일)
    document.querySelectorAll('.nav-tab-btn').forEach(btn => {
        if (btn.dataset.tab === tabName) {
            btn.className = 'nav-tab-btn segment-btn active flex items-center gap-2';
        } else {
            btn.className = 'nav-tab-btn segment-btn flex items-center gap-2';
        }
    });

    // 뷰 섹션 제어
    const sections = {
        board: document.getElementById('section-board'),
        security: document.getElementById('section-security'),
        admin: document.getElementById('section-admin')
    };

    Object.keys(sections).forEach(key => {
        if (sections[key]) {
            if (key === tabName) {
                sections[key].classList.remove('hidden');
                sections[key].classList.add('animate-fade-in');
            } else {
                sections[key].classList.add('hidden');
            }
        }
    });

    // 탭별 데이터 로드
    if (tabName === 'board') {
        if (window.loadPosts) window.loadPosts(true);
    } else if (tabName === 'security') {
        if (window.loadSecurityData) window.loadSecurityData();
    } else if (tabName === 'admin') {
        if (window.loadAdminData) window.loadAdminData();
    }
}

// 인증 상태 UI 갱신
function updateAuthUI() {
    const unauthNav = document.getElementById('nav-unauth');
    const authNav = document.getElementById('nav-auth');
    const userNameEl = document.getElementById('nav-username');
    const userRoleEl = document.getElementById('nav-user-role');
    const adminNavBtn = document.getElementById('nav-admin-tab');

    if (state.token && state.user) {
        if (unauthNav) unauthNav.classList.add('hidden');
        if (authNav) authNav.classList.remove('hidden');
        if (userNameEl) userNameEl.textContent = state.user.nickname ? `${state.user.nickname} (${state.user.username})` : state.user.username;
        if (userRoleEl) {
            if (state.user.role === 'admin') {
                userRoleEl.textContent = '관리자';
                userRoleEl.className = 'px-2 py-0.5 text-[10px] font-semibold rounded bg-rose-500/15 text-rose-400 border border-rose-500/30 font-mono-code';
            } else if (state.user.role === 'gold') {
                userRoleEl.textContent = '골드회원';
                userRoleEl.className = 'px-2 py-0.5 text-[10px] font-semibold rounded bg-amber-500/15 text-amber-300 border border-amber-500/30 font-mono-code';
            } else {
                userRoleEl.textContent = '일반회원';
                userRoleEl.className = 'px-2 py-0.5 text-[10px] font-medium rounded bg-slate-800 text-slate-300 border border-slate-700 font-mono-code';
            }
        }

        if (adminNavBtn) {
            if (state.user.role === 'admin') {
                adminNavBtn.classList.remove('hidden');
            } else {
                adminNavBtn.classList.add('hidden');
            }
        }
    } else {
        if (unauthNav) unauthNav.classList.remove('hidden');
        if (authNav) authNav.classList.add('hidden');
        if (adminNavBtn) adminNavBtn.classList.add('hidden');
    }
}

// 로그인 실행
async function handleLogin(username, password) {
    try {
        const res = await fetch(`${API_BASE}/auth/login`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ username, password })
        });
        const data = await res.json();

        if (!res.ok) {
            showToast(data.error || '로그인에 실패했습니다.', 'error');
            return false;
        }

        state.token = data.access_token;
        state.user = data.user;
        localStorage.setItem('mb_token', state.token);
        localStorage.setItem('mb_user', JSON.stringify(state.user));

        const roleKr = data.user.role === 'admin' ? '관리자' : (data.user.role === 'gold' ? '골드회원' : '일반회원');
        showToast(`${data.user.nickname || data.user.username}님(${roleKr}) 환영합니다!`, 'success');
        updateAuthUI();
        closeModal('modal-login');
        if (window.loadPosts) window.loadPosts(true);
        return true;
    } catch (err) {
        console.error(err);
        showToast('서버 통신 오류가 발생했습니다.', 'error');
        return false;
    }
}

// 원클릭 빠른 로그인 데모 (관리자 / 골드 / 일반 3종 지원)
function quickLogin(type) {
    const userField = document.getElementById('login-username');
    const passField = document.getElementById('login-password');
    let u = 'testuser';
    let p = '1234';

    if (type === 'admin') {
        u = 'admin';
    } else if (type === 'gold') {
        u = 'golduser';
    } else {
        u = 'testuser';
    }

    if (userField) userField.value = u;
    if (passField) passField.value = p;

    handleLogin(u, p);
}


// 회원가입 실행
async function handleRegister(username, password, email) {
    try {
        const res = await fetch(`${API_BASE}/auth/register`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ username, password, email })
        });
        const data = await res.json();

        if (!res.ok) {
            showToast(data.error || '회원가입 실패', 'error');
            return false;
        }

        showToast('회원가입이 완료되었습니다! 로그인해주세요.', 'success');
        closeModal('modal-register');
        openModal('modal-login');
        document.getElementById('login-username').value = username;
        document.getElementById('login-password').value = password;
        return true;
    } catch (err) {
        console.error(err);
        showToast('서버 오류 발생', 'error');
        return false;
    }
}

// 로그아웃
function handleLogout() {
    state.token = null;
    state.user = null;
    localStorage.removeItem('mb_token');
    localStorage.removeItem('mb_user');
    updateAuthUI();
    showToast('로그아웃되었습니다.', 'info');
    if (state.activeTab === 'admin' || state.activeTab === 'security') {
        switchTab('board');
    }
    if (window.loadPosts) window.loadPosts(true);
}

// 앱 초기화
document.addEventListener('DOMContentLoaded', () => {
    updateAuthUI();

    // 탭 클릭 이벤트
    document.querySelectorAll('.nav-tab-btn').forEach(btn => {
        btn.addEventListener('click', (e) => {
            switchTab(e.currentTarget.dataset.tab);
        });
    });

    // 로그인 폼 제출
    const loginForm = document.getElementById('form-login');
    if (loginForm) {
        loginForm.addEventListener('submit', async (e) => {
            e.preventDefault();
            const u = document.getElementById('login-username').value.trim();
            const p = document.getElementById('login-password').value.trim();
            if (u && p) await handleLogin(u, p);
        });
    }

    // 회원가입 폼 제출
    const regForm = document.getElementById('form-register');
    if (regForm) {
        regForm.addEventListener('submit', async (e) => {
            e.preventDefault();
            const u = document.getElementById('reg-username').value.trim();
            const p = document.getElementById('reg-password').value.trim();
            const em = document.getElementById('reg-email').value.trim();
            if (u && p) await handleRegister(u, p, em);
        });
    }

    // 로그아웃 버튼
    const logoutBtn = document.getElementById('btn-logout');
    if (logoutBtn) {
        logoutBtn.addEventListener('click', handleLogout);
    }

    // 실시간 시계 업데이트 (스크린샷 매칭)
    function updateClock() {
        const el = document.getElementById('clock-display');
        if (el) {
            const now = new Date();
            el.textContent = now.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
        }
    }
    updateClock();
    setInterval(updateClock, 1000);

    // 첫 페이지 로드
    switchTab('board');
});

