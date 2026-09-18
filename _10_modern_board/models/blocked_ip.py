from datetime import datetime
from extensions import db

class BlockedIP(db.Model):
    """차단된 IP 목록 (실차단/active response)
    미들웨어가 매 요청 이 테이블을 확인하여 403 Forbidden 차단합니다.
    """
    __tablename__ = 'blocked_ips'

    ip = db.Column(db.String(45), primary_key=True)
    reason = db.Column(db.String(200), nullable=True)
    blocked_by = db.Column(db.String(80), nullable=True)
    blocked_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    def to_dict(self):
        return {
            'ip': self.ip,
            'reason': self.reason,
            'blocked_by': self.blocked_by,
            'blocked_at': self.blocked_at.strftime('%Y-%m-%d %H:%M:%S') if self.blocked_at else None
        }

    def __repr__(self):
        return f'<BlockedIP {self.ip} ({self.reason})>'
