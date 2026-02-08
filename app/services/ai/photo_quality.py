"""
Photo Quality Service
Performs lightweight checks using URL metadata.
"""
from typing import List, Dict, Any
from urllib.request import Request, urlopen
from urllib.error import URLError, HTTPError


def check_photo_quality(urls: List[str]) -> Dict[str, Any]:
    results = []
    for url in urls:
        quality = "unknown"
        warnings = []
        size_kb = None
        try:
            req = Request(url, method="HEAD")
            with urlopen(req, timeout=5) as resp:
                length = resp.headers.get("Content-Length")
                if length:
                    size_kb = int(length) / 1024
                    if size_kb < 30:
                        quality = "low"
                        warnings.append("File size is very small; image may be low quality")
                    elif size_kb < 80:
                        quality = "medium"
                        warnings.append("Image size is moderate")
                    else:
                        quality = "good"
        except (HTTPError, URLError, ValueError):
            warnings.append("Unable to verify image metadata")

        results.append({
            "url": url,
            "quality": quality,
            "size_kb": round(size_kb, 1) if size_kb else None,
            "warnings": warnings
        })

    overall = "good"
    if any(r["quality"] == "low" for r in results):
        overall = "low"
    elif any(r["quality"] == "medium" for r in results):
        overall = "medium"

    return {"overall_quality": overall, "results": results}
