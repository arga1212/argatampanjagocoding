from flask_sqlalchemy import SQLAlchemy
from datetime import datetime

db = SQLAlchemy()

class Quiz(db.Model):
    __tablename__ = 'quizzes'
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(255))

class Question(db.Model):
    __tablename__ = 'questions'
    id = db.Column(db.Integer, primary_key=True)
    quiz_id = db.Column(db.Integer, db.ForeignKey('quizzes.id'))
    pertanyaan = db.Column(db.Text)
    kategori_taksonomi = db.Column(db.String(10))
    jawaban_benar = db.Column(db.String(1))
    penjelasan = db.Column(db.Text)

    quiz = db.relationship('Quiz', backref='questions')

class Choice(db.Model):
    __tablename__ = 'choices'
    id = db.Column(db.Integer, primary_key=True)
    question_id = db.Column(db.Integer, db.ForeignKey('questions.id'))
    label = db.Column(db.String(1))  # A, B, C, D, E
    text = db.Column(db.Text)

    question = db.relationship('Question', backref='choices')

class StudentAnswer(db.Model):
    __tablename__ = 'student_answers'  # Tambahkan __tablename__ untuk konsistensi nama tabel
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.String(100), nullable=False)  # Bisa disesuaikan jika kamu ingin menambahkan autentikasi
    question_id = db.Column(db.Integer, db.ForeignKey('questions.id'), nullable=False)  # Perbaiki di sini
    answer = db.Column(db.String(10), nullable=False)  # Jawaban yang dipilih siswa (A, B, C, D, E)
    correct = db.Column(db.Boolean, default=False)  # Menyimpan status apakah jawabannya benar atau salah
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)

    question = db.relationship('Question', backref='student_answers')

    def __repr__(self):
        return f"<StudentAnswer {self.student_id} - Question {self.question_id}>"
