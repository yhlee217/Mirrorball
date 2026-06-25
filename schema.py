"""data(dict) -> schema.org JSON-LD dict (Person / FAQPage).

입력값에서 자동 생성. knowsAbout/specialties 등 겹치는 값은 입력 쪽에서
한 번만 받도록 하고(중복 입력 최소화), 여기서는 받은 dict 만 매핑한다.
"""

from __future__ import annotations


def _korean_name_plain(data: dict) -> str:
    return (data.get("korean_name") or "").replace(" ", "")


def _instagram_url(data: dict) -> str:
    return f"https://instagram.com/{data.get('instagram', '')}"


def person_ld(data: dict) -> dict:
    return {
        "@context": "https://schema.org",
        "@type": "Person",
        "name": _korean_name_plain(data),
        "alternateName": data.get("instagram", ""),
        "jobTitle": data.get("role", ""),
        "worksFor": {
            "@type": data.get("business_type", "HairSalon"),
            "name": data.get("salon", ""),
            "address": {
                "@type": "PostalAddress",
                "addressLocality": data.get("address_locality", ""),
                "addressRegion": data.get("address_region", ""),
                "addressCountry": "KR",
            },
        },
        "knowsAbout": list(data.get("knows_about", [])),
        "sameAs": [_instagram_url(data)],
    }


def faq_ld(data: dict) -> dict:
    return {
        "@context": "https://schema.org",
        "@type": "FAQPage",
        "mainEntity": [
            {
                "@type": "Question",
                "name": f.get("q", ""),
                "acceptedAnswer": {"@type": "Answer", "text": f.get("a", "")},
            }
            for f in data.get("faq", [])
        ],
    }
