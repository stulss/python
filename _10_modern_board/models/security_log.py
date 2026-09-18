from datetime import datetime
from extensions import db

class SecurityLog(db.Model):
    __tablename__ = 'security_logs'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    event_type = db.Column(db.String(50), nullable=False, index=True)
    severity = db.Column(db.String(20), default='INFO', nullable=False, index=True)
    ip_address = db.Column(db.String(45), default='127.0.0.1', nullable=False)
    endpoint = db.Column(db.String(255), nullable=True)
    method = db.Column(db.String(10), default='GET', nullable=True)
    status_code = db.Column(db.Integer, default=200, nullable=True)
    user_id = db.Column(db.Integer, nullable=True)
    username = db.Column(db.String(50), nullable=True)
    details = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False, index=True)

    def to_dict(self):
        return {
            'id': self.id,
            'event_type': self.event_type,
            'severity': self.severity,
            'ip_address': self.ip_address,
            'endpoint': self.endpoint,
            'method': self.method,
            'status_code': self.status_code,
            'user_id': self.user_id,
            'username': self.username,
            'details': self.details,
            'created_at': self.created_at.strftime('%Y-%m-%d %H:%M:%S') if self.created_at else None
        }

    def __repr__(self):
        return f'<SecurityLog {self.id}: {self.event_type} [{self.severity}]>'
