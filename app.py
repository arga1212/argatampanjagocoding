from flask import Flask, render_template, request, jsonify, send_file
import google.generativeai as genai
import json, math, os, io, tempfile
from werkzeug.utils import secure_filename
import PyPDF2
from collections import Counter

# Import dari models.py
from models import db, Quiz, Question, Choice, StudentAnswer

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = tempfile.gettempdir()
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max upload
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///quiz.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Inisialisasi database
db.init_app(app)

# Konfigurasi API Gemini
API_KEY = 'AIzaSyBrMJUmYN9k0_7Zduup7Y-szHGarGKWztA'
genai.configure(api_key=API_KEY)

@app.route('/')
def index():
    return render_template('index.html')

def extract_text_from_pdf(file_path):
    with open(file_path, 'rb') as file:
        pdf_reader = PyPDF2.PdfReader(file)
        text = ""
        for page in pdf_reader.pages:
            text += page.extract_text() + "\n"
    return text

def extract_text_from_file(file_path):
    ext = os.path.splitext(file_path)[1].lower()
    if ext == '.pdf':
        return extract_text_from_pdf(file_path)
    elif ext in ['.txt', '.md', '.html']:
        try:
            with open(file_path, 'r', encoding='utf-8') as file:
                return file.read()
        except:
            with open(file_path, 'r', encoding='latin-1') as file:
                return file.read()
    else:
        return "Format file tidak didukung"

def generate_questions(modul_content, jumlah_soal):
    model_soal = genai.GenerativeModel(
        'models/gemini-2.0-flash',
        generation_config=genai.types.GenerationConfig(
            temperature=0.2,
            top_p=0.1,
            top_k=40,
            max_output_tokens=4096
        )
    )

    # Distribusi Bloom
    c1_count = math.ceil(jumlah_soal * 0.20)
    c2_count = math.ceil(jumlah_soal * 0.25)
    c3_count = math.ceil(jumlah_soal * 0.25)
    c4_count = math.ceil(jumlah_soal * 0.15)
    c5_count = math.ceil(jumlah_soal * 0.10)
    c6_count = math.floor(jumlah_soal * 0.05)

    prompt_soal = f"""
Gunakan isi modul pembelajaran berikut sebagai satu-satunya sumber informasi untuk membuat soal.

=== MULAI MODUL ===
{modul_content}
=== AKHIR MODUL ===

Buatkan {jumlah_soal} soal pilihan ganda berdasarkan modul pembelajaran di atas.

Instruksi penting:
1. Setiap soal harus memiliki SATU kategori taksonomi Bloom (C1-C6) yang tepat:
    - C1: Mengingat
    - C2: Memahami
    - C3: Menerapkan
    - C4: Menganalisis
    - C5: Mengevaluasi
    - C6: Mencipta
    
2. Distribusikan soal berdasarkan taksonomi Bloom:
    - C1: {c1_count} soal
    - C2: {c2_count} soal
    - C3: {c3_count} soal
    - C4: {c4_count} soal
    - C5: {c5_count} soal
    - C6: {c6_count} soal

3. Setiap soal HARUS memiliki 5 pilihan jawaban (A-E) dengan SATU jawaban benar.
4. Sertakan penjelasan untuk setiap soal.
5. Format hasil HARUS dalam JSON:
{{
  "soal": [
    {{
      "pertanyaan": "...",
      "kategori_taksonomi": "C1",
      "pilihan": [
        "A. ...",
        "B. ...",
        "C. ...",
        "D. ...",
        "E. ..."
      ],
      "jawaban_benar": "A",
      "penjelasan": "..."
    }}
  ]
}}
"""

    try:
        response = model_soal.generate_content(
            prompt_soal,
            request_options={"timeout": 600}
        )
        response_text = response.text.strip()
        start_idx = response_text.find('{')
        end_idx = response_text.rfind('}')
        if start_idx != -1 and end_idx != -1:
            json_text = response_text[start_idx:end_idx+1]
            hasil_soal = json.loads(json_text)
            return hasil_soal
        else:
            return {"error": "Format JSON tidak valid dalam respons"}
    except json.JSONDecodeError as je:
        return {"error": f"Error parsing JSON: {str(je)}", "raw_text": response_text}
    except Exception as e:
        return {"error": f"Error saat menghasilkan soal: {str(e)}"}

@app.route('/generate', methods=['POST'])
def generate():
    input_type = request.form.get('inputType')
    jumlah_soal = int(request.form.get('jumlahSoal', 10))

    if input_type == 'text':
        modul_content = request.form.get('modulText', '')
    elif input_type == 'file':
        if 'modulFile' not in request.files:
            return jsonify({"error": "Tidak ada file"})
        file = request.files['modulFile']
        if file.filename == '':
            return jsonify({"error": "File kosong"})
        filename = secure_filename(file.filename)
        path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(path)
        modul_content = extract_text_from_file(path)
        os.unlink(path)
    else:
        return jsonify({"error": "Input tidak valid"})

    if not modul_content.strip():
        return jsonify({"error": "Modul kosong"})

    hasil_soal = generate_questions(modul_content, jumlah_soal)

    if "soal" not in hasil_soal:
        return jsonify({"error": "Gagal generate soal", "detail": hasil_soal.get("error", "")})

    with app.app_context():
        quiz = Quiz(title="Quiz dari modul")
        db.session.add(quiz)
        db.session.commit()

        for item in hasil_soal['soal']:
            q = Question(
                quiz_id=quiz.id,
                pertanyaan=item['pertanyaan'],
                kategori_taksonomi=item['kategori_taksonomi'],
                jawaban_benar=item['jawaban_benar'],
                penjelasan=item['penjelasan']
            )
            db.session.add(q)
            db.session.flush()

            for opt in item['pilihan']:
                label, text = opt.split('.', 1)
                db.session.add(Choice(
                    question_id=q.id,
                    label=label.strip(),
                    text=text.strip()
                ))
        db.session.commit()

    return jsonify(hasil_soal)

@app.route('/quiz/<int:quiz_id>')
def student_quiz(quiz_id):
    quiz = Quiz.query.get_or_404(quiz_id)
    questions = Question.query.filter_by(quiz_id=quiz.id).all()
    soal_data = []
    for q in questions:
        choices = Choice.query.filter_by(question_id=q.id).all()
        soal_data.append({
            "id": q.id,
            "pertanyaan": q.pertanyaan,
            "kategori": q.kategori_taksonomi,
            "pilihan": choices
        })
    return render_template('student_quiz.html', quiz=quiz, soal_data=soal_data)

@app.route('/submit_answers/<int:quiz_id>', methods=['POST'])
def submit_answers(quiz_id):
    quiz = Quiz.query.get_or_404(quiz_id)
    answers = request.form
    feedback = []
    student_answers = []
    salah_kategori = []

    for question_id, answer in answers.items():
        question = Question.query.get(int(question_id.split('_')[1]))
        correct_answer = question.jawaban_benar
        if answer == correct_answer:
            feedback.append(f"Question {question_id}: Correct!")
        else:
            kategori_taksonomi = question.kategori_taksonomi
            feedback.append(
                f"Question {question_id}: Incorrect. Correct answer: {correct_answer}. Taksonomi Bloom: {kategori_taksonomi}"
            )
            salah_kategori.append(kategori_taksonomi)

        student_answer = StudentAnswer(
            student_id="siswa123",
            question_id=question.id,
            answer=answer,
            correct=(answer == correct_answer)
        )
        student_answers.append(student_answer)

    db.session.add_all(student_answers)
    db.session.commit()

    counter = Counter(salah_kategori)
    kategori_terbanyak = counter.most_common(1)[0][0] if counter else None
    rekomendasi = rekomendasi_belajar(kategori_terbanyak)

    # Return feedback dengan rekomendasi lebih terstruktur
    return render_template('feedback.html', feedback=feedback, rekomendasi=rekomendasi, kategori_terbanyak=kategori_terbanyak)

def rekomendasi_belajar(kategori):
    if not kategori:
        return "Selamat! Kamu tidak memiliki kelemahan yang signifikan."

    prompt = f"""
Saya seorang siswa yang baru saja mengerjakan quiz dan saya salah dikategori taksonomi {[salah_kategori]}.
Berikan saya rekomendasi belajar, tips belajar efektif, dan saran agar saya bisa meningkatkan kemampuan di kategori ini. Jawab dalam bahasa Indonesia.
"""
    model = genai.GenerativeModel('models/gemini-2.0-flash')
    response = model.generate_content(prompt)
    return response.text.strip()


if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True)
