# Kiểm chứng môi trường sạch — chặng 6a

- Cách làm: sao chép cây làm việc vào thư mục tạm, loại `.git`, `.venv`, cache và `dist/`; tạo virtual environment mới; cài `requirements.txt`; chạy full pytest; khởi động Streamlit từ bản sao.
- Cài đặt: `python -m pip install -r requirements.txt` — exit 0.
- Full pytest trong bản sao sạch: `119 passed in 29.19s`.
- Streamlit từ virtual environment mới: `HTTP 200; body=ok`.
- Kiểm tra này không phải kiểm tra gói `dist/`; việc kiểm tra dist thuộc chặng 6b.
