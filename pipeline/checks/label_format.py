"""CHECK 2 — Dòng nhãn YOLO: sai định dạng, ID lớp lạ, box tràn ảnh, box rỗng, box lặp.   (Script 2 trong slide)   ★★

Test:  pytest tests/test_label_format.py -q

Mỗi dòng nhãn: `id cx cy w h` (5 số, toạ độ 0–1). Trả về list[Issue]; `Issue.line` = số dòng (đếm từ 1).

| code             | severity | khi nào                                                                  |
|------------------|----------|--------------------------------------------------------------------------|
| BAD_FORMAT       | ERROR    | không đúng 5 cột số (dùng `parse_yolo_line`, bắt `ValueError`)           |
| BAD_CLASS_ID     | ERROR    | id lớp ngoài 0..len(ds.classes)-1                                        |
| BOX_ZERO         | ERROR    | w <= 0 hoặc h <= 0                                                       |
| BOX_OUT_OF_IMAGE | ERROR    | mép box vượt [0,1] quá `cfg["label_format"]["overflow_tol"]`; extra={"overflow": mức tràn} |
| DUP_BOX          | ERROR    | cùng lớp với một dòng TRƯỚC ĐÓ và IoU > `dup_box_iou`; báo ở dòng SAU    |
| BOX_TINY         | WARN     | cạnh ngắn của box (px) < `min_box_px`  (cần `ds.image_size(stem)`)       |
| BOX_HUGE         | WARN     | w*h > `max_box_frac`                                                     |

Gợi ý
- Mép trái = x - w/2, mép phải = x + w/2 (xem câu hỏi "dòng YOLO nào lỗi?" trong slide).
- Một dòng hỏng (BAD_FORMAT, BAD_CLASS_ID, BOX_ZERO) thì `continue`, đừng kiểm tiếp hình học của dòng đó.
- Dòng thiếu cột làm script của slide dừng giữa chừng: đây là lý do phải `try/except`.
- `iou_xywh(a, b)` có sẵn trong common.py.
- Ngưỡng nằm trong `cfg["label_format"]` — đừng viết cứng số vào code.
"""
from ..common import ERROR, WARN, Issue, iou_xywh, parse_yolo_line  # noqa: F401




def run(ds, cfg):
    c = cfg["label_format"]
    n_cls = len(ds.classes)
    issues = []

    def add(sev, code, stem, no, msg, **extra):
        issues.append(Issue("label_format", sev, code, stem, msg, no, extra))

    for lp in ds.label_files():
        stem = lp.stem
        size = ds.image_size(stem)
        kept = []                                   # (lớp, box) các dòng hợp lệ trước đó, để so DUP_BOX
        for no, text in ds.read_label_lines(stem) or []:
            try:
                cls, x, y, w, h = parse_yolo_line(text)
            except ValueError as e:
                add(ERROR, "BAD_FORMAT", stem, no, f"dòng nhãn sai định dạng: {e}")
                continue
            if not 0 <= cls < n_cls:
                add(ERROR, "BAD_CLASS_ID", stem, no, f"id lớp {cls} ngoài 0..{n_cls - 1}")
                continue
            if w <= 0 or h <= 0:
                add(ERROR, "BOX_ZERO", stem, no, f"box rỗng (w={w}, h={h})")
                continue
            box = (x, y, w, h)

            over = max(0.0, -(x - w / 2), -(y - h / 2), (x + w / 2) - 1, (y + h / 2) - 1)
            if over > c["overflow_tol"]:
                add(ERROR, "BOX_OUT_OF_IMAGE", stem, no, f"box tràn ảnh {over:.4f}", overflow=round(over, 6))

            if any(k == cls and iou_xywh(b, box) > c["dup_box_iou"] for k, b in kept):
                add(ERROR, "DUP_BOX", stem, no, "box lặp (cùng lớp, IoU cao với dòng trước)")
            kept.append((cls, box))

            if size and min(w * size[0], h * size[1]) < c["min_box_px"]:
                add(WARN, "BOX_TINY", stem, no, f"box quá nhỏ: cạnh ngắn {min(w * size[0], h * size[1]):.1f}px")
            if w * h > c["max_box_frac"]:
                add(WARN, "BOX_HUGE", stem, no, f"box phủ {w * h:.0%} ảnh")
    return issues
