/**
 * Modern Board - Board Features (Cursor-based Pagination, CRUD, Search, Filter, Comments)
 */

const boardState = {
    cursor: null,        // 커서 기반 페이징용 마지막 ID
    limit: 6,           // 한 번에 가져올 개수
    category: '전체',
    search: '',
    sort: 'latest',
    hasMore: false,
    isLoading: false,
    currentPostId: null,
    editingPostId: null,
    viewMode: 'grid'    // 'grid' or 'list'
};

// 게시글 목록 불러오기 (커서 기반 페이징)
async function loadPosts(reset = false) {
    if (boardState.isLoading) return;

    const listEl = document.getElementById('posts-container');
    const loadMoreBtn = document.getElementById('btn-load-more');
    const emptyStateEl = document.getElementById('posts-empty');

    if (reset) {
        boardState.cursor = null;
        boardState.hasMore = false;
        if (listEl) listEl.innerHTML = '';
    }

    boardState.isLoading = true;
    if (loadMoreBtn) {
        loadMoreBtn.disabled = true;
        loadMoreBtn.innerHTML = '<i class="fas fa-spinner fa-spin mr-2"></i>게시글 불러오는 중...';
    }

    try {
        const params = new URLSearchParams({
            limit: boardState.limit,
            category: boardState.category,
            search: boardState.search,
            sort: boardState.sort
        });
        if (boardState.cursor) {
            params.append('cursor', boardState.cursor);
        }

        const res = await fetch(`${API_BASE}/posts?${params.toString()}`, {
            headers: getAuthHeaders(true)
        });
        const data = await res.json();

        if (!res.ok) {
            if (res.status === 403) {
                showToast(data.error || '보안 관련 글은 골드(Gold) 등급 이상부터 열람 가능합니다.', 'warning');
                if (emptyStateEl) {
                    emptyStateEl.innerHTML = `
                        <i class="fas fa-lock text-amber-400 text-3xl mb-2"></i>
                        <div class="text-sm font-bold text-amber-300">골드(Gold) 등급 전용 열람 구역</div>
                        <div class="text-xs text-slate-400 mt-1">보안 관련 글은 골드회원 또는 관리자로 로그인 후 열람할 수 있습니다.</div>
                    `;
                    emptyStateEl.classList.remove('hidden');
                }
                if (loadMoreBtn) loadMoreBtn.classList.add('hidden');
                return;
            }
            throw new Error(data.error || '목록을 불러오지 못했습니다.');
        }

        boardState.cursor = data.next_cursor;
        boardState.hasMore = data.has_more;

        // 렌더링
        if (reset && data.items.length === 0) {
            if (emptyStateEl) emptyStateEl.classList.remove('hidden');
        } else {
            if (emptyStateEl) emptyStateEl.classList.add('hidden');
            data.items.forEach((post, index) => {
                const card = renderPostCard(post, index);
                if (listEl) listEl.appendChild(card);
            });
        }

        // 전체 카운트 표시
        const totalCountEl = document.getElementById('total-posts-count');
        if (totalCountEl && data.total_count !== undefined) {
            totalCountEl.textContent = data.total_count;
        }
        const telemetryPostCountEl = document.getElementById('telemetry-post-count');
        if (telemetryPostCountEl && data.total_count !== undefined) {
            telemetryPostCountEl.textContent = data.total_count;
        }

        // 스크린샷의 Load comparison 실시간 차트 렌더링
        renderLoadComparisonChart();


        // 더보기 버튼 제어
        if (loadMoreBtn) {
            if (boardState.hasMore) {
                loadMoreBtn.classList.remove('hidden');
                loadMoreBtn.disabled = false;
                loadMoreBtn.innerHTML = '<i class="fas fa-chevron-down mr-2"></i>다음 게시글 더보기 (Cursor Pagination)';
            } else {
                loadMoreBtn.classList.add('hidden');
            }
        }
    } catch (err) {
        console.error(err);
        showToast('게시글을 불러오는 중 오류가 발생했습니다.', 'error');
    } finally {
        boardState.isLoading = false;
    }
}

// 개별 게시글 카드 엘리먼트 렌더링 (단정하고 모던한 SaaS 커뮤니티 스타일)
function renderPostCard(post, index) {
    const div = document.createElement('div');
    const isPinned = post.is_pinned;

    // 카테고리별 테마 컬러 (과하지 않은 차분한 뱃지)
    const categoryStyles = {
        '공지사항': 'bg-rose-500/10 text-rose-400 border-rose-500/20',
        '기술Q&A': 'bg-blue-500/10 text-blue-400 border-blue-500/20',
        '보안이슈': 'bg-amber-500/10 text-amber-400 border-amber-500/20',
        '팁&노하우': 'bg-emerald-500/10 text-emerald-400 border-emerald-500/20',
        '자유게시판': 'bg-slate-800 text-slate-300 border-slate-700'
    };
    const catStyle = categoryStyles[post.category] || 'bg-slate-800 text-slate-300 border-slate-700';

    // 작성일 포맷팅 (YYYY-MM-DD)
    const createdDate = post.created_at ? post.created_at.split(' ')[0] : '';
    const previewText = post.preview || '';

    div.className = `matrix-card p-4 flex flex-col justify-between min-h-[145px] cursor-pointer group ${
        isPinned ? 'featured-post' : ''
    }`;

    div.innerHTML = `
        <div>
            <!-- 상단 메타: 카테고리 뱃지 & 날짜/고정표시 -->
            <div class="flex items-center justify-between gap-2 mb-2 text-[11px]">
                <span class="px-2 py-0.5 rounded text-[11px] font-medium border ${catStyle}">
                    ${escapeHtml(post.category)}
                </span>
                <div class="flex items-center gap-1.5 text-slate-500 text-[11px] font-mono-code">
                    ${isPinned ? '<span class="px-1.5 py-0.2 rounded bg-indigo-500/20 text-indigo-300 text-[10px] font-bold">📌 공지</span>' : ''}
                    <span>${createdDate}</span>
                </div>
            </div>

            <!-- 제목 (2줄 제한) -->
            <h3 class="text-sm font-bold text-slate-100 line-clamp-2 leading-snug group-hover:text-indigo-400 transition-colors mb-1.5">
                ${escapeHtml(post.title)}
            </h3>

            <!-- 본문 미리보기 (1줄) -->
            ${previewText ? `<p class="text-xs text-slate-400 line-clamp-1 leading-relaxed mb-3">${escapeHtml(previewText)}</p>` : '<div class="mb-3"></div>'}
        </div>

        <!-- 하단 메타: 작성자 정보 & 조회/추천/댓글 통계 -->
        <div class="flex items-center justify-between pt-2.5 border-t border-slate-800/80 text-xs">
            <div class="flex items-center gap-1.5 text-slate-300">
                <span class="w-5 h-5 rounded-full bg-slate-800 border border-slate-700 flex items-center justify-center text-[10px] font-bold text-slate-400 shrink-0">
                    ${escapeHtml(post.author_name ? post.author_name.charAt(0).toUpperCase() : 'U')}
                </span>
                <span class="text-xs text-slate-300 font-medium truncate max-w-[90px]">
                    ${escapeHtml(post.author_name)}
                </span>
            </div>

            <div class="flex items-center gap-3 text-slate-400 text-[11px] font-mono-code">
                <span title="조회수"><i class="far fa-eye mr-1 text-slate-500"></i>${post.view_count}</span>
                <span title="추천" class="${post.like_count > 0 ? 'text-rose-400 font-semibold' : ''}"><i class="far fa-heart mr-1 ${post.like_count > 0 ? 'text-rose-400' : 'text-slate-500'}"></i>${post.like_count}</span>
                <span title="댓글" class="${post.comment_count > 0 ? 'text-indigo-400 font-semibold' : ''}"><i class="far fa-comment mr-1 ${post.comment_count > 0 ? 'text-indigo-400' : 'text-slate-500'}"></i>${post.comment_count}</span>
            </div>
        </div>
    `;

    div.addEventListener('click', () => openPostDetail(post.id));
    return div;
}



// 상세 게시글 보기
async function openPostDetail(postId) {
    boardState.currentPostId = postId;
    try {
        const res = await fetch(`${API_BASE}/posts/${postId}`, {
            headers: getAuthHeaders(true)
        });
        const data = await res.json();
        if (!res.ok) {
            if (res.status === 403) {
                showToast(data.error || '보안 관련 게시글은 골드(Gold) 등급 이상 회원만 열람할 수 있습니다.', 'warning');
                return;
            }
            throw new Error(data.error || '게시글을 찾을 수 없습니다.');
        }

        const post = data.post;
        document.getElementById('detail-id').textContent = `#${post.id}`;
        document.getElementById('detail-category').textContent = post.category;
        document.getElementById('detail-title').textContent = post.title;
        document.getElementById('detail-author').textContent = post.author_name;
        document.getElementById('detail-date').textContent = post.created_at;
        document.getElementById('detail-views').textContent = post.view_count;
        document.getElementById('detail-likes').textContent = post.like_count;
        document.getElementById('detail-content').textContent = post.content;

        // 태그 렌더링
        const tagsContainer = document.getElementById('detail-tags');
        if (tagsContainer) {
            tagsContainer.innerHTML = post.tags && post.tags.length > 0
                ? post.tags.map(t => `<span class="px-2.5 py-1 text-xs rounded-lg bg-slate-800 text-indigo-400 border border-slate-700/60 font-medium">#${t}</span>`).join(' ')
                : '';
        }

        // 수정/삭제 버튼 권한 제어
        const actionsEl = document.getElementById('detail-actions');
        const canManage = state.user && (state.user.id === post.author_id || state.user.role === 'admin');
        if (actionsEl) {
            actionsEl.style.display = canManage ? 'flex' : 'none';
        }

        // 댓글 렌더링
        renderComments(post.comments);

        openModal('modal-post-detail');
    } catch (err) {
        console.error(err);
        showToast('게시글 상세 정보를 가져오는데 실패했습니다.', 'error');
    }
}

// 댓글 목록 렌더링
function renderComments(comments) {
    const container = document.getElementById('comments-list');
    const countEl = document.getElementById('detail-comments-count');
    if (!container) return;

    container.innerHTML = '';
    if (countEl) countEl.textContent = comments ? comments.length : 0;

    if (!comments || comments.length === 0) {
        container.innerHTML = `<div class="py-6 text-center text-xs text-slate-500">등록된 댓글이 없습니다. 첫 댓글을 남겨보세요!</div>`;
        return;
    }

    comments.forEach(c => {
        const item = document.createElement('div');
        const canDelete = state.user && (state.user.id === c.author_id || state.user.role === 'admin');
        
        item.className = 'p-3 rounded-xl bg-slate-800/50 border border-slate-800 flex flex-col gap-1.5';
        item.innerHTML = `
            <div class="flex items-center justify-between text-xs">
                <div class="flex items-center gap-2">
                    <span class="font-bold text-slate-300">${escapeHtml(c.author_name)}</span>
                    <span class="text-[11px] text-slate-500">${c.created_at}</span>
                </div>
                ${canDelete ? `<button onclick="deleteComment(${c.id})" class="text-slate-500 hover:text-rose-400 transition-colors text-xs p-1" title="댓글 삭제"><i class="fas fa-trash-alt"></i></button>` : ''}
            </div>
            <p class="text-xs text-slate-300 whitespace-pre-wrap leading-relaxed">${escapeHtml(c.content)}</p>
        `;
        container.appendChild(item);
    });
}

// 댓글 등록
async function submitComment() {
    if (!state.token) {
        showToast('로그인이 필요한 서비스입니다.', 'warning');
        openModal('modal-login');
        return;
    }

    const input = document.getElementById('comment-input');
    const content = input.value.trim();
    if (!content) {
        showToast('댓글 내용을 입력해주세요.', 'warning');
        return;
    }

    try {
        const res = await fetch(`${API_BASE}/posts/${boardState.currentPostId}/comments`, {
            method: 'POST',
            headers: getAuthHeaders(true),
            body: JSON.stringify({ content })
        });
        const data = await res.json();
        if (!res.ok) throw new Error(data.error || '댓글 등록 실패');

        showToast('댓글이 등록되었습니다.', 'success');
        input.value = '';
        openPostDetail(boardState.currentPostId); // 갱신
    } catch (err) {
        console.error(err);
        showToast(err.message || '댓글 등록 중 오류가 발생했습니다.', 'error');
    }
}

// 댓글 삭제
async function deleteComment(commentId) {
    if (!confirm('이 댓글을 삭제하시겠습니까?')) return;
    try {
        const res = await fetch(`${API_BASE}/posts/${boardState.currentPostId}/comments/${commentId}`, {
            method: 'DELETE',
            headers: getAuthHeaders(true)
        });
        const data = await res.json();
        if (!res.ok) throw new Error(data.error || '댓글 삭제 실패');

        showToast('댓글이 삭제되었습니다.', 'info');
        openPostDetail(boardState.currentPostId);
    } catch (err) {
        showToast(err.message || '오류 발생', 'error');
    }
}

// 좋아요 증가
async function likeCurrentPost() {
    if (!boardState.currentPostId) return;
    try {
        const res = await fetch(`${API_BASE}/posts/${boardState.currentPostId}/like`, { method: 'POST' });
        const data = await res.json();
        if (res.ok) {
            document.getElementById('detail-likes').textContent = data.like_count;
            showToast('좋아요를 눌렀습니다! ❤️', 'success');
        }
    } catch (err) {
        console.error(err);
    }
}

// 글 작성/수정 모달 열기
function openPostForm(isEdit = false) {
    if (!state.token) {
        showToast('로그인이 필요한 기능입니다.', 'warning');
        openModal('modal-login');
        return;
    }

    const modalTitle = document.getElementById('modal-post-form-title');
    const form = document.getElementById('form-post');
    const pinGroup = document.getElementById('post-form-pin-group');

    // 관리자일 때만 공지 고정 옵션 노출
    if (pinGroup) {
        pinGroup.style.display = state.user && state.user.role === 'admin' ? 'block' : 'none';
    }

    if (isEdit && boardState.currentPostId) {
        boardState.editingPostId = boardState.currentPostId;
        modalTitle.textContent = '게시글 수정';
        document.getElementById('post-form-title').value = document.getElementById('detail-title').textContent;
        document.getElementById('post-form-category').value = document.getElementById('detail-category').textContent;
        document.getElementById('post-form-content').value = document.getElementById('detail-content').textContent;
        closeModal('modal-post-detail');
    } else {
        boardState.editingPostId = null;
        modalTitle.textContent = '새 게시글 작성';
        form.reset();
    }
    openModal('modal-post-form');
}

// 글 저장 (생성 또는 수정)
async function savePost(e) {
    e.preventDefault();
    const title = document.getElementById('post-form-title').value.trim();
    const category = document.getElementById('post-form-category').value;
    const tags = document.getElementById('post-form-tags').value.trim();
    const content = document.getElementById('post-form-content').value.trim();
    const isPinned = document.getElementById('post-form-pinned')?.checked || false;

    if (!title || !content) {
        showToast('제목과 내용을 모두 작성해주세요.', 'warning');
        return;
    }

    const payload = { title, category, tags, content, is_pinned: isPinned };
    const isEdit = Boolean(boardState.editingPostId);
    const url = isEdit ? `${API_BASE}/posts/${boardState.editingPostId}` : `${API_BASE}/posts`;
    const method = isEdit ? 'PUT' : 'POST';

    try {
        const res = await fetch(url, {
            method,
            headers: getAuthHeaders(true),
            body: JSON.stringify(payload)
        });
        const data = await res.json();
        if (!res.ok) throw new Error(data.error || '게시글 저장에 실패했습니다.');

        showToast(isEdit ? '게시글이 수정되었습니다.' : '새 게시글이 등록되었습니다!', 'success');
        closeModal('modal-post-form');
        loadPosts(true); // 목록 새로고침
        if (isEdit) {
            openPostDetail(boardState.editingPostId);
        }
    } catch (err) {
        showToast(err.message || '오류가 발생했습니다.', 'error');
    }
}

// 글 삭제
async function deleteCurrentPost() {
    if (!boardState.currentPostId) return;
    if (!confirm('정말로 이 게시글을 삭제하시겠습니까?')) return;

    try {
        const res = await fetch(`${API_BASE}/posts/${boardState.currentPostId}`, {
            method: 'DELETE',
            headers: getAuthHeaders(true)
        });
        const data = await res.json();
        if (!res.ok) throw new Error(data.error || '게시글 삭제 실패');

        showToast('게시글이 삭제되었습니다.', 'info');
        closeModal('modal-post-detail');
        loadPosts(true);
    } catch (err) {
        showToast(err.message || '삭제 중 오류가 발생했습니다.', 'error');
    }
}

// HTML 엔티티 이스케이프 헬퍼 (XSS 방어)
function escapeHtml(str) {
    if (!str) return '';
    return str
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#039;');
}

// 이벤트 바인딩
document.addEventListener('DOMContentLoaded', () => {
    // 카테고리 필터 클릭
    document.querySelectorAll('.filter-category-btn').forEach(btn => {
        btn.addEventListener('click', (e) => {
            document.querySelectorAll('.filter-category-btn').forEach(b => {
                b.className = 'filter-category-btn px-3.5 py-1.5 rounded-xl text-xs font-semibold text-slate-400 hover:text-white hover:bg-slate-800 transition-all';
            });
            e.currentTarget.className = 'filter-category-btn px-3.5 py-1.5 rounded-xl text-xs font-bold bg-indigo-600 text-white shadow-md shadow-indigo-600/30 transition-all';
            boardState.category = e.currentTarget.dataset.category;
            loadPosts(true);
        });
    });

    // 검색창 입력 이벤트
    const searchInput = document.getElementById('board-search-input');
    let searchDebounce = null;
    if (searchInput) {
        searchInput.addEventListener('input', (e) => {
            clearTimeout(searchDebounce);
            searchDebounce = setTimeout(() => {
                boardState.search = e.target.value.trim();
                loadPosts(true);
            }, 300);
        });
    }

    // 정렬 선택
    const sortSelect = document.getElementById('board-sort-select');
    if (sortSelect) {
        sortSelect.addEventListener('change', (e) => {
            boardState.sort = e.target.value;
            loadPosts(true);
        });
    }

    // 커서 페이징 더보기 버튼 클릭
    const loadMoreBtn = document.getElementById('btn-load-more');
    if (loadMoreBtn) {
        loadMoreBtn.addEventListener('click', () => {
            loadPosts(false); // 기존 목록 유지 후 다음 커서 로드
        });
    }

    // 새 글 작성 버튼
    const writeBtn = document.getElementById('btn-write-post');
    if (writeBtn) {
        writeBtn.addEventListener('click', () => openPostForm(false));
    }

    // 글 폼 저장 이벤트
    const postForm = document.getElementById('form-post');
    if (postForm) {
        postForm.addEventListener('submit', savePost);
    }

    // 상세 모달 이벤트들
    document.getElementById('btn-detail-like')?.addEventListener('click', likeCurrentPost);
    document.getElementById('btn-detail-edit')?.addEventListener('click', () => openPostForm(true));
    document.getElementById('btn-detail-delete')?.addEventListener('click', deleteCurrentPost);
    document.getElementById('btn-comment-submit')?.addEventListener('click', submitComment);
});

// Load Comparison Chart (Reference Screenshot Style)
let loadChartInstance = null;
function renderLoadComparisonChart() {
    const ctx = document.getElementById('chart-load-comparison');
    if (!ctx) return;

    if (loadChartInstance) {
        loadChartInstance.destroy();
    }

    loadChartInstance = new Chart(ctx, {
        type: 'line',
        data: {
            labels: ['15:00', '16:00', '17:00', '17:45', '18:30', '19:15', '20:00'],
            datasets: [
                {
                    label: '실시간 요청 트래픽 (피크: 20.84)',
                    data: [12.2, 14.8, 17.5, 20.84, 18.2, 14.1, 11.5],
                    borderColor: '#38bdf8', // Neon Cyan
                    backgroundColor: 'rgba(56, 189, 248, 0.1)',
                    tension: 0.4,
                    borderWidth: 2,
                    pointRadius: [0, 0, 0, 5, 0, 0, 0],
                    pointBackgroundColor: '#ffffff',
                    pointBorderColor: '#38bdf8',
                    pointBorderWidth: 2,
                    fill: false
                },
                {
                    label: '평균 트래픽 기준선',
                    data: [10.5, 12.0, 15.1, 18.73, 16.5, 12.8, 10.1],
                    borderColor: '#818cf8', // Neon Violet
                    borderDash: [3, 3],
                    tension: 0.4,
                    borderWidth: 1.5,
                    pointRadius: 0,
                    fill: false
                }
            ]

        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: { display: false },
                tooltip: {
                    backgroundColor: '#090d18',
                    borderColor: '#1e293b',
                    borderWidth: 1,
                    titleFont: { size: 10, family: 'JetBrains Mono' },
                    bodyFont: { size: 10, family: 'JetBrains Mono' }
                }
            },
            scales: {
                x: {
                    grid: { color: 'rgba(51, 65, 85, 0.15)' },
                    ticks: { color: '#64748b', font: { size: 9, family: 'JetBrains Mono' } }
                },
                y: {
                    display: false,
                    min: 8,
                    max: 23
                }
            }
        }
    });
}

// 태그 클릭 시 자동 검색
function searchByTag(tag) {
    const input = document.getElementById('board-search-input');
    if (input) input.value = tag;
    boardState.search = tag;
    loadPosts(true);
}

// 전역 노출
window.loadPosts = loadPosts;
window.openPostDetail = openPostDetail;
window.deleteComment = deleteComment;
window.renderLoadComparisonChart = renderLoadComparisonChart;
window.searchByTag = searchByTag;

