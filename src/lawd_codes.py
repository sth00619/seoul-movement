"""Legal-dong (법정동) code lookup for the MOLIT apartment transaction API.

The MOLIT API requires a 5-digit legal-dong code (`LAWD_CD`) as its region
parameter. These are the codes for the three focus gu used in this lecture,
verified against 행정표준코드관리시스템 (www.code.go.kr) on 2026-07-03.

To extend to all 25 Seoul gu, add the remaining codes here — every gu in Seoul
starts with the prefix ``116`` or ``114`` and follows the same 5-digit format.
"""

from __future__ import annotations

# 3 focus gu for the lecture
FOCUS_LAWD_CODES: dict[str, str] = {
    "강남구": "11680",   # Gangnam-gu   (contains Gangnam station)
    "마포구": "11440",   # Mapo-gu      (contains Hongik Univ. / 홍대입구)
    "영등포구": "11560",  # Yeongdeungpo-gu (contains Yeouido)
}

# Full 25-gu roll-out (for the extended version — Phase 6+)
ALL_SEOUL_LAWD_CODES: dict[str, str] = {
    "종로구": "11110", "중구": "11140", "용산구": "11170",
    "성동구": "11200", "광진구": "11215", "동대문구": "11230",
    "중랑구": "11260", "성북구": "11290", "강북구": "11305",
    "도봉구": "11320", "노원구": "11350", "은평구": "11380",
    "서대문구": "11410", "마포구": "11440", "양천구": "11470",
    "강서구": "11500", "구로구": "11530", "금천구": "11545",
    "영등포구": "11560", "동작구": "11590", "관악구": "11620",
    "서초구": "11650", "강남구": "11680", "송파구": "11710",
    "강동구": "11740",
}

# English display names (used everywhere in charts/labels per the English-only rule)
GU_EN_NAMES: dict[str, str] = {
    "강남구": "Gangnam-gu",
    "마포구": "Mapo-gu",
    "영등포구": "Yeongdeungpo-gu",
}

# Focus stations → their host gu
FOCUS_STATIONS: dict[str, dict[str, str]] = {
    "강남": {
        "en_name": "Gangnam",
        "gu_kr": "강남구",
        "gu_en": "Gangnam-gu",
        "cluster_hypothesis": "Business District",
    },
    "홍대입구": {
        "en_name": "Hongdae (Hongik Univ.)",
        "gu_kr": "마포구",
        "gu_en": "Mapo-gu",
        "cluster_hypothesis": "Nightlife District",
    },
    "여의도": {
        "en_name": "Yeouido",
        "gu_kr": "영등포구",
        "gu_en": "Yeongdeungpo-gu",
        # Yeouido clusters with Business District (same archetype as Gangnam
        # but with even sharper AM peak and near-zero weekend volume).
        # The cluster auto-labeler calls it "Business District 2" to distinguish
        # the two centroids — this is correct behaviour, not a mismatch.
        "cluster_hypothesis": "Business District",
    },
}
