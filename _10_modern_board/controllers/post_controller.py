"""게시글(Post) 및 댓글(Comment) 컨트롤러 — 커서 기반 페이징 + 검색 + 필터 + RBAC

기능:
  · 커서 기반 무한 스크롤 페이징 (cursor, limit, search, category, sort)
  · 골드(Gold) 등급 이상 회원만 '보안이슈' 카테고리 글 열람/작성/댓글 허용
  · 일반 회원의 보안글 접근 시 403 Forbidden 차단 및 보안 감사 로그(SecurityLog) 기록
  · 게시글 추천(Like), 댓글(Comment) CRUD
  · _7_board_test 와 _10_modern_board 의 모든 필드명(items, posts, message, msg) 동시 지원
"""
from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity, get_jwt
from sqlalchemy import or_

from extensions import db
from models.post import Post, Comment
from models.security_log import SecurityLog
from .rbac import current_user

post_bp = Blueprint('post', __name__, url_prefix='/api')
posts_bp = post_bp  # 별칭 지원

CATEGORIES = ['공지사항', '자유게시판', '기술Q&A', '보안이슈', '팁&노하우']


@post_bp.route('/categories', methods=['GET'])
def get_categories():
    return jsonify({'categories': CATEGORIES}), 200


@post_bp.route('/posts', methods=['GET'])
@jwt_required(optional=True)
def get_posts():
    """게시글 목록 조회 (커서 기반 페이징 + 검색 + 필터)
    - 보안 관련 글('보안이슈')은 골드(Gold) 등급 이상(gold, admin)만 조회 가능
    """
    claims = get_jwt() if get_jwt_identity() else {}
    role = claims.get('role', 'user')
    is_gold_or_admin = role in ('gold', 'admin')

    cursor = request.args.get('cursor', type=int)
    limit = min(request.args.get('limit', default=10, type=int), 50)
    category = request.args.get('category', default='전체', type=str).strip()
    search = request.args.get('search', default='', type=str).strip()
    sort_by = request.args.get('sort', default='latest', type=str).strip()

    # 골드 미만 유저가 보안이슈 카테고리 직접 요청 시 403 차단
    if category == '보안이슈' and not is_gold_or_admin:
        return jsonify({
            'error': '보안 관련 게시글은 골드(Gold) 등급 이상 회원만 열람할 수 있습니다.',
            'msg': '보안 관련 게시글은 골드(Gold) 등급 이상 회원만 열람할 수 있습니다.',
            'required_role': 'gold',
            'current_role': role,
            'items': [],
            'posts': [],
            'has_more': False,
            'next_cursor': None,
            'count': 0,
            'total_count': 0
        }), 403

    query = Post.query

    # 골드 미만 유저인 경우 목록에서 보안이슈 글 자동 제외
    if not is_gold_or_admin:
        query = query.filter(Post.category != '보안이슈')

    # 카테고리 필터
    if category and category != '전체':
        query = query.filter(Post.category == category)

    # 검색 필터 (제목, 본문, 작성자명, 태그)
    if search:
        search_pattern = f"%{search}%"
        query = query.filter(
            or_(
                Post.title.ilike(search_pattern),
                Post.content.ilike(search_pattern),
                Post.author_name.ilike(search_pattern),
                Post.tags.ilike(search_pattern)
            )
        )

    # 커서 기반 페이징 적용 (기본 최신순: id DESC)
    if cursor and sort_by == 'latest':
        query = query.filter(Post.id < cursor)

    # 정렬
    if sort_by == 'views':
        query = query.order_by(Post.is_pinned.desc(), Post.view_count.desc(), Post.id.desc())
    elif sort_by == 'likes':
        query = query.order_by(Post.is_pinned.desc(), Post.like_count.desc(), Post.id.desc())
    else:
        # 최신순 (공지글 상단 고정 후 id 역순)
        query = query.order_by(Post.is_pinned.desc(), Post.id.desc())

    fetch_limit = limit + 1
    results = query.limit(fetch_limit).all()

    has_more = len(results) > limit
    items = results[:limit]

    next_cursor = items[-1].id if items and has_more else None

    # 전체 개수 (등급별 접근 가능한 글 수만 카운트)
    if not is_gold_or_admin:
        total_count = Post.query.filter(Post.category != '보안이슈').count()
    else:
        total_count = Post.query.count()

    post_dicts = [post.to_dict(include_content=False) for post in items]

    return jsonify({
        'items': post_dicts,
        'posts': post_dicts,
        'next_cursor': next_cursor,
        'has_more': has_more,
        'count': len(items),
        'total_count': total_count
    }), 200


@post_bp.route('/posts/<int:post_id>', methods=['GET'])
@jwt_required(optional=True)
def get_post_detail(post_id):
    post = Post.query.get(post_id)
    if not post:
        return jsonify({'error': '게시글을 찾을 수 없습니다.', 'msg': '게시글을 찾을 수 없습니다.'}), 404

    claims = get_jwt() if get_jwt_identity() else {}
    role = claims.get('role', 'user')
    is_gold_or_admin = role in ('gold', 'admin')

    # 보안 관련 글 상세 조회 권한 체크: 골드 등급 이상만 가능
    if post.category == '보안이슈' and not is_gold_or_admin:
        ip = request.headers.get('X-Forwarded-For', request.remote_addr or '127.0.0.1').split(',')[0].strip()
        username = claims.get('username', 'anonymous')
        user_id = get_jwt_identity()
        log = SecurityLog(
            event_type='UNAUTHORIZED_SECURITY_ACCESS',
            severity='WARNING',
            ip_address=ip,
            endpoint=request.path,
            method=request.method,
            status_code=403,
            user_id=int(user_id) if user_id else None,
            username=username,
            details=f'회원 "{username}"(권한: {role})이 골드 등급 없이 보안 게시글 #{post.id} 열람 시도'
        )
        db.session.add(log)
        db.session.commit()

        return jsonify({
            'error': '보안 관련 게시글은 골드(Gold) 등급 이상 회원만 열람할 수 있습니다.',
            'msg': '보안 관련 게시글은 골드(Gold) 등급 이상 회원만 열람할 수 있습니다.',
            'required_role': 'gold',
            'current_role': role
        }), 403

    # 조회수 증가
    post.view_count += 1
    db.session.commit()

    post_data = post.to_dict(include_content=True)
    post_data['comments'] = [c.to_dict() for c in post.comments]

    return jsonify({'post': post_data, 'msg': 'success'}), 200


@post_bp.route('/posts', methods=['POST'])
@jwt_required()
def create_post():
    user_id = int(get_jwt_identity())
    claims = get_jwt()
    username = claims.get('username')
    role = claims.get('role', 'user')

    data = request.get_json(silent=True) or {}
    title = (data.get('title') or '').strip()
    content = (data.get('content') or '').strip()
    category = (data.get('category') or '자유게시판').strip()
    tags = (data.get('tags') or '').strip()
    is_pinned = bool(data.get('is_pinned', False)) if role == 'admin' else False

    if not title or not content:
        return jsonify({'error': '제목과 내용을 입력해주세요.', 'msg': 'title, content 는 필수입니다.'}), 400

    # 보안 관련 글 작성 권한 체크: 골드 등급 이상만 가능
    if category == '보안이슈' and role not in ('gold', 'admin'):
        return jsonify({
            'error': '보안 관련 게시글은 골드(Gold) 등급 이상 회원만 작성할 수 있습니다.',
            'msg': '보안 관련 게시글은 골드(Gold) 등급 이상 회원만 작성할 수 있습니다.'
        }), 403

    new_post = Post(
        title=title,
        content=content,
        category=category,
        tags=tags,
        is_pinned=is_pinned,
        author_id=user_id,
        author_name=username
    )

    db.session.add(new_post)
    db.session.commit()

    return jsonify({
        'message': '게시글이 등록되었습니다.',
        'msg': '게시글이 등록되었습니다.',
        'id': new_post.id,
        'post': new_post.to_dict(include_content=True)
    }), 201


@post_bp.route('/posts/<int:post_id>', methods=['PUT'])
@jwt_required()
def update_post(post_id):
    user_id = int(get_jwt_identity())
    claims = get_jwt()
    role = claims.get('role', 'user')

    post = Post.query.get(post_id)
    if not post:
        return jsonify({'error': '게시글을 찾을 수 없습니다.', 'msg': '게시글을 찾을 수 없습니다.'}), 404

    # 권한 검사: 본인 또는 관리자만 수정 가능
    if post.author_id != user_id and role != 'admin':
        return jsonify({'error': '수정 권한이 없습니다.', 'msg': '권한이 없습니다.'}), 403

    data = request.get_json(silent=True) or {}
    title = (data.get('title') or '').strip()
    content = (data.get('content') or '').strip()
    category = (data.get('category') or post.category).strip()
    tags = (data.get('tags') or post.tags).strip()

    if (category == '보안이슈' or post.category == '보안이슈') and role not in ('gold', 'admin'):
        return jsonify({'error': '보안 관련 게시글은 골드(Gold) 등급 이상 회원만 수정할 수 있습니다.'}), 403

    if not title or not content:
        return jsonify({'error': '제목과 내용을 입력해주세요.', 'msg': 'title, content 는 필수입니다.'}), 400

    post.title = title
    post.content = content
    post.category = category
    post.tags = tags

    if role == 'admin' and 'is_pinned' in data:
        post.is_pinned = bool(data['is_pinned'])

    db.session.commit()

    return jsonify({
        'message': '게시글이 수정되었습니다.',
        'msg': '수정되었습니다.',
        'post': post.to_dict(include_content=True)
    }), 200


@post_bp.route('/posts/<int:post_id>', methods=['DELETE'])
@jwt_required()
def delete_post(post_id):
    user_id = int(get_jwt_identity())
    claims = get_jwt()
    role = claims.get('role', 'user')

    post = Post.query.get(post_id)
    if not post:
        return jsonify({'error': '게시글을 찾을 수 없습니다.', 'msg': '게시글을 찾을 수 없습니다.'}), 404

    # 권한 검사: 본인 또는 관리자만 삭제 가능
    if post.author_id != user_id and role != 'admin':
        return jsonify({'error': '삭제 권한이 없습니다.', 'msg': '권한이 없습니다.'}), 403

    db.session.delete(post)
    db.session.commit()

    return jsonify({'message': '게시글이 성공적으로 삭제되었습니다.', 'msg': '삭제되었습니다.'}), 200


@post_bp.route('/posts/<int:post_id>/like', methods=['POST'])
def like_post(post_id):
    post = Post.query.get(post_id)
    if not post:
        return jsonify({'error': '게시글을 찾을 수 없습니다.', 'msg': '게시글을 찾을 수 없습니다.'}), 404

    post.like_count += 1
    db.session.commit()

    return jsonify({'like_count': post.like_count, 'msg': '추천 완료'}), 200


@post_bp.route('/posts/<int:post_id>/comments', methods=['GET'])
def get_comments(post_id):
    post = Post.query.get(post_id)
    if not post:
        return jsonify({'error': '게시글을 찾을 수 없습니다.', 'msg': '게시글을 찾을 수 없습니다.'}), 404

    comments = [c.to_dict() for c in post.comments]
    return jsonify({'comments': comments, 'count': len(comments)}), 200


@post_bp.route('/posts/<int:post_id>/comments', methods=['POST'])
@jwt_required()
def add_comment(post_id):
    user_id = int(get_jwt_identity())
    claims = get_jwt()
    username = claims.get('username')
    role = claims.get('role', 'user')

    post = Post.query.get(post_id)
    if not post:
        return jsonify({'error': '게시글을 찾을 수 없습니다.', 'msg': '게시글을 찾을 수 없습니다.'}), 404

    if post.category == '보안이슈' and role not in ('gold', 'admin'):
        return jsonify({'error': '보안 관련 게시글에는 골드(Gold) 등급 이상 회원만 댓글을 작성할 수 있습니다.'}), 403

    data = request.get_json(silent=True) or {}
    content = (data.get('content') or '').strip()
    if not content:
        return jsonify({'error': '댓글 내용을 입력해주세요.', 'msg': '댓글 내용을 입력해주세요.'}), 400

    comment = Comment(
        post_id=post_id,
        author_id=user_id,
        author_name=username,
        content=content
    )

    db.session.add(comment)
    db.session.commit()

    return jsonify({
        'message': '댓글이 등록되었습니다.',
        'msg': '댓글이 등록되었습니다.',
        'comment': comment.to_dict()
    }), 201


@post_bp.route('/posts/<int:post_id>/comments/<int:comment_id>', methods=['DELETE'])
@jwt_required()
def delete_comment(post_id, comment_id):
    user_id = int(get_jwt_identity())
    claims = get_jwt()
    role = claims.get('role', 'user')

    comment = Comment.query.filter_by(id=comment_id, post_id=post_id).first()
    if not comment:
        return jsonify({'error': '댓글을 찾을 수 없습니다.', 'msg': '댓글을 찾을 수 없습니다.'}), 404

    if comment.author_id != user_id and role != 'admin':
        return jsonify({'error': '삭제 권한이 없습니다.', 'msg': '삭제 권한이 없습니다.'}), 403

    db.session.delete(comment)
    db.session.commit()

    return jsonify({'message': '댓글이 삭제되었습니다.', 'msg': '댓글이 삭제되었습니다.'}), 200
