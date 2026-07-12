"""Sample fixtures for testing."""

FED_PRESS_RELEASE_HTML = """
<!DOCTYPE html>
<html>
<head><title>Federal Reserve issues FOMC statement</title></head>
<body>
<div class="col-xs-12 col-sm-8 col-md-8">
<p>Information received since the Federal Open Market Committee met in January
indicates that economic activity has been expanding at a solid pace. Job gains
have remained strong, and the unemployment rate has remained low. Inflation
remains somewhat elevated.</p>
<p>The Committee seeks to achieve maximum employment and inflation at the rate
of 2 percent over the longer run. In support of these goals, the Committee
decided to maintain the target range for the federal funds rate at 5-1/4 to
5-1/2 percent.</p>
</div>
</body>
</html>
"""

SAMPLE_SOURCES = [
    {
        "source_id": "fed",
        "source_name": "Federal Reserve",
        "source_type": "central_bank",
        "jurisdiction": "US",
        "homepage_url": "https://www.federalreserve.gov",
        "credibility_score": 0.95,
        "licence_type": "public_domain",
        "redistribution_allowed": True,
        "commercial_use_allowed": True,
        "active": True,
    },
    {
        "source_id": "gdelt",
        "source_name": "GDELT Project",
        "source_type": "news",
        "jurisdiction": None,
        "homepage_url": "https://www.gdeltproject.org",
        "credibility_score": 0.7,
        "licence_type": "open_data",
        "redistribution_allowed": True,
        "commercial_use_allowed": True,
        "active": True,
    },
]
