from app import app, db

# Menghapus semua tabel dan membuat ulang
with app.app_context():
    db.drop_all()  # Menghapus semua tabel yang ada
    db.create_all()  # Membuat ulang tabel di database
    print("Semua tabel telah dihapus dan database baru telah dibuat!")
