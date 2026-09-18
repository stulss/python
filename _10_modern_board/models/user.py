from datetime import datetime
from extensions import db
from werkzeug.security import generate_password_hash, check_password_hash

# ── 등급 정의 ──
# 계단식 등급: user(1) < gold(2) < admin(3)
ROLE_LEVEL = {'user': 1, 'gold': 2, 'admin': 3}
ROLE_LABEL = {'user': '일반', 'gold': '골드', 'admin': '관리자'}
VALID_ROLES = tuple(ROLE_LEVEL)

def role_level(role):
    """정의되지 않은 역할은 0(권한 없음)으로 안전하게 처리"""
    return ROLE_LEVEL.get(role, 0)


class User(db.Model):
    __tablename__ = 'users'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    username = db.Column(db.String(80), unique=True, nullable=False, index=True)
    nickname = db.Column(db.String(50), nullable=True)
    email = db.Column(db.String(120), unique=True, nullable=True)
    password_hash = db.Column(db.String(255), nullable=False)

    # ── 역할 기반 접근제어(RBAC) ──
    # 'user' | 'gold' | 'admin'
    role = db.Column(db.String(20), default='user', server_default='user', nullable=False)
    role_granted_by = db.Column(db.String(80), nullable=True)
    role_granted_at = db.Column(db.DateTime, nullable=True)
    role_reason = db.Column(db.String(200), nullable=True)

    # ── 계정 잠금(브루트포스 방어 / SOAR 연동) ──
    is_active = db.Column(db.Boolean, default=True, server_default='1', nullable=False)
    is_locked = db.Column(db.Boolean, default=False, server_default='0', nullable=False)
    locked_at = db.Column(db.DateTime, nullable=True)
    lock_reason = db.Column(db.String(200), nullable=True)
    failed_logins = db.Column(db.Integer, default=0, server_default='0', nullable=False)

    # 접속 기록
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    last_login_at = db.Column(db.DateTime, nullable=True)

    # 관계 설정
    posts = db.relationship('Post', backref='author_user', lazy=True, cascade='all, delete-orphan')
    comments = db.relationship('Comment', backref='author_user', lazy=True, cascade='all, delete-orphan')

    @property
    def password(self):
        raise AttributeError('비밀번호는 평문으로 읽을 수 없습니다.')

    @password.setter
    def password(self, plain_password):
        self.set_password(plain_password)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    @property
    def is_admin(self):
        return self.role == 'admin'

    @property
    def is_gold(self):
        return self.has_role('gold')

    def has_role(self, required):
        return role_level(self.role) >= role_level(required)

    def to_dict(self):
        return {
            'id': self.id,
            'username': self.username,
            'nickname': self.nickname or self.username,
            'email': self.email,
            'role': self.role,
            'role_label': ROLE_LABEL.get(self.role, self.role),
            'role_granted_by': self.role_granted_by,
            'role_granted_at': self.role_granted_at.strftime('%Y-%m-%d %H:%M:%S') if self.role_granted_at else None,
            'role_reason': self.role_reason,
            'is_active': self.is_active,
            'is_locked': self.is_locked,
            'locked_at': self.locked_at.strftime('%Y-%m-%d %H:%M:%S') if self.locked_at else None,
            'lock_reason': self.lock_reason,
            'failed_logins': self.failed_logins,
            'created_at': self.created_at.strftime('%Y-%m-%d %H:%M:%S') if self.created_at else None,
            'last_login_at': self.last_login_at.strftime('%Y-%m-%d %H:%M:%S') if self.last_login_at else None
        }

    def __repr__(self):
        return f'<User {self.username} ({self.role})>'
