/**
 * Flask RESTful Board Application JavaScript
 * Features: JWT Auth, RESTful CRUD, Cursor-based pagination, Search & Filter
 */

// Global State
function loadStoredUser() {
    try {
        return JSON.parse(localStorage.getItem('board_user_info') || 'null');
    } catch (e) {
        // 손상된 값이 남아있으면 스크립트 전체가 죽지 않도록 초기화하고 넘어간다
        localStorage.removeItem('board_user_info');
        return null;
    }
}

let state = {
    token: localStorage.getItem('board_jwt_token') || null,
    user: loadStoredUser(),
    currentCategory: '전체',
    searchKeyword: '',
    searchType: 'all',
    limit: 6,
    nextCursor: null,
    hasMore: false,
    posts: [],
    currentDetailPost: null
};

// ==================== INITIALIZATION ====================
document.addEventListener('DOMContentLoaded', () => {
    updateAuthUI();
    loadCategories();
    loadPosts(false);
});

// ==================== AUTHENTICATION ====================
function getAuthHeaders() {
    const headers = { 'Content-Type': 'application/json' };
    if (state.token) {
        headers['Authorization'] = `Bearer ${state.token}`;
    }
    return headers;
}

function updateAuthUI() {
    const guestSec = document.getElementById('authGuestSection');
    const userSec = document.getElementById('authUserSection');
    const nicknameSpan = document.getElementById('userNickname');

    if (state.token && state.user) {
        guestSec.classList.add('hidden');
        userSec.classList.remove('hidden');
        nicknameSpan.textContent = state.user.nickname || state.user.username;
    } else {
        guestSec.classList.remove('hidden');
        userSec.classList.add('hidden');
    }
}

async function handleLogin(e) {
    e.preventDefault();
    const username = document.getElementById('loginUsername').value.trim();
    const password = document.getElementById('loginPassword').value.trim();

    try {
        const res = await fetch('/api/auth/login', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ username, password })
        });
        const data = await res.json();

        if (res.ok && data.success) {
            state.token = data.token;
            state.user = data.user;
            localStorage.setItem('board_jwt_token', data.token);
            localStorage.setItem('board_user_info', JSON.stringify(data.user));
            
            updateAuthUI();
            closeModal('loginModal');
            document.getElementById('loginUsername').value = '';
            document.getElementById('loginPassword').value = '';
            showToast(data.message || '로그인되었습니다.', 'success');
        } else {
            showToast(data.message || '로그인 실패', 'error');
        }
    } catch (err) {
        showToast('로그인 요청 중 오류가 발생했습니다.', 'error');
    }
}

async function handleRegister(e) {
    e.preventDefault();
    const username = document.getElementById('regUsername').value.trim();
    const nickname = document.getElementById('regNickname').value.trim();
    const password = document.getElementById('regPassword').value.trim();

    try {
        const res = await fetch('/api/auth/register', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ username, nickname, password })
        });
        const data = await res.json();

        if (res.ok && data.success) {
            state.token = data.token;
            state.user = data.user;
            localStorage.setItem('board_jwt_token', data.token);
            localStorage.setItem('board_user_info', JSON.stringify(data.user));

            updateAuthUI();
            closeModal('registerModal');
            document.getElementById('regUsername').value = '';
            document.getElementById('regNickname').value = '';
            document.getElementById('regPassword').value = '';
            showToast('회원가입이 완료되었습니다!', 'success');
        } else {
            showToast(data.message || '회원가입 실패', 'error');
        }
    } catch (err) {
        showToast('회원가입 요청 중 오류가 발생했습니다.', 'error');
    }
}

function logout() {
    state.token = null;
    state.user = null;
    localStorage.removeItem('board_jwt_token');
    localStorage.removeItem('board_user_info');
    updateAuthUI();
    showToast('로그아웃 되었습니다.', 'info');
}

// ==================== CATEGORIES & SEARCH ====================
async function loadCategories() {
    try {
        const res = await fetch('/api/categories');
        const data = await res.json();
        if (data.success) {
            renderCategoryTabs(data.categories);
        }
    } catch (err) {
        console.error('Failed to load categories', err);
    }
}

function renderCategoryTabs(categories) {
    const container = document.getElementById('categoryTabs');
    container.innerHTML = categories.map(cat => {
        const isActive = state.currentCategory === cat.name;
        const activeClass = isActive 
            ? 'bg-blue-600 text-white shadow-sm' 
            : 'bg-slate-100 text-slate-700 hover:bg-slate-200';
        return `
            <button onclick="selectCategory('${cat.name}')" class="px-3.5 py-1.5 rounded-lg text-xs font-semibold transition-all ${activeClass}">
                ${cat.name} <span class="${isActive ? 'text-blue-100' : 'text-slate-400'} text-[11px] ml-0.5">(${cat.count})</span>
            </button>
        `;
    }).join('');
}

function selectCategory(catName) {
    state.currentCategory = catName;
    loadCategories();
    resetAndLoad();
}

function executeSearch() {
    const keyword = document.getElementById('searchInput').value.trim();
    const type = document.getElementById('searchType').value;
    state.searchKeyword = keyword;
    state.searchType = type;

    const clearBtn = document.getElementById('clearSearchBtn');
    if (keyword) {
        clearBtn.classList.remove('hidden');
    } else {
        clearBtn.classList.add('hidden');
    }

    resetAndLoad();
}

function clearSearch() {
    document.getElementById('searchInput').value = '';
    document.getElementById('clearSearchBtn').classList.add('hidden');
    state.searchKeyword = '';
    resetAndLoad();
}

function changeLimit() {
    state.limit = parseInt(document.getElementById('limitSelect').value, 10);
    resetAndLoad();
}

// ==================== POSTS & CURSOR PAGINATION ====================
function resetAndLoad() {
    state.nextCursor = null;
    state.posts = [];
    loadPosts(false);
}

function loadMorePosts() {
    if (state.hasMore && state.nextCursor) {
        loadPosts(true);
    }
}

async function loadPosts(append = false) {
    const params = new URLSearchParams();
    params.append('limit', state.limit);
    if (state.currentCategory && state.currentCategory !== '전체') {
        params.append('category', state.currentCategory);
    }
    if (state.searchKeyword) {
        params.append('search', state.searchKeyword);
        params.append('search_type', state.searchType);
    }
    if (append && state.nextCursor) {
        params.append('cursor', state.nextCursor);
    }

    try {
        const res = await fetch(`/api/posts?${params.toString()}`);
        const data = await res.json();

        if (res.ok && data.success) {
            state.hasMore = data.has_more;
            state.nextCursor = data.next_cursor;

            if (append) {
                state.posts = [...state.posts, ...data.items];
            } else {
                state.posts = data.items;
            }

            renderPosts();
            updatePaginationUI(data.total_count, append);
        } else {
            showToast(data.message || '게시글을 불러오지 못했습니다.', 'error');
        }
    } catch (err) {
        showToast('게시글 로딩 중 오류가 발생했습니다.', 'error');
    }
}

function getCategoryBadgeColor(category) {
    switch (category) {
        case '공지': return 'bg-red-50 text-red-600 border-red-200';
        case '자유': return 'bg-blue-50 text-blue-600 border-blue-200';
        case '질문': return 'bg-amber-50 text-amber-700 border-amber-200';
        case '팁': return 'bg-emerald-50 text-emerald-700 border-emerald-200';
        case '정보': return 'bg-purple-50 text-purple-700 border-purple-200';
        default: return 'bg-slate-100 text-slate-700 border-slate-200';
    }
}

function renderPosts() {
    const grid = document.getElementById('postGrid');
    const emptyState = document.getElementById('emptyState');

    if (!state.posts || state.posts.length === 0) {
        grid.innerHTML = '';
        emptyState.classList.remove('hidden');
        return;
    }

    emptyState.classList.add('hidden');
    grid.innerHTML = state.posts.map(post => {
        const badgeColor = getCategoryBadgeColor(post.category);
        return `
            <div class="bg-white rounded-2xl p-5 border border-slate-200 shadow-sm hover:shadow-md transition-all duration-200 flex flex-col justify-between group cursor-pointer" onclick="openPostDetail(${post.id})">
                <div>
                    <div class="flex items-center justify-between gap-2 mb-3">
                        <span class="px-2.5 py-0.5 rounded-full text-xs font-semibold border ${badgeColor}">
                            ${post.category}
                        </span>
                        <span class="text-[11px] font-mono text-slate-400">#${post.id}</span>
                    </div>

                    <h3 class="font-bold text-slate-900 text-base mb-2 group-hover:text-blue-600 transition-colors line-clamp-2">
                        ${escapeHtml(post.title)}
                    </h3>

                    <p class="text-xs text-slate-500 line-clamp-2 mb-4 leading-relaxed">
                        ${escapeHtml(post.content)}
                    </p>
                </div>

                <div class="pt-3 border-t border-slate-100 flex items-center justify-between text-xs text-slate-400">
                    <div class="flex items-center gap-2">
                        <div class="w-6 h-6 rounded-full bg-slate-100 flex items-center justify-center text-slate-600 text-[10px] font-bold">
                            <i class="fa-solid fa-user"></i>
                        </div>
                        <span class="text-slate-700 font-medium text-[11px]">${escapeHtml(post.author_nickname)}</span>
                    </div>
                    <div class="flex items-center gap-3 text-[11px]">
                        <span>${post.created_at ? post.created_at.split(' ')[0] : ''}</span>
                        <span class="flex items-center gap-1">
                            <i class="fa-regular fa-eye"></i> ${post.views}
                        </span>
                    </div>
                </div>
            </div>
        `;
    }).join('');
}

function updatePaginationUI(totalCount, isAppended) {
    document.getElementById('totalCountDisplay').textContent = totalCount;
    
    // Filter Info
    let filterText = '';
    if (state.currentCategory !== '전체') filterText += `[${state.currentCategory}] `;
    if (state.searchKeyword) filterText += `"${state.searchKeyword}" 검색결과`;
    document.getElementById('currentFilterInfo').textContent = filterText;

    // Cursor Badge
    const cursorBadge = document.getElementById('cursorStateBadge');
    if (state.nextCursor) {
        cursorBadge.innerHTML = `Next Cursor: <b class="text-blue-600">#${state.nextCursor}</b> (현재 ${state.posts.length}개 표시)`;
    } else {
        cursorBadge.innerHTML = `Cursor: <b class="text-slate-600">끝</b> (총 ${state.posts.length}개 로드)`;
    }

    // Load More Button
    const loadMoreBtn = document.getElementById('loadMoreBtn');
    const resetBtn = document.getElementById('resetCursorBtn');

    if (state.hasMore) {
        loadMoreBtn.classList.remove('hidden');
        loadMoreBtn.disabled = false;
    } else {
        loadMoreBtn.classList.add('hidden');
    }

    if (state.posts.length > state.limit) {
        resetBtn.classList.remove('hidden');
    } else {
        resetBtn.classList.add('hidden');
    }
}

// ==================== POST DETAIL & CRUD ====================
async function openPostDetail(postId) {
    try {
        const res = await fetch(`/api/posts/${postId}`, {
            headers: getAuthHeaders()
        });
        const data = await res.json();

        if (res.ok && data.success) {
            const post = data.post;
            state.currentDetailPost = post;

            document.getElementById('detailId').textContent = post.id;
            document.getElementById('detailTitle').textContent = post.title;
            document.getElementById('detailContent').textContent = post.content;
            document.getElementById('detailAuthor').textContent = `${post.author_nickname} (@${post.author_username})`;
            document.getElementById('detailDate').textContent = post.created_at;
            document.getElementById('detailViews').textContent = post.views;

            // Category badge
            const catBadge = document.getElementById('detailCategory');
            catBadge.textContent = post.category;
            catBadge.className = `px-2.5 py-1 rounded-md text-xs font-semibold border ${getCategoryBadgeColor(post.category)}`;

            // Author action buttons
            const authorActions = document.getElementById('detailAuthorActions');
            if (post.is_author) {
                authorActions.classList.remove('hidden');
            } else {
                authorActions.classList.add('hidden');
            }

            openModal('postDetailModal');

            // Update views in state list locally
            const p = state.posts.find(x => x.id === postId);
            if (p) {
                p.views = post.views;
                renderPosts();
            }
        } else {
            showToast(data.message || '게시글을 불러올 수 없습니다.', 'error');
        }
    } catch (err) {
        showToast('게시글 상세 정보 조회 중 오류가 발생했습니다.', 'error');
    }
}

function openCreatePostModal() {
    if (!state.token) {
        showToast('로그인이 필요한 기능입니다.', 'info');
        openModal('loginModal');
        return;
    }
    document.getElementById('formModalTitle').innerHTML = '<i class="fa-solid fa-pen-nib text-blue-600"></i> 새 글 작성';
    document.getElementById('editPostId').value = '';
    document.getElementById('formCategory').value = '일반';
    document.getElementById('formTitle').value = '';
    document.getElementById('formContent').value = '';
    document.getElementById('formSubmitBtn').textContent = '등록하기';
    openModal('postFormModal');
}

function openEditPostModalFromDetail() {
    const post = state.currentDetailPost;
    if (!post) return;

    closeModal('postDetailModal');
    document.getElementById('formModalTitle').innerHTML = '<i class="fa-solid fa-pen text-amber-600"></i> 게시글 수정';
    document.getElementById('editPostId').value = post.id;
    document.getElementById('formCategory').value = post.category;
    document.getElementById('formTitle').value = post.title;
    document.getElementById('formContent').value = post.content;
    document.getElementById('formSubmitBtn').textContent = '수정 완료';
    openModal('postFormModal');
}

async function handleSavePost(e) {
    e.preventDefault();
    if (!state.token) {
        showToast('로그인이 필요합니다.', 'error');
        return;
    }

    const editId = document.getElementById('editPostId').value;
    const category = document.getElementById('formCategory').value;
    const title = document.getElementById('formTitle').value.trim();
    const content = document.getElementById('formContent').value.trim();

    const isEdit = !!editId;
    const url = isEdit ? `/api/posts/${editId}` : '/api/posts';
    const method = isEdit ? 'PUT' : 'POST';

    try {
        const res = await fetch(url, {
            method: method,
            headers: getAuthHeaders(),
            body: JSON.stringify({ category, title, content })
        });
        const data = await res.json();

        if (res.ok && data.success) {
            closeModal('postFormModal');
            showToast(data.message || (isEdit ? '수정되었습니다.' : '등록되었습니다.'), 'success');
            loadCategories();
            resetAndLoad();
        } else {
            showToast(data.message || '저장에 실패했습니다.', 'error');
        }
    } catch (err) {
        showToast('요청 처리 중 오류가 발생했습니다.', 'error');
    }
}

async function confirmDeletePost() {
    const post = state.currentDetailPost;
    if (!post) return;

    if (!confirm(`'${post.title}' 게시글을 정말 삭제하시겠습니까?`)) {
        return;
    }

    try {
        const res = await fetch(`/api/posts/${post.id}`, {
            method: 'DELETE',
            headers: getAuthHeaders()
        });
        const data = await res.json();

        if (res.ok && data.success) {
            closeModal('postDetailModal');
            showToast('게시글이 삭제되었습니다.', 'success');
            loadCategories();
            resetAndLoad();
        } else {
            showToast(data.message || '삭제에 실패했습니다.', 'error');
        }
    } catch (err) {
        showToast('삭제 중 오류가 발생했습니다.', 'error');
    }
}

// ==================== MODAL & UTILS ====================
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

function switchModal(fromId, toId) {
    closeModal(fromId);
    openModal(toId);
}

function showToast(message, type = 'info') {
    const container = document.getElementById('toastContainer');
    const toast = document.createElement('div');
    
    let bg = 'bg-slate-800 text-white';
    let icon = '<i class="fa-solid fa-circle-info text-blue-400"></i>';

    if (type === 'success') {
        bg = 'bg-emerald-600 text-white';
        icon = '<i class="fa-solid fa-circle-check text-white"></i>';
    } else if (type === 'error') {
        bg = 'bg-red-600 text-white';
        icon = '<i class="fa-solid fa-circle-exclamation text-white"></i>';
    }

    toast.className = `${bg} px-4 py-3 rounded-xl shadow-lg flex items-center gap-2.5 text-xs font-medium transition-all duration-300 pointer-events-auto transform translate-y-2 opacity-0`;
    toast.innerHTML = `${icon} <span>${escapeHtml(message)}</span>`;

    container.appendChild(toast);

    // Animation
    setTimeout(() => {
        toast.classList.remove('translate-y-2', 'opacity-0');
    }, 10);

    setTimeout(() => {
        toast.classList.add('opacity-0', 'translate-y-2');
        setTimeout(() => toast.remove(), 300);
    }, 3000);
}

function escapeHtml(str) {
    if (!str) return '';
    return str
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#039;');
}

// ==================== [OPEN API] 부산 테마여행정보 100선 ====================
let busanThemeData = [];
let currentThemeGugun = '전체';

function switchView(viewName) {
    const boardSec = document.getElementById('boardViewSection');
    const openApiSec = document.getElementById('openApiViewSection');
    const navBoardBtn = document.getElementById('navBoardBtn');
    const navOpenApiBtn = document.getElementById('navOpenApiBtn');

    if (viewName === 'openapi') {
        boardSec.classList.add('hidden');
        openApiSec.classList.remove('hidden');

        navBoardBtn.className = 'px-3.5 py-2 rounded-xl text-sm font-medium text-slate-600 hover:bg-slate-100 transition-all flex items-center gap-1.5';
        navOpenApiBtn.className = 'px-3.5 py-2 rounded-xl text-sm font-bold bg-amber-50 text-amber-600 shadow-sm transition-all flex items-center gap-1.5';

        if (busanThemeData.length === 0) {
            loadBusanThemes();
        }
    } else {
        boardSec.classList.remove('hidden');
        openApiSec.classList.add('hidden');

        navBoardBtn.className = 'px-3.5 py-2 rounded-xl text-sm font-bold bg-blue-50 text-blue-600 transition-all flex items-center gap-1.5';
        navOpenApiBtn.className = 'px-3.5 py-2 rounded-xl text-sm font-medium text-slate-600 hover:bg-slate-100 transition-all flex items-center gap-1.5';
    }
}

async function loadBusanThemes() {
    const grid = document.getElementById('busanThemeGrid');
    grid.innerHTML = '<div class="col-span-full py-16 text-center text-slate-400"><i class="fa-solid fa-spinner fa-spin text-3xl mb-3 text-orange-500"></i><p class="font-medium">부산 테마여행 100선 데이터를 불러오는 중입니다...</p></div>';

    const params = new URLSearchParams();
    params.append('numOfRows', 100);
    if (currentThemeGugun !== '전체') params.append('gugun', currentThemeGugun);
    const searchVal = document.getElementById('themeSearchInput').value.trim();
    if (searchVal) params.append('search', searchVal);

    try {
        const res = await fetch(`/api/openapi/busan-themes?${params.toString()}`);
        const data = await res.json();

        if (data.success) {
            busanThemeData = data.items;
            document.getElementById('openApiSourceBadge').textContent = data.source;
            renderGugunTabs(data.gugunList || []);
            renderThemeCards(busanThemeData);
            showToast(`부산 테마여행지 ${busanThemeData.length}건이 로드되었습니다!`, 'success');
        } else {
            showToast('데이터 로드 실패', 'error');
        }
    } catch (err) {
        showToast('공공데이터 요청 중 오류 발생', 'error');
    }
}

function renderGugunTabs(guguns) {
    const container = document.getElementById('busanGugunTabs');
    container.innerHTML = guguns.map(g => {
        const isActive = currentThemeGugun === g;
        const cls = isActive ? 'bg-orange-500 text-white font-bold shadow-sm' : 'bg-slate-100 text-slate-600 hover:bg-slate-200';
        return `<button onclick="selectThemeGugun('${g}')" class="px-3 py-1 rounded-lg text-xs transition-all ${cls}">${g}</button>`;
    }).join('');
}

function selectThemeGugun(gugun) {
    currentThemeGugun = gugun;
    loadBusanThemes();
}

function executeThemeSearch() {
    loadBusanThemes();
}

function renderThemeCards(items) {
    const grid = document.getElementById('busanThemeGrid');
    if (!items || items.length === 0) {
        grid.innerHTML = '<div class="col-span-full py-16 text-center text-slate-400">조건에 맞는 테마여행지가 없습니다.</div>';
        return;
    }

    grid.innerHTML = items.map((item, idx) => `
        <div onclick="openThemeDetail(${idx})" class="bg-white rounded-2xl overflow-hidden border border-slate-200 shadow-sm hover:shadow-lg hover:-translate-y-1 transition-all duration-200 cursor-pointer flex flex-col justify-between group">
            <div>
                <div class="relative h-44 w-full bg-slate-100 overflow-hidden">
                    <img src="${item.imageUrl}" alt="${escapeHtml(item.title)}" class="w-full h-full object-cover group-hover:scale-105 transition-transform duration-300" onerror="this.src='https://images.unsplash.com/photo-1596422846543-75c6fc197f07?w=600'">
                    <span class="absolute top-2.5 left-2.5 bg-slate-900/80 backdrop-blur-sm text-white px-2.5 py-0.5 rounded-md text-[11px] font-bold">
                        ${item.gugun}
                    </span>
                    <span class="absolute top-2.5 right-2.5 bg-white/90 text-slate-700 px-2 py-0.5 rounded-md text-[10px] font-mono">
                        #${item.id}
                    </span>
                </div>
                <div class="p-4">
                    <h4 class="font-bold text-slate-900 text-sm mb-1.5 group-hover:text-orange-600 transition-colors line-clamp-1">
                        ${escapeHtml(item.title)}
                    </h4>
                    <p class="text-[11px] text-slate-500 line-clamp-2 leading-relaxed mb-3">
                        ${escapeHtml(item.contents)}
                    </p>
                </div>
            </div>
            <div class="px-4 py-2.5 bg-slate-50 border-t border-slate-100 flex items-center justify-between text-[11px] text-slate-400">
                <span class="truncate max-w-[150px]"><i class="fa-solid fa-location-dot text-slate-400 mr-1"></i>${item.addr}</span>
                <span class="text-orange-500 font-bold group-hover:underline">상세보기 &rarr;</span>
            </div>
        </div>
    `).join('');
}

function openThemeDetail(index) {
    const item = busanThemeData[index];
    if (!item) return;

    document.getElementById('tDetailImg').src = item.imageUrl;
    document.getElementById('tDetailGugun').textContent = item.gugun;
    document.getElementById('tDetailTitle').textContent = item.title;
    
    // 부제목
    const subTitleEl = document.getElementById('tDetailSubTitle');
    if (item.subTitle && item.subTitle !== item.title) {
        subTitleEl.textContent = item.subTitle;
        subTitleEl.classList.remove('hidden');
    } else {
        subTitleEl.classList.add('hidden');
    }

    document.getElementById('tDetailAddr').querySelector('span').textContent = item.addr || '부산광역시 일원';
    
    // 본문 내용 (HTML 태그가 포함되어 있을 수 있으므로 innerHTML 처리 및 정제)
    const contentsEl = document.getElementById('tDetailContents');
    if (item.contents && item.contents.includes('<')) {
        contentsEl.innerHTML = item.contents;
    } else {
        contentsEl.textContent = item.contents || '상세 정보가 없습니다.';
    }

    // 교통 정보
    const trafficBox = document.getElementById('tDetailTrafficBox');
    const trafficEl = document.getElementById('tDetailTraffic');
    if (item.traffic) {
        trafficEl.textContent = item.traffic;
        trafficBox.classList.remove('hidden');
    } else {
        trafficBox.classList.add('hidden');
    }

    document.getElementById('tDetailTime').textContent = item.usageTime || '상시 운영';
    document.getElementById('tDetailFee').textContent = item.fee || '무료 또는 개별 상이';
    document.getElementById('tDetailTel').textContent = item.tel || '051-1330 (관광안내)';
    
    const hpLink = document.getElementById('tDetailHomepage');
    hpLink.href = item.homepage && item.homepage.startsWith('http') ? item.homepage : 'https://www.visitbusan.net';

    openModal('busanThemeDetailModal');
}

async function saveOpenApiToDb() {
    if (!busanThemeData || busanThemeData.length === 0) {
        showToast('저장할 데이터가 없습니다.', 'error');
        return;
    }

    try {
        const res = await fetch('/api/openapi/save-to-db', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ items: busanThemeData })
        });
        const data = await res.json();
        if (res.ok && data.success) {
            showToast(data.message, 'success');
        } else {
            showToast(data.message || '저장 실패', 'error');
        }
    } catch (err) {
        showToast('DB 저장 요청 실패', 'error');
    }
}
