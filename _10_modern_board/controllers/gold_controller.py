"""골드 등급 전용 컨트롤러 (/api/gold)

골드(gold) 및 관리자(admin) 등급만 이용할 수 있는 전용 API 입니다.
서버 계층에서 @role_required('gold') 가드를 수행합니다.
"""
from flask import Blueprint, jsonify
from models.post import Post
from .rbac import role_required

gold_bp = Blueprint('gold', __name__, url_prefix='/api/gold')


@gold_bp.route('/posts', methods=['GET'])
@role_required('gold')
def gold_posts():
    """골드 및 관리자 전용 보안/프리미엄 게시글 목록"""
    rows = (Post.query.filter(Post.category.in_(['골드', '보안이슈', '보안']))
            .order_by(Post.id.desc()).limit(50).all())
    return jsonify({
        'count': len(rows),
        'posts': [p.to_dict(include_content=False) for p in rows],
        'items': [p.to_dict(include_content=False) for p in rows]
    }), 200
