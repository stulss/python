from datetime import datetime
from extensions import db

class Incident(db.Model):
    """보안 인시던트(사고) 티켓
    탐지 및 대응(잠금/차단) 내역을 단일 추적 단위로 관리합니다.
    """
    __tablename__ = 'incidents'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    title = db.Column(db.String(200), nullable=False)
    src_ip = db.Column(db.String(45), index=True, nullable=True)
    severity = db.Column(db.String(10), default='Medium', nullable=False)  # Low | Medium | High | Critical
    status = db.Column(db.String(12), default='open', index=True, nullable=False)  # open | closed
    summary = db.Column(db.Text, nullable=True)
    event_count = db.Column(db.Integer, default=0, nullable=False)
    actions = db.Column(db.String(255), nullable=True)
    student = db.Column(db.String(50), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    closed_at = db.Column(db.DateTime, nullable=True)

    def to_dict(self):
        return {
            'id': self.id,
            'title': self.title,
            'src_ip': self.src_ip,
            'severity': self.severity,
            'status': self.status,
            'summary': self.summary,
            'event_count': self.event_count,
            'actions': self.actions,
            'student': self.student,
            'created_at': self.created_at.strftime('%Y-%m-%d %H:%M:%S') if self.created_at else None,
            'updated_at': self.updated_at.strftime('%Y-%m-%d %H:%M:%S') if self.updated_at else None,
            'closed_at': self.closed_at.strftime('%Y-%m-%d %H:%M:%S') if self.closed_at else None
        }

    def __repr__(self):
        return f'<Incident {self.id}: {self.title} [{self.status}]>'
