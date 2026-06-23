# 디자이너 사진 자산

프로필 사진을 이 폴더에 넣고, `designers/{slug}.yaml` 의 `photo_url` 을 상대경로로 지정합니다.

예) 하예원: 첨부된 프로필 사진을 `hayewoni.jpg` 로 저장
    → `designers/hayewoni.yaml` 의 `photo_url: "assets/hayewoni.jpg"`

빌드 시 `dist/{slug}/` 로 함께 복사됩니다(빌더가 처리).
권장: 정사각형/세로 비율, 1000px 내외, jpg.
