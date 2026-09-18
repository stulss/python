from datetime import datetime
from extensions import db

class SecurityEvent(db.Model):
    __tablename__ = 'security_events'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    student = db.Column(db.String(50), nullable=False, index=True)
    src_ip = db.Column(db.String(45), nullable=False, index=True)
    level = db.Column(db.Integer, default=0, nullable=False)
    rule = db.Column(db.String(50), nullable=True)
    rule_id = db.Column(db.String(50), nullable=True)
    fail_count = db.Column(db.Integer, default=0, nullable=False)
    decision = db.Column(db.String(10), nullable=False, index=True)  # 'allow', 'deny'
    severity = db.Column(db.String(20), default='Low', nullable=False)  # 'Low', 'Medium', 'High', 'Critical'
    reason = db.Column(db.String(255), nullable=True)
    users = db.Column(db.String(255), nullable=True)
    last_seen = db.Column(db.String(50), nullable=True)
    window_min = db.Column(db.Integer, nullable=True)
    source = db.Column(db.String(50), default='login_guard', nullable=True)
    generated_at = db.Column(db.String(32), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    def to_dict(self):
        return {
            'id': self.id,
            'student': self.student,
            'src_ip': self.src_ip,
            'level': self.level,
            'rule': self.rule,
            'rule_id': self.rule_id,
            'fail_count': self.fail_count,
            'decision': self.decision,
            'severity': self.severity,
            'reason': self.reason,
            'users': self.users,
            'last_seen': self.last_seen,
            'window_min': self.window_min,
            'source': self.source,
            'generated_at': self.generated_at,
            'created_at': self.created_at.strftime('%Y-%m-%d %H:%M:%S') if self.created_at else None
        }

    def __repr__(self):
        return f'<SecurityEvent {self.id}: {self.decision} {self.src_ip}>'
