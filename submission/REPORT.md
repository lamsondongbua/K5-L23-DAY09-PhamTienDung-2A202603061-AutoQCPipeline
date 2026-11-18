# Báo cáo Day 09 — <Phạm Tiến Dũng>, <2A202603061>

## 1. Kết luận trước
**Hold** (mã thoát 10). Vào pipeline 224 ảnh, 22 ảnh bị loại ở bước nhận dữ liệu (hỏng, quá nhỏ, trùng, rò rỉ test), 202 ảnh vào bản nháp `submission/export/clean_v1` (chưa được phát hành). Không còn lỗi bắt buộc nào, nhưng 38/202 ảnh (18,8%) vẫn còn cảnh báo ngữ nghĩa chưa người duyệt, vượt ngưỡng 10%, chủ yếu là nghi ngờ nhãn box thừa/lỏng (`POSSIBLE_FALSE_POS` 21, `POSSIBLE_LOOSE_BOX` 20) và box thiếu (`POSSIBLE_MISSING` 13).

## 2. Lỗi và phân việc
Lấy từ `02_error_list_v1` (211 dòng: 12 mã lỗi bắt buộc, 8 mã cảnh báo). Cột "ai sửa": **máy** (autofix hoặc bước nhận dữ liệu) hay **người** (hàng đợi); chỉ ghi những mã có mặt trong lô của tôi.

| Mã lỗi | Số ảnh/dòng | Ai sửa (máy/người) | Vì sao |
|---|---:|---|---|
| `BAD_FORMAT` | 3 | máy (`drop_line`) | Dòng thiếu cột / `nan`, không có thông tin để đoán, xoá dòng là an toàn. |
| `BAD_CLASS_ID` | 6 | máy (`drop_line`) | ID lớp lạ (93, 4, −1) không ánh xạ được vào 4 lớp. |
| `BOX_ZERO` | 4 | máy (`drop_line`) | Box rộng/cao 0, không còn là box. |
| `DUP_BOX` | 7 | máy (`drop_line`) | Box lặp cùng lớp, giữ dòng đầu, xoá dòng sau. |
| `BOX_OUT_OF_IMAGE` | 8 | máy (`clip_box`) | Cắt về [0,1], giữ nguyên lớp; box nằm hẳn ngoài thì xoá dòng. |
| `BAD_CLASS_NAME` | 2 | máy (`rename_classes`) | Ghi lại `names` trong `data.yaml` theo `cfg["classes"]` (1 lần ghi). |
| `BAD_SIZE`, `CORRUPT_IMAGE` | 3 + 2 | máy (loại ảnh) | Ảnh quá nhỏ hoặc hỏng, không dùng được. |
| `DUP_IMAGE_EXACT`, `DUP_IMAGE_NEAR`, `LEAK_TEST` | 8 + 4 + 5 | máy (loại ảnh) | Ảnh trùng hoặc rò rỉ sang test, giữ ảnh đầu theo tên. |
| `MISSING_LABEL_FILE` | 6 | **người** (`needs_label`) | Máy không thể bịa nhãn, và file rỗng nghĩa là "ảnh nền" chứ không phải "chưa gán". Đưa lên đầu hàng đợi (priority 10). |
| `POSSIBLE_MISSING` / `WRONG_CLASS` / `FALSE_POS` / `LOOSE_BOX` | 53 / 18 / 29 / 28 | **người** | Chỉ là nghi ngờ từ model lớn, model cũng có thể sai nên chỉ cảnh báo, cần người nhìn ảnh. |
| `BOX_TINY`, `BOX_HUGE`, `EMPTY_LABEL`, `CLASS_RARE` | 6 / 3 / 12 / 4 | **người** | Cảnh báo, không có đáp án máy sửa an toàn. |

Tổng kết xử lý của máy (`03_fixes.csv`): 20 `drop_line`, 8 `clip_box`, 6 `needs_label`, 1 `rename_classes`.

**Vì sao `05_review_queue.csv` xếp ảnh đầu hàng như vậy:** hàng đợi xếp theo điểm ưu tiên = tổng trọng số các mã của ảnh (`review.weights` trong cấu hình). Ảnh `NEEDS_LABEL` (trọng số 10) đứng đầu vì chưa có nhãn nào, cả 6 ảnh đều ở top. Tiếp theo là ảnh có nhiều cờ ngữ nghĩa cùng lúc, ví dụ `img_0020` (11,5) có `FIXED_DROP_LINE`, `POSSIBLE_MISSING` và `POSSIBLE_WRONG_CLASS`, vì `WRONG_CLASS` (3) và `MISSING` (2) nặng hơn `LOOSE_BOX` (1,5) hay `BOX_TINY` (0,3). Hàng đợi có 125 ảnh, ngân sách 80 ảnh nên điểm cắt là khoảng 3,3 và 45 ảnh cuối không được xem. Trong 80 ảnh được duyệt, người sửa 6 ảnh thiếu nhãn và các cảnh báo ngữ nghĩa: so với trước khi duyệt (`04_error_list_v2`), `MISSING` giảm từ 53 xuống 13, `WRONG_CLASS` từ 18 xuống 3, `LOOSE_BOX` từ 28 xuống 20, `FALSE_POS` từ 24 xuống 21. Tức người xem được khoảng 40 + 15 + 8 + 3 = 66 cảnh báo ngữ nghĩa, và 45 ảnh ngoài ngân sách vẫn giữ nhãn máy. Lưu ý: "người duyệt" ở đây là mô phỏng, `scripts/human_review_sim.py` thay nhãn bằng nhãn tham chiếu.

## 3. Calibration (2 ngưỡng)
| Tham số | Khởi đầu | Đã chọn | Precision / Recall (trước → sau) | Lý do (đánh đổi) |
|---|---|---|---|---|
| `duplicates.phash_dist` | 2 | **10** | `DUP_IMAGE_NEAR`: P 1.00 → 1.00, R 0.50 → 0.67 (F1 0.67 → 0.80) | Tăng từ 2 lên 10 bắt thêm ảnh trùng thật mà không gộp nhầm. F1 cao nhất theo sweep là 16 (0.91) nhưng tôi **không chọn**, xem dưới. |
| `second_opinion.conf` | 0.25 | **0.6** | `WRONG_CLASS`: P 0.56 → 0.62, R 0.83 → 0.83. `MISSING`: P 0.50 → 0.57, R 1.00 → 1.00. `LOOSE_BOX`: P 0.29 → 0.20, R 0.40 → 0.20 | Lên 0.6 thì bớt cảnh báo sai ở `MISSING` và `WRONG_CLASS` mà recall `MISSING` vẫn 1.00. Đánh đổi: `LOOSE_BOX` kém đi (recall 0.40 → 0.20). Không chọn 0.7–0.8: recall `MISSING` tụt xuống 0.88 và 0.75, tức bỏ sót ảnh thiếu box. |

Hàng đợi sau khi đổi: số ảnh còn cảnh báo sau người duyệt giảm từ 60/205 (29,3%) xuống 38/202 (18,8%), vẫn Hold vì còn trên ngưỡng 10%.

**Chỗ calibration có thể đánh lừa:** chọn `phash_dist` theo F1 lớn nhất. Bảng sweep cho thấy 16 là tốt nhất (F1 `NEAR` 0.91), nhưng bảng chỉ có 6 mẫu `NEAR` và không đo `LEAK_TEST`, mà check này cũng dùng chính `phash_dist`. Tôi mở ảnh xem các ảnh chỉ bị cờ ở mức 16 (so với 10): cả 3 ảnh `LEAK_TEST` đã mở (`img_0013`/`test_087`, `img_0017`/`test_071`, `img_0021`/`test_048`) là ảnh khác nhau, và 2 trong 3 cặp `NEAR` mới (`img_0011`/`img_0008`, `img_0177`/`img_0113`) cũng là ảnh khác nhau. Nếu chọn 16, pipeline loại nhầm nhiều ảnh sạch và báo rò rỉ giả. Ngược lại các ảnh bị cờ ở mức 6 và 10 mở ra đều trùng thật: `img_0223`/`img_0077`, `img_0186`/`img_0061`, và `img_0101`/`test_039` (ảnh test bị chỉnh nhẹ). Ở bước 1, số ảnh bị loại tăng từ 19 lên 22 (còn 202/224 ảnh) khi nâng ngưỡng từ 2 lên 10, và 3 ảnh thêm đó là trùng thật nên hợp lý.

## 4. Cửa chặn và điều pipeline KHÔNG bắt được
### Đọc và nhìn (theo hướng dẫn 3 việc)
1. **`data/README.md`**: `raw/` (224 ảnh) là đầu vào pipeline, nhãn gán sẵn có lỗi, không có đáp án. `calib/` (39 ảnh) có lỗi chèn kèm đáp án trong `MANIFEST.csv`, dùng để đo công cụ kiểm và chọn ngưỡng. `gold_val/` (40 ảnh) là `val` khi train. `test/` (100 ảnh) chỉ dùng đánh giá cuối, không dùng để sửa nhãn hay chọn ngưỡng. Lỗi cú pháp máy bắt gần như chắc chắn, lỗi ngữ nghĩa chỉ nghi ngờ được rồi cần người xem.
2. **Xem 10 ảnh `work/viz/`** (`img_0001, 0030, 0031, 0043, 0059, 0076, 0123, 0128, 0180, 0224`; 2 ảnh đầu theo GUIDE, 8 ảnh còn lại chọn ngẫu nhiên từ `data/raw`). Chữ trên box dạng `số dòng:tên lớp`, không phải id lớp. Ba lỗi dễ nhận ra nhất, xếp từ dễ thấy nhất:
   - **Box thừa trên chỗ trống** (`img_0180`): có box `bus` (màu tím) nằm trên mặt đường, không có xe nào ở đó. Nhìn là thấy ngay, không cần biết dữ liệu.
   - **Mất toàn bộ box** (`img_0031`): ảnh có xe buýt đỏ và xe con rất rõ nhưng không có box nào. Nguyên nhân: ảnh **không có file nhãn** (`MISSING_LABEL_FILE`), pipeline ghi `needs_label` và chuyển người gán chứ không tự bịa nhãn. Cùng kiểu "thiếu box": `img_0001` thiếu box người lính ở giữa.
   - **Box phình to phủ gần cả ảnh** (`img_0128`): hai box lớn trùm gần hết khung hình, trong khi đối tượng chỉ là bàn tay cầm điện thoại.
3. **`pipeline/checks/duplicates.py`**: dùng md5 (trùng từng byte) và phash (trùng gần đúng), cộng kiểm rò rỉ sang test/val. Mỗi ảnh chỉ nhận một issue, ưu tiên `LEAK_TEST` > `DUP_IMAGE_EXACT` > `DUP_IMAGE_NEAR`. Ảnh đầu tiên (theo tên) được giữ, ảnh sau bị báo. `phash_dist` càng lớn càng dễ gộp nhầm ảnh khác nhau. Điểm mù: ảnh trùng bị biến đổi mạnh (cắt nhiều, xoay) vượt ngưỡng phash thì không bị bắt.

### (a) Cửa chặn chặn đúng
Chạy `python -X utf8 -m pipeline.run --budget 0 --reports work/rep_nb --export-dir work/exp_nb` (ngân sách 0 nên không có người duyệt, ảnh thiếu file nhãn còn nguyên):
- Kết luận **Rework**: "còn 6 lỗi bắt buộc chưa sửa: phải sửa hết trước khi xuất dataset". Cả 6 lỗi là `MISSING_LABEL_FILE`. Ngoài ra 112/202 ảnh (55,5%) còn cảnh báo.
- Mã thoát **20** (khớp bảng: 20 = Rework).
- **Không xuất** dataset: thư mục `work/exp_nb` không được tạo, log in "KHÔNG xuất: còn lỗi bắt buộc (Rework) — trả về bước 3".
- So với lần chạy thường (ngân sách 80): người duyệt xử lý 6 ảnh thiếu nhãn đó nên hết lỗi bắt buộc, kết luận chuyển sang Hold (mã 10) và chỉ ra bản nháp.

### (b) Điểm mù: điều pipeline KHÔNG bắt được
1. **Box thừa nằm lồng trong box đúng** (`img_0128`). Ảnh có 2 box `person`: một box phủ gần cả ảnh (0.99 × 1.00) và một box nhỏ hơn bên trong (0.68 × 0.65). Báo cáo `07_error_list_v3` chỉ có `BOX_HUGE` ở dòng 1, không có gì ở dòng 2. `DUP_BOX` không bắt vì IoU hai box chỉ khoảng 0,44, dưới ngưỡng 0,9. `second_opinion` cũng không cờ dòng 2. Ảnh không vào hàng đợi, nên cả hai box vẫn nằm trong dataset xuất ra. Ngoài ra `BOX_HUGE` đang cờ vào box phủ cả ảnh, có thể là box đúng với ảnh cận cảnh một người.
2. **Box lỏng nhẹ.** Trong bộ calibration, `POSSIBLE_LOOSE_BOX` ở `conf=0.6` chỉ có precision 0,20 và recall 0,20: bắt được 1 trên 5 lỗi chèn, bỏ sót 4. Box lệch nhẹ vẫn có IoU trên ngưỡng nên check coi là khớp. Tôi đã chọn `conf=0.6` ưu tiên `MISSING` và `WRONG_CLASS`, nên điểm yếu này là cái giá của lựa chọn đó.
3. **Ảnh trùng bị biến đổi mạnh.** Ở `phash_dist=10`, `DUP_IMAGE_NEAR` chỉ bắt 4 trên 6 ảnh chèn (recall 0,67). Tăng lên 16 để bắt thêm thì pipeline báo nhầm ảnh khác nhau là rò rỉ (xem mục 3), nên không có ngưỡng phash nào bắt hết mà không gộp nhầm.
4. **Giới hạn ngân sách duyệt.** Hàng đợi có 125 ảnh nhưng người chỉ xem 80, nên 45 ảnh cuối giữ nguyên nhãn máy. Sau duyệt vẫn còn 38/202 ảnh (18,8%) có cảnh báo, đây là lý do kết luận là Hold chứ chưa phải Release.

Lưu ý: tôi đã mở thử khoảng 10 ảnh "sạch" (không có cảnh báo, không được duyệt) để tìm lỗi mà máy bỏ sót. Có ảnh nhìn đáng ngờ (ví dụ `img_0098`, người lướt sóng ở giữa ảnh dường như không có box trong khi có một box nhỏ ở bọt sóng), nhưng tôi chưa đối chiếu được với nhãn đúng nên không đưa vào làm bằng chứng.

## 5. Train: raw vs clean (tùy chọn, chấm riêng)
**Chưa chạy.** Phần này cần Colab (GPU T4) và repo public để notebook tải `submission/export` và `submission/reports` về, mà tôi chưa đẩy repo lên và chưa chạy notebook `notebooks/day09_train_compare.ipynb`. Vì không có kết quả huấn luyện nên tôi không ghi số mAP50 hay kết luận nào ở mục này, và chấp nhận mất phần điểm tùy chọn (tối đa 85/100, `make check-core` vẫn dùng được). Pipeline cũng đang ở Hold nên `export/clean_v1` mới chỉ là bản nháp.

## 6. Quyết định và ghi chú AI
**(a) Quyết định cuối: Hold, chưa phát hành `clean_v1`.** Không còn lỗi bắt buộc, nhưng 38/202 ảnh (18,8%) vẫn còn cảnh báo ngữ nghĩa chưa người duyệt, vượt ngưỡng 10%. Để thành Release cần giảm xuống tối đa 20 ảnh có cảnh báo, bằng cách:
1. Người thật duyệt nốt 45 ảnh nằm ngoài ngân sách 80 ảnh của hàng đợi (ưu tiên các ảnh còn `POSSIBLE_MISSING`, `POSSIBLE_FALSE_POS`, `POSSIBLE_LOOSE_BOX`), thay cho bước duyệt mô phỏng `human_review_sim.py`.
2. Xem riêng điểm mù ở mục 4(b) (box lồng trong box phủ cả ảnh như `img_0128`) vì pipeline không tự bắt được.
3. Chạy lại `make run` sau khi duyệt, kiểm `08_summary.json` đã `Release` rồi mới dùng `export/clean_v1` để train.

**(b) Dùng AI viết code: có (Claude Code).**
- Prompt chính: nhờ AI đọc `GUIDE.md`/`RULES.md`, viết các check còn thiếu trong `pipeline/checks/`, bước `autofix`/`gate`, và giúp chạy calibrate rồi `make run`; cuối cùng nhờ đối chiếu repo với `SUBMISSION.md` và điền báo cáo.
- Cách kiểm: chạy `pytest` (79 test xanh), chạy `scripts/check_submission.py --no-train`, mở ảnh trong `work/viz/` và ảnh bị cờ trùng để đối chiếu bằng mắt; không dùng `data/calib`, `MANIFEST`, `data/test` trong code kiểm.
- Một lần AI sai: AI báo "pytest chưa xanh" và ban đầu coi đó là lỗi code, nhưng thật ra máy chưa cài `pytest`/`imagehash`; sau khi `pip install -r requirements.txt` thì 79 test đều qua. Bài học: phải chạy lại và đọc lỗi thật, không đoán nguyên nhân.

*(Thưởng +2, tùy chọn)* CVAT: lọc `width < 20`, ảnh/số box khớp, đối chiếu `BOX_TINY` (xem docs/CVAT_FILTER.md), 1 câu về `can_review`.
