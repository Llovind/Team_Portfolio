# Image Python versi ringan
FROM python:3.12-slim

# Semua perintah berikutnya dijalankan di folder /app di dalam kontainer
WORKDIR /app

# Salin kode backend ke dalam image
COPY app.py .

# Siapkan folder data (nanti ditempeli Named Volume)
RUN mkdir -p /var/lib/backend_data

# Supaya log print() langsung muncul di "docker logs"
ENV PYTHONUNBUFFERED=1

# Info: backend mendengarkan di port 5000
EXPOSE 5000

# Perintah yang dijalankan saat kontainer menyala
CMD ["python", "app.py"]