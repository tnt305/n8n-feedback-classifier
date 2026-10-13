# %% bench_classifier.py - benchmark kiem thu model/prompt qua API Ollama (smoke test 10 ca)
import json
import math
import statistics
import time
import urllib.request
from pathlib import Path

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


def percentile(sorted_values: list[float], p: float) -> float:
    """Tính percentile theo phương pháp nearest-rank (ceiling).

    Với N=9 phần tử (warm-state):
      P50 = statistics.median (trung vị - phần tử thứ 5)
      P95 = sorted_values[ceil(0.95 * 9) - 1] = sorted_values[8] (phần tử cuối)
    """
    n = len(sorted_values)
    k = math.ceil(p / 100.0 * n) - 1
    return sorted_values[max(0, min(k, n - 1))]


def main():
    script_dir = Path(__file__).resolve().parent
    results = {}
    for model in MODELS:
        rows = []
        correct = 0
        cold_start_ms = 0.0

        # -- Thu thập kết quả 10 ca --
        all_latencies = []
        for i, (text, expected) in enumerate(TEST_CASES, 1):
            got, ms = classify(model, text)
            ok = (got == expected)
            correct += ok
            all_latencies.append(ms)
            rows.append((i, expected, got, ok, round(ms)))
            print(f"[{model}] #{i}: expect={expected} got={got} "
                  f"{'OK' if ok else 'FAIL'} {ms:.0f}ms", flush=True)

        # -- Tách cold-start (lần gọi đầu) ra khỏi tập warm-state --
        cold_start_ms = all_latencies[0]
        warm_latencies = sorted(all_latencies[1:])  # 9 phần tử ở trạng thái ổn định

        # -- Tính P50 bằng statistics.median, P95 bằng nearest-rank --
        p50 = statistics.median(warm_latencies)
        p95 = percentile(warm_latencies, 95)

        results[model] = {
            "rows": rows,
            "accuracy": correct / len(TEST_CASES),
            "cold_start_ms": round(cold_start_ms),
            "warm_latencies_sorted_ms": [round(v) for v in warm_latencies],
            "latency_p50_ms": round(p50),
            "latency_p95_ms": round(p95),
            "note": (
                f"Cold-start ({round(cold_start_ms)} ms) đã được loại "
                f"khỏi tập 9 warm-state latencies. "
                f"P50 = statistics.median, P95 = nearest-rank ceiling."
            ),
        }
    print(json.dumps(results, ensure_ascii=False, indent=2))

    # -- Ghi kết quả vào scripts/bench_results.json --
    output_file = script_dir / "bench_results.json"
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    print(f"Saved benchmark results to {output_file}")

    # -- Đồng bộ sang artifacts nếu thư mục tồn tại --
    artifacts_dir = script_dir.parent.parent / "artifacts" / "n8n-feedback-classifier"
    if artifacts_dir.exists():
        art_output = artifacts_dir / "bench_results.json"
        with open(art_output, "w", encoding="utf-8") as f:
            json.dump(results, f, ensure_ascii=False, indent=2)
        print(f"Synced benchmark results to {art_output}")


if __name__ == "__main__":
    main()

