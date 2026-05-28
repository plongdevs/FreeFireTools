# Hướng dẫn Deploy lên Render (Miễn phí)

## Tổng quan
- **Web Service**: Flask app (app.py)
- **Worker Service**: Background worker (worker.py)
- **Platform**: Render (miễn phí)
- **Giới hạn**: 750 giờ/tháng, 512MB RAM

## Bước 1: Chuẩn bị GitHub

### 1.1 Tạo repository mới
```bash
# Đi đến https://github.com/new
# Tạo repository mới (ví dụ: garena-tools)
# Không cần README, .gitignore
```

### 1.2 Push code lên GitHub
```bash
cd c:/Users/ADMIN/Desktop/ToolsGopCli

# Khởi tạo git
git init

# Thêm tất cả file
git add .

# Commit
git commit -m "Initial commit"

# Thêm remote
git remote add origin https://github.com/USERNAME/garena-tools.git

# Push
git branch -M main
git push -u origin main main
```

## Bước 2: Deploy Web Service lên Render

### 2.1 Đăng ký Render
- Đi đến https://render.com
- Đăng ký bằng GitHub
- Authorize Render để truy cập repository

### 2.2 Tạo Web Service
1. Click "New +" → "Web Service"
2. Chọn repository: `garena-tools`
3. **Name**: `garena-web`
4. **Build & Deploy**:
   - **Branch**: `main`
   - **Runtime**: `Python`
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `python app.py`
5. **Environment Variables** (không cần)
6. Click "Deploy Web Service"

### 2.3 Chờ deploy
- Render sẽ clone code và build
- Quá trình mất 2-5 phút
- URL sẽ là: `https://garena-web.onrender.com`

## Bước 3: Deploy Worker Service lên Render

### 3.1 Tạo Worker Service
1. Click "New +" → "Web Service" (dùng Web Service cho worker)
2. Chọn repository: `garena-tools`
3. **Name**: `garena-worker`
4. **Build & Deploy**:
   - **Branch**: `main`
   - **Runtime**: `Python`
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `python worker.py`
5. Click "Deploy Web Service"

### 3.2 Chờ deploy
- Worker sẽ chạy ngầm
- Tự động restart nếu crash

## Bước 4: Kiểm tra

### 4.1 Test Web Service
- Truy cập: `https://garena-web.onrender.com`
- Test các tính năng

### 4.2 Test Worker Service
- Tạo Spam Log task
- Kiểm tra status sau vài phút

## Bước 5: Cấu hình nâng cấp (Tùy chọn)

### 5.1 Thêm Environment Variables
Nếu cần thêm biến môi trường:
- Vào Web Service → Settings → Environment Variables
- Thêm biến cần thiết

### 5.2 Auto-deploy
- Mặc định Render auto-deploy khi push code
- Có thể tắt trong Settings

## Lưu ý quan trọng

### Giới hạn miễn phí
- **750 giờ/tháng** cho cả web + worker
- Nếu chạy 24/7 sẽ hết sau ~15 ngày
- Worker sẽ sleep khi không có task

### Tối ưu hóa
- Worker chỉ chạy khi có task
- Web service sleep sau 15 phút không truy cập
- Lần truy cập đầu tiên sau sleep mất ~30s

### Backup
- Code an toàn trên GitHub
- Render không lưu dữ liệu vĩnh viễn
- Nên backup tasks.json định kỳ

## Troubleshooting

### Web không chạy
- Kiểm tra Logs tab trên Render
- Xem error message
- Đảm bảo requirements.txt đúng

### Worker không chạy
- Kiểm tra Worker Service logs
- Đảm bảo worker.py không có lỗi
- Restart worker service

### Task không chạy
- Kiểm tra tasks.json có tồn tại không
- Worker service đang chạy không
- Kiểm tra logs của worker

## URL sau khi deploy
- **Web**: `https://garena-web.onrender.com`
- **Worker**: Chỉ chạy ngầm, không có URL
- **Logs**: Xem trên Dashboard Render
