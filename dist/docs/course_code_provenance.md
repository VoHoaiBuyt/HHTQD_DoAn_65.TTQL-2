# Provenance của mã học phần

## Mã định danh nội bộ do nhóm gán

Theo xác nhận của người dùng, các mã có tiền tố `HP` không xuất hiện trong PDF
CTĐT. Trong `data/official/courses.csv`, 75 mã `HP...` hiện là mã định danh nội
bộ do nhóm gán để khóa các dòng và nhóm lựa chọn; không trình bày chúng như mã
được PDF xác nhận.

Các mã hiện có trong CSV:

`HP007`, `HP008`, `HP009`, `HP010`, `HP011`, `HP012`, `HP013`, `HP014`,
`HP015`, `HP016-A`, `HP016-B`, `HP017-A`, `HP018-A`, `HP018-B`, `HP018-C`,
`HP019-A`, `HP019-B`, `HP022`, `HP023`, `HP024`, `HP025`, `HP026`, `HP027`,
`HP028`, `HP029`, `HP030`, `HP031-A`, `HP031-B`, `HP031-C`, `HP031-D`,
`HP032`, `HP033`, `HP034`, `HP035`, `HP036`, `HP037`, `HP038`, `HP039-IS`,
`HP039-NW`, `HP039-SE`, `HP040-IS`, `HP040-NW`, `HP040-SE`, `HP041-IS`,
`HP041-NW`, `HP041-SE`, `HP042-IS`, `HP042-NW`, `HP042-SE`, `HP043-IS`,
`HP043-NW`, `HP043-SE`, `HP044-IS`, `HP044-NW`, `HP044-SE`, `HP045-IS-A`,
`HP045-IS-B`, `HP045-NW-A`, `HP045-NW-B`, `HP045-SE-A`, `HP045-SE-B`,
`HP046-IS-A`, `HP046-IS-B`, `HP046-NW-A`, `HP046-NW-B`, `HP046-SE-A`,
`HP046-SE-B`, `HP047-IS-A`, `HP047-IS-B`, `HP047-NW-A`, `HP047-NW-B`,
`HP047-SE-A`, `HP047-SE-B`, `HP048-A`, `HP048-B`.

## Mã được ghi nhận theo tiền tố trong PDF

`config/program_official.yaml` ghi các tiền tố nguồn PDF là `POL`, `SSH`, `BUA`,
`MKT`, `PHE`, `QPAD`. Các mã không mang tiền tố `HP` hiện có trong CSV:

- `POL`: `POL307`, `POL308`, `POL309`, `POL310`, `POL333`.
- `SSH`: `SSH313`.
- `BUA`: `BUA319`.
- `PHE`: `PHE6000`–`PHE6014` (các mã nguyên văn hiện có trong CSV).
- `QPAD`: `QPAD011`, `QPAD02`, `QPAD033`, `QPAD044`.
- `MKT`: không có mã nào trong `data/official/courses.csv`.

Đặc biệt, CSV có `POL307`, `SSH313`, `BUA319`. Đây là các mã thuộc tiền tố
được config ghi nhận từ PDF; không suy rộng từ tiền tố sang mã không có trong
CSV.

## Giới hạn truy nguyên

PDF nguồn `210_CNTT.pdf` không được lưu trong repository nên không thể kiểm tra
đối chiếu trực tiếp từng mã với trang PDF trong bản source này. Danh sách trên
là các mã nguyên văn trong CSV OFFICIAL và metadata tiền tố trong config; nếu
nhóm cung cấp lại PDF, cần rà soát từng dòng trước khi khẳng định mã cụ thể.
Nhãn OFFICIAL của nội dung CTĐT không biến mã `HP...` do nhóm gán thành mã
được trường xác nhận.
