# %% bench_classifier.py - benchmark phan loai phan hoi bang Ollama, mo phong node Text Classifier cua n8n
import json
import time
import urllib.request

OLLAMA_URL = "http://localhost:11434/api/chat"

CATEGORIES = {
    "gop_y": "Góp ý, đề xuất cải tiến: mong muốn tính năng mới, thay đổi giao diện, cải thiện trải nghiệm. Không chứa báo lỗi và không đặt câu hỏi.",
    "loi": "Báo lỗi hệ thống: chức năng không hoạt động, crash, màn hình trắng, lỗi HTTP, thanh toán thất bại, hiển thị sai dữ liệu.",
    "cau_hoi": "Câu hỏi cần giải đáp: cách sử dụng tính năng, chính sách, giá cả, tài khoản. Không phải báo lỗi hay đề xuất tính năng.",
}

SYSTEM_PROMPT = (
    "Bạn là bộ phân loại phản hồi khách hàng viết bằng tiếng Việt. "
    "Phân loại văn bản người dùng vào đúng một trong các nhóm: "
    f"{', '.join(CATEGORIES)}.\n"
    "Mô tả từng nhóm:\n"
    + "\n".join(f"- {k}: {v}" for k, v in CATEGORIES.items())
    + "\nNếu không khớp nhóm nào, dùng nhãn \"other\".\n"
    'Chỉ trả về JSON dạng {"category": "<nhan>"}, không giải thích thêm.'
)

TEST_CASES = [
    ("Đề xuất thêm chế độ tối cho trang quản trị, nhìn ban đêm hơi chói mắt.", "gop_y"),
    ("Nên cho phép xuất báo cáo ra file Excel thay vì chỉ xem trên web như hiện nay.", "gop_y"),
    ("Phần thông báo nên gom theo nhóm thay vì hiển thị từng cái một, hiện tại hơi rối.", "gop_y"),
    ("Khi nhấn nút thanh toán bằng ví MoMo, trang báo lỗi 500 và đơn hàng không được tạo dù tiền đã trừ.", "loi"),
    ("App bị crash mỗi khi mở mục Lịch sử đơn hàng trên iPhone 12 chạy iOS 17, đã thử cài lại vẫn bị.", "loi"),
    ("Ảnh đại diện upload xong bị quay ngược 90 độ, thử trên cả Chrome và Firefox đều gặp.", "loi"),
    ("Làm sao để đổi email đăng nhập tài khoản? Tôi không tìm thấy mục này trong phần Cài đặt.", "cau_hoi"),
    ("Gói Pro có giới hạn số thành viên trong team không? Giá 199k tính theo tháng hay theo năm?", "cau_hoi"),
    ("Khi hủy tài khoản thì dữ liệu của tôi có bị xóa hoàn toàn không? Chính sách lưu trữ bao lâu?", "cau_hoi"),
    ("Chuyên cung cấp backlink giá rẻ, tăng traffic nhanh, liên hệ zalo 09xxx để được tư vấn!!!", "other"),
]

MODELS = ["qwen3:4b-instruct", "tinix-lm:latest", "qwen2.5:7b"]


def classify(model: str, text: str) -> tuple[str, float]:
    payload = {
        "model": model,
        "stream": False,
        "format": "json",
        "options": {"temperature": 0},
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": text},
        ],
    }
    req = urllib.request.Request(
        OLLAMA_URL,
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"},
    )
    t0 = time.perf_counter()
    with urllib.request.urlopen(req, timeout=180) as resp:
        body = json.loads(resp.read())
    latency = (time.perf_counter() - t0) * 1000
    raw = body["message"]["content"]
    try:
        return json.loads(raw).get("category", "parse_error").strip(), latency
    except json.JSONDecodeError:
        return "parse_error", latency


def main():
    results = {}
    for model in MODELS:
        rows, correct, latencies = [], 0, []
        for i, (text, expected) in enumerate(TEST_CASES, 1):
            got, ms = classify(model, text)
            ok = got == expected
            correct += ok
            latencies.append(ms)
            rows.append((i, expected, got, ok, round(ms)))
            print(f"[{model}] #{i}: expect={expected} got={got} {'OK' if ok else 'FAIL'} {ms:.0f}ms", flush=True)
        latencies.sort()
        results[model] = {
            "rows": rows,
            "accuracy": correct / len(TEST_CASES),
            "latency_p50_ms": round(latencies[len(latencies) // 2]),
            "latency_p95_ms": round(latencies[int(len(latencies) * 0.95) - 1]),
        }
    print(json.dumps(results, ensure_ascii=False, indent=2))
    with open("artifacts/n8n-feedback-classifier/bench_results.json", "w") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)


if __name__ == "__main__":
    main()
