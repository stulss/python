"""웹 페이지(HTML) 뷰 라우트 컨트롤러

단일 페이지 애플리케이션(SPA) 반응형 템플릿 서빙:
  · /                : 메인 게시판 화면
  · /login, /register: 로그인 및 회원가입 모달/화면
  · /posts/<id>      : 게시글 상세
  · /admin           : 관리자 대시보드
  · /security        : 보안 SIEM 대시보드
  · /gold            : 골드회원 전용 화면
  · /dashboard       : 보안 이벤트 대시보드
  · /public-posts    : 공공데이터 여행지 화면
"""
from flask import Blueprint, render_template

page_bp = Blueprint('page', __name__)


@page_bp.route('/')
@page_bp.route('/login')
@page_bp.route('/register')
@page_bp.route('/posts/<int:post_id>')
def index(post_id=None):
    return render_template('index.html')


@page_bp.route('/dashboard')
def dashboard():
    """보안 이벤트 대시보드 (n8n 이 저장한 허용/거부 기록 화면)"""
    return render_template('dashboard.html')


@page_bp.route('/gold')
def gold_page():
    """골드 등급 전용 화면"""
    return render_template('gold.html')


@page_bp.route('/admin')
def admin_page():
    """관리자 화면"""
    return render_template('admin.html')


@page_bp.route('/security')
def security_spa():
    """SPA 보안 관제 센터"""
    return render_template('index.html')


@page_bp.route('/public-posts')
def public_posts_page():
    return render_template('public_posts.html')


@page_bp.route('/public-posts/<int:uc_seq>')
def public_post_detail_page(uc_seq):
    return render_template('public_detail.html', uc_seq=uc_seq)
