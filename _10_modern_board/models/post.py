from datetime import datetime
from extensions import db

class Post(db.Model):
    __tablename__ = 'posts'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    title = db.Column(db.String(200), nullable=False, index=True)
    content = db.Column(db.Text, nullable=False)
    category = db.Column(db.String(50), default='일반', nullable=False, index=True)
    tags = db.Column(db.String(255), default='', nullable=False)
    view_count = db.Column(db.Integer, default=0, nullable=False)
    like_count = db.Column(db.Integer, default=0, nullable=False)
    is_pinned = db.Column(db.Boolean, default=False, nullable=False)

    author_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    author_name = db.Column(db.String(50), nullable=False)

    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False, index=True)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    comments = db.relationship('Comment', backref='post', lazy=True, cascade='all, delete-orphan', order_by='Comment.created_at.asc()')

    def to_dict(self, include_content=True):
        data = {
            'id': self.id,
            'title': self.title,
            'category': self.category,
            'tags': [t.strip() for t in self.tags.split(',') if t.strip()] if self.tags else [],
            'view_count': self.view_count,
            'like_count': self.like_count,
            'is_pinned': self.is_pinned,
            'author_id': self.author_id,
            'author_name': self.author_name,
            'author': self.author_name,  # _7_ 호환 author 필드
            'comment_count': len(self.comments),
            'created_at': self.created_at.strftime('%Y-%m-%d %H:%M:%S') if self.created_at else None,
            'updated_at': self.updated_at.strftime('%Y-%m-%d %H:%M:%S') if self.updated_at else None
        }
        if include_content:
            data['content'] = self.content
        else:
            data['preview'] = self.content[:150] + ('...' if len(self.content) > 150 else '')
        return data

    def __repr__(self):
        return f'<Post {self.id}: {self.title}>'


class Comment(db.Model):
    __tablename__ = 'comments'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    post_id = db.Column(db.Integer, db.ForeignKey('posts.id', ondelete='CASCADE'), nullable=False, index=True)
    author_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    author_name = db.Column(db.String(50), nullable=False)
    content = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    def to_dict(self):
        return {
            'id': self.id,
            'post_id': self.post_id,
            'author_id': self.author_id,
            'author_name': self.author_name,
            'content': self.content,
            'created_at': self.created_at.strftime('%Y-%m-%d %H:%M:%S') if self.created_at else None
        }

    def __repr__(self):
        return f'<Comment {self.id} on Post {self.post_id}>'
