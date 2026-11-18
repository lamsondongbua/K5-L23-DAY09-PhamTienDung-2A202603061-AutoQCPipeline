"""BƯỚC 2/4 — Sửa tự động những lỗi bắt buộc mà máy sửa được AN TOÀN.   ★★

Test:  pytest tests/test_autofix.py -q

`fix(ds, issues, cfg) -> list[dict]`: duyệt `issues` (chỉ lỗi severity ERROR), sửa thẳng vào thư mục `ds`,
và trả về danh sách thay đổi; mỗi phần tử có khoá: image, line, action, before, after
(đây chính là file `03_fixes.csv` — bằng chứng pipeline đã làm gì, người có thể kiểm lại).

| code lỗi                                       | cách sửa                                    | action           |
|------------------------------------------------|---------------------------------------------|------------------|
| BAD_FORMAT, BAD_CLASS_ID, BOX_ZERO, DUP_BOX    | xoá dòng đó khỏi file nhãn                  | "drop_line"      |
| BOX_OUT_OF_IMAGE                               | cắt box về trong [0,1] (giữ nguyên lớp)     | "clip_box"       |
| MISSING_LABEL_FILE                             | KHÔNG sửa file (máy không thể bịa nhãn): ghi 1 dòng fix, before="(không có file)", after="chuyển người gán" | "needs_label" |
| BAD_CLASS_NAME                                 | ghi lại `names` trong data.yaml đúng `cfg["classes"]` | "rename_classes" |
| DUP_IMAGE_*, LEAK_TEST, CORRUPT_IMAGE, BAD_SIZE| xoá ảnh + nhãn khỏi `ds`                    | "remove_image"   |

Bẫy cần nghĩ tới (có test cho từng cái)
- Một file có NHIỀU dòng lỗi: số dòng trong `issues` là số dòng GỐC. Nếu xoá từng dòng một thì số dòng lệch.
  Gom theo file, rồi ghi lại MỘT lần.
- Sau khi cắt, box có thể không còn diện tích (nằm hẳn ngoài ảnh): lúc đó xoá dòng thay vì ghi box rỗng.
- Một dòng có 2 lỗi (vd. BOX_OUT_OF_IMAGE + DUP_BOX): xoá dòng thắng, chỉ ghi 1 fix `drop_line`, không ghi thêm `clip_box`. Dòng trống ở giữa file vẫn đếm vào số dòng gốc.
- Ảnh vừa bị xoá (DUP_IMAGE_*...) mà còn issue dòng của chính nó: bỏ qua êm, không được báo lỗi/chết.
- Không động tới lỗi WARN (cảnh báo là việc của người). Không sửa file ở `data/raw/` — chỉ sửa `ds`.
- Chạy lần 2 trên dữ liệu đã sửa phải không làm gì thêm (idempotent) — NGOẠI LỆ duy nhất: `needs_label` được ghi lại mỗi lần còn lỗi `MISSING_LABEL_FILE` (vì ảnh vẫn chưa có nhãn).

- `needs_label` KHÔNG tạo file nhãn rỗng (rỗng = "ảnh nền", khác với "chưa gán"). `review_queue` sẽ đẩy ảnh này lên đầu hàng đợi cho người.

Gợi ý: `yaml.safe_load / safe_dump`.
"""
from collections import defaultdict  # noqa: F401

import yaml  # noqa: F401

from ..common import ERROR, parse_yolo_line  # noqa: F401



DROP_LINE = {"BAD_FORMAT", "BAD_CLASS_ID", "BOX_ZERO", "DUP_BOX"}
REMOVE_IMAGE = {"DUP_IMAGE_EXACT", "DUP_IMAGE_NEAR", "LEAK_TEST", "CORRUPT_IMAGE", "BAD_SIZE"}


def _clip(text):
    """Cắt box về [0,1]. Trả dòng mới, hoặc None nếu box không còn diện tích / dòng không đọc được."""
    try:
        c, x, y, w, h = parse_yolo_line(text)
    except ValueError:
        return None
    x1, x2 = max(0.0, x - w / 2), min(1.0, x + w / 2)
    y1, y2 = max(0.0, y - h / 2), min(1.0, y + h / 2)
    if x2 - x1 <= 0 or y2 - y1 <= 0:
        return None
    return f"{c} {(x1 + x2) / 2:.6f} {(y1 + y2) / 2:.6f} {x2 - x1:.6f} {y2 - y1:.6f}"


def fix(ds, issues, cfg):
    errors = [i for i in issues if i.severity == ERROR]
    fixes = []

    def log(image, line, action, before, after):
        fixes.append({"image": image, "line": "" if line is None else line, "action": action, "before": before, "after": after})

    # 1) xoá ảnh (làm trước để bỏ qua êm các issue dòng của ảnh đó)
    removed = set()
    for i in errors:
        if i.code in REMOVE_IMAGE and i.image not in removed:
            removed.add(i.image)
            p = ds.image_path(i.image)
            before = p.name if p else i.image
            if p:
                p.unlink()
            lp = ds.label_path(i.image)
            if lp.exists():
                lp.unlink()
            log(i.image, None, "remove_image", before, "(đã xoá ảnh và nhãn)")

    # 2) data.yaml: ghi lại tên lớp
    if any(i.code == "BAD_CLASS_NAME" for i in errors) and ds.yaml_path.exists():
        d = yaml.safe_load(ds.yaml_path.read_text(encoding="utf-8")) or {}
        old = d.get("names")
        d["names"] = list(cfg["classes"]) if isinstance(old, list) else dict(enumerate(cfg["classes"]))
        ds.yaml_path.write_text(yaml.safe_dump(d, allow_unicode=True, sort_keys=False), encoding="utf-8")
        log("data.yaml", None, "rename_classes", str(old), str(d["names"]))

    # 3) thiếu file nhãn: chuyển người gán, KHÔNG bịa file
    for i in errors:
        if i.code == "MISSING_LABEL_FILE" and i.image not in removed:
            log(i.image, None, "needs_label", "(không có file)", "chuyển người gán")

    # 4) lỗi theo dòng: gom theo file, ghi lại một lần (số dòng là số dòng GỐC)
    by_img = defaultdict(lambda: {"drop": set(), "clip": set()})
    for i in errors:
        if i.line is None or i.image in removed:
            continue
        if i.code in DROP_LINE:
            by_img[i.image]["drop"].add(i.line)
        elif i.code == "BOX_OUT_OF_IMAGE":
            by_img[i.image]["clip"].add(i.line)
    for stem, g in by_img.items():
        lp = ds.label_path(stem)
        if not lp.exists():
            continue
        old = lp.read_text(encoding="utf-8", errors="replace").splitlines()
        new = []
        for no, text in enumerate(old, 1):
            if no in g["drop"]:
                log(stem, no, "drop_line", text, "(đã xoá dòng)")
            elif no in g["clip"]:
                fixed = _clip(text)
                if fixed is None:
                    log(stem, no, "drop_line", text, "(đã xoá dòng: box nằm ngoài ảnh)")
                else:
                    log(stem, no, "clip_box", text, fixed)
                    new.append(fixed)
            else:
                new.append(text)
        if new != old:
            lp.write_text("".join(t + "\n" for t in new), encoding="utf-8", newline="\n")
    return fixes
