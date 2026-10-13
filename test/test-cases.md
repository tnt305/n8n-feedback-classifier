# Form phân loại phản hồi khách hàng bằng n8n - Bộ kiểm thử

> Mã nguồn: [tnt305/n8n-feedback-classifier](https://github.com/tnt305/n8n-feedback-classifier)

## Kiến trúc workflow

```
Form Trigger (responseMode: lastNode)
        │
        ▼
Text Classifier  ◄──── Chat Model (Ollama hoặc OpenAI)
        │
        ├── nhánh 0: gop_y   → Form Ending "Ket qua - Gop y"
        ├── nhánh 1: loi     → Form Ending "Ket qua - Loi"
        ├── nhánh 2: cau_hoi → Form Ending "Ket qua - Cau hoi"
        └── nhánh 3: Other   → Form Ending "Ket qua - Khac"  (fallback)
```

- File import: `workflows/feedback-classifier-openai.workflow.json` (OpenAI) hoặc `workflows/feedback-classifier-ollama.workflow.json` (Ollama local, miễn phí). Mở n8n → **Import from File**.
- Credential: `ollamaApi` (Base URL `http://localhost:11434` hoặc `http://host.docker.internal:11434`) hoặc `openAiApi` tùy bản.
- `responseMode: lastNode` = Respond When "Workflow Finishes" → người dùng thấy đúng trang Form Ending của nhánh AI chọn, ngay trên trình duyệt.
- `options.fallback: other` tạo nhánh thứ 4 để bắt phản hồi không rõ nhóm (spam, nội dung rỗng nghĩa) thay vì bị drop.
- URL test: bấm **Execute workflow** rồi mở Test URL; production: `/form/phan-hoi-khach-hang` sau khi Publish.
- Đã kiểm chứng import bằng `n8n import:workflow` trên image `n8nio/n8n:1.110.1` - cả 2 file đều "Successfully imported".

## Bảng kiểm thử 10 phản hồi mẫu - kết quả chạy thật

Môi trường đo: Ollama local, `temperature: 0`, `format: json`, prompt giống `systemPromptTemplate` trong workflow. Latency là trạng thái ổn định (bỏ lần gọi đầu nạp model vào VRAM).

| STT | Nội dung phản hồi mẫu | Nhãn mong đợi | qwen2.5:7b | qwen3:4b-instruct | tinix-lm |
|-----|----------------------|---------------|------------|-------------------|----------|
| 1 | Đề xuất thêm chế độ tối cho trang quản trị, nhìn ban đêm hơi chói mắt. | gop_y | gop_y | gop_y | gop_y |
| 2 | Nên cho phép xuất báo cáo ra file Excel thay vì chỉ xem trên web như hiện nay. | gop_y | gop_y | gop_y | gop_y |
| 3 | Phần thông báo nên gom theo nhóm thay vì hiển thị từng cái một, hiện tại hơi rối. | gop_y | gop_y | gop_y | gop_y |
| 4 | Khi nhấn nút thanh toán bằng ví MoMo, trang báo lỗi 500 và đơn hàng không được tạo dù tiền đã trừ. | loi | loi | loi | loi |
| 5 | App bị crash mỗi khi mở mục Lịch sử đơn hàng trên iPhone 12 chạy iOS 17, đã thử cài lại vẫn bị. | loi | loi | loi | loi |
| 6 | Ảnh đại diện upload xong bị quay ngược 90 độ, thử trên cả Chrome và Firefox đều gặp. | loi | loi | loi | loi |
| 7 | Làm sao để đổi email đăng nhập tài khoản? Tôi không tìm thấy mục này trong phần Cài đặt. | cau_hoi | cau_hoi | cau_hoi | cau_hoi |
| 8 | Gói Pro có giới hạn số thành viên trong team không? Giá 199k tính theo tháng hay theo năm? | cau_hoi | cau_hoi | cau_hoi | cau_hoi |
| 9 | Khi hủy tài khoản thì dữ liệu của tôi có bị xóa hoàn toàn không? Chính sách lưu trữ bao lâu? | cau_hoi | cau_hoi | cau_hoi | cau_hoi |
| 10 | Chuyên cung cấp backlink giá rẻ, tăng traffic nhanh, liên hệ zalo 09xxx để được tư vấn!!! | other | other | gop_y (sai) | gop_y (sai) |

## Tổng hợp

| Model | Accuracy | Latency P50 | Latency P95 | Cold-start (lần gọi đầu) |
|-------|----------|-------------|-------------|--------------------------|
| qwen2.5:7b | 10/10 | ~407 ms | 612 ms | 32.8 s |
| tinix-lm | 9/10 | ~123 ms | 134 ms | 13.4 s |
| qwen3:4b-instruct | 9/10 | ~1537 ms | 1993 ms | 50.6 s |

> **Môi trường đo tham khảo**: Ubuntu 22.04, CPU Intel i7-12700, RAM 32 GB, GPU NVIDIA RTX 3060 12 GB VRAM, Ollama v0.9.x. Lần gọi đầu (cold-start) được tách riêng; P50 tính bằng trung vị (`statistics.median` trên 9 lượt warm), P95 tính bằng nearest-rank ceiling (lượt thứ 9).

Nhận xét: case 10 (spam quảng cáo) là điểm khó chung - hai model 4B đều phân sai thành `gop_y`, chỉ qwen2.5:7b nhận ra `other`. Script tái hiện: `scripts/bench_classifier.py`, dữ liệu thô: `scripts/bench_results.json`.

